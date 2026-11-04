from toolbr.types import ModelTurn, ToolCall


class ScriptedModel:
    """Modelo de teste com roteiro fixo: lista de chamadas por passo e a resposta final."""

    name = "roteiro"
    provider = "teste"
    is_test_model = True
    temperature = None
    settings = {}

    def __init__(self, steps, answer):
        self.steps, self.answer = steps, answer

    def for_episode(self, task):
        return self

    def complete(self, system, history, tools):
        i = sum(1 for m in history if m["role"] == "assistant")
        if i < len(self.steps):
            calls = [
                ToolCall(f"c{i}-{j}", name, args) for j, (name, args) in enumerate(self.steps[i])
            ]
            return ModelTurn("", calls, stop_reason="tool_use")
        return ModelTurn(self.answer, [])
