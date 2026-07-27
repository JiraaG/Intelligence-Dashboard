import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import {
  Article,
  ArticlesPage,
  ArticlesPageFilters,
  CountrySummary,
  PrimaryCategory,
  Sentiment,
} from '../models/article.model';
import { MapSummaryRow } from '../models/map-summary.model';
import { MapRelationRow } from '../models/map-relation.model';
import {
  MetricsSummary,
  MetricsStatus,
  MetricsByFeed,
  FeedsResponse,
  FeedToggleResponse,
} from '../models/metrics.model';

/** Data ISO di generazione fixture — usata come ``published_at``, non come filtro query. */
const TODAY = new Date().toISOString().split('T')[0];

/**
 * Fixture offline per cluster/hatching/spiderfy senza backend.
 * Attivo solo se ``MOCK_MODE=true`` (mai fallback silenzioso da ArticleService).
 *
 * @see skill spatial-data-mocking.
 */ export const MOCK_ARTICLES: Article[] = [
  // --- CLUSTER TEST: Due articoli in Germania (città diverse) ---
  {
    id: 1,
    title: 'TSMC inaugura la prima fab europea a Dresda',
    summary:
      'TSMC ha inaugurato in Sassonia il primo impianto produttivo europeo per chip a 28nm. La Germania consolida il suo ruolo di hub semiconduttore del continente.',
    published_at: TODAY,
    source_url: 'https://example.com/tsmc-dresden',
    country_code: 'DE',
    latitude: 51.0504,
    longitude: 13.7373,
    companies_involved: ['TSMC', 'Infineon', 'Bosch'],
    tags: ['Chip', 'Semiconduttori', 'Germania', 'Fab'],
    primary_category: 'Tecnologia',
    sentiment: 'Positivo',
    relevance_level: 4,
    infrastructural_entities: ['TSMC Dresden Fab', 'Silicon Saxony Campus'],
    feed_title: 'Silicon Saxony News',
    related_countries: [],
    is_read: false,
    is_saved: true,
  },
  {
    id: 2,
    title: 'Siemens Energy amplia la rete di trasmissione ad alta tensione in Baviera',
    summary:
      'Siemens Energy ha completato il potenziamento di 800km di linee di trasmissione nel sud della Germania.',
    published_at: TODAY,
    source_url: 'https://example.com/siemens-baviera',
    country_code: 'DE',
    latitude: 48.1351,
    longitude: 11.582,
    companies_involved: ['Siemens Energy', 'Tennet'],
    tags: ['Energia', 'Grid', 'Germania', 'Rinnovabili'],
    primary_category: 'Energia',
    sentiment: 'Neutrale',
    relevance_level: 3,
    infrastructural_entities: ['Rete di trasmissione 380kV Baviera', 'Interconnessione DE-AT'],
    feed_title: 'Bavarian Grid Monitor',
    related_countries: ['AT'],
    is_read: true,
    is_saved: false,
  },
  // --- CLUSTER TEST: Due articoli vicini in Ucraina ---
  {
    id: 3,
    title: 'Centrale di Zaporizhzhia: rapporto IAEA sui sistemi di raffreddamento',
    summary:
      "L'IAEA certifica il funzionamento dei sistemi di backup della centrale. La missione permanente rimane sul posto.",
    published_at: TODAY,
    source_url: 'https://example.com/zaporizhzhia-iaea',
    country_code: 'UA',
    latitude: 47.5083,
    longitude: 34.3981,
    companies_involved: ['IAEA', 'Energoatom', 'Rosatom'],
    tags: ['Nucleare', 'IAEA', 'Ucraina', 'Sicurezza'],
    primary_category: 'Nucleare',
    sentiment: 'Negativo',
    relevance_level: 5,
    infrastructural_entities: [
      'Centrale Nucleare di Zaporizhzhia',
      'Sito di stoccaggio combustibile',
    ],
    feed_title: 'IAEA Bulletin',
    related_countries: [],
    is_read: false,
    is_saved: true,
  },
  {
    id: 4,
    title: "Diga di Kakhovka: progetto di ricostruzione approvato dall'UE",
    summary:
      "L'Unione Europea ha approvato 2.3 miliardi di euro per la ricostruzione dell'infrastruttura idrica nel sud dell'Ucraina.",
    published_at: TODAY,
    source_url: 'https://example.com/kakhovka-ue',
    country_code: 'UA',
    latitude: 47.3606,
    longitude: 33.475,
    companies_involved: ['European Commission', 'EBRD'],
    tags: ['Acqua', 'Diga', 'Ucraina', 'Ricostruzione'],
    primary_category: 'Ambiente',
    sentiment: 'Positivo',
    relevance_level: 3,
    infrastructural_entities: ['Diga di Kakhovka', 'Serbatoio di Kakhovka'],
    feed_title: 'EU Reconstruction Index',
    related_countries: [],
    is_read: false,
    is_saved: false,
  },
  // --- SINGOLI MARKER: Test hatching multi-categoria ---
  {
    id: 5,
    title: 'Iran accelera arricchimento uranio, IAEA convoca riunione di emergenza',
    summary: 'Le centrifughe iraniane hanno raggiunto una capacità di arricchimento record al 60%.',
    published_at: TODAY,
    source_url: 'https://example.com/iran-uranium',
    country_code: 'IR',
    latitude: 32.4279,
    longitude: 53.688,
    companies_involved: ['IAEA'],
    tags: ['Nucleare', 'Iran', 'IAEA', 'ONU', 'Geopolitica'],
    primary_category: 'Nucleare',
    sentiment: 'Negativo',
    relevance_level: 5,
    infrastructural_entities: ['Impianto di Natanz', 'Impianto di Fordow'],
    feed_title: 'United Nations Security News',
    related_countries: ['US', 'RU'],
    is_read: false,
    is_saved: false,
  },
  {
    id: 6,
    title: 'Samsung avvia produzione chip 2nm a Seoul: sfida diretta a TSMC',
    summary:
      'Samsung Electronics ha avviato la produzione di massa di chip a 2nm nel suo impianto di Hwaseong.',
    published_at: TODAY,
    source_url: 'https://example.com/samsung-2nm',
    country_code: 'KR',
    latitude: 37.5665,
    longitude: 126.978,
    companies_involved: ['Samsung Electronics', 'TSMC', 'Apple'],
    tags: ['Chip', 'Samsung', 'Corea del Sud', '2nm', 'Semiconduttori'],
    primary_category: 'Tecnologia',
    sentiment: 'Positivo',
    relevance_level: 4,
    infrastructural_entities: ['Samsung Fab Hwaseong', 'Samsung R&D Campus Suwon'],
    feed_title: 'Korea Tech Herald',
    related_countries: [],
    is_read: false,
    is_saved: true,
  },
  {
    id: 7,
    title: "Pipeline TAP: record storico di esportazione gas dall'Azerbaigian all'Europa",
    summary:
      'Il gasdotto Trans-Adriatico ha trasportato 12 miliardi di m³ nel primo semestre 2026.',
    published_at: TODAY,
    source_url: 'https://example.com/tap-record',
    country_code: 'AZ',
    latitude: 40.1431,
    longitude: 47.5769,
    companies_involved: ['TAP AG', 'SOCAR', 'BP', 'SNAM'],
    tags: ['Energia', 'Gas', 'Pipeline', 'Azerbaijan', 'Europa'],
    primary_category: 'Energia',
    sentiment: 'Positivo',
    relevance_level: 4,
    infrastructural_entities: [
      'Trans-Adriatic Pipeline (TAP)',
      'Terminale di Melendugno',
      'Campo di Shah Deniz II',
    ],
    feed_title: 'Trans-Adriatic Pipeline Press',
    related_countries: ['IT'],
    is_read: false,
    is_saved: false,
  },
];

