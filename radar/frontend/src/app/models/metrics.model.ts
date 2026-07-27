export interface ModelBreakdownItem {
  model: string;
  reasoning_effort?: string;
  provider?: string;
  requests_count: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  cached_tokens?: number;
  total_tokens: number;
  estimated_cost_usd?: number;
  articles_count?: number;
}

export interface MetricsSummaryLlm {
  total_requests: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_cached_prompt_tokens: number;
  cache_hit_rate_pct: number;
  avg_execution_time_ms: number | null;
  total_estimated_cost_usd?: number;
  models_breakdown?: ModelBreakdownItem[];
}

export interface MetricsSummaryDedup {
  total_events: number;
  url_exact_count: number;
  semantic_vector_count: number;
  content_hash_count: number;
}

export interface MetricsSummaryOverall {
  total_estimated_cost_usd: number;
  total_articles: number;
  total_requests: number;
  total_tokens: number;
  total_dedup_events: number;
}

export interface MetricsSummary {
  from: string;
  to: string;
  total_articles: number;
  total_clean_chars: number;
  total_clean_words: number;
  avg_pipeline_latency_ms: number | null;
  avg_embedding_time_ms: number | null;
  llm: MetricsSummaryLlm;
  dedup: MetricsSummaryDedup;
  overall?: MetricsSummaryOverall;
}

export type StatusLevel = 'nominal' | 'fallback_or_escalation' | 'degraded';

export type L1Reason = 'none' | 'primary_cooldown' | 'primary_rpd_exhausted' | 'recent_articles';

export interface ModelStatusItem {
  role: 'primary' | 'fallback' | 'complex';
  lane: 'simple' | 'complex';
  provider: string;
  model: string;
  rpd_used: number;
  rpd_limit: number;
  cooling_down: boolean;
  cooldown_until: string | null;
  reasoning_effort?: string;
}

export interface BorderlineStatusInfo {
  model: string;
  provider?: string;
  reasoning_effort: string;
  articles_today: number;
  rpd_used?: number;
  rpd_limit?: number;
}

export interface MetricsStatus {
  as_of: string;
  timezone: string;
  level: StatusLevel;
  estimated_cost_usd_today: number;
  l1_likely_active: boolean;
  l1_reason: L1Reason;
  models: ModelStatusItem[];
  borderline?: BorderlineStatusInfo;
  llm?: MetricsSummaryLlm;
}

/** Item di `GET /api/metrics/by-feed` (aggregati per feed). */
export interface MetricsByFeedItem {
  feed_id: number | null;
  feed_domain: string | null;
  feed_title: string | null;
  article_count: number;
  total_clean_chars: number;
  avg_clean_chars: number | null;
  avg_pipeline_latency_ms: number | null;
  avg_embedding_time_ms: number | null;
}

export interface MetricsByFeed {
  from: string;
  to: string;
  items: MetricsByFeedItem[];
}

/** Feed nel catalogo `GET /api/feeds`. */
export interface FeedCatalogItem {
  id: number | null;
  title: string;
  feed_url: string;
  site_url: string;
  category: string;
  scraper_rules: string;
  crawler: boolean;
  disabled: boolean;
  enabled_in_seed: boolean;
  in_seed: boolean;
  parsing_error_count: number;
  parsing_error_msg: string;
  checked_at: string | null;
  next_check_at: string | null;
}

export interface FeedCatalogGroup {
  category: string;
  feeds: FeedCatalogItem[];
}

export interface FeedsResponse {
  active_count: number;
  total_count: number;
  error_count: number;
  groups: FeedCatalogGroup[];
}

export interface FeedToggleResponse {
  id: number;
  disabled: boolean;
  status: string;
}
