"""O mesmo agente em LangGraph 1.x: grafo próprio com estado, ToolNode e ferramentas LangChain.

Para medir só o efeito da orquestração, o modelo é o MESMO objeto do loop próprio,
embrulhado como chat model do LangChain (mesmo prompt, mesmas ferramentas, mesmas
defesas). Muda só quem conduz a conversa: o grafo, o ToolNode e o estado.

Sem `from __future__ import annotations` aqui: o LangGraph lê as anotações do TypedDict
do estado em tempo de execução, e o TypedDict precisa ficar no nível do módulo.
"""

import time
from collections.abc import Sequence
from typing import Annotated, Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import StructuredTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from toolbr.agents.loop import MAX_STEPS, transcript
from toolbr.agents.runtime import ToolRuntime
from toolbr.types import Episode, ToolCall, Usage
from toolbr.worlds.base import ToolSpec


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    steps: int


class ToolbrChatModel(BaseChatModel):
    """Chat model do LangChain que chama um modelo do ToolBR."""

    toolbr_model: Any

    @property
    def _llm_type(self) -> str:
        return "toolbr"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any):
        functions = [convert_to_openai_tool(t)["function"] for t in tools]
        return self.bind(toolbr_tools=functions, **kwargs)

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs: Any):
        specs = [
            ToolSpec(f["name"], f.get("description", ""), f["parameters"])
            for f in kwargs.get("toolbr_tools", [])
        ]
        system, history = to_neutral(messages)
        turn = self.toolbr_model.complete(system, history, specs)
        message = AIMessage(
            content=turn.text,
            tool_calls=[
                {"name": c.name, "args": c.arguments, "id": c.id, "type": "tool_call"}
                for c in turn.tool_calls
            ],
            additional_kwargs={"toolbr_raw": turn.raw},
            response_metadata={"stop_reason": turn.stop_reason, "toolbr_usage": vars(turn.usage)},
        )
        return ChatResult(generations=[ChatGeneration(message=message)])


def to_neutral(messages: list[BaseMessage]) -> tuple[str, list[dict[str, Any]]]:
    """Mensagens do LangChain -> (prompt de sistema, histórico neutro do ToolBR)."""
    system, history = "", []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            system = msg.text
        elif isinstance(msg, HumanMessage):
            history.append({"role": "user", "content": msg.text})
        elif isinstance(msg, AIMessage):
            history.append(
                {
                    "role": "assistant",
                    "content": msg.text,
                    "tool_calls": [
                        ToolCall(tc["id"], tc["name"], tc["args"]) for tc in msg.tool_calls
                    ],
                    "raw": msg.additional_kwargs.get("toolbr_raw"),
                }
            )
        elif isinstance(msg, ToolMessage):
            result = {
                "id": msg.tool_call_id,
                "name": msg.name,
                "content": msg.text,
                "is_error": msg.status == "error" or bool((msg.artifact or {}).get("is_error")),
            }
            if history and history[-1]["role"] == "tool":
                history[-1]["results"].append(result)
            else:
                history.append({"role": "tool", "results": [result]})
    return system, history


def langchain_tools(runtime: ToolRuntime) -> list[StructuredTool]:
    """Ferramentas do mundo no formato LangChain, executadas pelo mesmo runtime do loop."""

    def make(spec: ToolSpec) -> StructuredTool:
        def run(**kwargs: Any) -> tuple[str, dict[str, bool]]:
            content, is_error = runtime.execute(spec.name, kwargs)
            return content, {"is_error": is_error}

        return StructuredTool(
            name=spec.name,
            description=spec.description,
            args_schema=spec.parameters,
            func=run,
            response_format="content_and_artifact",
        )

    return [make(spec) for spec in runtime.specs()]


def build_graph(chat_model: ToolbrChatModel, tools: list[StructuredTool], max_steps: int):
    bound = chat_model.bind_tools(tools)

    def call_model(state: AgentState) -> dict[str, Any]:
        return {"messages": [bound.invoke(state["messages"])], "steps": state["steps"] + 1}

    def after_model(state: AgentState) -> str:
        last = state["messages"][-1]
        if last.response_metadata.get("stop_reason") == "refusal" or not last.tool_calls:
            return END
        return "tools"

    def after_tools(state: AgentState) -> str:
        # igual ao loop próprio: as ferramentas do último passo rodam, depois para
        return END if state["steps"] >= max_steps else "model"

    graph = StateGraph(AgentState)
    graph.add_node("model", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", after_model, ["tools", END])
    graph.add_conditional_edges("tools", after_tools, ["model", END])
    return graph.compile()


class LangGraphAgent:
    name = "langgraph"

    def __init__(self, max_steps: int = MAX_STEPS):
        self.max_steps = max_steps

    def run(self, model, runtime: ToolRuntime, system: str, user_text: str) -> Episode:
        graph = build_graph(
            ToolbrChatModel(toolbr_model=model), langchain_tools(runtime), self.max_steps
        )
        start = time.perf_counter()
        messages: list[BaseMessage] = [SystemMessage(system), HumanMessage(user_text)]
        steps, error = 0, None
        try:
            state = graph.invoke(
                {"messages": messages, "steps": 0},
                config={"recursion_limit": 2 * self.max_steps + 5},
            )
            messages, steps = state["messages"], state["steps"]
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"

        usage = Usage()
        for msg in messages:
            if isinstance(msg, AIMessage):
                usage.add(Usage(**msg.response_metadata.get("toolbr_usage", {})))
        last = messages[-1]
        if error:
            final, stopped = "", "erro"
        elif isinstance(last, AIMessage) and last.response_metadata.get("stop_reason") == "refusal":
            final, stopped = last.text, "recusa_modelo"
        elif isinstance(last, AIMessage) and not last.tool_calls:
            final, stopped = last.text, "resposta"
        else:
            final, stopped = "", "limite_passos"
        _, history = to_neutral(messages)
        return Episode(
            final_text=final,
            calls=runtime.records,
            steps=steps,
            usage=usage,
            latency_s=time.perf_counter() - start,
            stopped=stopped,
            error=error,
            transcript=transcript(history),
        )
