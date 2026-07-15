import {
  Article,
  PrimaryCategory,
  Sentiment,
} from './article.model';

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

export function parseArticlesDto(payload: unknown): Article[] {
  if (!Array.isArray(payload)) {
    throw new Error('Articles payload must be an array');
  }
  const articles: Article[] = [];
  for (const item of payload) {
    if (!isArticleDto(item)) {
      throw new Error('Invalid article DTO in API payload');
    }
    articles.push(item);
  }
  return articles;
}