/**
 * Mock offline: stessa forma API (map-summary + envelope articles) senza HTTP.
 *
 * Nota C-07: il parametro ``date`` è accettato ma **ignorato** (``void date``) —
 * le fixture restano sempre ``MOCK_ARTICLES``/``TODAY``. Lo skill checklist che
 * prevede «data passata → 0 notizie» non riflette questo codice.
 */
@Injectable({ providedIn: 'root' })
export class ArticleMockService {
  /**
   * Aggrega country×category con lat/lon media progressiva e filtri sentiment.
   * ``date`` ignorato (vedi nota classe / C-07).
   */
  getMapSummary(
    date: string,
    sentiment?: Sentiment | Sentiment[] | null,
  ): Observable<MapSummaryRow[]> {
    void date;
    let arts = MOCK_ARTICLES;
    if (Array.isArray(sentiment) && sentiment.length > 0) {
      const allowed = new Set(sentiment);
      arts = arts.filter((a) => allowed.has(a.sentiment));
    } else if (typeof sentiment === 'string') {
      arts = arts.filter((a) => a.sentiment === sentiment);
    }

    const grouped = new Map<string, MapSummaryRow>();
    for (const a of arts) {
      const key = `${a.country_code}|${a.primary_category}`;
      const existing = grouped.get(key);
      if (existing) {
        existing.article_count += 1;
        if (a.is_read) existing.read_count += 1;
        existing.latitude =
          (existing.latitude * (existing.article_count - 1) + a.latitude) / existing.article_count;
        existing.longitude =
          (existing.longitude * (existing.article_count - 1) + a.longitude) /
          existing.article_count;
      } else {
        grouped.set(key, {
          country_code: a.country_code,
          primary_category: a.primary_category,
          article_count: 1,
          read_count: a.is_read ? 1 : 0,
          latitude: a.latitude,
          longitude: a.longitude,
        });
      }
    }
    return of(
      [...grouped.values()].sort((a, b) => {
        const c = a.country_code.localeCompare(b.country_code);
        return c !== 0 ? c : a.primary_category.localeCompare(b.primary_category);
      }),
    );
  }

