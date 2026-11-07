-- C4ISTAR MONITOR · schema Postgres (substitui os CSVs históricos)
-- Multi-cliente: quase tudo carrega cliente_documento.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS clientes (
    documento           VARCHAR(20) PRIMARY KEY,
    nome                TEXT NOT NULL DEFAULT '',
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analitico (
    id                  BIGSERIAL PRIMARY KEY,
    cliente_documento   VARCHAR(20) NOT NULL DEFAULT '',
    data                DATE NOT NULL,
    hora                TIME,
    camera              TEXT NOT NULL DEFAULT '',
    categoria           TEXT NOT NULL DEFAULT '',
    classe              TEXT NOT NULL DEFAULT '',
    track_id            TEXT NOT NULL DEFAULT '',
    total_unicos        INTEGER NOT NULL DEFAULT 0,
    qtd_cena            INTEGER NOT NULL DEFAULT 0,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_analitico_cli_data ON analitico (cliente_documento, data);
CREATE INDEX IF NOT EXISTS ix_analitico_camera ON analitico (camera, data);

CREATE TABLE IF NOT EXISTS ocorrencias (
    id                  BIGSERIAL PRIMARY KEY,
    cliente_documento   VARCHAR(20) NOT NULL DEFAULT '',
    data                DATE NOT NULL,
    hora                TIME,
    camera              TEXT NOT NULL DEFAULT '',
    categoria           TEXT NOT NULL DEFAULT '',
    classe              TEXT NOT NULL DEFAULT '',
    track_id            TEXT NOT NULL DEFAULT '',
    total_unicos        INTEGER NOT NULL DEFAULT 0,
    qtd_cena            INTEGER NOT NULL DEFAULT 0,
    id_alvo             TEXT NOT NULL DEFAULT '',
    duracao_segundos    DOUBLE PRECISION NOT NULL DEFAULT 0,
    confianca           DOUBLE PRECISION NOT NULL DEFAULT 0,
    status              TEXT NOT NULL DEFAULT '',
    pessoas_envolvidas  INTEGER NOT NULL DEFAULT 0,
    detalhe             TEXT NOT NULL DEFAULT '',
    risco               TEXT NOT NULL DEFAULT '',
    nivel_risco         INTEGER NOT NULL DEFAULT 1,
    qualidade_pose      DOUBLE PRECISION NOT NULL DEFAULT 0,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_ocorrencias_cli_data ON ocorrencias (cliente_documento, data);
CREATE INDEX IF NOT EXISTS ix_ocorrencias_risco ON ocorrencias (nivel_risco, data);

CREATE TABLE IF NOT EXISTS faces (
    id                  BIGSERIAL PRIMARY KEY,
    cliente_documento   VARCHAR(20) NOT NULL DEFAULT '',
    data                DATE NOT NULL,
    hora                TIME,
    camera              TEXT NOT NULL DEFAULT '',
    face_id             TEXT NOT NULL DEFAULT '',
    evento              TEXT NOT NULL DEFAULT '',
    total_passagens     INTEGER NOT NULL DEFAULT 0,
    track_id            TEXT NOT NULL DEFAULT '',
    confianca           DOUBLE PRECISION NOT NULL DEFAULT 0,
    proximidade         DOUBLE PRECISION NOT NULL DEFAULT 0,
    caminho_foto        TEXT NOT NULL DEFAULT '',
    foto_referencia     TEXT NOT NULL DEFAULT '',
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_faces_cli_face ON faces (cliente_documento, face_id, data);

CREATE TABLE IF NOT EXISTS placas (
    id                  BIGSERIAL PRIMARY KEY,
    cliente_documento   VARCHAR(20) NOT NULL DEFAULT '',
    data                DATE NOT NULL,
    hora                TIME,
    camera              TEXT NOT NULL DEFAULT '',
    placa_id            TEXT NOT NULL DEFAULT '',
    placa               TEXT NOT NULL DEFAULT '',
    evento              TEXT NOT NULL DEFAULT '',
    total_passagens     INTEGER NOT NULL DEFAULT 0,
    track_id_veiculo    TEXT NOT NULL DEFAULT '',
    tipo_veiculo        TEXT NOT NULL DEFAULT '',
    confianca           DOUBLE PRECISION NOT NULL DEFAULT 0,
    caminho_foto        TEXT NOT NULL DEFAULT '',
    foto_referencia     TEXT NOT NULL DEFAULT '',
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_placas_cli_placa ON placas (cliente_documento, placa, data);

CREATE TABLE IF NOT EXISTS audio (
    id                  BIGSERIAL PRIMARY KEY,
    cliente_documento   VARCHAR(20) NOT NULL DEFAULT '',
    data                DATE NOT NULL,
    hora                TIME,
    camera              TEXT NOT NULL DEFAULT '',
    tipo                TEXT NOT NULL DEFAULT '',
    categoria           TEXT NOT NULL DEFAULT '',
    nivel               INTEGER NOT NULL DEFAULT 0,
    texto               TEXT NOT NULL DEFAULT '',
    palavras            TEXT NOT NULL DEFAULT '',
    confianca           DOUBLE PRECISION NOT NULL DEFAULT 0,
    detalhe             TEXT NOT NULL DEFAULT '',
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_audio_cli_data ON audio (cliente_documento, data);
CREATE INDEX IF NOT EXISTS ix_audio_nivel ON audio (nivel, data);

CREATE TABLE IF NOT EXISTS ocorrencias_informadas (
    id                  BIGSERIAL PRIMARY KEY,
    cliente_documento   VARCHAR(20) NOT NULL DEFAULT '',
    id_externo          TEXT NOT NULL DEFAULT '',
    data                DATE,
    hora                TIME,
    natureza            TEXT NOT NULL DEFAULT '',
    descricao           TEXT NOT NULL DEFAULT '',
    endereco            TEXT NOT NULL DEFAULT '',
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    placa               TEXT NOT NULL DEFAULT '',
    pessoa              TEXT NOT NULL DEFAULT '',
    pessoas_ligadas     TEXT NOT NULL DEFAULT '',
    veiculos_ligados    TEXT NOT NULL DEFAULT '',
    situacoes           TEXT NOT NULL DEFAULT '',
    foto                TEXT NOT NULL DEFAULT '',
    video               TEXT NOT NULL DEFAULT '',
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_inf_cli_data ON ocorrencias_informadas (cliente_documento, data);

CREATE TABLE IF NOT EXISTS alertas_ia (
    id                  BIGSERIAL PRIMARY KEY,
    cliente_documento   VARCHAR(20) NOT NULL DEFAULT '',
    data_geracao        DATE,
    hora_geracao        TIME,
    data_evento         DATE,
    hora_evento         TIME,
    origem              TEXT NOT NULL DEFAULT '',
    tipo                TEXT NOT NULL DEFAULT '',
    ident               TEXT NOT NULL DEFAULT '',
    nome                TEXT NOT NULL DEFAULT '',
    motivo              TEXT NOT NULL DEFAULT '',
    camera              TEXT NOT NULL DEFAULT '',
    evento              TEXT NOT NULL DEFAULT '',
    passagens           TEXT NOT NULL DEFAULT '',
    nivel               TEXT NOT NULL DEFAULT '',
    descricao           TEXT NOT NULL DEFAULT '',
    foto                TEXT NOT NULL DEFAULT '',
    modelo              TEXT NOT NULL DEFAULT '',
    arquivo_relatorio   TEXT NOT NULL DEFAULT '',
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS insights (
    id                  BIGSERIAL PRIMARY KEY,
    cliente_documento   VARCHAR(20) NOT NULL DEFAULT '',
    data_geracao        DATE,
    hora_geracao        TIME,
    periodo             TEXT NOT NULL DEFAULT '',
    inicio_periodo      DATE,
    fim_periodo         DATE,
    tipo                TEXT NOT NULL DEFAULT '',
    nome                TEXT NOT NULL DEFAULT '',
    valor               TEXT NOT NULL DEFAULT '',
    descricao           TEXT NOT NULL DEFAULT '',
    nivel               TEXT NOT NULL DEFAULT '',
    modelo              TEXT NOT NULL DEFAULT '',
    arquivo_relatorio   TEXT NOT NULL DEFAULT '',
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS contagens (
    id                  BIGSERIAL PRIMARY KEY,
    cliente_documento   VARCHAR(20) NOT NULL DEFAULT '',
    data                DATE NOT NULL,
    hora                TIME,
    camera              TEXT NOT NULL DEFAULT '',
    pessoas             INTEGER NOT NULL DEFAULT 0,
    veiculos            INTEGER NOT NULL DEFAULT 0,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ingestao_lote (
    id                  BIGSERIAL PRIMARY KEY,
    cliente_documento   VARCHAR(20) NOT NULL DEFAULT '',
    origem              TEXT NOT NULL DEFAULT 'borda',
    tabela              TEXT NOT NULL DEFAULT '',
    quantidade          INTEGER NOT NULL DEFAULT 0,
    recebido_em         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
