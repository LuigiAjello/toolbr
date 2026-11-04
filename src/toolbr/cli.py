"""Linha de comando: python -m toolbr run | table | gate | rag-eval | security | mcp."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from toolbr.paths import ROOT


def load_dotenv() -> None:
    """Lê o .env da raiz sem depender de biblioteca. Não sobrescreve variáveis já definidas."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            if value.strip():
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _select_tasks(args) -> list:
    from toolbr.tasks import load_tasks

    tasks = list(load_tasks())
    if args.mundos != "todos":
        worlds = set(args.mundos.split(","))
        tasks = [t for t in tasks if t.world in worlds]
    if args.tarefas:
        ids = set(args.tarefas.split(","))
        tasks = [t for t in tasks if t.id in ids]
    if not tasks:
        sys.exit("nenhuma tarefa selecionada")
    return tasks


def estimate(tasks: list, k: int, max_steps: int, model_name: str) -> dict[str, Any]:
    """Estimativa de chamadas e tokens antes de gastar. Tokens: ~3,5 caracteres por token."""
    from toolbr.agents.prompt import build_system_prompt
    from toolbr.defenses import Defense
    from toolbr.results import load_prices
    from toolbr.worlds import make_world

    calls = 0
    tokens_in = 0
    for task in tasks:
        world = make_world(task.world)
        prompt = build_system_prompt(world, task, Defense())
        tools = json.dumps([s.schema() for s in world.tool_specs()], ensure_ascii=False)
        per_call = (len(prompt) + len(tools) + len(task.request)) / 3.5
        steps = len(task.gold_calls) + 1
        calls += steps * k
        # o histórico cresce a cada passo: ~300 tokens por chamada anterior
        tokens_in += k * sum(per_call + 300 * i for i in range(steps))
    estimate = {
        "episodios": len(tasks) * k,
        "chamadas_estimadas": calls,
        "chamadas_maximas": len(tasks) * k * max_steps,
        "tokens_entrada_estimados": int(tokens_in),
        "tokens_saida_estimados": calls * 150,
    }
    prices = load_prices(model_name)
    if prices and prices.get("entrada") is not None:
        estimate["usd_estimado_sem_cache"] = round(
            tokens_in * prices["entrada"] / 1e6 + calls * 150 * prices["saida"] / 1e6, 4
        )
    return estimate


def _confirm(model, info: dict[str, Any], yes: bool) -> None:
    print("Estimativa:", json.dumps(info, ensure_ascii=False), file=sys.stderr)
    if model.is_test_model or yes:
        return
    answer = input(f"Rodar {model.name} com até {info['chamadas_maximas']} chamadas? [s/N] ")
    if answer.strip().lower() not in ("s", "sim", "y"):
        sys.exit("cancelado")


def _progress(result: dict[str, Any]) -> None:
    print("." if result["nota"]["success"] else "x", end="", file=sys.stderr, flush=True)


def print_summary(summary: dict[str, Any], path) -> None:
    from toolbr.results import pct, with_ci

    k = str(summary["tentativas_por_tarefa"])
    d = summary["diagnostico"]
    print(f"\nSucesso: {with_ci(summary['sucesso'])}   Pass^{k}: {with_ci(summary['pass_hat'][k])}")
    print(
        f"Diagnóstico: ferramentas {pct(d['ferramentas'])} | argumentos {pct(d['argumentos'])} | "
        f"estado {pct(d['estado'])} | resposta {pct(d['resposta'])}"
    )
    print(f"Falhas: {summary['falhas'] or 'nenhuma'}")
    c = summary["custo"]
    usd = c["usd_total"]
    print(
        f"Tokens: {c['tokens_entrada']} entrada, {c['tokens_saida']} saída | "
        f"US$: {'sem preço em data/precos.yaml' if usd is None else f'{usd:.4f}'}"
    )
    lat = summary["latencia_s"]
    print(
        f"Latência p50 {lat['p50']:.2f} s, p95 {lat['p95']:.2f} s | "
        f"passos médios {summary['passos_medios']:.1f}"
    )
    print(f"Resultado: {path}")


def cmd_run(args) -> None:
    from toolbr.agents import make_agent
    from toolbr.metrics import summarize
    from toolbr.models import make_model
    from toolbr.results import build_metadata, load_prices, save_result
    from toolbr.runner import run_suite

    tasks = _select_tasks(args)
    model = make_model(args.modelo, temperature=args.temperatura, effort=args.effort)
    retrieval = _retrieval_method(args.busca)
    info = estimate(tasks, args.k, args.max_passos, model.name)
    if args.estimar:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return
    _confirm(model, info, args.sim)
    trials = run_suite(
        tasks,
        model,
        make_agent(args.agente, args.max_passos),
        k=args.k,
        defense_name=args.defesa,
        policy_mode=args.politica,
        workers=args.paralelo,
        retrieval=retrieval,
        on_done=_progress,
    )
    summary = summarize(trials, load_prices(model.name))
    metadata = build_metadata(
        model,
        agente=args.agente,
        defesa=args.defesa,
        k=args.k,
        politica=args.politica,
        busca=retrieval,
        max_passos=args.max_passos,
        tarefas=[t.id for t in tasks],
    )
    path = save_result(metadata, summary, trials, "tarefas")
    print_summary(summary, path)
    if args.mlflow:
        from toolbr.tracking import log_run

        log_run(metadata, summary, path)


