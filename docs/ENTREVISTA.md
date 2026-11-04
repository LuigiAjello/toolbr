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
