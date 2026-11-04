"""O agente LangGraph precisa se comportar como o loop próprio com o mesmo modelo."""

import pytest
from helpers import ScriptedModel

pytest.importorskip("langgraph")

from toolbr.agents import make_agent  # noqa: E402
from toolbr.models.mock import OracleModel  # noqa: E402
from toolbr.runner import run_trial  # noqa: E402
from toolbr.tasks import get_task  # noqa: E402

SCENARIOS = [
    ("delivery-02", [[("cancelar_pedido", {"pedido_id": 1042, "motivo": "x"})]], "Cancelado."),
    (
        "delivery-02",
        [
            [
                ("cancelar_pedido", {"pedido_id": 1042, "motivo": "x"}),
                ("consultar_pedido", {"pedido_id": 1043}),
            ]
        ],
        "Cancelado.",
    ),
    ("delivery-03", [], "Já saiu para entrega."),
    ("delivery-01", [[("consultar_pedido", {"pedido_id": 1042})]] * 10, "em preparo"),
]


@pytest.mark.parametrize(("task_id", "steps", "answer"), SCENARIOS)
def test_same_grade_steps_and_calls_in_both_agents(task_id, steps, answer):
    out = {}
    for agent in ("loop", "langgraph"):
        r = run_trial(
            get_task(task_id), 1, ScriptedModel(steps, answer), make_agent(agent, max_steps=4)
        )
        out[agent] = r
    loop, graph = out["loop"], out["langgraph"]
    assert graph["nota"] == loop["nota"]
    assert graph["episodio"]["steps"] == loop["episodio"]["steps"]
    assert graph["episodio"]["stopped"] == loop["episodio"]["stopped"]
    assert [c["name"] for c in graph["episodio"]["calls"]] == [
        c["name"] for c in loop["episodio"]["calls"]
    ]


def test_tool_error_flag_reaches_the_model_in_langgraph():
    r = run_trial(get_task("banco-06"), 1, OracleModel(), make_agent("langgraph"))
    tool_msgs = [m for m in r["episodio"]["transcript"] if m["role"] == "tool"]
    flags = [res["is_error"] for m in tool_msgs for res in m["results"]]
    assert flags == [False, True, False]  # listar, bloquear (503), bloquear de novo
    assert r["nota"]["success"]
