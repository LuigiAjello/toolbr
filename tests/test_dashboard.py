import json
import re

from toolbr.dashboard import collect, render


def test_test_models_never_appear_as_real_models():
    data = collect()
    assert all(
        r["modelo"] not in ("oracle", "naive", "vulnerable", "cautious") for r in data["reais"]
    )
    assert {r["modelo"] for r in data["teste"]} >= {"oracle", "naive"}
    assert len(data["tarefas"]) == 25


def test_rendered_page_is_self_contained_and_data_cannot_break_out():
    data = collect()
    data["teste"][0]["rotulo"] = "</script><script>alert(1)</script>"
    html = render(data)
    payload = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    assert json.loads(payload.group(1))["teste"][0]["rotulo"].startswith("</script>")
    assert "<script>alert(1)" not in html
    assert not re.search(r'(src|href)="https?://', html), "o dashboard não carrega nada externo"
