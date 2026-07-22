-- Migrazione 012: Supporto alla deduplicazione semantica e tracciamento costi LLM (pgvector).

CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Estratto del testo grezzo/pulito per confronto di qualità
ALTER TABLE articles
  ADD COLUMN IF NOT EXISTS body_excerpt VARCHAR(8000);

COMMENT ON COLUMN articles.body_excerpt IS
  'Estratto iniziale dell''articolo (max 8000 char) per il confronto di qualità LLM e anteprima';

-- 2. Estensione llm_request_ledger con lane, provider e stima costo
ALTER TABLE llm_request_ledger
  ADD COLUMN IF NOT EXISTS lane VARCHAR(32),
  ADD COLUMN IF NOT EXISTS provider VARCHAR(32),
  ADD COLUMN IF NOT EXISTS estimated_cost_usd NUMERIC(10, 6) DEFAULT 0.0;

CREATE INDEX IF NOT EXISTS idx_llm_request_ledger_created_purpose
  ON llm_request_ledger(created_at, purpose);

CREATE INDEX IF NOT EXISTS idx_llm_request_ledger_created_lane
  ON llm_request_ledger(created_at, lane);

-- 3. Tabella embeddings degli articoli (pgvector 384 dim per all-MiniLM-L6-v2)
CREATE TABLE IF NOT EXISTS article_embeddings (
    article_id INT PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,
    embedding vector(384) NOT NULL,
    model_id VARCHAR(64) NOT NULL DEFAULT 'all-MiniLM-L6-v2',
    text_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_article_embeddings_hnsw
  ON article_embeddings USING hnsw (embedding vector_cosine_ops);

-- 4. Registro eventi append-only di deduplicazione semantica e scontro di qualità
CREATE TABLE IF NOT EXISTS article_dedup_events (
    id BIGSERIAL PRIMARY KEY,
    incoming_url VARCHAR(2048) NOT NULL,
    existing_article_id INT REFERENCES articles(id) ON DELETE SET NULL,
    winner VARCHAR(16) NOT NULL, -- 'existing', 'incoming', 'keep_new'
    cosine_distance DOUBLE PRECISION NOT NULL,
    same_story BOOLEAN,
    confidence DOUBLE PRECISION,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS idx_article_dedup_events_created
  ON article_dedup_events(created_at);
