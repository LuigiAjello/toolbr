# Como contribuir com o ToolBR

Obrigado pelo interesse! As contribuições que mais ajudam agora:

1. **Tarefas novas**, principalmente as difíceis: políticas com exceções, várias ferramentas em sequência, armadilhas.
2. **Correções de gabarito.** Um gabarito errado é o pior defeito de um benchmark.
3. **Mundos brasileiros novos:** Pix, nota fiscal, escritório jurídico, saúde suplementar.
4. **Resultados de modelos**, rodados com o comando e o arquivo de resultado junto.

## Preparar o ambiente

```bash
uv sync --all-extras      # ou: make install
make test                 # pytest
make lint                 # ruff
make smoke                # portão de qualidade (oracle 100%, naive <= 10%, segurança)
```

Os três precisam passar antes de abrir um pull request. O CI roda os mesmos comandos.

## Adicionar uma tarefa

As tarefas ficam em [`data/tarefas.yaml`](data/tarefas.yaml); o cabeçalho do arquivo documenta cada campo. Exemplo mínimo:

```yaml
- id: delivery-10
  mundo: delivery
  nivel: medio
  tipo: recusa
  cliente: C-002
  pedido: "Cancela o pedido 1045, por favor."
  efeitos_esperados: []                      # nada deve mudar no banco
  argumentos_esperados:                      # o gabarito, na ordem; o oracle repete isto
    - {ferramenta: consultar_pedido, argumentos: {pedido_id: 1045}}
  ferramentas_esperadas: [consultar_pedido]
  ferramentas_proibidas: [cancelar_pedido]
  resposta_deve_conter:
    - ["entregue", "já foi entregue"]        # uma lista = qualquer uma das alternativas
  resposta_referencia: "O pedido 1045 já foi entregue, então não dá para cancelar."
```

Regras:

- **O gabarito é validado executando.** Depois de editar, rode `make smoke`: o oracle precisa dar 100%. Se não der, o efeito esperado ou o gabarito está errado, e o portão diz qual tarefa falhou.
- **Sem efeito esperado, a resposta é obrigatória.** Se `efeitos_esperados` é vazio, preencha `resposta_deve_conter`; senão, um modelo que não faz nada passaria.
- **Casamento por palavra inteira.** Ofereça alternativas generosas; a nota principal é o estado do banco.
- **Efeitos com todas as colunas.** Num `insere`, liste todas as colunas, menos a chave e o texto livre escrito pelo modelo.
- **Dados fictícios.** Nunca use nome, CPF, telefone ou conta de pessoa real.

## Corrigir um gabarito

Abra uma issue do tipo "Errata" ou mande o PR direto. Toda correção entra em [`docs/ERRATA.md`](docs/ERRATA.md) com a data, a versão do dataset e o motivo, porque uma correção que muda notas torna os resultados anteriores não comparáveis.

## Adicionar um mundo

1. Crie `data/mundos/<nome>/estado_inicial.sql` (esquema + dados fictícios) e `politica.md` (uma seção `##` por regra).
2. Crie `src/toolbr/worlds/<nome>.py` herdando de `World`, com 4 a 6 ferramentas marcadas com `@tool`. Declare `primary_keys`, `free_text_columns` e `untrusted_keys`.
3. Regra de ouro: **a ferramenta barra só integridade**; regra de negócio fica na política.
4. Registre o mundo em `src/toolbr/worlds/__init__.py` e adicione tarefas.

O [guia de arquitetura](docs/ARQUITETURA.md) mostra como as peças se ligam.

## Adicionar um modelo ou provedor

Um adaptador implementa `complete(system, histórico, ferramentas) -> ModelTurn` (veja `src/toolbr/models/base.py`) e converte o histórico neutro para o formato do provedor. Teste a conversão sem rede, como em `tests/test_adapters.py`.

## Publicar resultados

Rode com `--k 4`, deixe o arquivo em `results/` e cite o comando junto. Nunca edite um número à mão. Preços só entram em `data/precos.yaml` com a fonte e a data da consulta.

## Estilo

- Código e identificadores em inglês; dados, mensagens ao usuário e documentação em português.
- `ruff format` e `ruff check` sem erros.
- Commits curtos e no imperativo, explicando o porquê.

## Dúvidas

Abra uma issue. Perguntas são contribuições também.
