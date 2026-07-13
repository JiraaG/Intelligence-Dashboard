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
  is_read?:                 boolean;          // Stato letto/da leggere
}

// ─── RIEPILOGO PAESE — per hatching SVG e click-nazione ──────────────────────
export interface CountrySummary {
  country_code:  string;
  categories:    PrimaryCategory[];
  article_count: number;
}

// ─── FILTRI ATTIVI ─────────────────────────────────────────────────────────────
export interface ArticleFilters {
  date:             string;                 // Formato 'YYYY-MM-DD'
  sentiment?:       Sentiment[] | null;     // Filtro multiscelta per sentiment
  categories?:      PrimaryCategory[] | null; // Filtro multiscelta per categoria
}

