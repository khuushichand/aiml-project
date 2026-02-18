type RecordValue = Record<string, unknown>;

export type TrendDirection = 'up' | 'down' | 'flat';

export interface MetricTrend {
  direction: TrendDirection;
  delta: number;
  percentChange: number | null;
}

export interface DashboardOperationalKpis {
  latencyP95Ms: number | null;
  latencyTrend: MetricTrend | null;
  errorRatePct: number | null;
  errorRateTrend: MetricTrend | null;
  dailyCostUsd: number | null;
  dailyCostTrend: MetricTrend | null;
  activeJobs: number | null;
  activeJobsTrend: MetricTrend | null;
  queuedJobs: number | null;
  failedJobs: number | null;
  queueDepth: number | null;
  queueDepthTrend: MetricTrend | null;
}

export interface JobSnapshot {
  activeJobs: number;
  queuedJobs: number;
  failedJobs: number;
  queueDepth: number;
}

export interface BuildDashboardOperationalKpisInput {
  usageDaily?: unknown;
  llmUsageSummary?: unknown;
  jobsStats?: unknown;
  metricsText?: unknown;
  previousJobsSnapshot?: JobSnapshot | null;
}

export interface BuildDashboardOperationalKpisResult {
  kpis: DashboardOperationalKpis;
  jobsSnapshot: JobSnapshot | null;
}

type UsageDailyRow = {
  day: string;
  requests: number;
  errors: number;
  latencyAvgMs: number | null;
};

type LlmDailyCostRow = {
  day: string;
  totalCostUsd: number;
};

const isRecord = (value: unknown): value is RecordValue =>
  typeof value === 'object' && value !== null;

const toFiniteNumber = (value: unknown): number | null => {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return null;
  }
  return value;
};

const toNonNegativeNumber = (value: unknown): number => {
  const parsed = toFiniteNumber(value);
  if (parsed === null || parsed < 0) return 0;
  return parsed;
};

const toStringValue = (value: unknown): string => {
  if (typeof value === 'string') return value;
  if (value instanceof Date) return value.toISOString();
  return '';
};

const extractItems = (payload: unknown): unknown[] => {
  if (Array.isArray(payload)) return payload;
  if (!isRecord(payload)) return [];
  const items = payload.items;
  if (Array.isArray(items)) return items;
  return [];
};

const compareDateDesc = (a: string, b: string) => {
  const aTime = Date.parse(a);
  const bTime = Date.parse(b);
  if (Number.isFinite(aTime) && Number.isFinite(bTime)) return bTime - aTime;
  return a < b ? 1 : -1;
};

const aggregateUsageDailyRows = (payload: unknown): UsageDailyRow[] => {
  const items = extractItems(payload);
  const byDay = new Map<string, {
    requests: number;
    errors: number;
    latencyWeightedTotal: number;
    latencyWeight: number;
  }>();

  items.forEach((item) => {
    if (!isRecord(item)) return;
    const day = toStringValue(item.day);
    if (!day) return;

    const requests = toNonNegativeNumber(item.requests);
    const errors = toNonNegativeNumber(item.errors);
    const latency = toFiniteNumber(item.latency_avg_ms);

    if (!byDay.has(day)) {
      byDay.set(day, {
        requests: 0,
        errors: 0,
        latencyWeightedTotal: 0,
        latencyWeight: 0,
      });
    }

    const aggregate = byDay.get(day);
    if (!aggregate) return;

    aggregate.requests += requests;
    aggregate.errors += errors;
    if (latency !== null) {
      const weight = requests > 0 ? requests : 1;
      aggregate.latencyWeightedTotal += latency * weight;
      aggregate.latencyWeight += weight;
    }
  });

  return [...byDay.entries()]
    .map(([day, aggregate]) => ({
      day,
      requests: aggregate.requests,
      errors: aggregate.errors,
      latencyAvgMs: aggregate.latencyWeight > 0
        ? aggregate.latencyWeightedTotal / aggregate.latencyWeight
        : null,
    }))
    .sort((a, b) => compareDateDesc(a.day, b.day));
};

