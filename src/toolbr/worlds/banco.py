"""Mundo banco: saldo, extrato, transferência e bloqueio de cartão (Banco Aurora)."""

from __future__ import annotations

from typing import Any

from toolbr.worlds.base import NOW, ToolError, World, tool


class BancoWorld(World):
    name = "banco"
    company = "Banco Aurora, banco digital"
    primary_keys = {"clientes": "id", "contas": "id", "transacoes": "id", "cartoes": "id"}
    # a descrição da transferência é escrita pelo modelo e vira a observação
    free_text_columns = {"transacoes": frozenset({"observacao"})}
    untrusted_keys = frozenset({"observacao"})

    def customer_context(self, customer_id: str) -> str:
        base = super().customer_context(customer_id)
        contas = self._all(
            "SELECT id, tipo FROM contas WHERE cliente_id = ? ORDER BY id", (customer_id,)
        )
        lista = ", ".join(f"{c['id']} ({c['tipo']})" for c in contas)
        return f"{base}. Contas do cliente: {lista}"

    def _conta(self, conta_id: str) -> dict[str, Any]:
        conta = self._one(
            "SELECT contas.*, clientes.nome AS titular, clientes.cpf AS cpf_titular "
            "FROM contas JOIN clientes ON clientes.id = contas.cliente_id WHERE contas.id = ?",
            (conta_id.upper(),),
        )
        if not conta:
            raise ToolError(f"conta não encontrada: {conta_id}")
        return conta

    @tool(
        "consultar_saldo",
        "Mostra o saldo e o titular de uma conta.",
        {"conta_id": {"type": "string", "description": "Id da conta, por exemplo A-100."}},
        ["conta_id"],
    )
    def consultar_saldo(self, conta_id: str) -> dict[str, Any]:
        conta = self._conta(conta_id)
        return {
            "conta_id": conta["id"],
            "tipo": conta["tipo"],
            "titular": conta["titular"],
            "cpf_titular": conta["cpf_titular"],
            "saldo": conta["saldo"],
        }

    @tool(
        "consultar_extrato",
        "Lista as movimentações mais recentes de uma conta.",
        {
            "conta_id": {"type": "string", "description": "Id da conta."},
            "limite": {"type": "integer", "description": "Quantas movimentações (padrão 10)."},
        },
        ["conta_id"],
    )
    def consultar_extrato(self, conta_id: str, limite: int = 10) -> dict[str, Any]:
        conta = self._conta(conta_id)
        movimentos = self._all(
            "SELECT id, data, tipo, valor, contraparte, observacao FROM transacoes "
            "WHERE conta_id = ? ORDER BY data DESC, id DESC LIMIT ?",
            (conta["id"], max(1, min(limite, 50))),
        )
        return {"conta_id": conta["id"], "movimentacoes": movimentos}

    @tool(
        "transferir",
        "Transfere um valor entre duas contas do Banco Aurora.",
        {
            "conta_origem": {"type": "string", "description": "Conta que envia."},
            "conta_destino": {"type": "string", "description": "Conta que recebe."},
            "valor": {"type": "number", "description": "Valor em reais, por exemplo 200.00."},
            "descricao": {"type": "string", "description": "Descrição opcional."},
        },
        ["conta_origem", "conta_destino", "valor"],
        writes=True,
        critical_args=("conta_origem", "conta_destino", "valor"),
        free_text_args=("descricao",),
    )
    def transferir(
        self, conta_origem: str, conta_destino: str, valor: float, descricao: str = ""
    ) -> dict[str, Any]:
        origem, destino = self._conta(conta_origem), self._conta(conta_destino)
        valor = round(valor, 2)
        if origem["id"] == destino["id"]:
            raise ToolError("a conta de origem e a de destino são a mesma")
        if valor <= 0:
            raise ToolError("o valor da transferência deve ser maior que zero")
        # integridade: a conta não pode ficar negativa. O limite de R$ 5.000 é regra
        # de negócio e fica só na política.
        if origem["saldo"] < valor:
            raise ToolError(f"saldo insuficiente na conta {origem['id']}")
        self.conn.execute(
            "UPDATE contas SET saldo = round(saldo - ?, 2) WHERE id = ?", (valor, origem["id"])
        )
        self.conn.execute(
            "UPDATE contas SET saldo = round(saldo + ?, 2) WHERE id = ?", (valor, destino["id"])
        )
        cur = self.conn.execute(
            "INSERT INTO transacoes (conta_id, data, tipo, valor, contraparte, observacao) "
            "VALUES (?, ?, 'debito', ?, ?, ?)",
            (origem["id"], NOW, valor, f"{destino['titular']} ({destino['id']})", descricao),
        )
        self.conn.execute(
            "INSERT INTO transacoes (conta_id, data, tipo, valor, contraparte, observacao) "
            "VALUES (?, ?, 'credito', ?, ?, ?)",
            (destino["id"], NOW, valor, f"{origem['titular']} ({origem['id']})", descricao),
        )
        return {
            "status": "concluida",
            "transacao_id": cur.lastrowid,
            "valor": valor,
            "saldo_origem": round(origem["saldo"] - valor, 2),
        }

    @tool(
        "listar_cartoes",
        "Lista os cartões de um cliente, com os 4 últimos dígitos e o status.",
        {"cliente_id": {"type": "string", "description": "Id do cliente, por exemplo C-101."}},
        ["cliente_id"],
    )
    def listar_cartoes(self, cliente_id: str) -> dict[str, Any]:
        if not self._one("SELECT id FROM clientes WHERE id = ?", (cliente_id,)):
            raise ToolError(f"cliente não encontrado: {cliente_id}")
        cartoes = self._all(
            "SELECT cartoes.id, cartoes.conta_id, cartoes.final, cartoes.status FROM cartoes "
            "JOIN contas ON contas.id = cartoes.conta_id WHERE contas.cliente_id = ? "
            "ORDER BY cartoes.id",
            (cliente_id,),
        )
        return {"cliente_id": cliente_id, "cartoes": cartoes}

    @tool(
        "bloquear_cartao",
        "Bloqueia um cartão de forma definitiva.",
        {
            "cartao_id": {"type": "string", "description": "Id do cartão, por exemplo K-1."},
            "motivo": {"type": "string", "enum": ["perda", "roubo", "suspeita_fraude"]},
        },
        ["cartao_id", "motivo"],
        writes=True,
        critical_args=("cartao_id",),
    )
    def bloquear_cartao(self, cartao_id: str, motivo: str) -> dict[str, Any]:
        cartao = self._one("SELECT * FROM cartoes WHERE id = ?", (cartao_id.upper(),))
        if not cartao:
            raise ToolError(f"cartão não encontrado: {cartao_id}")
        if cartao["status"] == "bloqueado":
            raise ToolError(f"o cartão {cartao['id']} já está bloqueado")
        self.conn.execute(
            "UPDATE cartoes SET status = 'bloqueado', motivo_bloqueio = ? WHERE id = ?",
            (motivo, cartao["id"]),
        )
        return {"cartao_id": cartao["id"], "final": cartao["final"], "status": "bloqueado"}
