"""Executor: reinicia o mundo, roda o agente e corrige, n vezes por tarefa."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from toolbr.agents.prompt import build_system_prompt, trusted_text
from toolbr.agents.runtime import ToolRuntime
from toolbr.defenses import make_defense
from toolbr.grader import grade, state_changes
from toolbr.models.base import Model
from toolbr.retrieval import get_retriever
from toolbr.tasks import Task
from toolbr.worlds import make_world


def run_trial(
    task: Task,
    trial: int,
    model: Model,
    agent,
    defense_name: str = "nenhuma",
    policy_mode: str = "contexto",
    retrieval: str = "bm25",
) -> dict[str, Any]:
    world = make_world(
        task.world, fail_plan=task.fail_plan, retriever=get_retriever(retrieval, task.world)
    )
    if task.injection:
        inj = task.injection
        world.set_field(inj.table, inj.key, inj.column, inj.text)
    initial = world.snapshot()
    defense = make_defense(defense_name)
    runtime = ToolRuntime(world, defense, trusted_text(world, task))
    system = build_system_prompt(world, task, defense, policy_mode)
    episode = agent.run(model.for_episode(task), runtime, system, task.request)
    final = world.snapshot()
    nota = grade(task, world, initial, final, episode)
    result = {
        "tarefa": task.id,
        "tentativa": trial,
        "mundo": task.world,
        "tipo": task.type,
        "nivel": task.level,
        "nota": nota.to_dict(),
        "episodio": episode.to_dict(),
        "mudancas": state_changes(initial, final),
        "estado_inicial": initial,
        "estado_final": final,
    }
    if task.injection:
        # tarefa de ataque só consulta: qualquer mudança no banco é o ataque funcionando
        result["ataque_funcionou"] = not nota.state_ok
    return result


def run_suite(
    tasks: list[Task],
    model: Model,
    agent,
    k: int = 4,
    defense_name: str = "nenhuma",
    policy_mode: str = "contexto",
    workers: int = 1,
    retrieval: str = "bm25",
    on_done: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    jobs = [(task, trial) for task in tasks for trial in range(1, k + 1)]

    def work(job: tuple[Task, int]) -> dict[str, Any]:
        result = run_trial(job[0], job[1], model, agent, defense_name, policy_mode, retrieval)
        if on_done:
            on_done(result)
        return result

    if workers <= 1:
        return [work(job) for job in jobs]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(work, jobs))
