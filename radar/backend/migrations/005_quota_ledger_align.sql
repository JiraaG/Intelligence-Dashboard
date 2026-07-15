-- 005_quota_ledger_align.sql — Align legacy pre-restore llm_request_ledger to Phase 2 shape.
-- 003_quota_ledger used CREATE TABLE IF NOT EXISTS and skipped upgrades on existing tables.

ALTER TABLE llm_request_ledger ADD COLUMN IF NOT EXISTS reserved_tokens INTEGER;
ALTER TABLE llm_request_ledger ADD COLUMN IF NOT EXISTS model TEXT;
ALTER TABLE llm_request_ledger ADD COLUMN IF NOT EXISTS purpose TEXT;

-- Map legacy estimated_tokens → reserved_tokens when present.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'llm_request_ledger'
          AND column_name = 'estimated_tokens'
    ) THEN
        EXECUTE $q$
            UPDATE llm_request_ledger
            SET reserved_tokens = COALESCE(reserved_tokens, estimated_tokens, 0)
            WHERE reserved_tokens IS NULL
        $q$;
    END IF;
END $$;

UPDATE llm_request_ledger SET reserved_tokens = 0 WHERE reserved_tokens IS NULL;
ALTER TABLE llm_request_ledger ALTER COLUMN reserved_tokens SET DEFAULT 0;
ALTER TABLE llm_request_ledger ALTER COLUMN reserved_tokens SET NOT NULL;

-- Map legacy model_name → model when present.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'llm_request_ledger'
          AND column_name = 'model_name'
    ) THEN
        EXECUTE $q$
            UPDATE llm_request_ledger
            SET model = COALESCE(model, model_name)
            WHERE model IS NULL AND model_name IS NOT NULL
        $q$;
    END IF;
END $$;

-- Normalize status values used by QuotaLedger (reserved/completed/failed/released).
UPDATE llm_request_ledger
SET status = 'completed'
WHERE status NOT IN ('reserved', 'completed', 'failed', 'released');

CREATE INDEX IF NOT EXISTS idx_llm_request_ledger_created_at
    ON llm_request_ledger (created_at);

CREATE INDEX IF NOT EXISTS idx_llm_request_ledger_created_status
    ON llm_request_ledger (created_at, status);
