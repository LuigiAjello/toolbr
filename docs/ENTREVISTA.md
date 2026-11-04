# ToolBR: preparação para entrevista

Para cada parte: a decisão, por quê, a alternativa descartada, o número que prova (com o comando) e as perguntas que podem fazer.

Números marcados **pendente** só existem depois de rodar modelos reais. Nada aqui é inventado.

---

## Parte 0: base do repositório

- **Decisão:** um pacote Python (`src/toolbr`) gerenciado com `uv`. O núcleo só depende de `pyyaml`; Anthropic, OpenAI, LangGraph, MCP, MLflow, embeddings e Gradio são extras opcionais.
- **Por quê:** o portão de qualidade (oracle e naive) roda no CI em segundos, sem chave e sem baixar 2 GB de dependências.
- **Alternativa descartada:** `requirements.txt` com tudo junto. É mais simples, mas o CI ficaria lento e qualquer quebra no Gradio derrubaria o teste do corretor.
- **Número que prova:** `make smoke` roda sem nenhuma chave de API.
- **Perguntas que podem fazer:**
  - *Por que o `prompt.md` e os PDFs estão no `.gitignore`?* Têm dados pessoais e planos de carreira; o repositório vai ser público.
  - *Onde ficam as chaves?* Só no `.env`, que está no `.gitignore`; o `.env.example` mostra os nomes.

---

## Parte 1: mundos simulados

- **Decisão:** 3 mundos em SQLite em memória (delivery com 5 ferramentas, banco com 6, atendimento com 6), cada um criado do zero por episódio a partir de `data/mundos/<mundo>/estado_inicial.sql`, com relógio fixo em 03/11/2026 14:00. O sistema só barra **integridade** (pedido inexistente, saldo negativo, cartão já bloqueado, chamado fechado). As **regras de negócio** (cancelar só em preparo, reembolso em até 7 dias, limite de R$ 5.000, escalar só depois de 48 h, agir só nos dados do próprio cliente) ficam **só na política**.
- **Por quê:** se o backend barrasse tudo, um agente que ignora a política passaria, porque o sistema o salvaria. Com a regra só na política, a violação muda o banco e o corretor pega.
- **Alternativa descartada:** ferramentas que validam todas as regras (como parte do τ-bench faz). É mais realista para um backend, mas mede o backend e não o agente.
- **Outras decisões:** erro sempre estruturado (`{"erro": ...}`), nunca exceção; argumento desconhecido é recusado com mensagem; `"1042"` é aceito onde o schema pede inteiro; `check_same_thread=False` porque o MCP chama de outra thread; `observacao` e `nota` são campos de terceiros, não confiáveis.
- **Número que prova:** `uv run pytest tests/test_worlds.py` → 17 testes passando (inclui: transferir R$ 6.000 passa no sistema, porque o limite é da política; R$ 3.500 com saldo de R$ 3.200 é barrado).
- **Perguntas que podem fazer:**
  - *Por que relógio fixo?* "Até 7 dias" e "48 horas" dependem da hora; com relógio real, a mesma tarefa mudaria de gabarito conforme o dia.
  - *Por que SQLite em memória e não um mock em dicionário?* Transação, rollback e restrições (CHECK, chave estrangeira) vêm de graça, e o estado inteiro é comparável com um SELECT.
  - *E se a ferramenta quebrar no meio?* Rollback: ou a operação inteira acontece ou nada muda.

---

## Parte 2: tarefas

