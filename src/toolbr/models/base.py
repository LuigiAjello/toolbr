"""Interface comum dos modelos. O agente só conhece esta interface."""

from __future__ import annotations

from typing import Any, Protocol

from toolbr.tasks import Task
from toolbr.types import ModelTurn
from toolbr.worlds.base import ToolSpec


class Model(Protocol):
    name: str
    provider: str
    is_test_model: bool
    # temperatura pedida; None quando o provedor não aceita ou ficou no padrão
    temperature: float | None
    # outros parâmetros que entram nos metadados do resultado (ex.: effort)
    settings: dict[str, Any]

    def for_episode(self, task: Task) -> Model:
        """Modelos de teste leem o gabarito da tarefa; modelos reais devolvem a si mesmos."""
        ...

    def complete(self, system: str, history: list[dict], tools: list[ToolSpec]) -> ModelTurn: ...
