-- Migrazione 013: Metrics, FinOps e Feed Tracking
-- SoT: plan-audit/active/plan_impl_fase_metrics_013.md §4 + correzioni C1-C8

-- 1. articles: colonne di denormalizzazione metriche e FinOps
ALTER TABLE articles
  ADD COLUMN IF NOT EXISTS feed_id INT,
  ADD COLUMN IF NOT EXISTS feed_domain VARCHAR(255),
  ADD COLUMN IF NOT EXISTS classification_lane VARCHAR(16),
  ADD COLUMN IF NOT EXISTS classified_by_model VARCHAR(64),
  ADD COLUMN IF NOT EXISTS classified_by_provider VARCHAR(32),
  ADD COLUMN IF NOT EXISTS was_escalated BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS dedup_kind VARCHAR(32),
  ADD COLUMN IF NOT EXISTS dedup_match_article_id INT REFERENCES articles(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS dedup_action VARCHAR(32),
  ADD COLUMN IF NOT EXISTS clean_text_chars INT,
  ADD COLUMN IF NOT EXISTS clean_text_words INT,
  ADD COLUMN IF NOT EXISTS embedding_time_ms INT,
  ADD COLUMN IF NOT EXISTS pipeline_latency_ms INT,
  ADD COLUMN IF NOT EXISTS geo_resolution_method VARCHAR(32);

CREATE INDEX IF NOT EXISTS idx_articles_feed_id ON articles(feed_id);
CREATE INDEX IF NOT EXISTS idx_articles_classification_lane ON articles(classification_lane);
CREATE INDEX IF NOT EXISTS idx_articles_dedup_kind ON articles(dedup_kind);

-- 2. article_dedup_events: tipo evento, azione, feed e drop NOT NULL su cosine_distance
ALTER TABLE article_dedup_events
  ADD COLUMN IF NOT EXISTS dedup_kind VARCHAR(32) NOT NULL DEFAULT 'semantic_vector',
  ADD COLUMN IF NOT EXISTS action_taken VARCHAR(32),
  ADD COLUMN IF NOT EXISTS feed_id INT,
  ADD COLUMN IF NOT EXISTS incoming_miniflux_entry_id INT;

ALTER TABLE article_dedup_events ALTER COLUMN cosine_distance DROP NOT NULL;

-- 3. llm_request_ledger: tracciamento FinOps, timing e link articolo/entry
ALTER TABLE llm_request_ledger
  ADD COLUMN IF NOT EXISTS article_id INT REFERENCES articles(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS miniflux_entry_id INT,
  ADD COLUMN IF NOT EXISTS prompt_tokens INT,
  ADD COLUMN IF NOT EXISTS completion_tokens INT,
  ADD COLUMN IF NOT EXISTS cached_prompt_tokens INT,
  ADD COLUMN IF NOT EXISTS execution_time_ms INT,
  ADD COLUMN IF NOT EXISTS http_status INT,
  ADD COLUMN IF NOT EXISTS error_code VARCHAR(64);

CREATE INDEX IF NOT EXISTS idx_llm_ledger_article ON llm_request_ledger(article_id);
CREATE INDEX IF NOT EXISTS idx_llm_ledger_miniflux_entry ON llm_request_ledger(miniflux_entry_id);
CREATE INDEX IF NOT EXISTS idx_llm_ledger_feed_window
  ON llm_request_ledger(created_at, lane, purpose);

-- 4. article_embeddings: timing embedding
ALTER TABLE article_embeddings
  ADD COLUMN IF NOT EXISTS embedding_time_ms INT;
