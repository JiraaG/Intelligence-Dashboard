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

  // ─── FINOPS & TRACCIAMENTO METRICHE (Phase 013 + W2) ─────────────────────────
  feed_id?:                 number | null;
  feed_domain?:             string | null;
  classification_lane?:     string | null;
  classified_by_model?:     string | null;
  classified_by_provider?:  string | null;
  was_escalated?:           boolean | null;
  pipeline_latency_ms?:     number | null;
  embedding_time_ms?:        number | null;
  clean_text_chars?:        number | null;
  clean_text_words?:        number | null;
  prompt_tokens?:           number | null;
  completion_tokens?:       number | null;
  cached_prompt_tokens?:    number | null;
  estimated_cost_usd?:      number | null;
  llm_execution_time_ms?:   number | null;
  llm_request_count?:       number | null;
  feed_url?:                string | null;
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
