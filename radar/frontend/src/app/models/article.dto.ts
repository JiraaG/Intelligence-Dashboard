import {
  Article,
  ArticlesPage,
  PrimaryCategory,
  Sentiment,
} from './article.model';
import { MapSummaryRow } from './map-summary.model';
import { MapRelationRow } from './map-relation.model';

const PRIMARY_CATEGORIES: ReadonlySet<string> = new Set<PrimaryCategory>([
  'Nucleare',
  'Energia',
  'Infrastrutture',
  'Geopolitica',
  'Economia',
  'Tecnologia',
  'Spazio',
  'Ambiente',
  'Salute',
  'Sicurezza',
  'Intelligenza Artificiale',
  'Cybersecurity',
  'Finanza',
  'Difesa',
  'Materie Prime',
]);

const SENTIMENTS: ReadonlySet<string> = new Set<Sentiment>([
  'Positivo',
  'Neutrale',
  'Negativo',
]);

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

/**
 * Guard runtime DTO articolo API prima di mappa/template.
 *
 * FE: ``companies_involved`` / ``tags`` / ``infrastructural_entities`` sono
 * ``string[]`` (SQL ``array_agg``). Non confondere con Pydantic CSV ``str``
 * sullo schema Gemini lato backend.
 *
 * @see radar-api-contract; docs/03.
 */
export function isArticleDto(value: unknown): value is Article {
  if (!value || typeof value !== 'object') return false;
  const row = value as Record<string, unknown>;

  if (typeof row['id'] !== 'number' || !Number.isFinite(row['id'])) return false;
  if (typeof row['title'] !== 'string') return false;
  if (typeof row['summary'] !== 'string') return false;
  if (typeof row['published_at'] !== 'string') return false;
  if (typeof row['source_url'] !== 'string') return false;
  if (typeof row['country_code'] !== 'string') return false;
  if (!isFiniteNumber(row['latitude'])) return false;
  if (!isFiniteNumber(row['longitude'])) return false;
  if (typeof row['primary_category'] !== 'string') return false;
  if (!PRIMARY_CATEGORIES.has(row['primary_category'])) return false;
  if (typeof row['sentiment'] !== 'string') return false;
  if (!SENTIMENTS.has(row['sentiment'])) return false;
  if (!isFiniteNumber(row['relevance_level'])) return false;
  if (row['relevance_level'] < 1 || row['relevance_level'] > 5) return false;
  if (!isStringArray(row['companies_involved'])) return false;
  if (!isStringArray(row['tags'])) return false;
  if (!isStringArray(row['infrastructural_entities'])) return false;
  if (typeof row['feed_title'] !== 'string') return false;
  if (!isStringArray(row['related_countries'])) return false;
  if (row['is_read'] !== undefined && typeof row['is_read'] !== 'boolean') return false;
  if (row['is_saved'] !== undefined && typeof row['is_saved'] !== 'boolean') return false;

  // Optional FinOps checks
  if (row['feed_id'] !== undefined && row['feed_id'] !== null && typeof row['feed_id'] !== 'number') return false;
  if (row['feed_domain'] !== undefined && row['feed_domain'] !== null && typeof row['feed_domain'] !== 'string') return false;
  if (row['classification_lane'] !== undefined && row['classification_lane'] !== null && typeof row['classification_lane'] !== 'string') return false;
  if (row['classified_by_model'] !== undefined && row['classified_by_model'] !== null && typeof row['classified_by_model'] !== 'string') return false;
  if (row['classified_by_provider'] !== undefined && row['classified_by_provider'] !== null && typeof row['classified_by_provider'] !== 'string') return false;
  if (row['was_escalated'] !== undefined && row['was_escalated'] !== null && typeof row['was_escalated'] !== 'boolean') return false;
  if (row['pipeline_latency_ms'] !== undefined && row['pipeline_latency_ms'] !== null && !isFiniteNumber(row['pipeline_latency_ms'])) return false;
  if (row['embedding_time_ms'] !== undefined && row['embedding_time_ms'] !== null && !isFiniteNumber(row['embedding_time_ms'])) return false;
  if (row['clean_text_chars'] !== undefined && row['clean_text_chars'] !== null && typeof row['clean_text_chars'] !== 'number') return false;
  if (row['clean_text_words'] !== undefined && row['clean_text_words'] !== null && typeof row['clean_text_words'] !== 'number') return false;
  if (row['prompt_tokens'] !== undefined && row['prompt_tokens'] !== null && typeof row['prompt_tokens'] !== 'number') return false;
  if (row['completion_tokens'] !== undefined && row['completion_tokens'] !== null && typeof row['completion_tokens'] !== 'number') return false;
  if (row['cached_prompt_tokens'] !== undefined && row['cached_prompt_tokens'] !== null && typeof row['cached_prompt_tokens'] !== 'number') return false;
  if (row['estimated_cost_usd'] !== undefined && row['estimated_cost_usd'] !== null && !isFiniteNumber(row['estimated_cost_usd'])) return false;
  if (row['llm_execution_time_ms'] !== undefined && row['llm_execution_time_ms'] !== null && !isFiniteNumber(row['llm_execution_time_ms'])) return false;
  if (row['llm_request_count'] !== undefined && row['llm_request_count'] !== null && typeof row['llm_request_count'] !== 'number') return false;
  if (row['feed_url'] !== undefined && row['feed_url'] !== null && typeof row['feed_url'] !== 'string') return false;

  return true;
}

