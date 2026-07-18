-- 006_quota_ledger_legacy_nulls.sql — Relax legacy NOT NULL columns that Phase 2 INSERT omits.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'llm_request_ledger'
          AND column_name = 'request_type'
    ) THEN
        ALTER TABLE llm_request_ledger ALTER COLUMN request_type DROP NOT NULL;
        
        UPDATE llm_request_ledger
        SET request_type = COALESCE(request_type, purpose, 'classify')
        WHERE request_type IS NULL;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'llm_request_ledger'
          AND column_name = 'model_name'
    ) THEN
        ALTER TABLE llm_request_ledger ALTER COLUMN model_name DROP NOT NULL;
        
        UPDATE llm_request_ledger
        SET model_name = COALESCE(model_name, model, 'unknown')
        WHERE model_name IS NULL;
    END IF;
END $$;