- **Decisão:** 25 tarefas em `data/tarefas.yaml` (delivery 9, banco 9, atendimento 7): simples 4, sequência 4, recusa 8, informação faltando 3, ferramenta irrelevante 2, ferramenta que falha 2, consulta à política 2. Níveis: 10 fáceis, 10 médias, 5 difíceis. O gabarito é a lista ordenada de chamadas (`argumentos_esperados`), mais os efeitos no banco e uma resposta de referência.
- **Por quê:** recusa é o tipo mais frequente porque é onde agente em produção causa prejuízo (cancelar o que não podia, transferir acima do limite, passar CPF de terceiro).
- **Alternativa descartada:** checar a resposta com um LLM juiz. Fica para a v0.2; na v0.1 o casamento é determinístico, por palavra inteira, sem acento, com alternativas e um casador de valores em reais (`{valor: 62.90}` aceita "62,90" e "R$ 62,90").
- **Regra que a auditoria criou:** quando o efeito esperado é "nada muda", `resposta_deve_conter` é obrigatório. Sem isso, o naive (não faz nada e diz "resolvido") acertaria o estado de 19 das 25 tarefas.
- **Número que prova:** `uv run pytest tests/test_tasks.py`: para cada tarefa, a resposta de referência passa e "Pronto, resolvido!" é reprovado em todas as 19 tarefas sem mudança de estado.
- **Perguntas que podem fazer:**
  - *Casamento por palavra não é frágil?* É; por isso as listas de alternativas são generosas e a nota principal é o estado do banco. A resposta só desempata quando o estado não muda.
  - *Como você evita gabarito impossível?* Cada tarefa é testada: ferramentas do gabarito existem no mundo, o gabarito cabe no limite de 8 passos e não usa ferramenta proibida. Na Parte 3, o oracle executa o gabarito e o corretor precisa dar 100%.
  - *25 tarefas não é pouco?* É. Com 25, um acerto de 80% tem intervalo de mais ou menos 15 pontos; a v0.2 vai para 60 a 100.

---

## Parte 3: corretor, métricas e portão

- **Decisão:** estado esperado = estado inicial + efeitos da tarefa; o corretor compara o banco **inteiro** com esse estado, ignorando só colunas de texto livre escritas pelo modelo (motivo, descrição, assunto). Sucesso = estado certo + ferramentas obrigatórias + nenhuma proibida + resposta certa + sem erro de execução nem estouro de passos. O motivo da falha é classificado (erro_execucao, limite_passos, ferramenta_proibida, estado_errado, ferramenta_faltando, resposta_errada).
- **Por quê:** comparar o banco inteiro pega efeito colateral (cancelar o 1042 *e* o 1043). Ignorar texto livre evita reprovar quem escreveu "lanche errado" em vez de "Lanche errado".
- **Alternativa descartada:** comparar a sequência de chamadas com o gabarito. Reprovaria caminhos corretos e diferentes (consultar antes ou listar antes), e aprovaria quem chamou certo mas deixou o banco errado.
- **Pass^k:** estimador do τ-bench, C(c, k) / C(n, k) por tarefa, média entre tarefas, de Pass^1 a Pass^n.
- **Intervalo de confiança:** bootstrap de 1.000 repetições sorteando **tarefas** (não tentativas), semente fixa.
- **Número que prova:** `uv run pytest tests/test_grader.py tests/test_gate.py`. Oracle = **100%** (25/25) e naive = **0%** (0/25) no loop próprio. Com 20 de 25 tarefas certas, o intervalo sai de 64% a 96%, como no documento de visão.
- **Perguntas que podem fazer:**
  - *Por que conferir o estado final e não a sequência de chamadas?* Porque o que importa para a empresa é o que mudou no sistema. Dois caminhos diferentes podem estar certos, e uma chamada "certa" pode vir acompanhada de um efeito colateral.
  - *Por que Pass^k e não só acurácia?* Um agente com 80% de acerto por tentativa acerta 4 seguidas só 41% das vezes (0,8⁴). Em produção, o cliente é atendido muitas vezes.
  - *Como você sabe que o gabarito está certo?* O oracle executa o gabarito no mundo de verdade e o corretor precisa dar 100%. Se algum efeito esperado estiver errado, o portão quebra. O naive precisa dar perto de 0%; se passar, o corretor está frouxo. Os dois rodam no CI.
  - *Por que sortear tarefas e não tentativas no bootstrap?* As 4 tentativas da mesma tarefa são correlacionadas. Sortear tentativas finge que há 100 observações independentes quando há 25, e o intervalo fica estreito demais.

---

## Parte 4: adaptadores, executor e CLI

