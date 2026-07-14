-- 003_quota_ledger.sql — Durable LLM quota ledger (RPM / TPM / RPD)
-- Phase 2: transactional reserve before every provider attempt; update by reservation id.

CREATE TABLE IF NOT EXISTS llm_request_ledger (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reserved_tokens INTEGER NOT NULL,
    actual_tokens INTEGER NULL,
    status TEXT NOT NULL CHECK (status IN ('reserved', 'completed', 'failed', 'released')),
    model TEXT,
    purpose TEXT,
    CONSTRAINT llm_request_ledger_reserved_tokens_nonneg CHECK (reserved_tokens >= 0),
    CONSTRAINT llm_request_ledger_actual_tokens_nonneg CHECK (
        actual_tokens IS NULL OR actual_tokens >= 0
    )
);

CREATE INDEX IF NOT EXISTS idx_llm_request_ledger_created_at
    ON llm_request_ledger (created_at);

-- Window sums/counts for RPM/TPM (rolling 60s) and status filters.
CREATE INDEX IF NOT EXISTS idx_llm_request_ledger_created_status
    ON llm_request_ledger (created_at, status);
