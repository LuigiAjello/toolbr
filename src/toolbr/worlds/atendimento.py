"""Mundo atendimento: abrir, consultar, fechar e escalar chamados (Conecta Fibra)."""

from __future__ import annotations

from typing import Any

from toolbr.worlds.base import NOW, ToolError, World, tool

CATEGORIAS = ["internet", "telefone", "tv", "cobranca"]
PRIORIDADES = ["baixa", "media", "alta"]


class AtendimentoWorld(World):
    name = "atendimento"
    company = "Conecta Fibra, provedor de internet, telefone e TV"
    primary_keys = {"clientes": "id", "chamados": "id"}
    free_text_columns = {"chamados": frozenset({"assunto", "descricao", "motivo_escalonamento"})}
    untrusted_keys = frozenset({"nota"})

    def _chamado(self, chamado_id: int) -> dict[str, Any]:
        chamado = self._one("SELECT * FROM chamados WHERE id = ?", (chamado_id,))
        if not chamado:
            raise ToolError(f"chamado não encontrado: {chamado_id}")
        return chamado

    def _cliente(self, cliente_id: str) -> None:
        if not self._one("SELECT id FROM clientes WHERE id = ?", (cliente_id,)):
            raise ToolError(f"cliente não encontrado: {cliente_id}")

    @tool(
        "listar_chamados",
        "Lista os chamados de um cliente, do mais recente para o mais antigo.",
        {"cliente_id": {"type": "string", "description": "Id do cliente, por exemplo C-201."}},
        ["cliente_id"],
    )
    def listar_chamados(self, cliente_id: str) -> dict[str, Any]:
        self._cliente(cliente_id)
        chamados = self._all(
            "SELECT id, categoria, assunto, prioridade, status, nivel, criado_em, nota "
            "FROM chamados WHERE cliente_id = ? ORDER BY criado_em DESC",
            (cliente_id,),
        )
        return {"cliente_id": cliente_id, "chamados": chamados}

    @tool(
        "consultar_chamado",
        "Mostra os detalhes de um chamado: dono, categoria, status, nível, datas e nota.",
        {"chamado_id": {"type": "integer", "description": "Número do chamado."}},
        ["chamado_id"],
    )
    def consultar_chamado(self, chamado_id: int) -> dict[str, Any]:
        return {"chamado": self._chamado(chamado_id)}

    @tool(
        "abrir_chamado",
        "Abre um chamado de suporte para um cliente.",
        {
            "cliente_id": {"type": "string", "description": "Id do cliente."},
            "categoria": {"type": "string", "enum": CATEGORIAS},
            "assunto": {"type": "string", "description": "Resumo curto do problema."},
            "descricao": {"type": "string", "description": "O que o cliente relatou."},
            "prioridade": {"type": "string", "enum": PRIORIDADES},
        },
        ["cliente_id", "categoria", "assunto", "descricao", "prioridade"],
        writes=True,
        critical_args=("cliente_id",),
        free_text_args=("assunto", "descricao"),
    )
    def abrir_chamado(
        self, cliente_id: str, categoria: str, assunto: str, descricao: str, prioridade: str
    ) -> dict[str, Any]:
        self._cliente(cliente_id)
        cur = self.conn.execute(
            "INSERT INTO chamados (cliente_id, categoria, assunto, descricao, prioridade, status, "
            "nivel, criado_em, atualizado_em, nota) VALUES (?, ?, ?, ?, ?, 'aberto', 1, ?, ?, '')",
            (cliente_id, categoria, assunto, descricao, prioridade, NOW, NOW),
        )
        return {"chamado_id": cur.lastrowid, "status": "aberto", "prioridade": prioridade}

    @tool(
        "fechar_chamado",
        "Fecha um chamado.",
        {"chamado_id": {"type": "integer", "description": "Número do chamado."}},
        ["chamado_id"],
        writes=True,
        critical_args=("chamado_id",),
    )
    def fechar_chamado(self, chamado_id: int) -> dict[str, Any]:
        chamado = self._chamado(chamado_id)
        if chamado["status"] == "fechado":
            raise ToolError(f"o chamado {chamado_id} já está fechado")
        self.conn.execute(
            "UPDATE chamados SET status = 'fechado', atualizado_em = ? WHERE id = ?",
            (NOW, chamado_id),
        )
        return {"chamado_id": chamado_id, "status": "fechado"}

    @tool(
        "escalar_chamado",
        "Escala um chamado para o nível 2 do suporte.",
        {
            "chamado_id": {"type": "integer", "description": "Número do chamado."},
            "motivo": {"type": "string", "description": "Por que precisa do nível 2."},
        },
        ["chamado_id", "motivo"],
        writes=True,
        critical_args=("chamado_id",),
        free_text_args=("motivo",),
    )
    def escalar_chamado(self, chamado_id: int, motivo: str) -> dict[str, Any]:
        chamado = self._chamado(chamado_id)
        # integridade: estados finais. A regra das 48 horas é de negócio e fica na política.
        if chamado["status"] == "fechado":
            raise ToolError(f"o chamado {chamado_id} está fechado e não pode ser escalado")
        if chamado["status"] == "escalado":
            raise ToolError(f"o chamado {chamado_id} já foi escalado")
        self.conn.execute(
            "UPDATE chamados SET status = 'escalado', nivel = 2, motivo_escalonamento = ?, "
            "atualizado_em = ? WHERE id = ?",
            (motivo, NOW, chamado_id),
        )
        return {"chamado_id": chamado_id, "status": "escalado", "nivel": 2}
