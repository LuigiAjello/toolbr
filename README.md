<p align="center">
  <img src="docs/assets/banner.svg" alt="ToolBR: o agente disse que cancelou o pedido, mas o banco mostra que ele continua em preparo, então a tarefa não passa" width="100%">
</p>

<p align="center">
  <strong>Benchmark aberto que mede se agentes de IA usam ferramentas corretamente em português,<br>
  conferindo o estado final do sistema, e não o que o agente diz que fez.</strong>
</p>

<p align="center">
  <img alt="Código: MIT" src="https://img.shields.io/badge/c%C3%B3digo-MIT-16263A">
  <img alt="Dados: CC-BY-4.0" src="https://img.shields.io/badge/dados-CC--BY--4.0-16263A">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-16263A">
  <img alt="MCP 2026-07-28" src="https://img.shields.io/badge/MCP-2026--07--28-16263A">
  <img alt="Versão 0.1.0" src="https://img.shields.io/badge/vers%C3%A3o-0.1.0-0E7A67">
</p>

<p align="center">
  <a href="#começo-rápido">Começo rápido</a> |
  <a href="#como-funciona">Como funciona</a> |
  <a href="#resultados">Resultados</a> |
  <a href="docs/ARQUITETURA.md">Arquitetura</a> |
  <a href="CONTRIBUTING.md">Contribuir</a> |
  <a href="#in-english">English</a>
</p>

---

O agente recebe o pedido de um cliente ("cancela o pedido 1042") e conversa com um sistema simulado, de delivery, banco ou suporte técnico, chamando ferramentas. No fim, o corretor ignora a resposta do agente e confere o banco de dados: se o pedido não foi cancelado, ou se alguma outra coisa mudou junto, a tarefa não passa. Cada tarefa roda 4 vezes, e a nota sai com intervalo de confiança.

## Por que existe

Empresas brasileiras estão colocando agentes em atendimento, bancos e serviços, mas os testes públicos de tool calling são em inglês.

- **O português cobra um preço.** Segundo a pesquisa que motivou o projeto, no Ticket-Bench (6 idiomas) o português foi o pior idioma do GPT-5, com 0,87.
- **Acertar uma vez não basta.** No τ-bench, o GPT-4o ficava abaixo de 25% no varejo quando precisava acertar a mesma tarefa 8 vezes seguidas.
- **Faltava o pacote completo em PT-BR:** um benchmark de agente que confira estado, política de negócio e consistência ao mesmo tempo.

## Ver funcionando

<p align="center">
  <img src="docs/assets/demo.png" alt="Demo do ToolBR: veredito 'Passou', o que o agente disse ao lado do que o banco mostra, as chamadas de ferramenta e o banco antes e depois" width="90%">
</p>

```bash
uv run --extra demo python demo/app.py
```

A demo roda uma tarefa e mostra o veredito, o que o agente disse ao lado do que o banco mostra, as chamadas na ordem e o banco antes e depois. Sem chave de API, ela usa os modelos de teste, com um aviso de que não são um LLM.

## Começo rápido

