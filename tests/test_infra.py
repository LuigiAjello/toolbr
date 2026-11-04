"""Servidor MCP (cliente em memória) e registro no MLflow."""

import json

import pytest

from toolbr.tracking import metric_name, summary_metrics


def test_mcp_server_lists_and_calls_tools():
    pytest.importorskip("mcp")
    import anyio
    from mcp.client.client import Client

    from toolbr.mcp_server import build_server

    async def main():
        async with Client(build_server("delivery")) as client:
            tools = await client.list_tools()
            ok = await client.call_tool("consultar_pedido", {"pedido_id": 1042})
            err = await client.call_tool("cancelar_pedido", {"pedido_id": 1040, "motivo": "x"})
            return client.protocol_version, tools, ok, err

    version, tools, ok, err = anyio.run(main)
    assert version == "2026-07-28"
    names = {t.name for t in tools.tools}
    assert {"consultar_pedido", "cancelar_pedido", "buscar_politica"} <= names
    assert not ok.is_error and ok.structured_content["pedido"]["status"] == "em_preparo"
    assert err.is_error and "entregue" in json.loads(err.content[0].text)["erro"]


def test_metric_names_have_no_caret():
    assert metric_name("pass^4") == "pass_hat_4"
    assert metric_name("recall@3") == "recall_at_3"


def test_mlflow_logs_params_metrics_and_artifact(tmp_path, monkeypatch):
    mlflow = pytest.importorskip("mlflow")
    monkeypatch.chdir(tmp_path)  # o MLflow grava os artefatos em ./mlruns
    from toolbr.agents import make_agent
    from toolbr.metrics import summarize
    from toolbr.models.mock import OracleModel
    from toolbr.runner import run_suite
    from toolbr.tasks import load_tasks
    from toolbr.tracking import log_run

    trials = run_suite(list(load_tasks())[:3], OracleModel(), make_agent("loop"), k=2)
    summary = summarize(trials)
    artifact = tmp_path / "resultado.json"
    artifact.write_text("{}")
    metadata = {"modelo": "oracle", "agente": "loop", "k": 2, "configuracao_modelo": {"x": 1}}
    uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    run_id = log_run(metadata, summary, artifact, uri=uri)

    mlflow.set_tracking_uri(uri)
    run = mlflow.get_run(run_id)
    assert run.data.metrics["pass_hat_2"] == 1.0
    assert run.data.params["modelo"] == "oracle" and run.data.params["modelo_x"] == "1"
    assert set(summary_metrics(summary)) <= set(run.data.metrics)
