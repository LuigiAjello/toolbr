"""Resultado em JSON com metadados, e a tabela comparativa."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from toolbr import __version__
from toolbr.paths import DATA_DIR, RESULTS_DIR, ROOT

CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")


def mask_pii(obj: Any) -> Any:
    """LGPD: mascara CPF em tudo que vai para o disco."""
    if isinstance(obj, str):
        return CPF.sub("***.***.***-**", obj)
    if isinstance(obj, dict):
        return {k: mask_pii(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [mask_pii(v) for v in obj]
    return obj


def load_prices(model_name: str) -> dict[str, float] | None:
    path = DATA_DIR / "precos.yaml"
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text("utf-8")) or {}
    return (data.get("modelos") or {}).get(model_name)


def git_commit() -> dict[str, Any]:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
        return {"commit": sha, "alteracoes_nao_commitadas": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "alteracoes_nao_commitadas": None}


def build_metadata(model, **run_info: Any) -> dict[str, Any]:
    from toolbr.tasks import dataset_version

    return {
        "modelo": model.name,
        "provedor": model.provider,
        "modelo_de_teste": model.is_test_model,
        "temperatura": model.temperature,
        "configuracao_modelo": dict(model.settings),
        **run_info,
        "versao_dataset": dataset_version(),
        "versao_toolbr": __version__,
        "data": datetime.now().astimezone().isoformat(timespec="seconds"),
        **git_commit(),
    }


def save_result(
    metadata: dict[str, Any], summary: dict[str, Any], trials: list[dict], kind: str
) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_model = re.sub(r"[^\w.-]+", "_", metadata["modelo"])
    path = RESULTS_DIR / f"{kind}_{safe_model}_{metadata.get('agente', 'na')}_{stamp}.json"
    slim = [
        {k: v for k, v in t.items() if k not in ("estado_inicial", "estado_final")} for t in trials
    ]
    payload = {"tipo": kind, "metadados": metadata, "resumo": summary, "tentativas": slim}
    path.write_text(json.dumps(mask_pii(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def save_json(payload: dict[str, Any], kind: str) -> Path:
    """Salva um resultado que não é de tarefas (busca, segurança), com os metadados do git."""
    from toolbr.tasks import dataset_version

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    payload = {
        **payload,
        "metadados_execucao": {
            "data": datetime.now().astimezone().isoformat(timespec="seconds"),
            "versao_dataset": dataset_version(),
            "versao_toolbr": __version__,
            **git_commit(),
            **payload.get("metadados_execucao", {}),
        },
    }
    path = RESULTS_DIR / f"{kind}_{stamp}.json"
    path.write_text(json.dumps(mask_pii(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_results(kind: str | None = None, directory: Path | None = None) -> list[tuple[Path, dict]]:
    out = []
    for path in sorted((directory or RESULTS_DIR).glob("*.json")):
        data = json.loads(path.read_text("utf-8"))
        if kind is None or data.get("tipo") == kind:
            out.append((path, data))
    return out


def pct(x: float | None) -> str:
    return "—" if x is None else f"{x:.0%}"


def with_ci(block: dict[str, Any]) -> str:
    lo, hi = block["ic95"]
    return f"{block['media']:.0%} [{lo:.0%}–{hi:.0%}]"


def runs_table(runs: list[tuple[Path, dict]]) -> str:
    header = (
        "| Modelo | Agente | Defesa | k | Sucesso [IC 95%] | Pass^k [IC 95%] | Ferram. | Args | "
        "Estado | Resposta | US$/tarefa | p50 / p95 (s) | Arquivo |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    )
    lines = [header]
    for path, data in runs:
        m, s = data["metadados"], data["resumo"]
        k = str(s["tentativas_por_tarefa"])
        d = s["diagnostico"]
        usd = s["custo"].get("usd_por_tarefa")
        name = m["modelo"] + (" (teste)" if m["modelo_de_teste"] else "")
        lines.append(
            f"| {name} | {m['agente']} | {m['defesa']} | {k} "
            f"| {with_ci(s['sucesso'])} | {with_ci(s['pass_hat'][k])} | {pct(d['ferramentas'])} "
            f"| {pct(d['argumentos'])} | {pct(d['estado'])} | {pct(d['resposta'])} "
            f"| {'sem preço' if usd is None else f'{usd:.4f}'} "
            f"| {s['latencia_s']['p50']:.1f} / {s['latencia_s']['p95']:.1f} | `{path.name}` |"
        )
    return "\n".join(lines)


def per_task_success(data: dict) -> dict[str, float]:
    by_task: dict[str, list[bool]] = {}
    for t in data["tentativas"]:
        by_task.setdefault(t["tarefa"], []).append(t["nota"]["success"])
    return {tid: sum(v) / len(v) for tid, v in by_task.items()}
