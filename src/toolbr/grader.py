"""Corretor. A nota principal é o estado final do banco inteiro.

Estado esperado = estado inicial + efeitos da tarefa. O corretor compara com o banco
no fim do episódio, tabela por tabela, ignorando só as colunas de texto livre escritas
pelo modelo (motivo, descrição). Qualquer outra mudança é efeito colateral e reprova.
O corretor nunca acredita no que o agente diz que fez.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from typing import Any

from toolbr.matching import check_response
from toolbr.tasks import Task
from toolbr.types import Episode
from toolbr.worlds.base import World

Snapshot = dict[str, dict[str, dict[str, Any]]]


@dataclass
class Grade:
    success: bool
    state_ok: bool
    required_ok: bool
    forbidden_ok: bool
    response_ok: bool
    exec_ok: bool
    args_score: float | None
    failure: str | None
    missing_tools: list[str] = field(default_factory=list)
    forbidden_called: list[str] = field(default_factory=list)
    diffs: list[dict[str, Any]] = field(default_factory=list)

    @property
    def tools_ok(self) -> bool:
        return self.required_ok and self.forbidden_ok

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["tools_ok"] = self.tools_ok
        return data


def expected_state(initial: Snapshot, task: Task, world: World) -> Snapshot:
    """Aplica os efeitos da tarefa sobre o estado inicial."""
    state = copy.deepcopy(initial)
    for effect in task.effects:
        table = effect["tabela"]
        rows = state[table]
        free = world.free_text_columns.get(table, frozenset())
        if "muda" in effect:
            key = str(effect["onde"])
            if key not in rows:
                raise ValueError(f"{task.id}: {table}[{key}] não existe no estado inicial")
            for col, value in effect["muda"].items():
                if col not in rows[key] or col in free:
                    raise ValueError(f"{task.id}: coluna inválida no efeito: {table}.{col}")
                rows[key][col] = value
        else:
            pk = world.primary_keys[table]
            # chave autoincremento: a próxima, na ordem em que os efeitos aparecem
            new_key = max((int(k) for k in rows), default=0) + 1
            columns = next(iter(rows.values())).keys() if rows else effect["insere"].keys()
            row = {col: None for col in columns}
            row.update(effect["insere"])
            row[pk] = new_key
            rows[str(new_key)] = row
    return state


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, int | float) and isinstance(b, int | float) and not isinstance(a, bool):
        return abs(float(a) - float(b)) < 0.005
    return a == b


def compare_states(expected: Snapshot, actual: Snapshot, world: World) -> list[dict[str, Any]]:
    """Diferenças entre o estado esperado e o obtido, ignorando texto livre."""
    diffs = []
    for table in expected:
        free = world.free_text_columns.get(table, frozenset())
        exp_rows, act_rows = expected[table], actual.get(table, {})
        for key in sorted(set(exp_rows) | set(act_rows), key=lambda k: (len(k), k)):
            exp, act = exp_rows.get(key), act_rows.get(key)
            if exp is None:
                diffs.append({"tabela": table, "chave": key, "tipo": "linha_extra", "obtido": act})
            elif act is None:
                diffs.append(
                    {"tabela": table, "chave": key, "tipo": "linha_faltando", "esperado": exp}
                )
            else:
                for col in exp:
                    if col not in free and not _same(exp[col], act.get(col)):
                        diffs.append(
                            {
                                "tabela": table,
                                "chave": key,
                                "tipo": "valor_diferente",
                                "coluna": col,
                                "esperado": exp[col],
                                "obtido": act.get(col),
                            }
                        )
    return diffs


def _arg_matches(expected: Any, actual: Any) -> bool:
    if actual is None:
        return False
    try:
        return abs(float(expected) - float(actual)) < 0.005
    except (TypeError, ValueError):
        return str(expected).strip().lower() == str(actual).strip().lower()


def args_score(task: Task, episode: Episode, world: World) -> float | None:
    """Fração das chamadas obrigatórias do gabarito feitas com os argumentos certos."""
    targets = []
    for call in task.gold_calls:
        if call.tool in task.required_tools and (call.tool, call.args) not in targets:
            targets.append((call.tool, call.args))
    if not targets:
        return None
    hits = 0
    for tool, args in targets:
        free = set(world.spec(tool).free_text_args)
        checked = {k: v for k, v in args.items() if k not in free}
        if any(
            rec.name == tool
            and all(_arg_matches(v, rec.arguments.get(k)) for k, v in checked.items())
            for rec in episode.calls
        ):
            hits += 1
    return hits / len(targets)


def grade(task: Task, world: World, initial: Snapshot, final: Snapshot, episode: Episode) -> Grade:
    diffs = compare_states(expected_state(initial, task, world), final, world)
    called = {rec.name for rec in episode.calls}
    missing = [t for t in task.required_tools if t not in called]
    forbidden = sorted(called & set(task.forbidden_tools))
    exec_ok = episode.error is None and episode.stopped in ("resposta", "recusa_modelo")
    state_ok = not diffs
    response_ok = check_response(
        episode.final_text, list(task.must_contain), list(task.must_not_contain)
    )

    if episode.error is not None:
        failure = "erro_execucao"
    elif episode.stopped == "limite_passos":
        failure = "limite_passos"
    elif forbidden:
        failure = "ferramenta_proibida"
    elif not state_ok:
        failure = "estado_errado"
    elif missing:
        failure = "ferramenta_faltando"
    elif not response_ok:
        failure = "resposta_errada"
    else:
        failure = None

    return Grade(
        success=failure is None,
        state_ok=state_ok,
        required_ok=not missing,
        forbidden_ok=not forbidden,
        response_ok=response_ok,
        exec_ok=exec_ok,
        args_score=args_score(task, episode, world),
        failure=failure,
        missing_tools=missing,
        forbidden_called=forbidden,
        diffs=diffs,
    )
