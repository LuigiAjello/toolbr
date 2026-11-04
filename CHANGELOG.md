# Changelog

O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o versionamento segue o [SemVer](https://semver.org/lang/pt-BR/). Mudanças no dataset que alteram notas sobem a versão e entram também na [errata](docs/ERRATA.md).

## [0.1.0] - 2026-11-04

Primeira versão: prova o método de ponta a ponta.

### Adicionado

- 3 mundos simulados em SQLite (delivery, banco, atendimento), com políticas em português.
- 25 tarefas de 7 tipos, corrigidas pelo estado final do banco inteiro.
- Pass^k (estimador do τ-bench) e intervalo de confiança por bootstrap de tarefas.
- Agente de loop próprio e agente equivalente em LangGraph.
- Adaptadores para Anthropic, OpenAI e Ollama; modelos de teste oracle, naive, vulnerable e cautious.
- 12 ataques de prompt injection indireta e as defesas delimitar e portão de proveniência.
- Avaliação da busca nas políticas com BM25 e embeddings.
- Servidor MCP (stdio e HTTP sem estado), registro no MLflow, demo em Gradio e dashboard estático.
- CI com ruff, pytest e portão de qualidade.
