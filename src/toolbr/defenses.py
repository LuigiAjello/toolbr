"""Defesas contra prompt injection indireta.

A defesa fica entre o agente e o mundo: pode avisar no prompt de sistema, mudar a
forma como o resultado da ferramenta é mostrado ao modelo, e barrar uma chamada.
"""

from __future__ import annotations

import json
from typing import Any

from toolbr.worlds.base import ToolSpec, World


class Defense:
    """Sem defesa: o resultado vai como JSON puro e nenhuma chamada é barrada."""

    name = "nenhuma"
    system_note = ""

    def start(self, world: World, trusted_text: str) -> None:
        self.world = world

    def before_call(self, spec: ToolSpec | None, args: dict[str, Any]) -> str | None:
        """Devolve o motivo do bloqueio, ou None para deixar passar."""
        return None

    def after_call(self, name: str, result: dict[str, Any]) -> None:
        pass

    def render(self, result: dict[str, Any]) -> str:
        return json.dumps(result, ensure_ascii=False)


DEFENSES: dict[str, type[Defense]] = {"nenhuma": Defense}


def make_defense(name: str) -> Defense:
    if name not in DEFENSES:
        raise ValueError(f"defesa desconhecida: {name}. Opções: {', '.join(DEFENSES)}")
    return DEFENSES[name]()
