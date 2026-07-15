import { PrimaryCategory } from './article.model';

/** One row from GET /api/map-summary (country_code × primary_category). */
export interface MapSummaryRow {
  country_code: string;
  primary_category: PrimaryCategory;
  article_count: number;
  read_count: number;
  latitude: number;
  longitude: number;
}
