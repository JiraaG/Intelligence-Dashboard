-- 001_initial.sql — Schema base Radar Informativo Globale
-- Tabelle articles (10 categorie), companies, tags, junction e indici.

CREATE TABLE IF NOT EXISTS articles (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    published_at DATE NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    country_code CHAR(2) NOT NULL DEFAULT 'XX',
    latitude DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    longitude DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    primary_category VARCHAR(50) NOT NULL CHECK (
        primary_category IN (
            'Nucleare',
            'Energia',
            'Infrastrutture',
            'Geopolitica',
            'Economia',
            'Tecnologia',
            'Spazio',
            'Ambiente',
            'Salute',
            'Sicurezza'
        )
    ),
    sentiment VARCHAR(20) NOT NULL CHECK (sentiment IN ('Positivo', 'Neutrale', 'Negativo')),
    relevance_level INTEGER NOT NULL CHECK (relevance_level BETWEEN 1 AND 5),
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    infrastructural_entities TEXT[] NOT NULL DEFAULT '{}',
    feed_title TEXT NOT NULL DEFAULT 'RSS Feed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS article_companies (
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    PRIMARY KEY (article_id, company_id)
);

CREATE TABLE IF NOT EXISTS article_tags (
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (article_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_geo_date ON articles (published_at, latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_articles_country_date ON articles (country_code, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles (primary_category, published_at DESC);

-- Compatibilità con database creati dal bootstrap ad-hoc precedente
ALTER TABLE articles ADD COLUMN IF NOT EXISTS infrastructural_entities TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS feed_title TEXT NOT NULL DEFAULT 'RSS Feed';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS is_read BOOLEAN NOT NULL DEFAULT FALSE;
