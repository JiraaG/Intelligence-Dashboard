-- Saved articles vault (cross-day bookmarks). Unread → unsave enforced in API.
ALTER TABLE articles ADD COLUMN IF NOT EXISTS is_saved BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_articles_is_saved
  ON articles (country_code)
  WHERE is_saved;