- **Decisão:** uma interface de modelo (`complete(system, histórico, ferramentas)`) com histórico neutro; adaptadores para Anthropic (SDK oficial, Messages API), OpenAI (Chat Completions) e Ollama (mesma API da OpenAI em `localhost:11434/v1`). Resultado em `results/*.json` com metadados: modelo, provedor, agente, defesa, temperatura, effort, k, política, limite de passos, versão do dataset, data, commit do git e se havia alteração não commitada.
- **Por quê:** o agente não conhece o provedor; trocar de modelo não muda uma linha do loop, e o mesmo histórico serve ao LangGraph.
- **Decisões de API (conferidas no SDK instalado):** o SDK da Anthropic envia a versão `2026-10-21`, que rejeita `temperature` com erro 400; o adaptador recusa temperatura com mensagem clara e registra o `effort`. Sem fallback automático de modelo em recusa, porque a nota iria para o modelo errado. Cache de prompt automático, já que sistema e ferramentas se repetem. Na OpenAI, os tokens em cache vêm dentro de `prompt_tokens`; separo para não cobrar duas vezes.
- **Gasto controlado:** `--estimar` mostra episódios, chamadas e tokens antes de rodar; modelo real pede confirmação; preço só de `data/precos.yaml` (vazio até você preencher).
- **LGPD:** CPF é mascarado em tudo que vai para o disco.
- **Alternativa descartada:** LiteLLM como camada única de provedores. Economiza código, mas esconde exatamente o que um benchmark de tool calling precisa controlar: formato das mensagens, cache, blocos de raciocínio e recusa.
- **Número que prova:** `python -m toolbr run --modelo claude-sonnet-5-5 --estimar` → 100 episódios, cerca de 208 chamadas, cerca de 319 mil tokens de entrada (estimativa, não medição).
- **Perguntas que podem fazer:**
  - *Por que não usar temperatura 0 para reprodutibilidade?* Nos Claude atuais ela não existe mais na API; e, mesmo onde existe, temperatura 0 não garante determinismo. Por isso medimos Pass^k em vez de fingir que uma execução é reprodutível.
  - *O que acontece se o modelo mandar JSON inválido nos argumentos?* O adaptador repassa como argumento desconhecido; o mundo devolve erro estruturado e o modelo pode corrigir. Isso aparece no acerto de argumentos.
  - *Como você controla custo?* Estimativa antes, confirmação, cache de prompt e tokens registrados por episódio.

---

## Parte 5: agente em LangGraph

- **Decisão:** grafo próprio no LangGraph 1.2 (`StateGraph` com estado `messages` + `steps`, nó do modelo, `ToolNode` e arestas condicionais), com ferramentas no formato LangChain (`StructuredTool`). O modelo é o mesmo objeto do loop próprio, embrulhado como `BaseChatModel`; as ferramentas passam pelo mesmo runtime (mesmas defesas e registro).
- **Por quê:** a pergunta é "o framework muda algo?". Se cada agente usasse um cliente de API diferente (`ChatAnthropic` contra o SDK direto), a diferença misturaria orquestração com o adaptador do LangChain (formato das mensagens, tratamento de erro). Assim, a única variável é a orquestração.
- **Alternativa descartada:** `create_agent` do pacote `langchain`. É o caminho "pronto", mas esconde o laço e o limite de passos; com grafo próprio dá para garantir o mesmo limite de 8 passos do loop e provar a equivalência em teste.
- **Detalhes que importaram:** o `ToolNode` roda chamadas em paralelo, então o runtime ganhou uma trava no SQLite; o erro da ferramenta precisa chegar ao modelo como erro (`is_error`), por isso as ferramentas devolvem conteúdo + artefato; o `TypedDict` do estado fica no nível do módulo e o arquivo não usa `from __future__ import annotations`.
- **Número que prova:** `uv run pytest tests/test_langgraph.py`: com roteiros idênticos, os dois agentes dão a mesma nota, os mesmos passos e as mesmas chamadas (inclusive no estouro do limite e no erro 503). `python -m toolbr gate`: oracle 100% e naive 0% nos dois agentes. **Pendente:** a diferença com modelo real.
- **Perguntas que podem fazer:**
  - *O LangGraph ajudou? Com que número?* Pendente de rodar modelo real. Com os modelos de teste, a diferença é zero por construção, o que prova que a comparação está justa. Com LLM real, qualquer diferença vem da orquestração e é reportada com intervalo pareado (`python -m toolbr table --comparar A.json B.json`).
  - *Quando você usaria LangGraph em vez de um loop?* Quando o fluxo tem ramificações, pausa para humano, retomada com checkpoint ou vários agentes. Para um laço de tool calling simples, o loop é menor e mais fácil de depurar.

