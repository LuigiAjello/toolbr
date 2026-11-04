"""Execução de ferramentas compartilhada pelos dois agentes (loop próprio e LangGraph).

Fica num lugar só para que a comparação entre agentes meça apenas a orquestração:
as mesmas ferramentas, a mesma defesa e o mesmo registro de chamadas.
"""

from __future__ import annotations

from typing import Any

from toolbr.defenses import Defense
from toolbr.types import CallRecord
from toolbr.worlds.base import ToolSpec, World


class ToolRuntime:
    def __init__(self, world: World, defense: Defense, trusted_text: str):
        self.world = world
        self.defense = defense
        self.records: list[CallRecord] = []
        defense.start(world, trusted_text)

    def specs(self) -> list[ToolSpec]:
        return self.world.tool_specs()

    def execute(self, name: str, args: dict[str, Any] | None) -> tuple[str, bool]:
        """Roda uma chamada e devolve (texto para o modelo, se é erro)."""
        args = args if isinstance(args, dict) else {}
        reason = self.defense.before_call(self.world.spec(name), args)
        if reason:
            result = {"erro": f"ação bloqueada pela defesa: {reason}"}
        else:
            result = self.world.call(name, args)
            self.defense.after_call(name, result)
        is_error = "erro" in result
        self.records.append(CallRecord(name, dict(args), result, is_error, blocked=bool(reason)))
        return self.defense.render(result), is_error
