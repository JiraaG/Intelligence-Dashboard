-- 006_quota_ledger_legacy_nulls.sql — Relax legacy NOT NULL columns that Phase 2 INSERT omits.

ALTER TABLE llm_request_ledger ALTER COLUMN request_type DROP NOT NULL;
ALTER TABLE llm_request_ledger ALTER COLUMN model_name DROP NOT NULL;

-- Prefer filling legacy columns from Phase 2 fields when rows are written later;
-- existing reserved rows may already have nulls after 005.
UPDATE llm_request_ledger
SET request_type = COALESCE(request_type, purpose, 'classify')
WHERE request_type IS NULL;

UPDATE llm_request_ledger
SET model_name = COALESCE(model_name, model, 'unknown')
WHERE model_name IS NULL;
