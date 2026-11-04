"""Métricas: sucesso, Pass^k, intervalo de confiança por bootstrap, custo e latência.

O bootstrap sorteia TAREFAS com reposição, não tentativas: as 4 tentativas de uma
mesma tarefa são correlacionadas, então sortear tentativas daria um intervalo
estreito demais.
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from math import comb
from typing import Any

BOOTSTRAP_REPS = 1000
SEED = 0


def pass_hat_k(c: int, n: int, k: int) -> float:
    """Estimador do τ-bench: chance de acertar k tentativas sorteadas entre as n feitas."""
    if k > n:
        raise ValueError("k não pode ser maior que n")
    return comb(c, k) / comb(n, k)


def bootstrap_ci(
    values: Sequence[Any],
    stat: Callable[[Sequence[Any]], float],
    reps: int = BOOTSTRAP_REPS,
    seed: int = SEED,
) -> tuple[float, float]:
    """Intervalo de 95% pelo percentil, reamostrando os itens (tarefas)."""
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(values)
    samples = sorted(stat([values[rng.randrange(n)] for _ in range(n)]) for _ in range(reps))
    return samples[int(0.025 * reps)], samples[int(0.975 * reps) - 1]


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def percentile(xs: Sequence[float], q: float) -> float:
    """Percentil com interpolação linear (q entre 0 e 100)."""
    if not xs:
        return float("nan")
    s = sorted(xs)
    pos = (len(s) - 1) * q / 100
    lo, hi = int(pos), min(int(pos) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _with_ci(per_task: list[float]) -> dict[str, float]:
    lo, hi = bootstrap_ci(per_task, mean)
    return {"media": mean(per_task), "ic95": [lo, hi]}


def _rate(trials: list[dict], key: Callable[[dict], Any]) -> float | None:
    values = [key(t) for t in trials]
    values = [v for v in values if v is not None]
    return mean([float(v) for v in values]) if values else None


def summarize(trials: list[dict], prices: dict[str, float] | None = None) -> dict[str, Any]:
    """Resume as tentativas de uma execução. Cada tentativa é o dicionário do executor."""
    by_task: dict[str, list[dict]] = defaultdict(list)
    for t in trials:
        by_task[t["tarefa"]].append(t)
    n = min(len(v) for v in by_task.values())
    successes = {tid: sum(t["nota"]["success"] for t in ts) for tid, ts in by_task.items()}

    summary: dict[str, Any] = {
        "tarefas": len(by_task),
        "tentativas_por_tarefa": n,
        "sucesso": _with_ci([successes[tid] / len(ts) for tid, ts in by_task.items()]),
        "pass_hat": {
            str(k): _with_ci(
                [pass_hat_k(successes[tid], len(ts), k) for tid, ts in by_task.items()]
            )
            for k in range(1, n + 1)
        },
        "diagnostico": {
            "ferramentas": _rate(trials, lambda t: t["nota"]["tools_ok"]),
            "argumentos": _rate(trials, lambda t: t["nota"]["args_score"]),
            "estado": _rate(trials, lambda t: t["nota"]["state_ok"]),
            "resposta": _rate(trials, lambda t: t["nota"]["response_ok"]),
        },
        "falhas": dict(Counter(t["nota"]["failure"] for t in trials if t["nota"]["failure"])),
    }
    for group in ("tipo", "nivel", "mundo"):
        grouped: dict[str, list[dict]] = defaultdict(list)
        for t in trials:
            grouped[t[group]].append(t)
        summary[f"por_{group}"] = {
            name: mean([float(t["nota"]["success"]) for t in ts])
            for name, ts in sorted(grouped.items())
        }

    latencies = [t["episodio"]["latency_s"] for t in trials]
    usage = [t["episodio"]["usage"] for t in trials]
    tokens_in = sum(u["input_tokens"] for u in usage)
    tokens_out = sum(u["output_tokens"] for u in usage)
    summary["custo"] = {
        "tokens_entrada": tokens_in,
        "tokens_saida": tokens_out,
        "tokens_cache_leitura": sum(u["cache_read_tokens"] for u in usage),
        "tokens_cache_escrita": sum(u["cache_write_tokens"] for u in usage),
        "usd_total": cost_usd(usage, prices),
    }
    if summary["custo"]["usd_total"] is not None:
        summary["custo"]["usd_por_tarefa"] = summary["custo"]["usd_total"] / len(trials)
    summary["latencia_s"] = {"p50": percentile(latencies, 50), "p95": percentile(latencies, 95)}
    summary["passos_medios"] = mean([t["episodio"]["steps"] for t in trials])
    summary["erros_execucao"] = sum(1 for t in trials if t["episodio"]["error"])
    return summary


def cost_usd(usage: list[dict[str, int]], prices: dict[str, float] | None) -> float | None:
    """Custo em US$ a partir de data/precos.yaml. Sem preço preenchido, não há custo."""
    if not prices or prices.get("entrada") is None or prices.get("saida") is None:
        return None
    per_m = 1_000_000
    total = 0.0
    for u in usage:
        total += u["input_tokens"] * prices["entrada"] / per_m
        total += u["output_tokens"] * prices["saida"] / per_m
        total += u["cache_read_tokens"] * prices.get("cache_leitura", prices["entrada"]) / per_m
        total += u["cache_write_tokens"] * prices.get("cache_escrita", prices["entrada"]) / per_m
    return total


def paired_difference(a: dict[str, float], b: dict[str, float]) -> dict[str, Any]:
    """Diferença de sucesso (b - a) nas mesmas tarefas, com intervalo pareado por bootstrap."""
    common = sorted(set(a) & set(b))
    diffs = [b[t] - a[t] for t in common]
    lo, hi = bootstrap_ci(diffs, mean)
    return {
        "tarefas": len(common),
        "diferenca": mean(diffs),
        "ic95": [lo, hi],
        "significativa": not (lo <= 0 <= hi),
    }