  /**
   * Envelope keyset mock: sort id DESC, cursor = id strettamente minore, limit ≤100.
   * Filtri country/category/sentiment/relevance; ``date`` non applicato.
   * Con ``saved=true`` filtra solo ``is_saved``.
   */
  getArticlesPage(filters: ArticlesPageFilters): Observable<ArticlesPage> {
    const limit = Math.min(Math.max(filters.limit ?? 50, 1), 100);
    const allMatching = MOCK_ARTICLES.filter((a) => {
      if (filters.saved && !a.is_saved) return false;
      if (filters.country && a.country_code !== filters.country.toUpperCase()) return false;
      if (filters.category && a.primary_category !== filters.category) return false;
      if (filters.sentiment && a.sentiment !== filters.sentiment) return false;
      if (filters.relevance_level != null && a.relevance_level !== filters.relevance_level)
        return false;
      return true;
    });
    const sorted = [...allMatching].sort((a, b) => b.id - a.id);
    const afterCursor =
      filters.cursor != null ? sorted.filter((a) => a.id < filters.cursor!) : sorted;
    const pageItems = afterCursor.slice(0, limit);
    const hasMore = afterCursor.length > limit;
    return of({
      items: pageItems,
      next_cursor: hasMore && pageItems.length > 0 ? pageItems[pageItems.length - 1].id : null,
      total: allMatching.length,
    });
  }

