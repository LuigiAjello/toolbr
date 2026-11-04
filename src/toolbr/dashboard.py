"""Dashboard estático dos resultados: um HTML só, sem servidor e sem nada externo.

    python -m toolbr dashboard   ->   docs/index.html (pronto para o GitHub Pages)

Os dados vêm de results/*.json. Modelos de teste nunca entram na tabela de modelos
reais: aparecem só na seção que valida o corretor.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from toolbr.paths import ROOT
from toolbr.results import git_commit, load_results, per_task_success
from toolbr.tasks import dataset_version, load_attacks, load_tasks

OUTPUT = ROOT / "docs" / "index.html"
FAILURES = [
    ("estado_errado", "banco terminou errado"),
    ("ferramenta_proibida", "ferramenta proibida"),
    ("ferramenta_faltando", "faltou ferramenta"),
    ("resposta_errada", "resposta incompleta"),
    ("limite_passos", "limite de passos"),
    ("erro_execucao", "erro de execução"),
]


def _latest(runs: list[tuple[Path, dict]], key) -> list[tuple[Path, dict]]:
    """A execução mais recente de cada configuração (os nomes de arquivo têm data e hora)."""
    by_key: dict[Any, tuple[Path, dict]] = {}
    for path, data in sorted(runs, key=lambda r: r[0].name):
        by_key[key(data)] = (path, data)
    return list(by_key.values())


def _run_row(path: Path, data: dict) -> dict[str, Any]:
    m, s = data["metadados"], data["resumo"]
    trials = len(data["tentativas"]) or 1
    return {
        "arquivo": path.name,
        "rotulo": f"{m['modelo']}, {m['agente']}"
        + ("" if m["defesa"] == "nenhuma" else f", {m['defesa']}"),
        "modelo": m["modelo"],
        "agente": m["agente"],
        "defesa": m["defesa"],
        "k": s["tentativas_por_tarefa"],
        "sucesso": s["sucesso"],
        "pass_hat": s["pass_hat"],
        "diagnostico": s["diagnostico"],
        "falhas": {k: s["falhas"].get(k, 0) / trials for k, _ in FAILURES},
        "usd_por_tarefa": s["custo"].get("usd_por_tarefa"),
        "latencia": s["latencia_s"],
        "tokens_entrada": s["custo"]["tokens_entrada"],
        "por_tarefa": per_task_success(data),
        "commit": (m.get("commit") or "")[:7],
    }


def collect() -> dict[str, Any]:
    task_runs = _latest(
        load_results("tarefas"),
        lambda d: (d["metadados"]["modelo"], d["metadados"]["agente"], d["metadados"]["defesa"]),
    )
    rows = [_run_row(p, d) for p, d in task_runs]
    security = []
    for path, data in _latest(load_results(), lambda d: d.get("metadados", {}).get("modelo")):
        if not path.name.startswith("seguranca_"):
            continue
        m = data["metadados"]
        security.append(
            {
                "arquivo": path.name,
                "modelo": m["modelo"],
                "teste": m["modelo_de_teste"],
                "defesas": [
                    {
                        "defesa": name,
                        "asr": row["asr"],
                        "tentou": row["tentou_acao_maliciosa"],
                        "utilidade_sob_ataque": row["utilidade_sob_ataque"],
                        "utilidade_tarefas": row.get("utilidade_tarefas"),
                    }
                    for name, row in data["por_defesa"].items()
                ],
            }
        )
    search = None
    busca = load_results("busca")
    if busca:
        path, data = sorted(busca, key=lambda r: r[0].name)[-1]
        search = {
            "arquivo": path.name,
            "metodos": [
                {
                    "metodo": "BM25"
                    if r["metodo"] == "bm25"
                    else r["metodo"].split(" (")[0].capitalize(),
                    "detalhe": r["metodo"],
                    "recall@1": r["recall@1"],
                    "recall@3": r["recall@3"],
                    "recall@5": r["recall@5"],
                    "mrr": r["mrr"],
                    "mrr_ic95": r["mrr_ic95"],
                }
                for r in data["relatorios"]
            ],
            "diferenca": data.get("diferenca_mrr"),
        }
    return {
        "gerado_em": datetime.now().astimezone().strftime("%d/%m/%Y %H:%M"),
        "versao_dataset": dataset_version(),
        "commit": (git_commit().get("commit") or "")[:7],
        "n_tarefas": len(load_tasks()),
        "n_ataques": len(load_attacks()),
        "tarefas": [{"id": t.id, "tipo": t.type, "nivel": t.level} for t in load_tasks()],
        "falhas": [{"chave": k, "rotulo": label} for k, label in FAILURES],
        "reais": [
            r
            for r, (_, d) in zip(rows, task_runs, strict=True)
            if not d["metadados"]["modelo_de_teste"]
        ],
        "teste": [
            r
            for r, (_, d) in zip(rows, task_runs, strict=True)
            if d["metadados"]["modelo_de_teste"]
        ],
        "seguranca": security,
        "busca": search,
    }


def render(data: dict[str, Any]) -> str:
    template = (Path(__file__).parent / "dashboard_template.html").read_text("utf-8")
    # todo "<" vira \u003c: um nome com "</script>" não fecha nem abre tag no meio dos dados
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    return template.replace("__DATA__", payload)


def build_dashboard(output: Path = OUTPUT) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(collect()), encoding="utf-8")
    return output