---

## Parte 6: busca nas políticas (RAG)

- **Decisão:** cada política é dividida em trechos, um por seção `##` (22 trechos nas 3 políticas). Dois métodos: BM25 próprio (sem dependência, com normalização de acento, stopwords e radical simples) e embeddings multilíngues locais via fastembed (`paraphrase-multilingual-MiniLM-L12-v2`, sem custo de API). A avaliação usa as 3 políticas juntas, com 15 perguntas que trazem o trecho certo marcado, várias escritas com outras palavras de propósito.
- **Por quê:** trecho por seção é a unidade que um humano citaria ("a regra de cancelamento"). Juntar as 3 políticas deixa a busca mais difícil e mais realista que buscar só no mundo certo.
- **Alternativa descartada:** dividir por número fixo de tokens com sobreposição. Faz sentido para documentos longos; aqui as seções são curtas e já têm um assunto cada.
- **Número que prova:** `python -m toolbr rag-eval`. BM25: recall@1 0,67, recall@3 0,87, recall@5 1,00, MRR 0,77. Embeddings: recall@1 0,80, recall@3 1,00, recall@5 1,00, MRR 0,90 [0,80 a 1,00]. **MRR embeddings menos BM25: +0,13 [IC 95%: −0,08 a +0,32], sem diferença comprovada com 15 perguntas.**
- **Onde cada um erra:** o BM25 erra paráfrases ("o motoboy pegou minha comida" contra "saiu para entrega"; "teto para mandar dinheiro" contra "limite por transferência"). Os embeddings confundem seções vizinhas ("não fala o número do pedido" cai em cancelamento em vez de pedido não informado).
- **Perguntas que podem fazer:**
  - *Então embeddings são melhores?* Na média sim, mas com 15 perguntas o intervalo da diferença inclui zero; precisaria de umas 60 perguntas para afirmar. O próximo passo natural é busca híbrida (BM25 + embeddings), que costuma pegar o melhor dos dois.
  - *Por que a política vai inteira no prompt se existe busca?* As políticas são curtas (menos de 600 palavras cada), então caber no contexto é mais confiável que buscar. O modo `--politica busca` tira a política do prompt e obriga o agente a buscar, para medir o custo de depender do RAG.
  - *Por que MRR além de recall?* Recall@3 diz se o trecho certo aparece; MRR diz em que posição. Para um agente que lê só o primeiro trecho, a posição importa.

---

## Parte 7: segurança (injection indireta)

