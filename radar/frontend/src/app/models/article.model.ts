export type PrimaryCategory =
  | 'Nucleare'
  | 'Energia'
  | 'Infrastrutture'
  | 'Geopolitica'
  | 'Economia'
  | 'Tecnologia'
  | 'Spazio'
  | 'Ambiente'
  | 'Salute'
  | 'Sicurezza';

export type Sentiment = 'Positivo' | 'Neutrale' | 'Negativo';

// ─── ARTICOLO — allineato a GeopoliticalArticleSchema Pydantic ────────────────
export interface Article {
  id:                       number;
  title:                    string;
  summary:                  string;
  published_at:             string;           // Formato 'YYYY-MM-DD'
  source_url:               string;
  country_code:             string;           // Codice ISO Alpha-2 (es. 'DE', 'IT'). 'XX' per fallback
  latitude:                 number;
  longitude:                number;
  primary_category:         PrimaryCategory;
  sentiment:                Sentiment;
  relevance_level:          number;           // Valore tra 1 e 5
  companies_involved:       string[];         // Lista aziende estratte
  tags:                     string[];         // Tag geopolitici associati
  infrastructural_entities: string[];         // Asset fisici identificati (es. "Zaporizhzhia Nuclear Plant")
  feed_title:               string;           // Fonte di acquisizione (es. "Yahoo Finance")
  related_countries:        string[];         // ISO Alpha-2 secondari
  is_read?:                 boolean;          // Stato letto/da leggere
  is_saved?:                boolean;          // Vault salvati (cross-day)
}

/** Paginated envelope from GET /api/articles (Phase 5 breaking). */
export interface ArticlesPage {
  items: Article[];
  next_cursor: number | null;
  total: number;
}

// ─── RIEPILOGO PAESE — per hatching SVG e click-nazione ──────────────────────
export interface CountrySummary {
  country_code:  string;
  categories:    PrimaryCategory[];
  article_count: number;
  read_count?:   number;
}

// ─── FILTRI ATTIVI ─────────────────────────────────────────────────────────────
export interface ArticleFilters {
  date:             string;                 // Formato 'YYYY-MM-DD'
  sentiment?:       Sentiment[] | null;     // Filtro multiscelta per sentiment
  categories?:      PrimaryCategory[] | null; // Filtro multiscelta per categoria
}

/** Query params for a single articles page (API contract). */
export interface ArticlesPageFilters {
  date?: string;
  country?: string;
  category?: string;
  sentiment?: Sentiment;
  relevance_level?: number;
  cursor?: number;
  limit?: number;
  /** When true, API ignores date and returns only saved articles. */
  saved?: boolean;
}
