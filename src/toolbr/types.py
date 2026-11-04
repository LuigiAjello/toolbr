"""Tipos neutros trocados entre agente, modelo e corretor (independentes de provedor).

Histórico da conversa, no formato neutro:
    {"role": "user", "content": str}
    {"role": "assistant", "content": str, "tool_calls": [ToolCall], "raw": <provedor>}
    {"role": "tool", "results": [{"id", "name", "content": str, "is_error": bool}]}
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    def add(self, other: Usage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_write_tokens += other.cache_write_tokens


@dataclass
class ModelTurn:
    text: str
    tool_calls: list[ToolCall]
    usage: Usage = field(default_factory=Usage)
    # "end" (respondeu), "tool_use", "max_tokens" ou "refusal" (o provedor recusou)
    stop_reason: str = "end"
    # resposta original do provedor, reenviada como está (ex.: blocos de raciocínio)
    raw: Any = None


@dataclass
class CallRecord:
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    is_error: bool
    blocked: bool = False  # barrada por uma defesa antes de chegar ao mundo


@dataclass
class Episode:
    final_text: str
    calls: list[CallRecord]
    steps: int
    usage: Usage
    latency_s: float
    # "resposta", "limite_passos", "recusa_modelo" ou "erro"
    stopped: str
    error: str | None = None
    transcript: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
