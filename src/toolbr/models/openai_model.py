"""Adaptador OpenAI e Ollama, pela Chat Completions API com tools.

O Ollama expõe a mesma API em http://localhost:11434/v1, então um adaptador serve para
os dois. Modelos de raciocínio da OpenAI podem recusar temperatura diferente do padrão;
nesse caso a chamada falha e o erro fica registrado no resultado.
"""

from __future__ import annotations

import json
import os
from typing import Any

from toolbr.types import ModelTurn, ToolCall, Usage
from toolbr.worlds.base import ToolSpec

STOP_REASONS = {
    "stop": "end",
    "tool_calls": "tool_use",
    "length": "max_tokens",
    "content_filter": "refusal",
}


class OpenAIModel:
    is_test_model = False

    def __init__(
        self,
        model_id: str,
        provider: str = "openai",
        temperature: float | None = None,
        effort: str | None = None,
    ):
        from openai import OpenAI

        if provider == "ollama":
            base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
            self.client = OpenAI(base_url=base_url, api_key="ollama", max_retries=2)
        else:
            self.client = OpenAI(max_retries=4)
        self.name = model_id
        self.provider = provider
        self.temperature = temperature
        self.effort = effort
        self.settings = {
            "temperatura": temperature if temperature is not None else "padrão do modelo",
            "reasoning_effort": effort or "padrão do modelo",
        }

    def for_episode(self, task) -> OpenAIModel:
        return self

    def complete(self, system: str, history: list[dict], tools: list[ToolSpec]) -> ModelTurn:
        kwargs: dict[str, Any] = {
            "model": self.name,
            "messages": [{"role": "system", "content": system}, *to_openai_messages(history)],
            "tools": [{"type": "function", "function": t.schema()} for t in tools],
        }
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if self.effort:
            kwargs["reasoning_effort"] = self.effort
        return parse_openai_response(self.client.chat.completions.create(**kwargs))


def to_openai_messages(history: list[dict]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for msg in history:
        if msg["role"] == "user":
            messages.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant":
            out: dict[str, Any] = {"role": "assistant", "content": msg["content"] or None}
            if msg["tool_calls"]:
                out["tool_calls"] = [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {
                            "name": c.name,
                            "arguments": json.dumps(c.arguments, ensure_ascii=False),
                        },
                    }
                    for c in msg["tool_calls"]
                ]
            messages.append(out)
        else:
            messages += [
                {"role": "tool", "tool_call_id": r["id"], "content": r["content"]}
                for r in msg["results"]
            ]
    return messages


def _parse_args(raw: str | None) -> dict[str, Any]:
    try:
        args = json.loads(raw or "{}")
        return args if isinstance(args, dict) else {"_argumentos_invalidos": raw}
    except json.JSONDecodeError:
        # JSON quebrado vira um argumento desconhecido: o mundo devolve erro e o modelo vê
        return {"_argumentos_invalidos": raw}


def parse_openai_response(response: Any) -> ModelTurn:
    choice = response.choices[0]
    msg = choice.message
    calls = [
        ToolCall(tc.id, tc.function.name, _parse_args(tc.function.arguments))
        for tc in (msg.tool_calls or [])
    ]
    u = response.usage
    cached = 0
    if u is not None and getattr(u, "prompt_tokens_details", None) is not None:
        cached = u.prompt_tokens_details.cached_tokens or 0
    usage = Usage(
        # prompt_tokens já inclui os tokens em cache: separo para não contar duas vezes
        input_tokens=(u.prompt_tokens - cached) if u else 0,
        output_tokens=u.completion_tokens if u else 0,
        cache_read_tokens=cached,
    )
    stop = STOP_REASONS.get(choice.finish_reason, str(choice.finish_reason))
    if msg.refusal:
        stop = "refusal"
    return ModelTurn(msg.content or msg.refusal or "", calls, usage, stop)
