# Como o ToolBR funciona por dentro

Este guia segue uma tarefa do começo ao fim e mostra onde cada coisa mora no código. Para o *porquê* de cada escolha, veja as [decisões de projeto](ENTREVISTA.md).

## Uma tentativa, passo a passo

Tome a tarefa `delivery-02`: a cliente Ana (C-001) pede "Quero cancelar o pedido 1042, está demorando demais."

```mermaid
sequenceDiagram
    participant R as Executor
    participant W as Mundo (SQLite)
    participant A as Agente
    participant M as Modelo
    participant G as Corretor
    R->>W: cria o banco do zero (+ falhas 503, + ataque, se houver)
    R->>R: guarda o estado inicial
    R->>A: prompt de sistema + pedido da cliente
    loop até 8 passos
        A->>M: histórico + ferramentas
        M-->>A: texto e/ou chamadas de ferramenta
        A->>W: cancelar_pedido(pedido_id=1042) (passando pela defesa)
        W-->>A: {"status": "cancelado", ...} ou {"erro": ...}
    end
    A-->>R: resposta final + chamadas + tokens + tempo
    R->>G: estado inicial, estado final, episódio
    G-->>R: nota (sucesso, diagnóstico, motivo da falha)
```

1. **O executor** (`runner.py`, `run_trial`) cria o mundo com `make_world`: um SQLite em memória carregado de `data/mundos/delivery/estado_inicial.sql`. Se a tarefa tem `falhas`, a ferramenta indicada devolve 503 nas primeiras chamadas. Se é um caso de ataque, o texto malicioso é escrito num campo de terceiros antes de tudo.
2. **O estado inicial** é fotografado com `world.snapshot()`: todas as tabelas, linha por linha.
3. **O prompt de sistema** (`agents/prompt.py`) diz quem é a empresa, quem é a cliente autenticada, a data e hora fixas, as regras gerais e a política inteira (ou só manda buscar, com `--politica busca`).
4. **O agente** (`agents/loop.py` ou `agents/langgraph_agent.py`) chama o modelo, executa as ferramentas pedidas e devolve os resultados, até o modelo responder sem chamar ferramenta ou até 8 passos (passo = uma chamada ao modelo).
5. **Toda chamada de ferramenta** passa pelo runtime (`agents/runtime.py`), o mesmo nos dois agentes. Ele consulta a defesa (que pode barrar), executa no mundo, registra a chamada e devolve o texto para o modelo.
6. **O mundo** (`worlds/delivery.py`) valida os argumentos contra o schema e executa. Erros viram `{"erro": "..."}`, nunca exceção.
7. **O estado final** é fotografado de novo.
8. **O corretor** (`grader.py`) monta o estado esperado (o inicial mais os efeitos da tarefa: aqui, `pedidos[1042].status = cancelado`) e compara com o final, **tabela por tabela, linha por linha**, ignorando só as colunas de texto livre escritas pelo modelo (como o motivo do cancelamento). Depois confere as ferramentas obrigatórias e as proibidas, e a resposta.
9. **As métricas** (`metrics.py`) juntam as tentativas: sucesso, Pass^1 a Pass^4, intervalo por bootstrap, diagnóstico, custo e latência. O resultado vai para `results/*.json` (`results.py`), com o commit do git e o CPF mascarado.

## Mapa do código

| Arquivo | Papel |
|---|---|
| `worlds/base.py` | Base dos mundos: SQLite, registro de ferramentas, validação de argumentos, falha 503, snapshot |
| `worlds/delivery.py`, `banco.py`, `atendimento.py` | As ferramentas de cada mundo (só regras de integridade) |
| `tasks.py` | Lê `data/tarefas.yaml` e `data/ataques.yaml` |
| `matching.py` | Casamento da resposta por palavra inteira, com valores em reais |
| `agents/loop.py` | Agente principal: loop próprio direto na API |
| `agents/langgraph_agent.py` | O mesmo agente como grafo do LangGraph, com o mesmo modelo embrulhado |
| `agents/runtime.py` | Execução de ferramentas compartilhada (defesa, trava, registro) |
| `agents/prompt.py` | Prompt de sistema |
| `models/anthropic_model.py`, `openai_model.py` | Adaptadores: histórico neutro para o formato de cada provedor |
| `models/mock.py` | Modelos de teste: oracle, naive, vulnerable, cautious |
| `grader.py` | Estado esperado, comparação, acerto de argumentos, motivo da falha |
| `metrics.py` | Pass^k, bootstrap, percentis, custo, diferença pareada |
| `defenses.py` | Delimitar e portão de proveniência |
| `security.py` | Roda os ataques com cada defesa |
| `retrieval.py`, `rag_eval.py` | Trechos das políticas, BM25, embeddings, recall@k e MRR |
| `gate.py` | Portão de qualidade do CI |
| `mcp_server.py` | Ferramentas de um mundo via MCP |
| `tracking.py` | Registro no MLflow |
| `dashboard.py` | Página estática de resultados |
| `cli.py` | `python -m toolbr ...` |

## O histórico neutro

O agente não conhece o provedor. Ele guarda a conversa num formato próprio (`types.py`):

```python
{"role": "user", "content": "Quero cancelar o pedido 1042..."}
{"role": "assistant", "content": "", "tool_calls": [ToolCall(...)], "raw": <resposta original>}
{"role": "tool", "results": [{"id": ..., "content": "{...}", "is_error": False}]}
```

Cada adaptador converte isso para a API do provedor. O campo `raw` guarda a resposta original (com blocos de raciocínio, no caso do Claude) para ser reenviada sem alteração.

## Por que três camadas de prova

| Prova | Onde | O que pega |
|---|---|---|
| Formato | `tests/test_tasks.py` | Ferramenta inexistente, gabarito longo demais, tarefa sem checagem de resposta |
| Oracle = 100% | `gate.py` | Efeito esperado que não bate com o que o gabarito faz de verdade |
| Naive ≤ 10% | `gate.py` | Corretor frouxo, que aprova quem não fez nada |

Na segurança, o `vulnerable` precisa ter ASR de 100% sem defesa (prova que o detector de ataque funciona) e o portão precisa barrar exatamente os casos que não estão marcados como limitação.

## Estender

- **Tarefa nova:** `data/tarefas.yaml`, depois `make smoke`. Veja o [guia de contribuição](../CONTRIBUTING.md).
- **Mundo novo:** SQL + política em `data/mundos/<nome>/`, classe em `worlds/<nome>.py`, registro em `worlds/__init__.py`.
- **Provedor novo:** um adaptador com `complete(system, history, tools) -> ModelTurn`.
- **Defesa nova:** uma subclasse de `Defense` em `defenses.py`, com `before_call` (barrar), `after_call` (observar) e `render` (como o modelo vê o resultado).
