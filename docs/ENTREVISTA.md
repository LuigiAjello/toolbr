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
