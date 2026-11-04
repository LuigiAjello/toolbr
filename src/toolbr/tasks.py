"""Tarefas e casos de ataque: leitura e validação do formato."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from typing import Any

import yaml

from toolbr.paths import DATA_DIR

TASK_TYPES = (
    "simples",
    "sequencia",
    "recusa",
    "informacao_faltando",
    "ferramenta_irrelevante",
    "ferramenta_falha",
    "consulta_politica",
)
LEVELS = ("facil", "medio", "dificil")


@dataclass(frozen=True)
class Call:
    tool: str
    args: dict[str, Any]


@dataclass(frozen=True)
class Injection:
    """Instrução maliciosa escondida num campo não confiável."""

    table: str
    key: Any
    column: str
    text: str
    malicious_call: Call
    language: str
    disguise: str


@dataclass(frozen=True)
class Task:
    id: str
    world: str
    level: str
    type: str
    customer: str
    request: str
    effects: tuple[dict[str, Any], ...]
    gold_calls: tuple[Call, ...]
    required_tools: tuple[str, ...]
    forbidden_tools: tuple[str, ...]
    must_contain: tuple[Any, ...]
    must_not_contain: tuple[Any, ...]
    reference_answer: str
    fail_plan: dict[str, int] = field(default_factory=dict)
    injection: Injection | None = None
    notes: str = ""


def _parse_task(raw: dict[str, Any]) -> Task:
    injection = None
    if "injecao" in raw:
        inj = raw["injecao"]
        mal = inj["acao_maliciosa"]
        injection = Injection(
            table=inj["tabela"],
            key=inj["onde"],
            column=inj["campo"],
            text=inj["texto"],
            malicious_call=Call(mal["ferramenta"], dict(mal["argumentos"])),
            language=inj["idioma"],
            disguise=inj["disfarce"],
        )
    return Task(
        id=raw["id"],
        world=raw["mundo"],
        level=raw["nivel"],
        type=raw["tipo"],
        customer=raw["cliente"],
        request=raw["pedido"],
        effects=tuple(raw.get("efeitos_esperados") or ()),
        gold_calls=tuple(
            Call(c["ferramenta"], dict(c.get("argumentos") or {}))
            for c in raw.get("argumentos_esperados") or ()
        ),
        required_tools=tuple(raw.get("ferramentas_esperadas") or ()),
        forbidden_tools=tuple(raw.get("ferramentas_proibidas") or ()),
        must_contain=tuple(raw.get("resposta_deve_conter") or ()),
        must_not_contain=tuple(raw.get("resposta_nao_deve_conter") or ()),
        reference_answer=raw["resposta_referencia"],
        fail_plan=dict(raw.get("falhas") or {}),
        injection=injection,
        notes=raw.get("notas", ""),
    )


def _load(filename: str, key: str) -> tuple[str, tuple[Task, ...]]:
    raw = yaml.safe_load((DATA_DIR / filename).read_text(encoding="utf-8"))
    return str(raw["versao"]), tuple(_parse_task(t) for t in raw[key])


@cache
def load_tasks() -> tuple[Task, ...]:
    return _load("tarefas.yaml", "tarefas")[1]


@cache
def load_attacks() -> tuple[Task, ...]:
    return _load("ataques.yaml", "ataques")[1]


@cache
def dataset_version() -> str:
    return _load("tarefas.yaml", "tarefas")[0]


def get_task(task_id: str) -> Task:
    pool = load_tasks()
    if (DATA_DIR / "ataques.yaml").exists():
        pool += load_attacks()
    for task in pool:
        if task.id == task_id:
            return task
    raise KeyError(f"tarefa não encontrada: {task_id}")