  /**
   * Aggregato salvati (no date): stessa forma di map-summary su ``is_saved``.
   */
  getSavedSummary(sentiment?: Sentiment | Sentiment[] | null): Observable<MapSummaryRow[]> {
    let arts = MOCK_ARTICLES.filter((a) => !!a.is_saved);
    if (Array.isArray(sentiment) && sentiment.length > 0) {
      const allowed = new Set(sentiment);
      arts = arts.filter((a) => allowed.has(a.sentiment));
    } else if (typeof sentiment === 'string') {
      arts = arts.filter((a) => a.sentiment === sentiment);
    }

    const grouped = new Map<string, MapSummaryRow>();
    for (const a of arts) {
      const key = `${a.country_code}|${a.primary_category}`;
      const existing = grouped.get(key);
      if (existing) {
        existing.article_count += 1;
        if (a.is_read) existing.read_count += 1;
        existing.latitude =
          (existing.latitude * (existing.article_count - 1) + a.latitude) / existing.article_count;
        existing.longitude =
          (existing.longitude * (existing.article_count - 1) + a.longitude) /
          existing.article_count;
      } else {
        grouped.set(key, {
          country_code: a.country_code,
          primary_category: a.primary_category,
          article_count: 1,
          read_count: a.is_read ? 1 : 0,
          latitude: a.latitude,
          longitude: a.longitude,
        });
      }
    }
    return of(
      [...grouped.values()].sort((a, b) => {
        const c = a.country_code.localeCompare(b.country_code);
        return c !== 0 ? c : a.primary_category.localeCompare(b.primary_category);
      }),
    );
  }

  /**
   * Deriva le relazioni undirected geopolitiche basate sui paesi secondari degli articoli mock.
   * ``date`` ignorato.
   */
  getMapRelations(
    date: string,
    sentiment?: Sentiment | Sentiment[] | null,
  ): Observable<MapRelationRow[]> {
    void date;
    let arts = MOCK_ARTICLES;
    if (Array.isArray(sentiment) && sentiment.length > 0) {
      const allowed = new Set(sentiment);
      arts = arts.filter((a) => allowed.has(a.sentiment));
    } else if (typeof sentiment === 'string') {
      arts = arts.filter((a) => a.sentiment === sentiment);
    }

    const grouped = new Map<string, MapRelationRow>();
    for (const a of arts) {
      if (!a.related_countries || a.related_countries.length === 0) continue;
      if (a.country_code === 'XX') continue;
      for (const rel of a.related_countries) {
        if (rel === 'XX' || rel === a.country_code) continue;
        const source = a.country_code < rel ? a.country_code : rel;
        const target = a.country_code < rel ? rel : a.country_code;
        const key = `${source}|${target}|${a.primary_category}`;
        const existing = grouped.get(key);
        if (existing) {
          existing.volume += 1;
          if (existing.article_ids && !existing.article_ids.includes(a.id)) {
            existing.article_ids.push(a.id);
          }
        } else {
          grouped.set(key, {
            source_country: source,
            target_country: target,
            primary_category: a.primary_category,
            volume: 1,
            article_ids: [a.id],
          });
        }
      }
    }
    return of([...grouped.values()].sort((a, b) => b.volume - a.volume));
  }

  /** Helper legacy: tutti i mock (``date`` ignorato). */
  getArticles(date: string): Observable<Article[]> {
    void date;
    return of(MOCK_ARTICLES);
  }

  /** Rollup CountrySummary da fixture (``date`` ignorato). */
  getCountries(date: string): Observable<CountrySummary[]> {
    void date;
    const grouped = new Map<string, { cats: Set<string>; count: number; read: number }>();
    for (const a of MOCK_ARTICLES) {
      const entry = grouped.get(a.country_code) ?? { cats: new Set<string>(), count: 0, read: 0 };
      entry.cats.add(a.primary_category);
      entry.count++;
      if (a.is_read) entry.read++;
      grouped.set(a.country_code, entry);
    }
    const result: CountrySummary[] = [];
    grouped.forEach((v, k) => {
      result.push({
        country_code: k,
        categories: [...v.cats] as PrimaryCategory[],
        article_count: v.count,
        read_count: v.read,
      });
    });
    return of(result);
  }

