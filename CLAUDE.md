# ToolBR: instruções para o Claude Code

O contexto completo, a especificação e o ritmo de trabalho estão no `prompt.md` (local, fora do git):

@prompt.md

Regras que valem sempre, mesmo sem o `prompt.md`:

- Nunca invente número de resultado nem preço. Preço só vem de `data/precos.yaml`, preenchido pelo dono do projeto.
- Antes de rodar modelo pago: dizer quantas chamadas e o custo estimado, e esperar o ok.
- Chaves de API só no `.env`.
- Código e identificadores em inglês; dados, tarefas, mensagens ao usuário e documentação em português.
- Ao fim de cada parte: testes passando, commit, e `docs/ENTREVISTA.md` atualizado.
