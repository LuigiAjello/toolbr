import pytest

from toolbr.worlds import WORLDS, make_world
from toolbr.worlds.base import ERROR_503


@pytest.mark.parametrize("name", list(WORLDS))
def test_world_has_4_to_6_tools_with_schema(name):
    world = make_world(name)
    specs = world.tool_specs()
    assert 4 <= len(specs) <= 6, [s.name for s in specs]
    for spec in specs:
        assert spec.description
        params = spec.parameters
        assert params["type"] == "object" and params["additionalProperties"] is False
        assert set(params["required"]) <= set(params["properties"])
        for prop in params["properties"].values():
            assert prop["type"] in {"string", "integer", "number"}
        assert set(spec.critical_args) <= set(params["properties"])
        assert set(spec.free_text_args) <= set(params["properties"])
        if spec.writes:
            assert spec.critical_args, f"{spec.name} altera estado e precisa de argumentos críticos"


@pytest.mark.parametrize("name", list(WORLDS))
def test_world_resets_to_same_state(name):
    a, b = make_world(name), make_world(name)
    write_tool = next(s for s in a.tool_specs() if s.writes)
    a.call(write_tool.name, {})  # mesmo com erro, não pode vazar para outro mundo
    assert a.snapshot() == b.snapshot()


@pytest.mark.parametrize("name", list(WORLDS))
def test_tools_return_structured_errors_never_raise(name):
    world = make_world(name)
    before = world.snapshot()
    assert "erro" in world.call("nao_existe", {})
    for spec in world.tool_specs():
        assert "erro" in world.call(spec.name, {"campo_inventado": 1})
        assert "erro" in world.call(spec.name, None) or not spec.parameters["required"]
    assert world.snapshot() == before


def test_policy_and_untrusted_fields_declared():
    for name, cls in WORLDS.items():
        world = cls()
        assert "##" in world.policy()
        assert world.untrusted_keys, name


def test_delivery_integrity_vs_policy():
    world = make_world("delivery")
    # integridade: entregue não cancela (o sistema bloqueia)
    assert "erro" in world.call("cancelar_pedido", {"pedido_id": 1040, "motivo": "x"})
    # regra de negócio: saiu_para_entrega o sistema deixa, a política proíbe
    assert (
        world.call("cancelar_pedido", {"pedido_id": 1044, "motivo": "x"})["status"] == "cancelado"
    )
    # reembolso duplicado é integridade
    assert "erro" in world.call("solicitar_reembolso", {"pedido_id": 1045, "motivo": "x"})
    ok = world.call("solicitar_reembolso", {"pedido_id": "1040", "motivo": "lanche errado"})
    assert ok["valor"] == 62.90 and ok["reembolso_id"] == 2


def test_bank_transfer_rules():
    world = make_world("banco")
    assert (
        "insuficiente"
        in world.call(
            "transferir", {"conta_origem": "A-100", "conta_destino": "B-200", "valor": 3500}
        )["erro"]
    )
    # acima de R$ 5.000 o sistema deixa: o limite é regra da política
    res = world.call(
        "transferir", {"conta_origem": "A-101", "conta_destino": "D-300", "valor": 6000}
    )
    assert res["status"] == "concluida"
    snap = world.snapshot()
    assert snap["contas"]["A-101"]["saldo"] == 9000.0
    assert snap["contas"]["D-300"]["saldo"] == 6120.5
    assert len(snap["transacoes"]) == 10


def test_bank_enum_validation():
    world = make_world("banco")
    res = world.call("bloquear_cartao", {"cartao_id": "K-1", "motivo": "esqueci"})
    assert "inválido" in res["erro"]


def test_fail_plan_simulates_503_then_recovers():
    world = make_world("banco", fail_plan={"bloquear_cartao": 1})
    args = {"cartao_id": "K-1", "motivo": "roubo"}
    assert world.call("bloquear_cartao", args) == {"erro": ERROR_503}
    assert world.call("bloquear_cartao", args)["status"] == "bloqueado"


def test_atendimento_open_and_escalate():
    world = make_world("atendimento")
    res = world.call(
        "abrir_chamado",
        {
            "cliente_id": "C-203",
            "categoria": "telefone",
            "assunto": "Sem linha",
            "descricao": "Telefone mudo",
            "prioridade": "alta",
        },
    )
    assert res["chamado_id"] == 5006
    assert "erro" in world.call("escalar_chamado", {"chamado_id": 5002, "motivo": "x"})
    assert world.call("escalar_chamado", {"chamado_id": 5001, "motivo": "x"})["nivel"] == 2


def test_buscar_politica_finds_relevant_section():
    world = make_world("banco")
    res = world.call("buscar_politica", {"consulta": "qual o limite de transferência?"})
    assert res["trechos"][0]["id"] == "banco:limite_por_transferencia"


def test_customer_context_lists_accounts():
    world = make_world("banco")
    assert "A-100 (corrente)" in world.customer_context("C-101")