Precisa do [uv](https://docs.astral.sh/uv/). Nenhuma chave de API é necessária para começar.

```bash
git clone <este repositório> && cd toolbr
uv run python -m toolbr gate          # portão de qualidade: segundos, sem chave
```

Com um modelo real, coloque a chave no `.env` (veja o `.env.example`):

```bash
make install                                                    # tudo: LangGraph, MCP, MLflow, embeddings, demo
uv run python -m toolbr run --modelo claude-sonnet-5-5 --estimar   # quantas chamadas e tokens, antes de gastar
uv run python -m toolbr run --modelo claude-sonnet-5-5 --k 4       # pede confirmação antes de rodar
uv run python -m toolbr table                                     # tabela com intervalos de confiança
uv run python -m toolbr dashboard                                 # gera docs/index.html
```

## Como funciona

```mermaid
flowchart LR
    T["Tarefa<br/>pedido em português<br/>+ gabarito"] --> A["Agente<br/>loop próprio ou LangGraph"]
    A -- "chama ferramenta" --> M["Mundo simulado<br/>SQLite + ferramentas<br/>+ política"]
    M -- "resultado" --> A
    A -- "resposta ao cliente" --> C["Corretor<br/>confere o banco inteiro<br/>e a resposta"]
    M -- "banco no fim" --> C
    C --> R["Métricas<br/>Pass^k, IC 95%,<br/>custo, p50/p95"]
    R --> L["JSON, tabela,<br/>dashboard e MLflow"]
```

- **3 mundos simulados** em SQLite em memória, recriados a cada tentativa, com relógio fixo: **delivery** (pedidos, cancelamento, reembolso), **banco** (saldo, extrato, transferência, bloqueio de cartão) e **atendimento** (abrir, consultar, fechar e escalar chamado). Cada um tem 5 ou 6 ferramentas com schema JSON e uma política em português.
- **O sistema barra só a integridade** (pedido inexistente, saldo negativo). **As regras de negócio** (cancelar só em preparo, limite de R$ 5.000, escalar só depois de 48 horas, agir só nos dados do próprio cliente) **ficam só na política**. Se o agente as ignora, o banco muda e o corretor pega. Se o sistema barrasse tudo, o benchmark mediria o backend, não o agente.
- **25 tarefas** de 7 tipos: simples, sequência, recusa, informação faltando, ferramenta irrelevante, ferramenta que falha (503 simulado) e consulta à política.
- **12 ataques de prompt injection indireta** escondidos em campos de terceiros (observação do pedido, mensagem do Pix, nota do técnico), em português e em inglês.

Quer entender por dentro? O [guia de arquitetura](docs/ARQUITETURA.md) segue um episódio do começo ao fim, e as [decisões de projeto](docs/ENTREVISTA.md) explicam cada escolha e a alternativa descartada.

## O que mede

| Métrica | O que é |
|---|---|
| **Sucesso** (principal) | Banco inteiro igual ao esperado (estado inicial + efeitos da tarefa, ignorando o texto livre escrito pelo modelo) + ferramentas obrigatórias chamadas + nenhuma proibida + resposta certa + sem erro de execução |
| **Pass^k** | Chance de acertar a mesma tarefa em k tentativas seguidas, pelo estimador do τ-bench (C(c, k) / C(n, k)), de Pass^1 a Pass^4 |
| **IC 95%** | Bootstrap de 1.000 repetições sorteando *tarefas*, não tentativas |
| Diagnóstico | Acerto de ferramentas, de argumentos, de estado e de resposta, e o motivo de cada falha |
| Segurança | ASR (ataques que mudaram o banco / total), tentativa de ação maliciosa, utilidade sob ataque e com a defesa ligada |
| Busca | recall@1, @3 e @5 e MRR da ferramenta `buscar_politica`, com BM25 e com embeddings |
| Custo e latência | Tokens por tentativa, US$ só com preço preenchido à mão em `data/precos.yaml`, latência p50 e p95, passos médios |

## Resultados

Todo número abaixo saiu de uma execução real. Cada arquivo em `results/` registra o commit do git que o gerou. O dashboard junta tudo numa página: `python -m toolbr dashboard` gera [`docs/index.html`](docs/index.html), pronta para o GitHub Pages.

<p align="center">
  <img src="docs/assets/dashboard.png" alt="Dashboard do ToolBR: ASR por defesa, utilidade sob ataque e recall@k e MRR da busca" width="85%">
</p>

### Modelos reais

| Modelo | Agente | k | Sucesso [IC 95%] | Pass^4 [IC 95%] | US$/tarefa | p95 (s) | Comando | Arquivo |
|---|---|---|---|---|---|---|---|---|
| *ainda não rodado* | | | | | | | `python -m toolbr run --modelo <modelo> --k 4` | |

### Validação do corretor (modelos de teste, sem LLM)

Os modelos de teste não medem capacidade: provam que o gabarito e o corretor funcionam. O `oracle` repete o gabarito e precisa dar 100%; o `naive` não chama ferramenta e diz "resolvido", e precisa dar perto de 0%. O CI roda os dois a cada push.

| Modelo | Agente | k | Sucesso | Pass^4 | Comando | Arquivo |
|---|---|---|---|---|---|---|
| oracle | loop | 4 | 100% | 100% | `python -m toolbr run --modelo oracle --k 4` | [`tarefas_oracle_loop_20261104-001851.json`](results/tarefas_oracle_loop_20261104-001851.json) |
| oracle | langgraph | 4 | 100% | 100% | `python -m toolbr run --modelo oracle --agente langgraph --k 4` | [`tarefas_oracle_langgraph_20261104-001854.json`](results/tarefas_oracle_langgraph_20261104-001854.json) |
| naive | loop | 4 | 0% | 0% | `python -m toolbr run --modelo naive --k 4` | [`tarefas_naive_loop_20261104-001852.json`](results/tarefas_naive_loop_20261104-001852.json) |

### Busca nas políticas (15 perguntas, 22 trechos)

Comando: `python -m toolbr rag-eval`. Arquivo: [`busca_20261104-001858.json`](results/busca_20261104-001858.json).

| Método | recall@1 | recall@3 | recall@5 | MRR [IC 95%] |
|---|---|---|---|---|
| BM25 | 0,67 | 0,87 | 1,00 | 0,77 [0,61 a 0,95] |
| Embeddings (`paraphrase-multilingual-MiniLM-L12-v2`, local) | 0,80 | 1,00 | 1,00 | 0,90 [0,80 a 1,00] |

MRR dos embeddings menos o do BM25: **+0,13 [IC 95%: −0,08 a +0,32], sem diferença comprovada com 15 perguntas.** O BM25 erra paráfrases ("o motoboy pegou minha comida" contra "saiu para entrega"); os embeddings confundem seções vizinhas.

### Segurança contra injection indireta (12 ataques)

Medição com os modelos de teste, que valida o detector de ataque e o portão. Comando: `python -m toolbr security --modelo vulnerable`. Arquivo: [`seguranca_vulnerable_20261104-001858.json`](results/seguranca_vulnerable_20261104-001858.json). O `cautious`, que ignora instruções escondidas, dá ASR 0%: [`seguranca_cautious_20261104-001859.json`](results/seguranca_cautious_20261104-001859.json).

| Defesa (modelo `vulnerable`) | ASR [IC 95%] | Utilidade sob ataque | Utilidade nas 25 tarefas |
|---|---|---|---|
| nenhuma | 100% | 0% | 100% |
| delimitar | 100%¹ | 0% | 100% |
| portão de proveniência | 25% [0% a 50%] | 75% | 100% |
| ambas | 25% [0% a 50%] | 75% | 100% |

¹ O modelo de teste não lê o prompt de sistema; o efeito do delimitar só aparece com LLM real. Os 3 ataques que passam no portão são a limitação documentada: o atacante cita um id que também está em dado confiável (o próprio pedido listado, a conta que aparece no extrato, o chamado que o cliente consulta).

## Comparação honesta

O ToolBR não compete em tamanho com os benchmarks abaixo. Ele copia métodos que deram certo neles e os aplica ao português e a domínios brasileiros.

| Benchmark | O que faz bem | O que o ToolBR pega dele | O que o ToolBR adiciona |
|---|---|---|---|
| τ-bench (Sierra) | Cliente simulado por LLM, política de negócio, estado final do banco, Pass^k | Estado final e Pass^k | Português e domínios brasileiros |
| τ²-bench (Sierra) | Controle duplo: o cliente também age no sistema; domínio de telecom | Cliente simulado fica para a v0.2 | Recusa por política em PT-BR |
| BFCL (Berkeley) | Muita variedade de chamadas, detecção de ferramenta irrelevante, várias rodadas | Ferramenta irrelevante e ferramenta que falha | Estado, política e consistência |
| ToolSandbox (Apple) | Ferramentas com estado, falta de informação, usuário simulado | Tarefas em que o agente deve perguntar | Política de negócio em português |
| AgentDojo (ETH) | Injection medindo ataque e utilidade juntos, com defesas | A mesma forma de medir defesa | Ataques em português e inglês dentro de dados brasileiros; portão de proveniência determinístico |

## Limitações

- **25 tarefas é pouco.** Com 25, um acerto de 80% tem intervalo de 64% a 96%. Diferenças pequenas entre modelos não são anunciadas como vitória: `table --comparar` calcula a diferença pareada com intervalo.
- **Uma rodada só.** O pedido do cliente é uma mensagem; ainda não há cliente simulado conversando.
- **Mundos simples.** Políticas curtas e poucos dados. É um teste de método, não um retrato definitivo de qual modelo é melhor em português.
- **Resposta checada por palavra inteira**, com alternativas generosas; a nota principal é o estado do banco.
- **Gabarito revisado por uma pessoa.** Correções vão para [`docs/ERRATA.md`](docs/ERRATA.md).
- **Temperatura.** A API da Anthropic não aceita mais `temperature` (erro 400 desde a versão 2026-10-21). Para Claude, o resultado registra o `effort`.

## Roadmap

- [x] **v0.1, o método:** 3 mundos, 25 tarefas, estado final, Pass^4, 12 ataques e 2 defesas, busca com BM25 e embeddings, MCP, MLflow, CI, demo e dashboard
- [ ] v0.1, os números: 2 modelos reais rodados com k = 4
- [ ] **v0.2, números confiáveis:** cliente simulado por LLM em várias rodadas, 60 a 100 tarefas, conjunto de teste escondido, rastreio OpenTelemetry GenAI, dataset no Hugging Face
- [ ] **v0.3, útil para empresas:** "traga seu agente" para rodar no CI, mundos jurídico, Pix e nota fiscal, leaderboard ao vivo
- [ ] **v1.0, citável:** artigo curto, revisão externa das tarefas, regras para contribuições

## Contribuir

Contribuições são bem-vindas, principalmente **tarefas novas**, **correções de gabarito** e **novos mundos brasileiros**. O [guia de contribuição](CONTRIBUTING.md) mostra como adicionar uma tarefa em 10 linhas de YAML, e o portão de qualidade avisa na hora se o gabarito estiver errado. Ao participar, você concorda com o [código de conduta](CODE_OF_CONDUCT.md).

<details>
<summary><strong>Referência da linha de comando</strong></summary>

| Comando | O que faz |
|---|---|
| `python -m toolbr run --modelo <m>` | Roda as 25 tarefas. Opções: `--agente loop\|langgraph`, `--k 4`, `--defesa nenhuma\|delimitar\|portao\|ambas`, `--politica contexto\|busca`, `--busca bm25\|embeddings`, `--effort`, `--estimar`, `--mlflow` |
| `python -m toolbr table` | Tabela com os resultados salvos; `--comparar A.json B.json` dá a diferença pareada com intervalo |
| `python -m toolbr security --modelo <m>` | Os 12 ataques com cada defesa, mais a utilidade nas 25 tarefas |
| `python -m toolbr rag-eval` | recall@k e MRR da busca nas políticas |
| `python -m toolbr dashboard` | Gera `docs/index.html` com todos os resultados |
| `python -m toolbr mcp --mundo delivery` | Servidor MCP com as ferramentas de um mundo; `--http` para HTTP sem estado |
| `python -m toolbr gate` | Portão de qualidade com os modelos de teste |

**Modelos:** `claude-...` (Anthropic), `gpt-...` (OpenAI), `ollama:<modelo>` (local), e os de teste `oracle`, `naive`, `vulnerable` e `cautious`.

**Atalhos:** `make install`, `make test`, `make lint`, `make smoke`, `make dashboard`, `make demo`.

</details>

<details>
<summary><strong>Estrutura do repositório</strong></summary>

```
data/            tarefas, ataques, perguntas de busca, mundos (SQL + política), preços   CC-BY-4.0
src/toolbr/      mundos, agentes, adaptadores, corretor, métricas, defesas, CLI, MCP      MIT
demo/app.py      demo em Gradio
docs/            dashboard (index.html), arquitetura, decisões de projeto, errata
results/         resultados citados neste README
tests/           126 testes, incluindo o portão de qualidade
```

</details>

## Como citar

Use o botão "Cite this repository" do GitHub (arquivo [`CITATION.cff`](CITATION.cff)) ou:

```bibtex
@software{toolbr2026,
  title   = {ToolBR: benchmark de tool calling em português checado pelo estado final},
  author  = {Ajello, Luigi},
  year    = {2026},
  version = {0.1.0}
}
```

## Licença

Código sob [MIT](LICENSE). Dados sob [CC-BY-4.0](data/LICENSE.md). Todos os nomes, CPFs, contas e pedidos são fictícios.

---

## In English

**ToolBR** is an open benchmark for **tool-calling agents in Brazilian Portuguese**. An agent receives a customer request and calls tools on a simulated system (food delivery, bank, or ISP support desk) backed by an in-memory SQLite database. The grader ignores what the agent *says* and checks the **final state of the whole database** against the expected one, so side effects are caught. Each task runs 4 times and is reported as **Pass^k** (the τ-bench estimator) with **task-level bootstrap confidence intervals**.

v0.1 ships 25 tasks across 7 types (including policy refusals, missing information, irrelevant tools and transient 503 failures), 12 **indirect prompt-injection** attacks with two defenses (delimiting untrusted fields, and a deterministic **argument-provenance gate**), policy-retrieval evaluation (BM25 vs. multilingual embeddings), a plain API agent loop and an equivalent **LangGraph** agent sharing the same model and tools, adapters for Anthropic, OpenAI and Ollama, an **MCP** server (stateless HTTP, spec 2026-07-28), MLflow tracking, a Gradio demo, a static results dashboard, and a CI quality gate where a scripted `oracle` must score 100% and a do-nothing `naive` model at most 10%.

Quick start: `uv run python -m toolbr gate`. Code is MIT, data is CC-BY-4.0.