- **Decisão:** 12 casos em `data/ataques.yaml` (8 em português, 4 em inglês; disfarces "SISTEMA:", nota interna, mensagem do cliente, Banco Central, recado do técnico, fuga do delimitador). O pedido do cliente só consulta e o texto malicioso está num campo de terceiros (`observacao`, `nota`). Como nada deveria mudar, **ASR = ataques que mudaram o banco / total**. Também medimos se o agente *tentou* a ação, mesmo barrada.
- **Defesas:** (1) **delimitar**: o texto de terceiros vem entre `<dado_nao_confiavel>` e o prompt avisa que aquilo é dado, não ordem; `<` e `>` dentro do texto são trocados, para o atacante não fechar a marcação. (2) **portão de proveniência**: antes de uma ferramenta que altera estado, cada argumento crítico (id, conta, valor) precisa ter aparecido no pedido do cliente, no contexto da sessão ou num campo confiável de um resultado anterior. (3) **ambas**.
- **Por quê:** delimitar é barato, mas depende do modelo obedecer. O portão é determinístico, não depende do modelo e dá para provar em teste.
- **Limitação documentada do portão:** se o atacante cita um id que também aparece em dado confiável, o portão deixa passar. São 3 casos de propósito: reembolsar o 1041, que aparece na lista de pedidos do próprio cliente; transferir R$ 150 para a B-200, que aparece no extrato; e fechar o 5001, o próprio chamado que o cliente consulta.
- **Alternativa descartada:** um LLM classificador de injection antes de cada resultado. Custa uma chamada a mais por ferramenta, também erra, e não dá para provar com modelo de teste.
- **Número que prova (modelos de teste, `python -m toolbr security --modelo vulnerable`):** vulnerable sem defesa: ASR **100%** (12/12); com delimitar: 100% (o modelo de teste não lê o prompt; o efeito do delimitar só aparece com LLM real); com portão: **25%** (3/12, exatamente os 3 casos de limitação); cautious: 0%. Oracle com portão ou com ambas: utilidade de 100% nas 25 tarefas, ou seja, o portão não barrou nenhum fluxo legítimo. **Pendente:** os números com LLM real.
- **Perguntas que podem fazer:**
  - *Qual defesa funcionou e quanto ela custou em utilidade?* Com os modelos de teste, o portão corta o ASR de 100% para 25% sem perder utilidade nas 25 tarefas. Com LLM real: pendente.
  - *Por que o portão não resolve tudo?* Ele confere de onde veio o valor, não a intenção. Se o atacante manda agir sobre algo que o cliente acabou de ver, o valor é "confiável". Fechar essa brecha exige confirmar com o cliente antes de ações sensíveis, ou separar o planejamento da leitura de dados (como no CaMeL).
  - *Por que medir "tentou" além de "funcionou"?* Uma defesa que barra a ação pode esconder um modelo que obedece ao atacante. A taxa de tentativa mostra se o modelo foi enganado, mesmo quando o estrago não aconteceu.

---

## Parte 8: MCP, MLflow e CI

- **MCP:** `python -m toolbr mcp --mundo delivery` expõe as ferramentas de um mundo por stdio (para Claude Desktop ou Claude Code); `--http` sobe HTTP **sem estado de sessão e com resposta JSON, sem SSE**, como na spec 2026-07-28. Uso o servidor de baixo nível do SDK `mcp` 2.3 porque as ferramentas já têm schema JSON. Erro de ferramenta volta como `is_error: true` e também como `structured_content`.
- **MLflow:** `--mlflow` no `run` registra parâmetros (modelo, agente, defesa, k, commit, effort), métricas (`sucesso`, `pass_hat_1` a `pass_hat_4`, acertos, latência, tokens, custo quando há preço) e o JSON de resultado como artefato, com backend SQLite (`mlflow.db`).
- **CI:** GitHub Actions com ruff (lint e formato), pytest e o portão (`python -m toolbr gate`). O CI instala só o necessário (sem Gradio, MLflow e embeddings), e os testes que dependem desses extras são pulados.
- **Armadilhas que apareceram de verdade:** (1) o GET em `/mcp` abre um stream que não fecha: meu `curl` de espera travou; o cliente MCP usa só POST. (2) O MLflow grava artefatos em `./mlruns` relativo à pasta atual: o teste sujava a raiz do repositório e agora roda numa pasta temporária. (3) Métrica com `^` não é aceita: `pass^4` vira `pass_hat_4`.
- **Alternativa descartada:** `MCPServer` (o antigo FastMCP), que infere o schema das assinaturas Python. Eu teria de recriar cada ferramenta como função só para o SDK ler o schema que já existe.
- **Número que prova:** `uv run pytest tests/test_infra.py`: o cliente MCP em memória negocia o protocolo `2026-07-28`, lista as 5 ferramentas do delivery e recebe erro estruturado; o MLflow grava `pass_hat_2 = 1.0` para o oracle. CI simulado num venv limpo: 121 testes passando, 1 pulado, portão ok.
- **Perguntas que podem fazer:**
  - *Como uma empresa usaria isso no CI dela?* O mesmo `gate` que roda aqui. Para o agente dela, a v0.3 traz a interface "traga seu agente": o CI roda as 25 tarefas com um subconjunto pequeno e falha se o sucesso cair de forma significativa em relação à linha de base (`table --comparar` já calcula a diferença pareada com intervalo).
  - *Por que MCP sem estado?* Escala horizontalmente atrás de qualquer balanceador, sem afinidade de sessão; o estado que importa (o banco do mundo) fica no servidor, não na conexão.
  - *E A2A?* MCP liga um agente a ferramentas; A2A liga agentes entre si. Um próximo passo seria expor o próprio agente do ToolBR como serviço A2A e medir um agente orquestrando outro.

