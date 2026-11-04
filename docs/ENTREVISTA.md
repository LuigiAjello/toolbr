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