function parseArticleArray(items: unknown[]): Article[] {
  const articles: Article[] = [];
  for (const item of items) {
    if (!isArticleDto(item)) {
      throw new Error('Invalid article DTO in API payload');
    }
    articles.push(item);
  }
  return articles;
}

/**
 * Accetta envelope Phase 5 ``{ items, next_cursor, total }`` oppure array nudo legacy.
 * Shape invalida → throw (caller → StateService.error). ``ArticleService`` usa
 * di preferenza ``parseArticlesPageDto`` sull’envelope.
 */
export function parseArticlesDto(payload: unknown): Article[] {
  if (Array.isArray(payload)) {
    return parseArticleArray(payload);
  }
  if (payload && typeof payload === 'object' && Array.isArray((payload as Record<string, unknown>)['items'])) {
    return parseArticlesPageDto(payload).items;
  }
  throw new Error('Articles payload must be an array or { items, next_cursor, total } envelope');
}

/**
 * Parser envelope paginato Phase 5 (SoT API).
 * ``next_cursor``: number finito o null; ``total`` obbligatorio finito.
 */
export function parseArticlesPageDto(payload: unknown): ArticlesPage {
  if (!payload || typeof payload !== 'object') {
    throw new Error('Articles page payload must be an object');
  }
  const row = payload as Record<string, unknown>;
  if (!Array.isArray(row['items'])) {
    throw new Error('Articles page payload missing items array');
  }
  const next = row['next_cursor'];
  if (next !== null && next !== undefined && !(typeof next === 'number' && Number.isFinite(next))) {
    throw new Error('Articles page next_cursor must be number|null');
  }
  if (!isFiniteNumber(row['total'])) {
    throw new Error('Articles page total must be a finite number');
  }
  return {
    items: parseArticleArray(row['items']),
    next_cursor: next === undefined ? null : (next as number | null),
    total: row['total'],
  };
}

/** Riga ``GET /api/map-summary``: country×category + count/read + lat/lon finite. */
export function isMapSummaryRowDto(value: unknown): value is MapSummaryRow {
  if (!value || typeof value !== 'object') return false;
  const row = value as Record<string, unknown>;
  if (typeof row['country_code'] !== 'string') return false;
  if (typeof row['primary_category'] !== 'string') return false;
  if (!PRIMARY_CATEGORIES.has(row['primary_category'])) return false;
  if (!isFiniteNumber(row['article_count'])) return false;
  if (!isFiniteNumber(row['read_count'])) return false;
  if (!isFiniteNumber(row['latitude'])) return false;
  if (!isFiniteNumber(row['longitude'])) return false;
  return true;
}

export function parseMapSummaryDto(payload: unknown): MapSummaryRow[] {
  if (!Array.isArray(payload)) {
    throw new Error('Map-summary payload must be an array');
  }
  const rows: MapSummaryRow[] = [];
  for (const item of payload) {
    if (!isMapSummaryRowDto(item)) {
      throw new Error('Invalid map-summary DTO in API payload');
    }
    rows.push(item);
  }
  return rows;
}

export function isMapRelationRowDto(value: unknown): value is MapRelationRow {
  if (!value || typeof value !== 'object') return false;
  const row = value as Record<string, unknown>;
  if (typeof row['source_country'] !== 'string') return false;
  if (typeof row['target_country'] !== 'string') return false;
  if (typeof row['primary_category'] !== 'string') return false;
  if (!PRIMARY_CATEGORIES.has(row['primary_category'] as PrimaryCategory)) return false;
  if (!isFiniteNumber(row['volume'])) return false;
  if ('article_ids' in row && row['article_ids'] !== undefined) {
    if (!Array.isArray(row['article_ids'])) return false;
    if (!row['article_ids'].every(isFiniteNumber)) return false;
  }
  return true;
}

export function parseMapRelationsDto(payload: unknown): MapRelationRow[] {
  if (!Array.isArray(payload)) {
    throw new Error('Map-relations payload must be an array');
  }
  const rows: MapRelationRow[] = [];
  for (const item of payload) {
    if (!isMapRelationRowDto(item)) {
      throw new Error('Invalid map-relations DTO in API payload');
    }
    rows.push(item);
  }
  return rows;
}

export function parseMetricsSummaryDto(payload: unknown): any {
  if (!payload || typeof payload !== 'object') {
    throw new Error('Metrics summary payload must be an object');
  }
  return payload;
}

export function parseMetricsStatusDto(payload: unknown): any {
  if (!payload || typeof payload !== 'object') {
    throw new Error('Metrics status payload must be an object');
  }
  return payload;
}
