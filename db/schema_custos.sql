-- Ledger de custos de comunicação (e-mail, WhatsApp, tokens Stive/OpenAI)

CREATE TABLE IF NOT EXISTS custos_mensagens (
    id                  BIGSERIAL PRIMARY KEY,
    cliente_documento   VARCHAR(20) NOT NULL DEFAULT '',
    canal               TEXT NOT NULL DEFAULT '',   -- email | whatsapp | openai
    direcao             TEXT NOT NULL DEFAULT '',   -- in | out | interno
    unidades            DOUBLE PRECISION NOT NULL DEFAULT 1,
    usd_estimado        DOUBLE PRECISION NOT NULL DEFAULT 0,
    detalhe             TEXT NOT NULL DEFAULT '',
    referencia          TEXT NOT NULL DEFAULT '',
    quando              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_custos_cli_quando ON custos_mensagens (cliente_documento, quando DESC);
CREATE INDEX IF NOT EXISTS ix_custos_canal ON custos_mensagens (canal, quando DESC);