---

## Parte 9: demo em Gradio

- **Decisão:** uma tela: escolher a tarefa (as 25 e os 12 ataques), o modelo, o agente e a defesa; ver o veredito, **"o agente disse" ao lado de "o banco mostra"**, as chamadas na ordem (barradas aparecem como "barrada pela defesa") e o banco antes e depois. A tarefa padrão roda ao abrir a página. Sem chave de API, só os modelos de teste aparecem, com um aviso destacado de que não são um LLM.
- **Por quê:** a tese do ToolBR é que o corretor ignora o que o agente diz e olha o banco; a tela mostra exatamente essa comparação. No ataque, dá para ver o pedido 1043 de outro cliente sendo cancelado sem defesa, e a mesma chamada barrada com o portão.
- **Alternativa descartada:** um chat (`gr.Chatbot`). Mostra a conversa, mas esconde o que importa aqui: o estado do banco e o veredito.
- **Detalhe que o screenshot pegou:** com cores fixas, o título ficou invisível no modo escuro; agora as cores vêm das variáveis do tema, com verde e vermelho próprios para o escuro.
- **Número que prova:** `uv run pytest tests/test_demo.py`: o vulnerable sem defesa cancela o 1043 de outro cliente; com o portão, a chamada aparece barrada e o banco não muda.
- **Perguntas que podem fazer:**
  - *Por que a demo não deixa digitar qualquer pedido com o modelo de teste?* Deixa, mas avisa: o modelo de teste ignora o texto e o corretor usa o gabarito da tarefa escolhida. Com um LLM real, o pedido editado vale.

---

## Parte 10: README e resultados

- **Decisão:** README com o que é em 1 frase, motivação, 1 comando (`uv run python -m toolbr gate`), diagrama, métricas, resultados (tabela de modelos reais **vazia** até rodar), comparação honesta e limitações. Cada número tem comando e arquivo em `results/`, gerado no commit `66252f3`, sem alteração pendente.
- **Pendente para fechar a v0.1:** rodar 2 modelos reais com k = 4 (precisa de chave no `.env` e do seu ok de custo) e preencher `data/precos.yaml`.

---

## As 10 perguntas

