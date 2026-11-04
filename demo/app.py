"""Demo do ToolBR em Gradio: rode uma tarefa e veja as chamadas e o banco antes e depois.

    uv run python demo/app.py

Sem chave de API, só os modelos de teste aparecem, com aviso de que não são um LLM.
"""

from __future__ import annotations

import dataclasses
import html
import json
import os

import gradio as gr

from toolbr.agents import make_agent
from toolbr.cli import load_dotenv
from toolbr.defenses import DEFENSES
from toolbr.models import make_model
from toolbr.models.mock import TEST_MODELS
from toolbr.results import load_results, mask_pii, runs_table
from toolbr.runner import run_trial
from toolbr.tasks import load_attacks, load_tasks

load_dotenv()

TASKS = {t.id: t for t in (*load_tasks(), *load_attacks())}
TEST_NOTE = {
    "oracle": "repete exatamente o gabarito da tarefa",
    "naive": "não chama ferramenta e responde sempre “Pronto, resolvido!”",
    "vulnerable": "faz o gabarito e obedece a instrução escondida, se houver",
    "cautious": "faz o gabarito e ignora a instrução escondida",
}
FAILURE_LABEL = {
    "erro_execucao": "erro de execução",
    "limite_passos": "estourou o limite de passos",
    "ferramenta_proibida": "chamou ferramenta proibida",
    "estado_errado": "o banco terminou errado",
    "ferramenta_faltando": "faltou chamar ferramenta obrigatória",
    "resposta_errada": "a resposta ao cliente está incompleta",
}


def model_choices() -> list[str]:
    choices = list(TEST_MODELS)
    if os.environ.get("ANTHROPIC_API_KEY"):
        choices += ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"]
    return choices


def task_label(task_id: str) -> str:
    t = TASKS[task_id]
    kind = "ataque" if t.injection else t.type.replace("_", " ")
    return f"{t.id} ({kind}): {t.request}"


def fill_request(task_id: str) -> str:
    return TASKS[task_id].request


def _verdict_html(nota: dict, injection: bool, attack_worked: bool | None) -> str:
    ok = nota["success"]
    title = "Passou" if ok else f"Não passou: {FAILURE_LABEL.get(nota['failure'], nota['failure'])}"
    checks = [
        ("Banco no estado certo", nota["state_ok"]),
        ("Ferramentas certas", nota["tools_ok"]),
        ("Resposta ao cliente", nota["response_ok"]),
    ]
    if nota["args_score"] is not None:
        checks.append((f"Argumentos {nota['args_score']:.0%}", nota["args_score"] == 1.0))
    items = "".join(
        f'<li class="{"ok" if good else "bad"}">{"✓" if good else "✗"} {html.escape(label)}</li>'
        for label, good in checks
    )
    attack = ""
    if injection:
        attack = (
            '<p class="attack bad">O ataque escondido funcionou: o banco mudou.</p>'
            if attack_worked
            else '<p class="attack ok">O ataque escondido não funcionou: o banco não mudou.</p>'
        )
    return (
        f'<section class="verdict {"pass" if ok else "fail"}"><h2>{html.escape(title)}</h2>'
        f"<ul>{items}</ul>{attack}</section>"
    )


def _changes_html(changes: list[dict], diffs: list[dict]) -> str:
    if not changes:
        body = "<p>Nada mudou no banco.</p>"
    else:
        rows = []
        for c in changes:
            where = f"{c['tabela']} {c['chave']}"
            if c["tipo"] == "alterada":
                cols = ", ".join(
                    f"{k}: {v['antes']!r} → {v['depois']!r}" for k, v in c["colunas"].items()
                )
                rows.append(
                    f"<li><strong>{html.escape(where)}</strong> alterada: {html.escape(cols)}</li>"
                )
            elif c["tipo"] == "inserida":
                rows.append(f"<li><strong>{html.escape(where)}</strong> criada</li>")
            else:
                rows.append(f"<li><strong>{html.escape(where)}</strong> apagada</li>")
        body = f"<ul>{''.join(rows)}</ul>"
    if diffs:
        expected = "".join(
            f"<li>{html.escape(d['tabela'])} {html.escape(d['chave'])}: "
            f"{html.escape(d['tipo'].replace('_', ' '))}"
            + (
                f" em {html.escape(d['coluna'])} "
                f"(esperado {d['esperado']!r}, ficou {d['obtido']!r})"
                if d["tipo"] == "valor_diferente"
                else ""
            )
            + "</li>"
            for d in diffs
        )
        body += f'<p class="bad">Diferente do gabarito:</p><ul class="bad">{expected}</ul>'
    return body


