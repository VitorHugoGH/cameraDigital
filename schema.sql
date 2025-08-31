-- Deleta as tabelas antigas se existirem, para recomeçar
DROP TABLE IF EXISTS pareceres;
DROP TABLE IF EXISTS membros;
DROP TABLE IF EXISTS comissoes;

-- Tabela para armazenar as comissões permanentes
CREATE TABLE comissoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    sigla TEXT NOT NULL UNIQUE
);

-- Tabela para armazenar os membros e seus cargos em cada comissão
CREATE TABLE membros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    cargo TEXT NOT NULL,
    comissao_id INTEGER NOT NULL,
    FOREIGN KEY (comissao_id) REFERENCES comissoes (id)
);

-- Tabela para o histórico de pareceres gerados
CREATE TABLE pareceres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pdf_name TEXT NOT NULL,
    docx_name TEXT NOT NULL,
    numero_projeto TEXT,
    data_geracao TEXT NOT NULL
);