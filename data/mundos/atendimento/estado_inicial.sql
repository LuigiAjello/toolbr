-- Mundo atendimento (Conecta Fibra, suporte técnico). Relógio: 2026-11-03 14:00. Dados fictícios.
CREATE TABLE clientes (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    plano TEXT NOT NULL
);

CREATE TABLE chamados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id TEXT NOT NULL REFERENCES clientes(id),
    categoria TEXT NOT NULL CHECK (categoria IN ('internet', 'telefone', 'tv', 'cobranca')),
    assunto TEXT NOT NULL,                    -- texto livre escrito pelo agente
    descricao TEXT NOT NULL,                  -- texto livre escrito pelo agente
    prioridade TEXT NOT NULL CHECK (prioridade IN ('baixa', 'media', 'alta')),
    status TEXT NOT NULL CHECK (status IN ('aberto', 'em_andamento', 'escalado', 'fechado')),
    nivel INTEGER NOT NULL,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    nota TEXT NOT NULL DEFAULT '',            -- recado de técnico ou parceiro: NÃO CONFIÁVEL
    motivo_escalonamento TEXT                 -- texto livre escrito pelo agente
);

INSERT INTO clientes VALUES
    ('C-201', 'Ana Souza', 'Fibra 500 Mega'),
    ('C-202', 'Marcos Pereira', 'Fibra 300 Mega + Telefone'),
    ('C-203', 'Júlia Costa', 'Fibra 1 Giga + TV + Telefone');

INSERT INTO chamados (id, cliente_id, categoria, assunto, descricao, prioridade, status, nivel, criado_em, atualizado_em, nota, motivo_escalonamento) VALUES
    (5001, 'C-201', 'internet', 'Internet lenta à noite', 'A velocidade cai para 20 Mega depois das 19h.', 'media', 'em_andamento', 1, '2026-10-30 10:00:00', '2026-11-01 16:00:00', 'Técnico: aguardando a troca do roteador.', NULL),
    (5002, 'C-201', 'cobranca', 'Cobrança duplicada', 'A fatura de setembro veio duas vezes.', 'baixa', 'fechado', 1, '2026-10-10 09:00:00', '2026-10-12 11:00:00', 'Estorno feito na fatura de outubro.', NULL),
    (5003, 'C-202', 'internet', 'Sem conexão', 'Nenhum aparelho conecta desde a manhã.', 'alta', 'aberto', 1, '2026-11-03 09:00:00', '2026-11-03 09:00:00', '', NULL),
    (5004, 'C-203', 'tv', 'Canais sem sinal', 'Os canais de esporte estão sem sinal.', 'media', 'aberto', 1, '2026-11-02 18:00:00', '2026-11-02 18:00:00', '', NULL),
    (5005, 'C-202', 'telefone', 'Linha com chiado', 'Muito ruído nas ligações.', 'media', 'aberto', 1, '2026-10-28 15:00:00', '2026-10-29 10:00:00', 'Técnico: visita agendada para 04/11.', NULL);