def _cell(value) -> str:
    return "vazio" if value is None else str(value)


def run_demo(task_id: str, request: str, model_name: str, agent_name: str, defense: str):
    task = TASKS[task_id]
    notice = ""
    if model_name in TEST_MODELS:
        notice = (
            f"**Modelo de teste, não é um LLM:** o `{model_name}` {TEST_NOTE[model_name]}. "
            "Ele existe para provar que o corretor funciona. Para ver um LLM de verdade, "
            "coloque uma chave de API no `.env`."
        )
        if request.strip() != task.request:
            notice += " Você mudou o pedido, mas o modelo de teste ignora o texto."
    elif request.strip() != task.request:
        notice = "Você mudou o pedido: o corretor continua usando o gabarito da tarefa escolhida."
    task = dataclasses.replace(task, request=request.strip() or task.request)
    try:
        model = make_model(model_name)
    except Exception as exc:
        raise gr.Error(f"Não consegui criar o modelo {model_name}: {exc}") from exc

    result = mask_pii(run_trial(task, 1, model, make_agent(agent_name), defense_name=defense))
    nota, episode = result["nota"], result["episodio"]
    said = episode["final_text"] or "(o agente não respondeu)"
    if episode["error"]:
        said += f"\n\nErro: {episode['error']}"
    comparison = (
        '<div class="compare">'
        f"<div><h3>O agente disse</h3><blockquote>{html.escape(said)}</blockquote></div>"
        f"<div><h3>O banco mostra</h3>{_changes_html(result['mudancas'], nota['diffs'])}</div>"
        "</div>"
    )
    calls = [
        [
            i,
            c["name"],
            json.dumps(c["arguments"], ensure_ascii=False),
            "barrada pela defesa" if c["blocked"] else ("erro" if c["is_error"] else "ok"),
            json.dumps(c["result"], ensure_ascii=False)[:300],
        ]
        for i, c in enumerate(episode["calls"], 1)
    ]
    before_after = []
    for c in result["mudancas"]:
        if c["tipo"] == "alterada":
            for col, v in c["colunas"].items():
                before_after.append(
                    [c["tabela"], c["chave"], col, str(v["antes"]), str(v["depois"])]
                )
        elif c["tipo"] == "inserida":
            before_after.append(
                [
                    c["tabela"],
                    c["chave"],
                    "(linha nova)",
                    "",
                    json.dumps(c["depois"], ensure_ascii=False),
                ]
            )
        else:
            before_after.append(
                [
                    c["tabela"],
                    c["chave"],
                    "(linha apagada)",
                    json.dumps(c["antes"], ensure_ascii=False),
                    "",
                ]
            )
    summary = (
        f"{episode['steps']} passos, {len(episode['calls'])} chamadas, "
        f"{episode['latency_s']:.2f} s, {episode['usage']['input_tokens']} tokens de entrada"
    )
    return (
        gr.update(value=notice, visible=bool(notice)),
        _verdict_html(nota, task.injection is not None, result.get("ataque_funcionou")),
        comparison,
        gr.update(value=calls, visible=bool(calls)),
        gr.update(value=before_after, visible=bool(before_after)),
        summary,
    )


def results_markdown(include_test: bool) -> str:
    runs = load_results("tarefas")
    if not include_test:
        runs = [r for r in runs if not r[1]["metadados"]["modelo_de_teste"]]
    if not runs:
        return (
            "Ainda não há resultados de modelos reais. "
            "Rode `python -m toolbr run --modelo <modelo>`."
        )
    return runs_table(runs)


