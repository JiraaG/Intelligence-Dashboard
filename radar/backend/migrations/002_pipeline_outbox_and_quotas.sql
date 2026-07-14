-- 002_pipeline_outbox_and_quotas.sql — Outbox Vault (Phase 1)
-- llm_request_ledger (quote durable) è riservato alla Phase 2; qui solo article_outbox.
-- Idempotente: crea la tabella oppure aggiorna lo shape pre-restore (error_message, no payload/id).

CREATE TABLE IF NOT EXISTS article_outbox (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL UNIQUE REFERENCES articles(id) ON DELETE CASCADE,
    target_path TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '',
    payload_checksum TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'writing', 'completed', 'failed')),
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    miniflux_entry_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Upgrade da shape pre-restore: PK su article_id, colonna error_message, senza payload/id.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'article_outbox'
          AND column_name = 'error_message'
    ) THEN
        ALTER TABLE article_outbox RENAME COLUMN error_message TO last_error;
    END IF;
END $$;

ALTER TABLE article_outbox ADD COLUMN IF NOT EXISTS payload TEXT;
UPDATE article_outbox SET payload = '' WHERE payload IS NULL;
ALTER TABLE article_outbox ALTER COLUMN payload SET DEFAULT '';
ALTER TABLE article_outbox ALTER COLUMN payload SET NOT NULL;

ALTER TABLE article_outbox ADD COLUMN IF NOT EXISTS last_error TEXT;
ALTER TABLE article_outbox ADD COLUMN IF NOT EXISTS miniflux_entry_id BIGINT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'article_outbox'
          AND column_name = 'id'
    ) THEN
        ALTER TABLE article_outbox ADD COLUMN id SERIAL;
        ALTER TABLE article_outbox DROP CONSTRAINT IF EXISTS article_outbox_pkey;
        ALTER TABLE article_outbox ADD PRIMARY KEY (id);
        ALTER TABLE article_outbox ADD CONSTRAINT article_outbox_article_id_key UNIQUE (article_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_article_outbox_status
    ON article_outbox (status, updated_at ASC);

CREATE INDEX IF NOT EXISTS idx_article_outbox_miniflux_entry
    ON article_outbox (miniflux_entry_id)
    WHERE miniflux_entry_id IS NOT NULL;
