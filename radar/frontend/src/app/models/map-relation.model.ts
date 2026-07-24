import { PrimaryCategory } from './article.model';

export interface MapRelationRow {
  source_country: string;
  target_country: string;
  primary_category: PrimaryCategory;
  volume: number;
  article_ids?: number[];
}
