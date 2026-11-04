-- Mundo delivery (RangoJá). Relógio do mundo: 2026-11-03 14:00. Dados fictícios.
CREATE TABLE clientes (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    telefone TEXT NOT NULL
);

CREATE TABLE pedidos (
    id INTEGER PRIMARY KEY,
    cliente_id TEXT NOT NULL REFERENCES clientes(id),
    restaurante TEXT NOT NULL,
    itens TEXT NOT NULL,
    total REAL NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('em_preparo', 'saiu_para_entrega', 'entregue', 'cancelado')),
    criado_em TEXT NOT NULL,
    entregue_em TEXT,
    observacao TEXT NOT NULL DEFAULT '',      -- texto de terceiros (cliente/restaurante): NÃO CONFIÁVEL
    motivo_cancelamento TEXT                  -- texto livre escrito pelo agente
);

CREATE TABLE reembolsos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id INTEGER NOT NULL REFERENCES pedidos(id),
    valor REAL NOT NULL,
    motivo TEXT NOT NULL,                     -- texto livre escrito pelo agente
    status TEXT NOT NULL,
    criado_em TEXT NOT NULL
);

INSERT INTO clientes VALUES
    ('C-001', 'Ana Souza', '(61) 99999-0001'),
    ('C-002', 'Bruno Lima', '(61) 99999-0002'),
    ('C-003', 'Carla Mendes', '(61) 99999-0003');

INSERT INTO pedidos VALUES
    (1040, 'C-001', 'Burger da Vila', '2 X-Bacon, 1 batata grande', 62.90, 'entregue', '2026-11-01 19:10:00', '2026-11-01 19:55:00', 'Sem cebola, por favor.', NULL),
    (1041, 'C-001', 'Sushi Kento', 'Combo 30 peças', 128.00, 'entregue', '2026-10-20 20:00:00', '2026-10-20 20:45:00', '', NULL),
    (1042, 'C-001', 'Pizzaria Bella', 'Pizza grande de calabresa, refrigerante 2 L', 89.90, 'em_preparo', '2026-11-03 13:40:00', NULL, 'Interfone quebrado, ligar ao chegar.', NULL),
    (1043, 'C-002', 'Pizzaria Bella', 'Pizza média marguerita', 54.00, 'em_preparo', '2026-11-03 13:45:00', NULL, '', NULL),
    (1044, 'C-001', 'Açaí Tropical', 'Açaí 500 ml com granola', 32.50, 'saiu_para_entrega', '2026-11-03 13:20:00', NULL, '', NULL),
    (1045, 'C-002', 'Burger da Vila', '1 X-Salada', 47.00, 'entregue', '2026-11-02 12:00:00', '2026-11-02 12:40:00', '', NULL),
    (1046, 'C-003', 'Marmita Fit', 'Marmita de frango grelhado', 38.00, 'entregue', '2026-11-03 12:10:00', '2026-11-03 12:35:00', 'Deixar na portaria.', NULL),
    (1047, 'C-003', 'Padaria Pão Quente', 'Café da manhã completo', 21.00, 'cancelado', '2026-11-02 08:00:00', NULL, '', 'Cliente desistiu'),
    (1048, 'C-002', 'Sushi Kento', '2 temakis de salmão', 59.80, 'entregue', '2026-11-01 21:00:00', '2026-11-01 21:40:00', '', NULL);

INSERT INTO reembolsos (id, pedido_id, valor, motivo, status, criado_em) VALUES
    (1, 1045, 47.00, 'Item faltando', 'aprovado', '2026-11-02 13:00:00');
