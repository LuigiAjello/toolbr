"""Portão de qualidade: os modelos de teste provam que o corretor funciona.

Se o oracle (gabarito exato) não dá 100%, o gabarito ou o corretor está errado.
Se o naive (não faz nada, diz "resolvido") passa em mais de 10%, o corretor está frouxo.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass

from toolbr.agents import make_agent
from toolbr.metrics import summarize
from toolbr.models.mock import NaiveModel, OracleModel
from toolbr.runner import run_suite
from toolbr.tasks import load_tasks

NAIVE_MAX = 0.10


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def available_agents() -> list[str]:
    agents = ["loop"]
    if importlib.util.find_spec("langgraph"):
        agents.append("langgraph")
    return agents


def _success(model, agent_name: str, tasks) -> tuple[float, list[dict]]:
    trials = run_suite(list(tasks), model, make_agent(agent_name), k=1)
    return summarize(trials)["sucesso"]["media"], trials


def grader_checks(agents: list[str] | None = None) -> list[Check]:
    tasks = load_tasks()
    checks = []
    for agent in agents or available_agents():
        rate, trials = _success(OracleModel(), agent, tasks)
        failed = [t["tarefa"] for t in trials if not t["nota"]["success"]]
        checks.append(
            Check(
                f"oracle = 100% ({agent})",
                rate == 1.0,
                f"{rate:.0%}; falhou: {failed or 'nenhuma'}",
            )
        )
        rate, trials = _success(NaiveModel(), agent, tasks)
        passed = [t["tarefa"] for t in trials if t["nota"]["success"]]
        checks.append(
            Check(
                f"naive <= {NAIVE_MAX:.0%} ({agent})",
                rate <= NAIVE_MAX,
                f"{rate:.0%}; passou em: {passed or 'nenhuma'}",
            )
        )
    return checks


def run_gate(agents: list[str] | None = None) -> list[Check]:
    return grader_checks(agents)