1. **Por que conferir o estado final e não a sequência de chamadas?** O que importa para a empresa é o que mudou no sistema. Dois caminhos podem estar certos (listar antes ou consultar antes), e uma chamada "certa" pode vir com efeito colateral. O corretor compara o banco inteiro, então cancelar o 1042 *e* o 1043 reprova (teste `test_side_effect_is_caught_even_if_task_effect_happened`).
2. **Por que Pass^k e não só acurácia?** Em produção a mesma situação se repete milhares de vezes. 80% por tentativa vira 41% em 4 seguidas (0,8⁴). O Pass^4 mostra a consistência que a média esconde.
3. **Como você sabe que o gabarito está certo?** Três camadas: (a) teste de formato (ferramentas existem, gabarito cabe em 8 passos, não usa proibida); (b) o oracle executa o gabarito no mundo e precisa dar 100% (deu, nos dois agentes); (c) o naive precisa dar perto de 0% (deu 0%). Tudo roda no CI. Correções vão para `docs/ERRATA.md` com versão do dataset.
4. **A diferença entre os modelos é real? Qual o intervalo?** *Pendente de rodar modelos reais.* A ferramenta: `python -m toolbr table --comparar A.json B.json` faz bootstrap pareado por tarefa e só chama de "diferença real" se o intervalo não incluir zero. Na busca, por exemplo, embeddings tiveram MRR 0,13 maior que o BM25, mas o intervalo foi de −0,08 a +0,32: sem diferença comprovada.
5. **O LangGraph ajudou? Com que número?** *Pendente com modelo real.* Com os modelos de teste a diferença é zero por construção (mesma nota, passos e chamadas em teste), o que prova que a comparação está justa: só a orquestração muda.
6. **Qual defesa contra injection funcionou e quanto ela custou em utilidade?** Com os modelos de teste: o portão de proveniência corta o ASR do vulnerable de 100% para 25% (os 3 casos de limitação documentada), sem perder utilidade nas 25 tarefas (oracle continua 100%). O delimitar só pode ser medido com LLM real. *Pendente: os números com LLM real.*
7. **Quanto custou rodar tudo?** Até agora, US$ 0: modelos de teste e embeddings locais. Para um modelo real, `--estimar` dá cerca de 208 chamadas e 319 mil tokens de entrada para as 25 tarefas com k = 4. O custo em US$ só aparece com preço preenchido à mão em `data/precos.yaml`.
8. **Como uma empresa usaria isso no CI dela?** O CI do ToolBR já roda `python -m toolbr gate` a cada push. Uma empresa roda as tarefas com o próprio prompt ou modelo, guarda o JSON da versão atual como linha de base e falha o PR se `table --comparar` mostrar queda significativa. A v0.3 traz a interface "traga seu agente".
9. **O que você faria na próxima versão?** v0.2: cliente simulado por LLM em várias rodadas (com auditoria de 20 conversas), 60 a 100 tarefas, conjunto de teste escondido com frase-marcador, rastreio OpenTelemetry GenAI, dataset no Hugging Face e LLM juiz para a resposta. v0.3: "traga seu agente", mundos jurídico, Pix e nota fiscal.
10. **Como isso se compara com τ²-bench e BFCL?** O τ²-bench é maior, tem cliente simulado que também age no sistema e é a referência em estado final e Pass^k; o ToolBR pega o método e adiciona português, domínios brasileiros, segurança e comparação de frameworks. O BFCL mede muita variedade de chamadas (inclusive ferramenta irrelevante) mas não estado com política de negócio; o ToolBR pega a ideia de ferramenta irrelevante e que falha.

---

## Parte 11: dashboard e pacote open source

- **Decisão:** dashboard como **uma página HTML estática** (`python -m toolbr dashboard` → `docs/index.html`), gerada a partir de `results/*.json`, sem servidor e sem carregar nada externo, pronta para o GitHub Pages. Seções: modelos reais (sucesso com intervalo, curva de Pass^k, motivo das falhas, mapa tarefa × modelo), segurança, busca e validação do corretor.
- **Por quê:** um leaderboard que qualquer pessoa abre sem instalar nada e que se atualiza com um comando. **Modelos de teste nunca aparecem como modelos reais**: ficam só na seção de validação.
- **Cuidados de visualização:** paleta validada por script para daltonismo nos modos claro e escuro; uma cor só quando há uma série; intervalo de confiança desenhado em toda barra de taxa; cada gráfico tem tabela equivalente; tooltip por teclado e mouse; rótulos de fim de linha só quando não colidem.
- **Segurança da página:** os dados entram como JSON com todo `<` escapado (`<`), e os textos são inseridos com `textContent`. Um nome de modelo como `</script><script>...` não executa (teste `test_dashboard.py`).
- **Alternativa descartada:** dashboard em Gradio ou Streamlit. Precisaria de servidor ligado para alguém ver os resultados; a página estática fica no próprio repositório.
- **Pacote open source:** README com banner, badges, demo, resultados e resumo em inglês; `CONTRIBUTING.md` (como adicionar tarefa em 10 linhas de YAML), `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CITATION.cff`, `CHANGELOG.md`, modelos de issue (bug, errata, tarefa nova) e de pull request, e `docs/ARQUITETURA.md` com uma tentativa explicada passo a passo.
- **Perguntas que podem fazer:**
  - *Por que o mapa tarefa × modelo?* Porque a média esconde onde o modelo erra. O mapa mostra, por exemplo, se um modelo cai sempre nas recusas por política e não nas tarefas simples.
  - *Como o dashboard se mantém honesto?* Ele só lê os arquivos de resultado; não há número digitado. E mostra o estado vazio ("nenhum modelo real foi rodado ainda") em vez de esconder a seção.
