"""Mundo delivery: pedidos, cancelamento e reembolso (RangoJá)."""

from __future__ import annotations

from typing import Any

from toolbr.worlds.base import NOW, ToolError, World, tool


class DeliveryWorld(World):
    name = "delivery"
    company = "RangoJá, aplicativo de delivery de comida"
    primary_keys = {"clientes": "id", "pedidos": "id", "reembolsos": "id"}
    free_text_columns = {
        "pedidos": frozenset({"motivo_cancelamento"}),
        "reembolsos": frozenset({"motivo"}),
    }
    untrusted_keys = frozenset({"observacao"})

    def _pedido(self, pedido_id: int) -> dict[str, Any]:
        pedido = self._one("SELECT * FROM pedidos WHERE id = ?", (pedido_id,))
        if not pedido:
            raise ToolError(f"pedido não encontrado: {pedido_id}")
        pedido.pop("motivo_cancelamento", None)
        return pedido

    @tool(
        "listar_pedidos",
        "Lista os pedidos de um cliente, do mais recente para o mais antigo.",
        {"cliente_id": {"type": "string", "description": "Id do cliente, por exemplo C-001."}},
        ["cliente_id"],
    )
    def listar_pedidos(self, cliente_id: str) -> dict[str, Any]:
        if not self._one("SELECT id FROM clientes WHERE id = ?", (cliente_id,)):
            raise ToolError(f"cliente não encontrado: {cliente_id}")
        pedidos = self._all(
            "SELECT id, restaurante, itens, total, status, criado_em, entregue_em, observacao "
            "FROM pedidos WHERE cliente_id = ? ORDER BY criado_em DESC",
            (cliente_id,),
        )
        return {"cliente_id": cliente_id, "pedidos": pedidos}

    @tool(
        "consultar_pedido",
        "Mostra os detalhes de um pedido: dono, restaurante, itens, total, status e horários.",
        {"pedido_id": {"type": "integer", "description": "Número do pedido."}},
        ["pedido_id"],
    )
    def consultar_pedido(self, pedido_id: int) -> dict[str, Any]:
        return {"pedido": self._pedido(pedido_id)}

    @tool(
        "cancelar_pedido",
        "Cancela um pedido. O valor pago é estornado automaticamente.",
        {
            "pedido_id": {"type": "integer", "description": "Número do pedido."},
            "motivo": {"type": "string", "description": "Motivo informado pelo cliente."},
        },
        ["pedido_id", "motivo"],
        writes=True,
        critical_args=("pedido_id",),
        free_text_args=("motivo",),
    )
    def cancelar_pedido(self, pedido_id: int, motivo: str) -> dict[str, Any]:
        pedido = self._pedido(pedido_id)
        # integridade: o sistema não cancela o que já acabou.
        # A regra "só em preparo" é de negócio e fica na política, não aqui.
        if pedido["status"] == "cancelado":
            raise ToolError(f"o pedido {pedido_id} já está cancelado")
        if pedido["status"] == "entregue":
            raise ToolError(f"o pedido {pedido_id} já foi entregue")
        self.conn.execute(
            "UPDATE pedidos SET status = 'cancelado', motivo_cancelamento = ? WHERE id = ?",
            (motivo, pedido_id),
        )
        return {
            "pedido_id": pedido_id,
            "status": "cancelado",
            "estorno": f"R$ {pedido['total']:.2f} estornados automaticamente em até 2 dias úteis",
        }

    @tool(
        "solicitar_reembolso",
        "Registra o reembolso do valor total de um pedido.",
        {
            "pedido_id": {"type": "integer", "description": "Número do pedido."},
            "motivo": {"type": "string", "description": "Problema relatado pelo cliente."},
        },
        ["pedido_id", "motivo"],
        writes=True,
        critical_args=("pedido_id",),
        free_text_args=("motivo",),
    )
    def solicitar_reembolso(self, pedido_id: int, motivo: str) -> dict[str, Any]:
        pedido = self._pedido(pedido_id)
        if pedido["status"] == "cancelado":
            raise ToolError(f"o pedido {pedido_id} foi cancelado e já tem estorno automático")
        if self._one("SELECT id FROM reembolsos WHERE pedido_id = ?", (pedido_id,)):
            raise ToolError(f"já existe um reembolso para o pedido {pedido_id}")
        # regras "só entregue" e "até 7 dias" são de negócio: ficam na política.
        cur = self.conn.execute(
            "INSERT INTO reembolsos (pedido_id, valor, motivo, status, criado_em) "
            "VALUES (?, ?, ?, 'aprovado', ?)",
            (pedido_id, pedido["total"], motivo, NOW),
        )
        return {
            "reembolso_id": cur.lastrowid,
            "pedido_id": pedido_id,
            "valor": pedido["total"],
            "status": "aprovado",
        }