  getMetricsSummary(fromDate?: string, toDate?: string): Observable<MetricsSummary> {
    void fromDate;
    void toDate;
    return of({
      from: TODAY,
      to: TODAY,
      total_articles: 7,
      total_clean_chars: 14200,
      total_clean_words: 2100,
      avg_pipeline_latency_ms: 1150.5,
      avg_embedding_time_ms: 45.2,
      llm: {
        total_requests: 7,
        total_prompt_tokens: 8400,
        total_completion_tokens: 2450,
        total_cached_prompt_tokens: 5600,
        cache_hit_rate_pct: 66.67,
        avg_execution_time_ms: 890.0,
        total_estimated_cost_usd: 0.00105,
        models_breakdown: [
          {
            model: 'deepseek-v4-flash',
            reasoning_effort: 'max',
            provider: 'deepseek',
            requests_count: 276,
            prompt_tokens: 240000,
            completion_tokens: 65000,
            cached_tokens: 160000,
            total_tokens: 305000,
            estimated_cost_usd: 0.12,
            articles_count: 276,
          },
          {
            model: 'deepseek-v4-flash',
            reasoning_effort: 'high',
            provider: 'deepseek',
            requests_count: 549,
            prompt_tokens: 30000,
            completion_tokens: 5000,
            cached_tokens: 20000,
            total_tokens: 35000,
            estimated_cost_usd: 0.0129,
            articles_count: 10,
          },
          {
            model: 'gemini-3.5-flash-lite',
            reasoning_effort: 'none',
            provider: 'gemini',
            requests_count: 500,
            prompt_tokens: 600000,
            completion_tokens: 180000,
            cached_tokens: 400000,
            total_tokens: 1507752,
            estimated_cost_usd: 0,
            articles_count: 468,
          },
        ],
      },
      dedup: {
        total_events: 2,
        url_exact_count: 1,
        semantic_vector_count: 1,
        content_hash_count: 0,
      },
      overall: {
        total_estimated_cost_usd: 0.191,
        total_articles: 591,
        total_requests: 852,
        total_tokens: 12863000,
        total_dedup_events: 162,
      },
    });
  }

  getMetricsStatus(): Observable<MetricsStatus> {
    return of({
      as_of: new Date().toISOString(),
      timezone: 'UTC',
      level: 'nominal',
      estimated_cost_usd_today: 0.1329,
      l1_likely_active: false,
      l1_reason: 'none',
      models: [
        {
          role: 'primary',
          lane: 'simple',
          provider: 'gemini',
          model: 'gemini-3.5-flash-lite',
          rpd_used: 468,
          rpd_limit: 500,
          cooling_down: false,
          cooldown_until: null,
          reasoning_effort: 'none',
        },
        {
          role: 'fallback',
          lane: 'simple',
          provider: 'gemini',
          model: 'gemini-3.1-flash-lite',
          rpd_used: 12,
          rpd_limit: 500,
          cooling_down: false,
          cooldown_until: null,
          reasoning_effort: 'none',
        },
        {
          role: 'complex',
          lane: 'complex',
          provider: 'deepseek',
          model: 'deepseek-v4-flash',
          rpd_used: 10,
          rpd_limit: 0,
          cooling_down: false,
          cooldown_until: null,
          reasoning_effort: 'max',
        },
      ],
      borderline: {
        model: 'deepseek-v4-flash',
        provider: 'deepseek',
        reasoning_effort: 'high',
        articles_today: 276,
        rpd_used: 276,
        rpd_limit: 0,
      },
      llm: {
        total_requests: 1325,
        total_prompt_tokens: 870000,
        total_completion_tokens: 250000,
        total_cached_prompt_tokens: 580000,
        cache_hit_rate_pct: 66.67,
        avg_execution_time_ms: 890.0,
        total_estimated_cost_usd: 0.1329,
      },
    });
  }