const extractLlmDailyCostRows = (payload: unknown): LlmDailyCostRow[] => {
  const items = extractItems(payload);

  const rows = items
    .map((item) => {
      if (!isRecord(item)) return null;
      const day = toStringValue(item.group_value);
      const totalCostUsd = toFiniteNumber(item.total_cost_usd);
      if (!day || totalCostUsd === null) return null;
      return { day, totalCostUsd };
    })
    .filter((row): row is LlmDailyCostRow => row !== null)
    .sort((a, b) => compareDateDesc(a.day, b.day));

  return rows;
};

const parseHistogramLe = (value: string): number | null => {
  const normalized = value.trim();
  if (
    normalized === '+Inf' ||
    normalized === 'Inf' ||
    normalized === '+inf' ||
    normalized === 'inf'
  ) {
    return Number.POSITIVE_INFINITY;
  }
  const parsed = Number.parseFloat(normalized);
  if (!Number.isFinite(parsed)) return null;
  return parsed;
};

export const extractRequestLatencyP95Ms = (metricsText: string): number | null => {
  const bucketPattern = /^http_request_duration_seconds_bucket\{([^}]*)\}\s+([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)$/;
  const bucketCounts = new Map<number, number>();

  metricsText.split('\n').forEach((line) => {
    const match = line.match(bucketPattern);
    if (!match) return;

    const labels = match[1];
    const count = Number.parseFloat(match[2]);
    if (!Number.isFinite(count)) return;

    const leMatch = labels.match(/(?:^|,)le="([^"]+)"/);
    if (!leMatch) return;

    const boundary = parseHistogramLe(leMatch[1]);
    if (boundary === null) return;

    bucketCounts.set(boundary, (bucketCounts.get(boundary) ?? 0) + count);
  });

  if (bucketCounts.size === 0) return null;

  const sortedBuckets = [...bucketCounts.entries()].sort((a, b) => a[0] - b[0]);
  const total = sortedBuckets.find(([le]) => !Number.isFinite(le))?.[1]
    ?? sortedBuckets[sortedBuckets.length - 1]?.[1];
  if (!Number.isFinite(total) || total <= 0) return null;

  const target = total * 0.95;
  let previousLe = 0;
  let previousCount = 0;

  for (const [le, count] of sortedBuckets) {
    if (count < target) {
      if (Number.isFinite(le)) {
        previousLe = le;
      }
      previousCount = count;
      continue;
    }

    if (!Number.isFinite(le)) {
      return Number.isFinite(previousLe) ? previousLe * 1000 : null;
    }

    const bucketSpan = count - previousCount;
    if (bucketSpan <= 0) {
      return le * 1000;
    }

    const interpolation = (target - previousCount) / bucketSpan;
    const quantileSeconds = previousLe + ((le - previousLe) * Math.min(Math.max(interpolation, 0), 1));
    return quantileSeconds * 1000;
  }

  const lastFinite = [...sortedBuckets]
    .reverse()
    .find(([le]) => Number.isFinite(le));
  return lastFinite ? lastFinite[0] * 1000 : null;
};

export const buildTrend = (
  currentValue: number | null | undefined,
  previousValue: number | null | undefined
): MetricTrend | null => {
  if (
    currentValue === null ||
    currentValue === undefined ||
    previousValue === null ||
    previousValue === undefined ||
    !Number.isFinite(currentValue) ||
    !Number.isFinite(previousValue)
  ) {
    return null;
  }

  const delta = currentValue - previousValue;
  const direction: TrendDirection = delta > 0 ? 'up' : delta < 0 ? 'down' : 'flat';
  const percentChange = Math.abs(previousValue) > Number.EPSILON
    ? (delta / Math.abs(previousValue)) * 100
    : null;

  return {
    direction,
    delta,
    percentChange,
  };
};

