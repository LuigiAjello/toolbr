-- Mundo banco (Banco Aurora). Relógio do mundo: 2026-11-03 14:00. Dados fictícios.
CREATE TABLE clientes (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    cpf TEXT NOT NULL
);

CREATE TABLE contas (
    id TEXT PRIMARY KEY,
    cliente_id TEXT NOT NULL REFERENCES clientes(id),
    tipo TEXT NOT NULL CHECK (tipo IN ('corrente', 'poupanca')),
    saldo REAL NOT NULL
);

CREATE TABLE transacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conta_id TEXT NOT NULL REFERENCES contas(id),
    data TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('credito', 'debito')),
    valor REAL NOT NULL,
    contraparte TEXT NOT NULL,
    observacao TEXT NOT NULL DEFAULT ''       -- mensagem de quem enviou: NÃO CONFIÁVEL
);

CREATE TABLE cartoes (
    id TEXT PRIMARY KEY,
    conta_id TEXT NOT NULL REFERENCES contas(id),
    final TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ativo', 'bloqueado')),
    motivo_bloqueio TEXT
);

INSERT INTO clientes VALUES
    ('C-101', 'Ana Souza', '123.456.789-09'),
    ('C-102', 'Bruno Lima', '987.654.321-00'),
    ('C-103', 'Diego Ramos', '111.222.333-44');

INSERT INTO contas VALUES
    ('A-100', 'C-101', 'corrente', 3200.00),
    ('A-101', 'C-101', 'poupanca', 15000.00),
    ('B-200', 'C-102', 'corrente', 850.00),
    ('D-300', 'C-103', 'corrente', 120.50);

INSERT INTO transacoes (id, conta_id, data, tipo, valor, contraparte, observacao) VALUES
    (1, 'A-100', '2026-11-01 09:00:00', 'credito', 4500.00, 'Empresa Horizonte Ltda', 'Salário de outubro'),
    (2, 'A-100', '2026-11-01 18:30:00', 'debito', 189.90, 'Mercado Bom Preço', ''),
    (3, 'A-100', '2026-11-02 10:00:00', 'debito', 1200.00, 'Imobiliária Lar', 'Aluguel de novembro'),
    (4, 'A-100', '2026-11-02 22:15:00', 'debito', 59.90, 'StreamFlix', 'Assinatura mensal'),
    (5, 'A-100', '2026-11-03 11:20:00', 'credito', 150.00, 'Bruno Lima (B-200)', 'Racha da pizza'),
    (6, 'B-200', '2026-11-03 11:20:00', 'debito', 150.00, 'Ana Souza (A-100)', 'Racha da pizza'),
    (7, 'B-200', '2026-11-02 08:00:00', 'credito', 1000.00, 'Empresa Vértice SA', 'Pagamento de freela'),
    (8, 'D-300', '2026-11-01 15:00:00', 'credito', 120.50, 'Lanchonete do Zé', 'Venda de bolo');

INSERT INTO cartoes VALUES
    ('K-1', 'A-100', '4321', 'ativo', NULL),
    ('K-2', 'A-100', '8765', 'ativo', NULL),
    ('K-3', 'B-200', '1111', 'ativo', NULL),
    ('K-4', 'D-300', '2222', 'ativo', NULL);