def _retrieval_method(choice: str) -> str:
    from toolbr.rag_eval import DEFAULT_EMBEDDING

    return DEFAULT_EMBEDDING if choice == "embeddings" else choice


def cmd_rag_eval(args) -> None:
    from toolbr.rag_eval import compare_methods, rag_table, run_rag_eval
    from toolbr.results import save_json

    model = None if args.so_bm25 else _retrieval_method(args.embedding)
    reports = run_rag_eval(model)
    print(rag_table(reports))
    for r in reports:
        print(f"\n{r['metodo']}: {len(r['erros_no_top1'])} perguntas fora do 1º lugar")
        for e in r["erros_no_top1"]:
            print(
                f"  [{e['posicao']}º] {e['pergunta']}  (certo: {e['trecho']}; 1º: {e['top3'][0]})"
            )
    payload = {"tipo": "busca", "relatorios": reports}
    if len(reports) == 2:
        diff = compare_methods(reports[0], reports[1])
        payload["diferenca_mrr"] = diff
        lo, hi = diff["ic95"]
        verdict = "diferença real" if diff["significativa"] else "sem diferença comprovada"
        print(
            f"\nMRR embeddings menos BM25: {diff['diferenca']:+.2f} "
            f"[IC 95%: {lo:+.2f} a {hi:+.2f}] → {verdict}"
        )
    print(f"Resultado: {save_json(payload, 'busca')}")


def cmd_table(args) -> None:
    from toolbr.metrics import paired_difference
    from toolbr.paths import RESULTS_DIR
    from toolbr.results import load_results, per_task_success, runs_table

    if args.comparar:
        a, b = (json.loads((RESULTS_DIR / name).read_text("utf-8")) for name in args.comparar)
        diff = paired_difference(per_task_success(a), per_task_success(b))
        lo, hi = diff["ic95"]
        verdict = "diferença real" if diff["significativa"] else "sem diferença comprovada"
        print(
            f"{b['metadados']['modelo']} ({b['metadados']['agente']}) menos "
            f"{a['metadados']['modelo']} ({a['metadados']['agente']}): "
            f"{diff['diferenca']:+.0%} [IC 95%: {lo:+.0%} a {hi:+.0%}] "
            f"em {diff['tarefas']} tarefas → {verdict}"
        )
        return
    runs = load_results("tarefas")
    if not args.todos:
        runs = [r for r in runs if not r[1]["metadados"]["modelo_de_teste"]]
    if not runs:
        print(
            "Nenhum resultado de modelo real em results/. Use --todos para ver os modelos de teste."
        )
        return
    print(runs_table(runs))


def cmd_gate(args) -> None:
    from toolbr.gate import run_gate

    checks = run_gate()
    for c in checks:
        print(f"{'OK   ' if c.ok else 'FALHA'} {c.name}: {c.detail}")
    if not all(c.ok for c in checks):
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="toolbr", description="Benchmark de tool calling em português")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="roda as 25 tarefas com um modelo")
    run.add_argument(
        "--modelo", required=True, help="oracle, naive, claude-..., gpt-..., ollama:<id>"
    )
    run.add_argument("--agente", default="loop", choices=["loop", "langgraph"])
    run.add_argument("--k", type=int, default=4, help="tentativas por tarefa")
    run.add_argument("--mundos", default="todos", help="delivery,banco,atendimento")
    run.add_argument("--tarefas", default="", help="ids separados por vírgula")
    run.add_argument("--defesa", default="nenhuma")
    run.add_argument("--politica", default="contexto", choices=["contexto", "busca"])
    run.add_argument("--busca", default="bm25", help="bm25, embeddings ou fastembed:<modelo>")
    run.add_argument("--temperatura", type=float, default=None)
    run.add_argument("--effort", default=None, help="low, medium, high (quando o modelo aceita)")
    run.add_argument("--max-passos", type=int, default=8)
    run.add_argument("--paralelo", type=int, default=4, help="episódios ao mesmo tempo")
    run.add_argument("--estimar", action="store_true", help="só mostra a estimativa de chamadas")
    run.add_argument("--sim", action="store_true", help="não pede confirmação antes de gastar")
    run.add_argument(
        "--mlflow", action="store_true", help="registra no MLflow (sqlite:///mlflow.db)"
    )
    run.set_defaults(func=cmd_run)

    table = sub.add_parser("table", help="tabela com os resultados salvos")
    table.add_argument("--todos", action="store_true", help="inclui os modelos de teste")
    table.add_argument(
        "--comparar", nargs=2, metavar=("A.json", "B.json"), help="diferença pareada"
    )
    table.set_defaults(func=cmd_table)

    rag = sub.add_parser("rag-eval", help="avalia a busca nas políticas (BM25 e embeddings)")
    rag.add_argument(
        "--embedding", default="embeddings", help="fastembed:<modelo> ou openai:<modelo>"
    )
    rag.add_argument("--so-bm25", action="store_true", help="não roda embeddings")
    rag.set_defaults(func=cmd_rag_eval)

    gate = sub.add_parser("gate", help="portão de qualidade com os modelos de teste")
    gate.set_defaults(func=cmd_gate)
    return p


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
