import {
  Article,
  ArticlesPage,
  PrimaryCategory,
  Sentiment,
} from './article.model';
import { MapSummaryRow } from './map-summary.model';

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
 * Runtime validation for API article DTOs before they reach map/template code.
 * FE arrays (`companies_involved`, `tags`, `infrastructural_entities`) come from
 * SQL `array_agg` — do not confuse with Pydantic CSV `str` on the Gemini schema.
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
  if (row['is_read'] !== undefined && typeof row['is_read'] !== 'boolean') return false;

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
 * Accepts Phase 5 envelope `{ items, next_cursor, total }` (preferred) or a legacy bare array.
 * Invalid shapes throw; callers may catch and surface via StateService.error.
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
