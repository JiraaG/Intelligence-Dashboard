-- 004_worker_heartbeat.sql — Singleton row for ingest-leader liveness (Phase 3 readiness).
-- Only the advisory-lock leader UPSERTs this row; /health/ready checks freshness.
-- Compatible with legacy pre-restore shape (worker_id / hostname / pid).

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'worker_heartbeat'
    ) AND EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'worker_heartbeat'
          AND column_name = 'worker_id'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'worker_heartbeat'
          AND column_name = 'id'
    ) THEN
        -- Legacy Phase-3-pre-restore table: drop and recreate singleton shape.
        DROP TABLE worker_heartbeat;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS worker_heartbeat (
    id SMALLINT PRIMARY KEY CHECK (id = 1),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'starting'
        CHECK (status IN ('starting', 'running', 'degraded', 'stopped')),
    leader_pid INTEGER,
    detail TEXT
);

-- If an older singleton table exists without status/leader_pid, add columns.
ALTER TABLE worker_heartbeat ADD COLUMN IF NOT EXISTS status TEXT;
ALTER TABLE worker_heartbeat ADD COLUMN IF NOT EXISTS leader_pid INTEGER;
ALTER TABLE worker_heartbeat ADD COLUMN IF NOT EXISTS detail TEXT;

UPDATE worker_heartbeat
SET status = 'starting'
WHERE status IS NULL;

ALTER TABLE worker_heartbeat ALTER COLUMN status SET DEFAULT 'starting';
ALTER TABLE worker_heartbeat ALTER COLUMN status SET NOT NULL;

INSERT INTO worker_heartbeat (id, status, detail)
VALUES (1, 'starting', 'awaiting leader')
ON CONFLICT (id) DO NOTHING;
