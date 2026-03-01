export type RouterAnalyticsRange = 'realtime' | '1h' | '8h' | '24h' | '7d' | '30d';

export type RouterAnalyticsGranularity = '1m' | '5m' | '15m' | '1h';

export type RouterAnalyticsQuery = {
  range?: RouterAnalyticsRange;
  orgId?: number;
  provider?: string;
  model?: string;
  tokenId?: number;
  granularity?: RouterAnalyticsGranularity;
};

export type RouterAnalyticsDataWindow = {
  start: string;
  end: string;
  range: RouterAnalyticsRange;
};

export type RouterAnalyticsSeriesPoint = {
  ts: string;
  provider?: string | null;
  model?: string | null;
  requests: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  avg_latency_ms?: number | null;
};

export type RouterAnalyticsBreakdownRow = {
  key: string;
  label?: string | null;
  requests: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  errors: number;
  avg_latency_ms?: number | null;
};

export type RouterAnalyticsStatusKpis = {
  requests: number;
  prompt_tokens: number;
  generated_tokens: number;
  total_tokens: number;
  avg_latency_ms?: number | null;
  avg_gen_toks_per_s?: number | null;
};

export type RouterAnalyticsStatusResponse = {
  kpis: RouterAnalyticsStatusKpis;
  series: RouterAnalyticsSeriesPoint[];
  providers_available: number;
  providers_online: number;
  generated_at: string;
  data_window: RouterAnalyticsDataWindow;
  stale_seconds?: number | null;
  partial?: boolean;
  warnings?: string[] | null;
};

export type RouterAnalyticsBreakdownsResponse = {
  providers: RouterAnalyticsBreakdownRow[];
  models: RouterAnalyticsBreakdownRow[];
  token_names: RouterAnalyticsBreakdownRow[];
  remote_ips: RouterAnalyticsBreakdownRow[];
  user_agents: RouterAnalyticsBreakdownRow[];
  generated_at: string;
  data_window: RouterAnalyticsDataWindow;
  stale_seconds?: number | null;
  partial?: boolean;
  warnings?: string[] | null;
};

export type RouterAnalyticsMetaOption = {
  value: string;
  label: string;
};

export type RouterAnalyticsMetaResponse = {
  providers: RouterAnalyticsMetaOption[];
  models: RouterAnalyticsMetaOption[];
  tokens: RouterAnalyticsMetaOption[];
  ranges: RouterAnalyticsRange[];
  granularities: RouterAnalyticsGranularity[];
  generated_at: string;
};

export type RouterAnalyticsQuotaMetric = {
  used: number;
  limit: number;
  utilization_pct?: number | null;
  exceeded: boolean;
};

export type RouterAnalyticsQuotaRow = {
  key_id: number;
  token_name: string;
  requests: number;
  total_tokens: number;
  total_cost_usd: number;
  day_tokens?: RouterAnalyticsQuotaMetric | null;
  month_tokens?: RouterAnalyticsQuotaMetric | null;
  day_usd?: RouterAnalyticsQuotaMetric | null;
  month_usd?: RouterAnalyticsQuotaMetric | null;
  over_budget: boolean;
  reasons?: string[] | null;
  last_seen_at?: string | null;
};

export type RouterAnalyticsQuotaSummary = {
  keys_total: number;
  keys_over_budget: number;
  budgeted_keys: number;
};

export type RouterAnalyticsQuotaResponse = {
  summary: RouterAnalyticsQuotaSummary;
  items: RouterAnalyticsQuotaRow[];
  generated_at: string;
  data_window: RouterAnalyticsDataWindow;
  stale_seconds?: number | null;
  partial?: boolean;
  warnings?: string[] | null;
};
