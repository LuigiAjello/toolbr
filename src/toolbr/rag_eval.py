"""Avaliação da busca nas políticas: recall@1, @3 e @5 e MRR, para BM25 e embeddings."""

from __future__ import annotations

from typing import Any

import yaml

from toolbr.metrics import bootstrap_ci, mean, paired_difference
from toolbr.paths import DATA_DIR
from toolbr.retrieval import BM25Retriever, EmbeddingRetriever, all_chunks

DEFAULT_EMBEDDING = "fastembed:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
KS = (1, 3, 5)


def load_questions() -> list[dict[str, str]]:
    raw = yaml.safe_load((DATA_DIR / "busca" / "perguntas.yaml").read_text("utf-8"))
    return raw["perguntas"]


def evaluate(retriever, questions: list[dict[str, str]]) -> dict[str, Any]:
    """Posição do trecho certo em cada pergunta, e as métricas agregadas."""
    n_chunks = len(retriever.chunks)
    rows = []
    for q in questions:
        ranked = [c.id for c, _ in retriever.search(q["pergunta"], k=n_chunks)]
        rank = ranked.index(q["trecho"]) + 1
        rows.append({**q, "posicao": rank, "top3": ranked[:3]})
    rr = [1 / r["posicao"] for r in rows]
    return {
        "metodo": retriever.name,
        "perguntas": len(rows),
        **{f"recall@{k}": mean([float(r["posicao"] <= k) for r in rows]) for k in KS},
        "mrr": mean(rr),
        # 15 perguntas é pouco: o intervalo mostra o quanto o número pode variar
        "mrr_ic95": list(bootstrap_ci(rr, mean)),
        "erros_no_top1": [r for r in rows if r["posicao"] > 1],
        "detalhe": rows,
    }


def compare_methods(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Diferença de MRR (b - a) nas mesmas perguntas, com intervalo pareado."""
    rr_a = {r["pergunta"]: 1 / r["posicao"] for r in a["detalhe"]}
    rr_b = {r["pergunta"]: 1 / r["posicao"] for r in b["detalhe"]}
    return paired_difference(rr_a, rr_b)


def run_rag_eval(embedding_model: str | None = DEFAULT_EMBEDDING) -> list[dict[str, Any]]:
    chunks = all_chunks()
    questions = load_questions()
    reports = [evaluate(BM25Retriever(chunks), questions)]
    if embedding_model:
        reports.append(evaluate(EmbeddingRetriever(chunks, embedding_model), questions))
    return reports


def rag_table(reports: list[dict[str, Any]]) -> str:
    lines = [
        "| Método | recall@1 | recall@3 | recall@5 | MRR [IC 95%] |",
        "|---|---|---|---|---|",
    ]
    for r in reports:
        lo, hi = r["mrr_ic95"]
        lines.append(
            f"| {r['metodo']} | {r['recall@1']:.2f} | {r['recall@3']:.2f} | {r['recall@5']:.2f} "
            f"| {r['mrr']:.2f} [{lo:.2f}–{hi:.2f}] |"
        )
    return "\n".join(lines)
