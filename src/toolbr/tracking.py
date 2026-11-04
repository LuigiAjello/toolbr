"""Registro das execuções no MLflow, com backend SQLite.

O backend de arquivos do MLflow está em modo de manutenção, por isso SQLite
(mlflow.db na raiz). Nomes de métrica não aceitam "^": Pass^4 vira pass_hat_4.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from toolbr.paths import ROOT

DEFAULT_URI = f"sqlite:///{ROOT / 'mlflow.db'}"
EXPERIMENT = "toolbr"


def metric_name(name: str) -> str:
    name = name.replace("^", "_hat_").replace("@", "_at_")
    return re.sub(r"[^\w\-./ ]", "_", name)


def summary_metrics(summary: dict[str, Any]) -> dict[str, float]:
    metrics = {"sucesso": summary["sucesso"]["media"]}
    metrics["sucesso_ic95_inf"], metrics["sucesso_ic95_sup"] = summary["sucesso"]["ic95"]
    for k, block in summary["pass_hat"].items():
        metrics[metric_name(f"pass^{k}")] = block["media"]
    for key, value in summary["diagnostico"].items():
        if value is not None:
            metrics[f"acerto_{key}"] = value
    metrics["latencia_p50_s"] = summary["latencia_s"]["p50"]
    metrics["latencia_p95_s"] = summary["latencia_s"]["p95"]
    metrics["passos_medios"] = summary["passos_medios"]
    metrics["erros_execucao"] = summary["erros_execucao"]
    metrics["tokens_entrada"] = summary["custo"]["tokens_entrada"]
    metrics["tokens_saida"] = summary["custo"]["tokens_saida"]
    if summary["custo"]["usd_total"] is not None:
        metrics["custo_usd"] = summary["custo"]["usd_total"]
    return metrics


def log_run(
    metadata: dict[str, Any], summary: dict[str, Any], artifact: Path, uri: str | None = None
) -> str:
    import mlflow

    mlflow.set_tracking_uri(uri or os.environ.get("MLFLOW_TRACKING_URI", DEFAULT_URI))
    mlflow.set_experiment(EXPERIMENT)
    params = {
        k: v
        for k, v in metadata.items()
        if k not in ("tarefas", "configuracao_modelo") and not isinstance(v, dict | list)
    }
    params.update({f"modelo_{k}": v for k, v in metadata.get("configuracao_modelo", {}).items()})
    with mlflow.start_run(run_name=f"{metadata['modelo']} | {metadata.get('agente')}") as run:
        mlflow.log_params({k: str(v) for k, v in params.items()})
        mlflow.log_metrics(summary_metrics(summary))
        mlflow.log_artifact(str(artifact))
        return run.info.run_id
