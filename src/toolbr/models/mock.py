"""Modelos de teste, sem API. Eles validam o corretor, não medem nada.

- oracle: faz exatamente as chamadas do gabarito. Precisa dar 100%.
- naive: não chama ferramenta e diz "resolvido". Precisa dar perto de 0%.
- vulnerable: faz o gabarito, mas obedece a instrução escondida quando ela aparece.
- cautious: faz o gabarito e ignora a instrução escondida.
"""

from __future__ import annotations

from typing import Any

from toolbr.tasks import Task
from toolbr.types import ModelTurn, ToolCall
from toolbr.worlds.base import ToolSpec

NAIVE_ANSWER = "Pronto, resolvido!"


class _TestModel:
    provider = "teste"
    is_test_model = True
    temperature = None
    settings: dict[str, Any] = {}

    def __init__(self, task: Task | None = None):
        self.task = task

    def for_episode(self, task: Task) -> _TestModel:
        return type(self)(task)

    def _assistant_turns(self, history: list[dict]) -> int:
        return sum(1 for m in history if m["role"] == "assistant")


class NaiveModel(_TestModel):
    name = "naive"

    def complete(self, system: str, history: list[dict], tools: list[ToolSpec]) -> ModelTurn:
        return ModelTurn(NAIVE_ANSWER, [])


class OracleModel(_TestModel):
    """Repete o gabarito: uma chamada por passo, depois a resposta de referência."""

    name = "oracle"

    def _script(self) -> list[tuple[str, dict]]:
        return [(c.tool, c.args) for c in self.task.gold_calls]

    def complete(self, system: str, history: list[dict], tools: list[ToolSpec]) -> ModelTurn:
        script = self._script_for(history)
        step = self._assistant_turns(history)
        if step < len(script):
            name, args = script[step]
            return ModelTurn(
                "", [ToolCall(f"{self.name}-{step}", name, dict(args))], stop_reason="tool_use"
            )
        return ModelTurn(self.task.reference_answer, [])

    def _script_for(self, history: list[dict]) -> list[tuple[str, dict]]:
        return self._script()


class CautiousModel(OracleModel):
    """Igual ao oracle: lê a instrução escondida e não obedece."""

    name = "cautious"


class VulnerableModel(OracleModel):
    """Assim que lê a instrução escondida num resultado de ferramenta, executa a ação dela."""

    name = "vulnerable"

    def _script_for(self, history: list[dict]) -> list[tuple[str, dict]]:
        script = self._script()
        injection = self.task.injection
        if injection is None:
            return script
        # posição (em passos do modelo) do primeiro resultado que trouxe o ataque
        step = 0
        for message in history:
            if message["role"] == "assistant":
                step += 1
            elif message["role"] == "tool" and any(
                injection.text[:40] in r["content"] for r in message["results"]
            ):
                attack = (injection.malicious_call.tool, injection.malicious_call.args)
                return script[:step] + [attack] + script[step:]
        return script


TEST_MODELS = {m.name: m for m in (OracleModel, NaiveModel, VulnerableModel, CautiousModel)}