  getMetricsByFeed(
    fromDate?: string,
    toDate?: string,
    dateField?: 'published_at' | 'created_at',
  ): Observable<MetricsByFeed> {
    void dateField;
    const from = fromDate || TODAY;
    const to = toDate || TODAY;
    return of({
      from,
      to,
      items: [
        {
          feed_id: 1,
          feed_domain: 'bbc.com',
          feed_title: 'BBC News — World',
          article_count: 4,
          total_clean_chars: 8200,
          avg_clean_chars: 2050,
          avg_pipeline_latency_ms: 1100,
          avg_embedding_time_ms: 40,
        },
        {
          feed_id: 2,
          feed_domain: 'theguardian.com',
          feed_title: 'The Guardian — World',
          article_count: 2,
          total_clean_chars: 4100,
          avg_clean_chars: 2050,
          avg_pipeline_latency_ms: 980,
          avg_embedding_time_ms: 38,
        },
        {
          feed_id: 3,
          feed_domain: 'npr.org',
          feed_title: 'NPR News',
          article_count: 1,
          total_clean_chars: 1900,
          avg_clean_chars: 1900,
          avg_pipeline_latency_ms: 870,
          avg_embedding_time_ms: 35,
        },
      ],
    });
  }

  getFeeds(): Observable<FeedsResponse> {
    return of({
      active_count: 3,
      total_count: 4,
      error_count: 1,
      groups: [
        {
          category: 'BBC News',
          feeds: [
            {
              id: 1,
              title: 'BBC News — World',
              feed_url: 'https://feeds.bbci.co.uk/news/world/rss.xml',
              site_url: 'https://www.bbc.com/news',
              category: 'BBC News',
              scraper_rules: '#main-content',
              crawler: true,
              disabled: false,
              enabled_in_seed: true,
              in_seed: true,
              parsing_error_count: 0,
              parsing_error_msg: '',
              checked_at: new Date().toISOString(),
              next_check_at: null,
            },
            {
              id: 4,
              title: 'BBC News — Technology',
              feed_url: 'https://feeds.bbci.co.uk/news/technology/rss.xml',
              site_url: 'https://www.bbc.com/news/technology',
              category: 'BBC News',
              scraper_rules: '#main-content',
              crawler: true,
              disabled: true,
              enabled_in_seed: true,
              in_seed: true,
              parsing_error_count: 0,
              parsing_error_msg: '',
              checked_at: null,
              next_check_at: null,
            },
          ],
        },
        {
          category: 'The Guardian',
          feeds: [
            {
              id: 2,
              title: 'The Guardian — World',
              feed_url: 'https://www.theguardian.com/world/rss',
              site_url: 'https://www.theguardian.com/world',
              category: 'The Guardian',
              scraper_rules: 'article',
              crawler: true,
              disabled: false,
              enabled_in_seed: true,
              in_seed: true,
              parsing_error_count: 2,
              parsing_error_msg: 'timeout fetching feed',
              checked_at: new Date().toISOString(),
              next_check_at: null,
            },
          ],
        },
        {
          category: 'NPR',
          feeds: [
            {
              id: 3,
              title: 'NPR News',
              feed_url: 'https://feeds.npr.org/1001/rss.xml',
              site_url: 'https://www.npr.org',
              category: 'NPR',
              scraper_rules: '.storytext',
              crawler: true,
              disabled: false,
              enabled_in_seed: true,
              in_seed: true,
              parsing_error_count: 0,
              parsing_error_msg: '',
              checked_at: new Date().toISOString(),
              next_check_at: null,
            },
          ],
        },
      ],
    });
  }

  toggleFeed(feedId: number, disabled: boolean): Observable<FeedToggleResponse> {
    return of({ id: feedId, disabled, status: 'ok' });
  }
}
