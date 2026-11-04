"""Base dos mundos simulados.

Cada mundo é um SQLite em memória criado do zero a cada episódio, com ferramentas
de schema JSON e uma política em português. Ferramentas nunca quebram: qualquer
problema vira {"erro": "..."} para o agente ler e reagir.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from toolbr.paths import DATA_DIR
from toolbr.retrieval import BM25Retriever, load_chunks

# Relógio fixo: a mesma tarefa dá o mesmo resultado em qualquer dia em que rodar.
NOW = "2026-11-03 14:00:00"
NOW_LABEL = "terça-feira, 03/11/2026, 14:00"

ERROR_503 = "503 Service Unavailable: o sistema está temporariamente indisponível."


class ToolError(Exception):
    """Erro de integridade ou de entrada. Vira {"erro": mensagem}."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    writes: bool = False
    # argumentos que o portão de proveniência confere (ids, contas, valores)
    critical_args: tuple[str, ...] = ()
    # texto livre escrito pelo modelo: fora do acerto de argumentos
    free_text_args: tuple[str, ...] = ()

    def schema(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "parameters": self.parameters}


def tool(
    name: str,
    description: str,
    properties: dict[str, dict[str, Any]],
    required: list[str],
    *,
    writes: bool = False,
    critical_args: tuple[str, ...] = (),
    free_text_args: tuple[str, ...] = (),
) -> Callable:
    """Registra um método do mundo como ferramenta."""
    params = {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
    spec = ToolSpec(name, description, params, writes, critical_args, free_text_args)

    def decorator(method: Callable) -> Callable:
        method._tool_spec = spec
        return method

    return decorator


BUSCAR_POLITICA = ToolSpec(
    "buscar_politica",
    "Busca trechos da política da empresa. Use para tirar dúvidas sobre regras e prazos.",
    {
        "type": "object",
        "properties": {
            "consulta": {"type": "string", "description": "Pergunta ou palavras-chave."}
        },
        "required": ["consulta"],
        "additionalProperties": False,
    },
)


class World:
    name: str = ""
    company: str = ""
    # tabela -> coluna da chave primária (define o que entra no snapshot)
    primary_keys: dict[str, str] = {}
    # colunas de texto livre escritas pelo modelo: o corretor ignora
    free_text_columns: dict[str, frozenset[str]] = {}
    # campos de texto que vêm de terceiros: não confiáveis, é onde ficam os ataques
    untrusted_keys: frozenset[str] = frozenset()

    def __init__(self, fail_plan: dict[str, int] | None = None, retriever=None):
        # check_same_thread=False: o servidor MCP chama as ferramentas de outra thread
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        sql = (DATA_DIR / "mundos" / self.name / "estado_inicial.sql").read_text("utf-8")
        self.conn.executescript(sql)
        self.fail_plan = dict(fail_plan or {})
        self.call_counts: Counter[str] = Counter()
        self._retriever = retriever or BM25Retriever(load_chunks(self.name))
        self._handlers: dict[str, tuple[ToolSpec, Callable]] = {}
        for attr in dir(type(self)):
            method = getattr(self, attr)
            spec = getattr(method, "_tool_spec", None)
            if spec:
                self._handlers[spec.name] = (spec, method)
        self._handlers[BUSCAR_POLITICA.name] = (BUSCAR_POLITICA, self._buscar_politica)

    # ---- interface usada pelo agente e pelo corretor ----

    def tool_specs(self) -> list[ToolSpec]:
        return sorted((spec for spec, _ in self._handlers.values()), key=lambda s: s.name)

    def spec(self, name: str) -> ToolSpec | None:
        entry = self._handlers.get(name)
        return entry[0] if entry else None

    def call(self, name: str, args: dict[str, Any] | None) -> dict[str, Any]:
        """Executa uma ferramenta. Nunca levanta exceção."""
        self.call_counts[name] += 1
        if name not in self._handlers:
            return {"erro": f"ferramenta desconhecida: {name}"}
        if self.call_counts[name] <= self.fail_plan.get(name, 0):
            return {"erro": ERROR_503}
        spec, handler = self._handlers[name]
        try:
            clean = validate_args(spec, args)
            result = handler(**clean)
            self.conn.commit()
            return result
        except ToolError as exc:
            self.conn.rollback()
            return {"erro": str(exc)}
        except Exception as exc:  # erro inesperado ainda vira dado, não exceção
            self.conn.rollback()
            return {"erro": f"erro interno: {type(exc).__name__}: {exc}"}

    def snapshot(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Estado inteiro do banco: tabela -> chave primária (texto) -> linha."""
        out = {}
        for table, pk in self.primary_keys.items():
            rows = self.conn.execute(f"SELECT * FROM {table} ORDER BY {pk}").fetchall()
            out[table] = {str(row[pk]): dict(row) for row in rows}
        return out

    def policy(self) -> str:
        return (DATA_DIR / "mundos" / self.name / "politica.md").read_text("utf-8")

    def customer_context(self, customer_id: str) -> str:
        row = self.conn.execute("SELECT * FROM clientes WHERE id = ?", (customer_id,)).fetchone()
        if not row:
            raise ValueError(f"cliente {customer_id} não existe no mundo {self.name}")
        return f"{row['id']} ({row['nome']})"

    def set_field(self, table: str, pk_value: Any, column: str, value: Any) -> None:
        """Muda um campo antes do episódio (usado para esconder ataques)."""
        pk = self.primary_keys[table]
        cur = self.conn.execute(
            f"UPDATE {table} SET {column} = ? WHERE {pk} = ?", (value, pk_value)
        )
        if cur.rowcount != 1:
            raise ValueError(f"{table}.{pk}={pk_value} não existe")
        self.conn.commit()

    # ---- helpers para os mundos ----

    def _one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def _all(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def _buscar_politica(self, consulta: str) -> dict[str, Any]:
        hits = self._retriever.search(consulta, k=3)
        return {"trechos": [{"id": c.id, "titulo": c.title, "texto": c.text} for c, _ in hits]}


def validate_args(spec: ToolSpec, args: Any) -> dict[str, Any]:
    """Confere os argumentos contra o schema e converte tipos simples.

    Aceita "1042" onde o schema pede inteiro (APIs reais costumam aceitar), mas
    recusa argumento desconhecido ou faltando, com mensagem que o agente entende.
    """
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise ToolError("os argumentos devem ser um objeto JSON")
    props = spec.parameters["properties"]
    unknown = sorted(set(args) - set(props))
    if unknown:
        raise ToolError(
            f"argumento desconhecido: {', '.join(unknown)}. Aceitos: {', '.join(props)}"
        )
    for req in spec.parameters.get("required", []):
        if args.get(req) in (None, ""):
            raise ToolError(f"faltou o argumento obrigatório: {req}")
    clean = {}
    for key, value in args.items():
        clean[key] = _coerce(key, value, props[key])
    return clean


def _coerce(key: str, value: Any, schema: dict[str, Any]) -> Any:
    kind = schema.get("type")
    try:
        if kind == "integer":
            if isinstance(value, bool):
                raise ValueError
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            value = int(str(value).strip())
        elif kind == "number":
            if isinstance(value, bool):
                raise ValueError
            value = (
                float(str(value).strip().replace(",", "."))
                if isinstance(value, str)
                else float(value)
            )
        elif kind == "string":
            value = str(value).strip()
    except (TypeError, ValueError):
        raise ToolError(f"o argumento {key} deve ser do tipo {kind}") from None
    if "enum" in schema and value not in schema["enum"]:
        raise ToolError(
            f"valor inválido para {key}: {value!r}. Opções: {', '.join(schema['enum'])}"
        )
    return value
