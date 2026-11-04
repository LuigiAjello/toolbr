# Segurança

## Os ataques do benchmark

Os 12 casos de prompt injection em `data/ataques.yaml` são sintéticos e só agem sobre os mundos simulados (bancos SQLite em memória, com dados fictícios). Eles servem para medir defesas; não use contra sistemas reais.

## Relatar uma vulnerabilidade

Se você encontrar uma falha no código do ToolBR (por exemplo, no servidor MCP ou na geração do dashboard), não abra uma issue pública. Use o relato privado do GitHub: aba **Security**, depois **Report a vulnerability**. Responderemos assim que possível.

## Chaves de API

O ToolBR lê chaves só do `.env`, que fica fora do git. Nunca cole uma chave em issue, pull request ou resultado.
