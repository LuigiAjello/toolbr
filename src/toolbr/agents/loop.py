"""Agente principal: loop próprio direto na API do modelo, com limite de passos.

É o principal porque a maioria dos agentes em produção é feita assim: um while que
chama o modelo, executa as ferramentas pedidas e devolve os resultados.
Passo = uma chamada ao modelo.
"""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from toolbr.agents.runtime import ToolRuntime
from toolbr.models.base import Model
from toolbr.types import Episode, Usage

MAX_STEPS = 8


class LoopAgent:
    name = "loop"

    def __init__(self, max_steps: int = MAX_STEPS):
        self.max_steps = max_steps

    def run(self, model: Model, runtime: ToolRuntime, system: str, user_text: str) -> Episode:
        history: list[dict[str, Any]] = [{"role": "user", "content": user_text}]
        usage, steps, final, stopped, error = Usage(), 0, "", "limite_passos", None
        start = time.perf_counter()
        try:
            while steps < self.max_steps:
                turn = model.complete(system, history, runtime.specs())
                steps += 1
                usage.add(turn.usage)
                if turn.stop_reason == "refusal":
                    final, stopped = turn.text, "recusa_modelo"
                    break
                history.append(
                    {
                        "role": "assistant",
                        "content": turn.text,
                        "tool_calls": turn.tool_calls,
                        "raw": turn.raw,
                    }
                )
                if not turn.tool_calls:
                    final, stopped = turn.text, "resposta"
                    break
                results = []
                for call in turn.tool_calls:
                    content, is_error = runtime.execute(call.name, call.arguments)
                    results.append(
                        {"id": call.id, "name": call.name, "content": content, "is_error": is_error}
                    )
                history.append({"role": "tool", "results": results})
        except Exception as exc:  # erro de API ou de adaptador: registrado, não esconde
            error, stopped = f"{type(exc).__name__}: {exc}", "erro"
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


def transcript(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Histórico sem o conteúdo bruto do provedor, pronto para JSON."""
    out = []
    for msg in history:
        if msg["role"] == "assistant":
            out.append(
                {
                    "role": "assistant",
                    "content": msg["content"],
                    "tool_calls": [asdict(c) for c in msg["tool_calls"]],
                }
            )
        else:
            out.append(msg)
    return out
