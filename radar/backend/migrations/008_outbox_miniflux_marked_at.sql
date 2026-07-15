-- 008_outbox_miniflux_marked_at.sql — Aggiunta tracking mark-read Miniflux (T-P1-03)

ALTER TABLE article_outbox
  ADD COLUMN IF NOT EXISTS miniflux_marked_at TIMESTAMPTZ NULL;

-- Backfill per evitare storm su righe storiche già completate
UPDATE article_outbox
SET miniflux_marked_at = NOW()
WHERE status = 'completed' AND miniflux_marked_at IS NULL;
