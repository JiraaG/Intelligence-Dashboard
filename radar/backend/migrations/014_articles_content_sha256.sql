-- Migrazione 014: aggiunta colonna content_sha256 su articles e relativo indice per FinOps M6

ALTER TABLE articles ADD COLUMN IF NOT EXISTS content_sha256 CHAR(64) NULL;

CREATE INDEX IF NOT EXISTS idx_articles_content_sha256_created_at
  ON articles (content_sha256, created_at DESC)
  WHERE content_sha256 IS NOT NULL;
