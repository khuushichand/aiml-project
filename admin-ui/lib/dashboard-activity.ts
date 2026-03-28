export type DashboardActivityRange = '24h' | '7d' | '30d';

export type DashboardActivityGranularity = 'hour' | 'day';

export type DashboardActivityRangeOption = {
  value: DashboardActivityRange;
  label: string;
};

export interface DashboardActivityQuery {
  days: number;
  granularity: DashboardActivityGranularity;
}

export interface DashboardActivityPoint {
  bucketStart: string;
  requests: number;
  users: number;
}

export interface DashboardActivityChartPoint {
  bucketStart: string;
  name: string;
  requests: number;
  users: number;
  errors?: number;
  latencyAvgMs?: number;
  costUsd?: number;
}

type DashboardActivityApiPoint = {
  date?: string;
  bucket_start?: string;
  requests?: number;
  users?: number;
};

type DashboardActivityApiResponse = {
  points?: DashboardActivityApiPoint[];
};

export const DASHBOARD_ACTIVITY_RANGE_OPTIONS: DashboardActivityRangeOption[] = [
  { value: '24h', label: '24h' },
  { value: '7d', label: '7d' },
  { value: '30d', label: '30d' },
];

const DASHBOARD_ACTIVITY_RANGE_QUERY: Record<DashboardActivityRange, DashboardActivityQuery> = {
  '24h': { days: 1, granularity: 'hour' },
  '7d': { days: 7, granularity: 'day' },
  '30d': { days: 30, granularity: 'day' },
};

const floorToUtcDay = (date: Date): Date => new Date(Date.UTC(
  date.getUTCFullYear(),
  date.getUTCMonth(),
  date.getUTCDate(),
));

const floorToUtcHour = (date: Date): Date => new Date(Date.UTC(
  date.getUTCFullYear(),
  date.getUTCMonth(),
  date.getUTCDate(),
  date.getUTCHours(),
));

const toSafeNumber = (value: unknown): number => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const toBucketStart = (value: string, granularity: DashboardActivityGranularity): Date | null => {
  const normalized = value.trim().length <= 10 ? `${value}T00:00:00Z` : value;
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return granularity === 'hour' ? floorToUtcHour(parsed) : floorToUtcDay(parsed);
};

const buildBucketSeries = (
  range: DashboardActivityRange,
  now: Date
): DashboardActivityPoint[] => {
  const query = DASHBOARD_ACTIVITY_RANGE_QUERY[range];
  if (query.granularity === 'hour') {
    const endHour = floorToUtcHour(now);
    const firstHourMs = endHour.getTime() - (23 * 60 * 60 * 1000);
    return Array.from({ length: 24 }, (_, index) => ({
      bucketStart: new Date(firstHourMs + (index * 60 * 60 * 1000)).toISOString(),
      requests: 0,
      users: 0,
    }));
  }

  const endDay = floorToUtcDay(now);
  const firstDayMs = endDay.getTime() - ((query.days - 1) * 24 * 60 * 60 * 1000);
  return Array.from({ length: query.days }, (_, index) => ({
    bucketStart: new Date(firstDayMs + (index * 24 * 60 * 60 * 1000)).toISOString(),
    requests: 0,
    users: 0,
  }));
};

const formatHourLabel = (bucketStart: string) => new Intl.DateTimeFormat('en-US', {
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone: 'UTC',
}).format(new Date(bucketStart));

const formatDayLabel = (bucketStart: string) => new Intl.DateTimeFormat('en-US', {
  weekday: 'short',
  timeZone: 'UTC',
}).format(new Date(bucketStart));

const formatMonthDayLabel = (bucketStart: string) => new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  timeZone: 'UTC',
}).format(new Date(bucketStart));

export const getDashboardActivityQuery = (
  range: DashboardActivityRange
): DashboardActivityQuery => DASHBOARD_ACTIVITY_RANGE_QUERY[range];

export const resolveDashboardActivityPoints = (
  result: PromiseSettledResult<unknown>,
  range: DashboardActivityRange,
  now: Date = new Date(),
): DashboardActivityPoint[] => {
  const query = DASHBOARD_ACTIVITY_RANGE_QUERY[range];
  const baseline = buildBucketSeries(range, now);
  if (result.status !== 'fulfilled') {
    return baseline;
  }

  const payload = result.value as DashboardActivityApiResponse | null;
  const points = Array.isArray(payload?.points) ? payload.points : [];
  if (points.length === 0) {
    return baseline;
  }

  const byBucket = new Map(baseline.map((point) => [point.bucketStart, { ...point }]));
  points.forEach((rawPoint) => {
    const rawBucket = typeof rawPoint.bucket_start === 'string'
      ? rawPoint.bucket_start
      : typeof rawPoint.date === 'string'
        ? rawPoint.date
        : '';
    if (!rawBucket) return;

    const bucketStart = toBucketStart(rawBucket, query.granularity);
    if (!bucketStart) return;
    const key = bucketStart.toISOString();
    const existing = byBucket.get(key);
    if (!existing) return;
    byBucket.set(key, {
      bucketStart: key,
      requests: existing.requests + toSafeNumber(rawPoint.requests),
      users: existing.users + toSafeNumber(rawPoint.users),
    });
  });

  return baseline.map((point) => byBucket.get(point.bucketStart) ?? point);
};

export const buildDashboardActivityChartData = (
  points: DashboardActivityPoint[],
  range: DashboardActivityRange,
): DashboardActivityChartPoint[] => points.map((point) => {
  const name = range === '24h'
    ? formatHourLabel(point.bucketStart)
    : range === '30d'
      ? formatMonthDayLabel(point.bucketStart)
      : formatDayLabel(point.bucketStart);
  return {
    bucketStart: point.bucketStart,
    name,
    requests: point.requests,
    users: point.users,
  };
});

/**
 * Merge per-day usage overlay data (errors, latency, cost) into chart points.
 * Only works for 7d and 30d ranges (day granularity). 24h (hour) is too fine-grained
 * for daily aggregates — overlays are left undefined for hourly charts.
 */
export interface DailyOverlayRow {
  day: string;
  errors?: number;
  latencyAvgMs?: number | null;
  costUsd?: number | null;
}

export const mergeOverlayData = (
  chartPoints: DashboardActivityChartPoint[],
  overlayRows: DailyOverlayRow[],
): DashboardActivityChartPoint[] => {
  if (overlayRows.length === 0) return chartPoints;

  const byDay = new Map<string, DailyOverlayRow>();
  for (const row of overlayRows) {
    byDay.set(row.day, row);
  }

  return chartPoints.map((point) => {
    // Extract YYYY-MM-DD from bucketStart ISO string
    const dayKey = point.bucketStart.slice(0, 10);
    const overlay = byDay.get(dayKey);
    if (!overlay) return point;
    return {
      ...point,
      errors: overlay.errors ?? undefined,
      latencyAvgMs: overlay.latencyAvgMs ?? undefined,
      costUsd: overlay.costUsd ?? undefined,
    };
  });
};
