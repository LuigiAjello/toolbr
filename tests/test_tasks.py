from collections import Counter

import pytest

from toolbr.matching import check_response, contains_phrase, money_variants
from toolbr.tasks import LEVELS, TASK_TYPES, load_tasks
from toolbr.worlds import make_world

NAIVE_ANSWER = "Pronto, resolvido!"
MAX_STEPS = 8

TASKS = load_tasks()


def test_25_tasks_with_unique_ids_and_all_types():
    assert len(TASKS) == 25
    assert len({t.id for t in TASKS}) == 25
    assert set(TASK_TYPES) == {t.type for t in TASKS}
    assert {t.level for t in TASKS} == set(LEVELS)
    assert Counter(t.world for t in TASKS) == {"delivery": 9, "banco": 9, "atendimento": 7}


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_task_is_consistent_with_its_world(task):
    world = make_world(task.world)
    tools = {s.name for s in world.tool_specs()}
    world.customer_context(task.customer)  # cliente existe
    gold_tools = {c.tool for c in task.gold_calls}
    assert gold_tools <= tools
    assert set(task.required_tools) <= gold_tools, "o oracle precisa chamar as obrigatórias"
    assert set(task.forbidden_tools) <= tools
    assert not set(task.forbidden_tools) & gold_tools, "o gabarito não pode usar proibida"
    assert set(task.fail_plan) <= tools
    assert len(task.gold_calls) + 1 <= MAX_STEPS, "o oracle precisa caber no limite de passos"
    for effect in task.effects:
        assert effect["tabela"] in world.primary_keys
        assert ("muda" in effect) != ("insere" in effect)


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_reference_answer_passes_and_naive_fails_when_state_does_not_change(task):
    assert check_response(task.reference_answer, task.must_contain, task.must_not_contain)
    if not task.effects:
        assert task.must_contain, "sem efeito esperado, só a resposta reprova o naive"
        assert not check_response(NAIVE_ANSWER, task.must_contain, task.must_not_contain)


def test_whole_word_matching_never_substring():
    assert not contains_phrase("Pronto, resolvido!", "id")
    assert contains_phrase("Qual é o ID do pedido?", "id")
    assert contains_phrase("Não É POSSÍVEL", "não é possível")
    assert not contains_phrase("chamado 50011", "5001")
    assert contains_phrase("o chamado 5001.", "5001")


def test_money_variants():
    assert {"62,90", "62.90", "62,9"} <= set(money_variants(62.90))
    assert {"5.000,00", "5.000", "5000"} <= set(money_variants(5000))
    assert check_response("Saldo: R$ 3.200,00", [{"valor": 3200}])
    assert not check_response("Saldo: R$ 32,00", [{"valor": 3200}])
