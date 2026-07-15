-- 007_articles_query_indexes.sql — Keyset + map-summary indexes for day-scoped queries.

CREATE INDEX IF NOT EXISTS idx_articles_published_id ON articles (published_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_articles_pub_country_cat ON articles (published_at, country_code, primary_category);
