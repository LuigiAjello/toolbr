"""Agentes: loop próprio (principal) e LangGraph (para medir o efeito da orquestração)."""

from __future__ import annotations

from toolbr.agents.loop import MAX_STEPS, LoopAgent

AGENT_NAMES = ("loop", "langgraph")


def make_agent(name: str, max_steps: int = MAX_STEPS):
    if name == "loop":
        return LoopAgent(max_steps)
    if name == "langgraph":
        from toolbr.agents.langgraph_agent import LangGraphAgent

        return LangGraphAgent(max_steps)
    raise ValueError(f"agente desconhecido: {name}. Opções: {', '.join(AGENT_NAMES)}")