CSS = """
.gradio-container { max-width: 1180px !important; }
#intro h1 { font-size: 2rem; margin-bottom: .25rem; }
#intro p { color: var(--body-text-color-subdued); max-width: 68ch; }
.verdict { border-left: 6px solid; padding: .75rem 1.25rem;
  background: var(--block-background-fill); }
.verdict h2 { margin: 0 0 .5rem; font-size: 1.5rem; }
.verdict ul { list-style: none; padding: 0; margin: 0; display: flex; flex-wrap: wrap;
  gap: 1.5rem; }
.verdict.pass { border-color: var(--ok); }
.verdict.fail { border-color: var(--bad); }
.verdict.pass h2, .ok { color: var(--ok); }
.verdict.fail h2, .bad { color: var(--bad); }
.attack { margin: .5rem 0 0; font-weight: 600; }
.compare { display: grid; grid-template-columns: 1fr 1fr; gap: 1px;
  background: var(--border-color-primary); border: 1px solid var(--border-color-primary); }
.compare > div { background: var(--block-background-fill); padding: .75rem 1.25rem; }
.compare h3 { margin: 0 0 .5rem; font-size: 1rem; font-weight: 600;
  color: var(--body-text-color-subdued); }
.compare blockquote { margin: 0; font-size: 1.05rem; line-height: 1.55; white-space: pre-wrap;
  border: 0; padding: 0; }
:root { --ok: #0E7A67; --bad: #B8322B; }
.dark { --ok: #4FC7AE; --bad: #F07A70; }
#notice { border-left: 4px solid #C98A12; padding: .5rem 1rem;
  background: var(--block-background-fill); }
#notice, #notice p { color: var(--body-text-color) !important; }
@media (max-width: 720px) { .compare { grid-template-columns: 1fr; } }
"""

THEME = gr.themes.Base(
    primary_hue=gr.themes.Color(
        c50="#E7F4F1",
        c100="#C6E6DF",
        c200="#9CD3C7",
        c300="#6CBDAD",
        c400="#3FA592",
        c500="#0E7A67",
        c600="#0B6A59",
        c700="#09584A",
        c800="#07463B",
        c900="#05342C",
        c950="#032720",
    ),
    neutral_hue="slate",
    font=[gr.themes.GoogleFont("Atkinson Hyperlegible"), "system-ui", "sans-serif"],
    font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "ui-monospace", "monospace"],
).set(body_background_fill="#F3F6F5", block_radius="4px", body_text_color="#16263A")


def build() -> gr.Blocks:
    first = "delivery-02"
    with gr.Blocks(title="ToolBR") as demo:
        gr.Markdown(
            "# ToolBR\n"
            "Um agente de atendimento em português recebe o pedido do cliente e usa as "
            "ferramentas de um sistema simulado. O corretor ignora o que o agente diz que "
            "fez e confere o banco de dados no fim.",
            elem_id="intro",
        )
        with gr.Tab("Rodar uma tarefa"):
            with gr.Row():
                with gr.Column(scale=3):
                    task = gr.Dropdown(
                        [(task_label(t), t) for t in TASKS], value=first, label="Tarefa"
                    )
                    request = gr.Textbox(TASKS[first].request, label="Pedido do cliente", lines=2)
                with gr.Column(scale=2):
                    model = gr.Dropdown(
                        model_choices(),
                        value="oracle",
                        label="Modelo",
                        allow_custom_value=True,
                        info="Modelos reais precisam de chave no .env "
                        "(ex.: claude-sonnet-5-5, ollama:qwen3:8b).",
                    )
                    with gr.Row():
                        agent = gr.Radio(["loop", "langgraph"], value="loop", label="Agente")
                        defense = gr.Dropdown(list(DEFENSES), value="nenhuma", label="Defesa")
            run = gr.Button("Rodar tarefa", variant="primary")
            notice = gr.Markdown(visible=False, elem_id="notice")
            verdict = gr.HTML()
            compare = gr.HTML()
            stats = gr.Markdown()
            calls = gr.Dataframe(
                headers=["#", "Ferramenta", "Argumentos", "Status", "Resultado"],
                column_widths=["4%", "17%", "29%", "12%", "38%"],
                label="Chamadas de ferramenta, na ordem",
                wrap=True,
                visible=False,
            )
            changes = gr.Dataframe(
                headers=["Tabela", "Chave", "Coluna", "Antes", "Depois"],
                label="Banco antes e depois",
                wrap=True,
                visible=False,
            )
            task.change(fill_request, task, request)
            inputs = [task, request, model, agent, defense]
            outputs = [notice, verdict, compare, calls, changes, stats]
            run.click(run_demo, inputs, outputs)
            demo.load(run_demo, inputs, outputs)
        with gr.Tab("Resultados salvos"):
            include = gr.Checkbox(False, label="Mostrar também os modelos de teste")
            table = gr.Markdown(results_markdown(False))
            include.change(results_markdown, include, table)
    return demo


if __name__ == "__main__":
    build().launch(theme=THEME, css=CSS)
