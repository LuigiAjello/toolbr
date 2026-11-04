.PHONY: install test lint format smoke bench dashboard demo

install:
	uv sync --all-extras

test:
	uv run pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

# portão de qualidade: oracle = 100%, naive <= 10%, segurança com modelos de teste
smoke:
	uv run python -m toolbr gate

# modelos reais: precisa de .env com as chaves. Mostra a estimativa antes de rodar.
MODELOS ?= claude-haiku-5-5 claude-sonnet-5-5
bench:
	@for m in $(MODELOS); do uv run python -m toolbr run --modelo $$m --k 4 --estimar; done
	@echo "Para rodar de verdade: uv run python -m toolbr run --modelo <modelo> --k 4"

# página estática com todos os resultados de results/ (para o GitHub Pages)
dashboard:
	uv run python -m toolbr dashboard

demo:
	uv run --extra demo python demo/app.py
