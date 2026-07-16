-- 009_llm_model_cooldown.sql — Durable per-model LLM cooldown (24h hard-fail)
-- Used by classification cascade: skip models until until_ts; shared across lanes.

CREATE TABLE IF NOT EXISTS llm_model_cooldown (
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    until_ts TIMESTAMPTZ NOT NULL,
    reason TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (provider, model)
);

CREATE INDEX IF NOT EXISTS idx_llm_model_cooldown_until_ts
    ON llm_model_cooldown (until_ts);
