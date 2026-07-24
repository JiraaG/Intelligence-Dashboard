-- 015_llm_ledger_reasoning_effort.sql — Tracciamento FinOps Reasoning Effort per-request
-- SoT: FinOps Reasoning Effort breakdown (high/medium/none/low)

ALTER TABLE llm_request_ledger
  ADD COLUMN IF NOT EXISTS reasoning_effort TEXT DEFAULT 'none';

UPDATE llm_request_ledger
  SET reasoning_effort = 'none'
  WHERE reasoning_effort IS NULL;

CREATE INDEX IF NOT EXISTS idx_llm_ledger_model_effort
  ON llm_request_ledger(model, reasoning_effort);