const extractJobSnapshot = (payload: unknown): JobSnapshot | null => {
  if (payload === undefined || payload === null) return null;

  const rows = Array.isArray(payload)
    ? payload
    : isRecord(payload) && Array.isArray(payload.items)
      ? payload.items
      : [];

  if (!Array.isArray(rows)) return null;

  const snapshot = rows.reduce(
    (acc, row) => {
      if (!isRecord(row)) return acc;
      const queued = toNonNegativeNumber(row.queued);
      const scheduled = toNonNegativeNumber(row.scheduled);
      const quarantined = toNonNegativeNumber(row.quarantined);
      const processing = toNonNegativeNumber(row.processing);

      acc.activeJobs += processing;
      acc.queuedJobs += queued + scheduled;
      acc.failedJobs += quarantined;
      acc.queueDepth += queued + scheduled + quarantined;
      return acc;
    },
    { activeJobs: 0, queuedJobs: 0, failedJobs: 0, queueDepth: 0 }
  );

  return snapshot;
};

const calculateErrorRate = (row: UsageDailyRow | undefined): number | null => {
  if (!row || row.requests <= 0) return null;
  return (row.errors / row.requests) * 100;
};

export const DEFAULT_DASHBOARD_OPERATIONAL_KPIS: DashboardOperationalKpis = {
  latencyP95Ms: null,
  latencyTrend: null,
  errorRatePct: null,
  errorRateTrend: null,
  dailyCostUsd: null,
  dailyCostTrend: null,
  activeJobs: null,
  activeJobsTrend: null,
  queuedJobs: null,
  failedJobs: null,
  queueDepth: null,
  queueDepthTrend: null,
};

export const buildDashboardOperationalKpis = ({
  usageDaily,
  llmUsageSummary,
  jobsStats,
  metricsText,
  previousJobsSnapshot = null,
}: BuildDashboardOperationalKpisInput): BuildDashboardOperationalKpisResult => {
  const usageByDay = aggregateUsageDailyRows(usageDaily);
  const latestUsage = usageByDay[0];
  const previousUsage = usageByDay[1];

  const latestErrorRate = calculateErrorRate(latestUsage);
  const previousErrorRate = calculateErrorRate(previousUsage);

  const llmDailyCosts = extractLlmDailyCostRows(llmUsageSummary);
  const latestCostRow = llmDailyCosts[0];
  const previousCostRow = llmDailyCosts[1];

  const jobsSnapshot = extractJobSnapshot(jobsStats);
  // TODO(hci-01-stage1): Prefer direct percentile fields from /admin/stats when backend exposes them.
  const latencyP95Ms = typeof metricsText === 'string'
    ? extractRequestLatencyP95Ms(metricsText)
    : null;

  const kpis: DashboardOperationalKpis = {
    latencyP95Ms,
    latencyTrend: latencyP95Ms === null
      ? null
      : buildTrend(latestUsage?.latencyAvgMs, previousUsage?.latencyAvgMs),
    errorRatePct: latestErrorRate,
    errorRateTrend: buildTrend(latestErrorRate, previousErrorRate),
    dailyCostUsd: latestCostRow?.totalCostUsd ?? null,
    dailyCostTrend: buildTrend(latestCostRow?.totalCostUsd, previousCostRow?.totalCostUsd),
    activeJobs: jobsSnapshot?.activeJobs ?? null,
    activeJobsTrend: buildTrend(jobsSnapshot?.activeJobs, previousJobsSnapshot?.activeJobs),
    queuedJobs: jobsSnapshot?.queuedJobs ?? null,
    failedJobs: jobsSnapshot?.failedJobs ?? null,
    queueDepth: jobsSnapshot?.queueDepth ?? null,
    queueDepthTrend: buildTrend(jobsSnapshot?.queueDepth, previousJobsSnapshot?.queueDepth),
  };

  return {
    kpis,
    jobsSnapshot,
  };
};
