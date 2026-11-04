"""Conversão de mensagens dos adaptadores, sem chamar a rede."""

from types import SimpleNamespace as NS

import pytest

from toolbr.models import make_model
from toolbr.models.anthropic_model import parse_anthropic_response, to_anthropic_messages
from toolbr.models.openai_model import parse_openai_response, to_openai_messages
from toolbr.results import mask_pii
from toolbr.types import ToolCall

HISTORY = [
    {"role": "user", "content": "Cancela o 1042"},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            ToolCall("t1", "consultar_pedido", {"pedido_id": 1042}),
            ToolCall("t2", "listar_pedidos", {"cliente_id": "C-001"}),
        ],
        "raw": None,
    },
    {
        "role": "tool",
        "results": [
            {
                "id": "t1",
                "name": "consultar_pedido",
                "content": '{"pedido": {}}',
                "is_error": False,
            },
            {"id": "t2", "name": "listar_pedidos", "content": '{"erro": "x"}', "is_error": True},
        ],
    },
]


def test_anthropic_tool_results_go_in_one_user_message():
    msgs = to_anthropic_messages(HISTORY)
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert [b["type"] for b in msgs[1]["content"]] == ["tool_use", "tool_use"]
    results = msgs[2]["content"]
    assert [r["tool_use_id"] for r in results] == ["t1", "t2"]
    assert results[1]["is_error"] is True


def test_anthropic_raw_content_is_sent_back_unchanged():
    raw = [NS(type="thinking", thinking=""), NS(type="tool_use", id="t1", name="x", input={})]
    history = [{"role": "assistant", "content": "", "tool_calls": [], "raw": raw}]
    assert to_anthropic_messages(history)[0]["content"] is raw


def test_parse_anthropic_response():
    response = NS(
        content=[
            NS(type="thinking", thinking=""),
            NS(type="text", text="Vou consultar."),
            NS(type="tool_use", id="t9", name="consultar_pedido", input={"pedido_id": 1042}),
        ],
        usage=NS(
            input_tokens=100,
            output_tokens=20,
            cache_read_input_tokens=900,
            cache_creation_input_tokens=0,
        ),
        stop_reason="tool_use",
    )
    turn = parse_anthropic_response(response)
    assert turn.text == "Vou consultar." and turn.stop_reason == "tool_use"
    assert turn.tool_calls[0].arguments == {"pedido_id": 1042}
    assert turn.usage.cache_read_tokens == 900 and turn.raw is response.content


def test_openai_messages_have_one_tool_message_per_result():
    msgs = to_openai_messages(HISTORY)
    assert [m["role"] for m in msgs] == ["user", "assistant", "tool", "tool"]
    assert msgs[1]["tool_calls"][0]["function"]["arguments"] == '{"pedido_id": 1042}'
    assert msgs[3]["tool_call_id"] == "t2"


def test_parse_openai_response_separates_cached_tokens_and_bad_json():
    tc = NS(id="c1", function=NS(name="transferir", arguments="{quebrado"))
    response = NS(
        choices=[
            NS(finish_reason="tool_calls", message=NS(content=None, refusal=None, tool_calls=[tc]))
        ],
        usage=NS(
            prompt_tokens=1000, completion_tokens=50, prompt_tokens_details=NS(cached_tokens=800)
        ),
    )
    turn = parse_openai_response(response)
    assert turn.usage.input_tokens == 200 and turn.usage.cache_read_tokens == 800
    assert turn.tool_calls[0].arguments == {"_argumentos_invalidos": "{quebrado"}


def test_model_registry():
    assert make_model("oracle").is_test_model
    with pytest.raises(ValueError):
        make_model("modelo-desconhecido")


def test_anthropic_rejects_temperature_with_clear_message():
    pytest.importorskip("anthropic")
    with pytest.raises(ValueError, match="effort"):
        make_model("claude-sonnet-5-5", temperature=0.0)


def test_cpf_is_masked_in_logs():
    data = {"a": ["CPF 987.654.321-00", "98765432100"], "b": 3}
    assert mask_pii(data) == {"a": ["CPF ***.***.***-**", "***.***.***-**"], "b": 3}
