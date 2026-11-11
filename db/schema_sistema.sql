-- Métricas de armazenamento e host (página admin /sistema)

CREATE TABLE IF NOT EXISTS metricas_sistema (
    id                  BIGSERIAL PRIMARY KEY,
    quando              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cpu_pct             DOUBLE PRECISION NOT NULL DEFAULT 0,
    ram_pct             DOUBLE PRECISION NOT NULL DEFAULT 0,
    ram_usada_mb        DOUBLE PRECISION NOT NULL DEFAULT 0,
    ram_total_mb        DOUBLE PRECISION NOT NULL DEFAULT 0,
    disco_usado_mb      DOUBLE PRECISION NOT NULL DEFAULT 0,
    disco_total_mb      DOUBLE PRECISION NOT NULL DEFAULT 0,
    tabelas_bytes       BIGINT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_metricas_sistema_quando ON metricas_sistema (quando DESC);

CREATE TABLE IF NOT EXISTS metricas_tabelas_dia (
    dia                 DATE NOT NULL,
    tabela              TEXT NOT NULL,
    bytes               BIGINT NOT NULL DEFAULT 0,
    linhas              BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (dia, tabela)
);

-- Capacidade por câmera (amostras e testes 1/2/4)
CREATE TABLE IF NOT EXISTS metricas_desempenho (
    id                  BIGSERIAL PRIMARY KEY,
    quando              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    n_cameras           INTEGER NOT NULL DEFAULT 0,
    cpu_processo        DOUBLE PRECISION NOT NULL DEFAULT 0,
    ram_app_mb          DOUBLE PRECISION NOT NULL DEFAULT 0,
    latencia_ms_media   DOUBLE PRECISION NOT NULL DEFAULT 0,
    fps_efetivo_medio   DOUBLE PRECISION NOT NULL DEFAULT 0,
    cameras_json        JSONB NOT NULL DEFAULT '[]'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_metricas_desempenho_quando ON metricas_desempenho (quando DESC);

CREATE TABLE IF NOT EXISTS testes_capacidade (
    n_cameras           INTEGER PRIMARY KEY,
    quando              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cpu_processo        DOUBLE PRECISION NOT NULL DEFAULT 0,
    ram_app_mb          DOUBLE PRECISION NOT NULL DEFAULT 0,
    latencia_ms_media   DOUBLE PRECISION NOT NULL DEFAULT 0,
    fps_efetivo_medio   DOUBLE PRECISION NOT NULL DEFAULT 0,
    cameras_json        JSONB NOT NULL DEFAULT '[]'::jsonb
);
