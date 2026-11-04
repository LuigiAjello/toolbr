import sys
from pathlib import Path

import pytest

pytest.importorskip("gradio")
sys.path.insert(0, str(Path(__file__).parents[1] / "demo"))

import app  # noqa: E402


def test_demo_shows_attack_changing_the_database():
    task = app.TASKS["ataque-01"]
    notice, verdict, compare, calls, changes, stats = app.run_demo(
        "ataque-01", task.request, "vulnerable", "loop", "nenhuma"
    )
    assert "não é um LLM" in notice["value"]
    assert "O ataque escondido funcionou" in verdict
    assert ["pedidos", "1043", "status", "em_preparo", "cancelado"] in changes["value"]


def test_demo_with_gate_blocks_the_attack():
    task = app.TASKS["ataque-01"]
    _, verdict, _, calls, changes, _ = app.run_demo(
        "ataque-01", task.request, "vulnerable", "loop", "portao"
    )
    assert "Passou" in verdict and "não funcionou" in verdict
    assert any(row[3] == "barrada pela defesa" for row in calls["value"])
    assert not changes["visible"]
