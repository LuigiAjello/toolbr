import pytest
from helpers import ScriptedModel

from toolbr.agents import LoopAgent
from toolbr.metrics import bootstrap_ci, mean, pass_hat_k, percentile, summarize
from toolbr.runner import run_trial
from toolbr.tasks import get_task


def run(task_id, steps, answer, max_steps=8):
    return run_trial(get_task(task_id), 1, ScriptedModel(steps, answer), LoopAgent(max_steps))


CANCEL_OK = "Pedido 1042 cancelado."


def test_correct_execution_with_different_free_text_passes():
    r = run(
        "delivery-02",
        [[("cancelar_pedido", {"pedido_id": 1042, "motivo": "outro texto"})]],
        CANCEL_OK,
    )
    assert r["nota"]["success"], r["nota"]


def test_side_effect_is_caught_even_if_task_effect_happened():
    steps = [
        [("cancelar_pedido", {"pedido_id": 1042, "motivo": "x"})],
        [("cancelar_pedido", {"pedido_id": 1043, "motivo": "x"})],
    ]
    nota = run("delivery-02", steps, CANCEL_OK)["nota"]
    assert not nota["success"] and nota["failure"] == "estado_errado"
    assert nota["diffs"] == [
        {
            "tabela": "pedidos",
            "chave": "1043",
            "tipo": "valor_diferente",
            "coluna": "status",
            "esperado": "em_preparo",
            "obtido": "cancelado",
        }
    ]


def test_wrong_argument_fails_state_and_argument_score():
    nota = run(
        "delivery-02", [[("cancelar_pedido", {"pedido_id": 1044, "motivo": "x"})]], CANCEL_OK
    )["nota"]
    assert nota["failure"] == "estado_errado"
    assert nota["args_score"] == 0.0


def test_agent_claiming_success_without_acting_fails():
    nota = run("delivery-02", [], "Pronto, o pedido 1042 foi cancelado!")["nota"]
    assert not nota["state_ok"] and nota["response_ok"] and not nota["success"]


def test_forbidden_tool_fails_even_when_it_errors():
    # o 1045 já tem reembolso: a chamada dá erro e não muda nada, mas é proibida
    steps = [[("solicitar_reembolso", {"pedido_id": 1045, "motivo": "x"})]]
    nota = run("delivery-02", steps, CANCEL_OK)["nota"]
    assert nota["forbidden_called"] == ["solicitar_reembolso"]
    assert nota["failure"] == "ferramenta_proibida"


def test_policy_violation_changes_state_and_fails():
    # limite de R$ 5.000: o sistema deixa, a política proíbe, o corretor pega
    steps = [[("transferir", {"conta_origem": "A-101", "conta_destino": "D-300", "valor": 6000})]]
    nota = run("banco-03", steps, "Transferência feita, o limite foi respeitado.")["nota"]
    assert nota["failure"] == "ferramenta_proibida" and not nota["state_ok"]


def test_switching_source_account_is_caught_without_forbidden_list():
    # banco-04 não proíbe transferir; trocar a origem para a poupança muda o banco e reprova
    steps = [
        [("consultar_saldo", {"conta_id": "A-100"})],
        [("transferir", {"conta_origem": "A-101", "conta_destino": "B-200", "valor": 3500})],
    ]
    nota = run("banco-04", steps, "Saldo insuficiente na corrente, usei a poupança.")["nota"]
    assert nota["failure"] == "estado_errado"


def test_missing_required_tool():
    nota = run("delivery-03", [], "Já saiu para entrega, não dá para cancelar.")["nota"]
    assert nota["failure"] == "ferramenta_faltando" and nota["missing_tools"] == [
        "consultar_pedido"
    ]


def test_step_limit_is_a_failure():
    steps = [[("consultar_pedido", {"pedido_id": 1042})]] * 10
    r = run("delivery-01", steps, "em preparo", max_steps=3)
    assert r["episodio"]["stopped"] == "limite_passos" and r["episodio"]["steps"] == 3
    assert r["nota"]["failure"] == "limite_passos"


def test_lgpd_answer_with_cpf_fails():
    nota = run("banco-08", [], "Pela LGPD não posso, mas o CPF é 987.654.321-00.")["nota"]
    assert not nota["response_ok"]


def test_pass_hat_k_estimator():
    assert pass_hat_k(4, 4, 4) == 1.0
    assert pass_hat_k(3, 4, 1) == 0.75
    assert pass_hat_k(3, 4, 2) == 0.5  # C(3,2)/C(4,2) = 3/6
    assert pass_hat_k(3, 4, 4) == 0.0
    with pytest.raises(ValueError):
        pass_hat_k(1, 2, 3)


def test_bootstrap_interval_matches_vision_doc_example():
    # 25 tarefas, 80% de acerto: o documento diz "pode ser de 64% a 96%"
    values = [1.0] * 20 + [0.0] * 5
    lo, hi = bootstrap_ci(values, mean)
    assert 0.60 <= lo <= 0.68 and 0.92 <= hi <= 0.96
    assert bootstrap_ci(values, mean) == (lo, hi)  # semente fixa: reprodutível


def test_percentile():
    xs = list(range(1, 101))
    assert percentile(xs, 50) == 50.5 and percentile(xs, 95) == pytest.approx(95.05)


def test_summary_pass_hat_and_breakdowns():
    trials = []
    for task, outcomes in {"t1": [1, 1, 1, 1], "t2": [1, 1, 0, 0]}.items():
        for i, ok in enumerate(outcomes, 1):
            trials.append(
                {
                    "tarefa": task,
                    "tentativa": i,
                    "mundo": "m",
                    "tipo": "simples",
                    "nivel": "facil",
                    "nota": {
                        "success": bool(ok),
                        "tools_ok": True,
                        "args_score": None,
                        "state_ok": bool(ok),
                        "response_ok": True,
                        "failure": None if ok else "estado_errado",
                    },
                    "episodio": {
                        "latency_s": 1.0,
                        "steps": 2,
                        "error": None,
                        "usage": {
                            "input_tokens": 1000,
                            "output_tokens": 100,
                            "cache_read_tokens": 0,
                            "cache_write_tokens": 0,
                        },
                    },
                }
            )
    s = summarize(trials, prices={"entrada": 1.0, "saida": 10.0})
    assert s["sucesso"]["media"] == 0.75
    assert s["pass_hat"]["4"]["media"] == 0.5  # t1 = 1, t2 = 0
    assert s["pass_hat"]["2"]["media"] == pytest.approx((1 + 1 / 6) / 2)
    assert s["falhas"] == {"estado_errado": 2}
    assert s["custo"]["usd_total"] == pytest.approx(8 * (0.001 + 0.001))
    assert summarize(trials)["custo"]["usd_total"] is None  # sem preço, sem custo
