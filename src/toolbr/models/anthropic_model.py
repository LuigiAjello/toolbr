"""Adaptador Anthropic (Claude), pelo SDK oficial e a Messages API com tool use.

Escolhas de benchmark:
- Sem temperatura: desde a versão 2026-10-21 da API, `temperature` dá erro 400 em todo
  modelo Claude. O controle disponível é o `effort`, que entra nos metadados.
- Sem fallback de modelo em recusa: o fallback trocaria o modelo no meio do episódio e
  a nota iria para o modelo errado. Uma recusa vira o motivo de falha "recusa_modelo".
- Cache de prompt automático: sistema e ferramentas se repetem em todas as chamadas.
- Os blocos devolvidos (inclusive raciocínio) voltam ao histórico sem alteração.
"""

from __future__ import annotations

from typing import Any

from toolbr.types import ModelTurn, ToolCall, Usage
from toolbr.worlds.base import ToolSpec

STOP_REASONS = {
    "end_turn": "end",
    "tool_use": "tool_use",
    "max_tokens": "max_tokens",
    "refusal": "refusal",
}


class AnthropicModel:
    provider = "anthropic"
    is_test_model = False
    temperature = None

    def __init__(
        self,
        model_id: str,
        temperature: float | None = None,
        effort: str | None = None,
        max_tokens: int = 16000,
    ):
        import anthropic

        if temperature is not None:
            raise ValueError(
                "a API da Anthropic não aceita temperature (erro 400 desde 2026-10-21); "
                "use --effort para controlar o modelo"
            )
        self.client = anthropic.Anthropic(max_retries=4)
        self.name = model_id
        self.effort = effort
        self.max_tokens = max_tokens
        self.settings = {
            "temperatura": "não suportada pela API",
            "effort": effort or "padrão do modelo",
            "max_tokens": max_tokens,
        }

    def for_episode(self, task) -> AnthropicModel:
        return self

    def complete(self, system: str, history: list[dict], tools: list[ToolSpec]) -> ModelTurn:
        kwargs: dict[str, Any] = {
            "model": self.name,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": to_anthropic_messages(history),
            "tools": [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in tools
            ],
            "cache_control": {"type": "ephemeral"},
        }
        if self.effort:
            kwargs["output_config"] = {"effort": self.effort}
        response = self.client.messages.create(**kwargs)
        return parse_anthropic_response(response)


def to_anthropic_messages(history: list[dict]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for msg in history:
        if msg["role"] == "user":
            messages.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant":
            content = msg.get("raw")
            if content is None:  # turno que não veio da Anthropic (não acontece num episódio)
                content = []
                if msg["content"]:
                    content.append({"type": "text", "text": msg["content"]})
                content += [
                    {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments}
                    for c in msg["tool_calls"]
                ]
            messages.append({"role": "assistant", "content": content})
        else:
            # todos os resultados do mesmo turno numa única mensagem
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": r["id"],
                            "content": r["content"],
                            "is_error": r["is_error"],
                        }
                        for r in msg["results"]
                    ],
                }
            )
    return messages


def parse_anthropic_response(response: Any) -> ModelTurn:
    text = "".join(b.text for b in response.content if b.type == "text")
    calls = [
        ToolCall(b.id, b.name, dict(b.input or {}))
        for b in response.content
        if b.type == "tool_use"
    ]
    u = response.usage
    usage = Usage(
        input_tokens=u.input_tokens or 0,
        output_tokens=u.output_tokens or 0,
        cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
        cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
    )
    stop = STOP_REASONS.get(response.stop_reason, str(response.stop_reason))
    return ModelTurn(text, calls, usage, stop, raw=response.content)
