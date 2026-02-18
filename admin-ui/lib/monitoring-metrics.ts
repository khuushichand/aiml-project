export type MonitoringTimeRangeOption = '1h' | '6h' | '24h' | '7d' | '30d' | 'custom';

export type MonitoringMetricSeriesKey =
  | 'cpu'
  | 'memory'
  | 'diskUsage'
  | 'throughput'
  | 'activeConnections'
  | 'queueDepth';

export type MonitoringMetricsSeriesVisibility = Record<MonitoringMetricSeriesKey, boolean>;

export interface MonitoringMetricsPoint {
  timestamp: string;
  label: string;
  cpu: number;
  memory: number;
  diskUsage: number;
  throughput: number;
  activeConnections: number;
  queueDepth: number;
}

export interface MonitoringRangeParams {
  start: string;
  end: string;
  granularity: string;
  rangeLabel: string;
  expectedPoints: number;
}

export type MonitoringRangeResolution =
  | {
      ok: true;
      params: MonitoringRangeParams;
    }
  | {
      ok: false;
      error: string;
    };

const HOUR_MS = 60 * 60 * 1000;
const DAY_MS = 24 * HOUR_MS;

const clampPercent = (value: number): number => Math.min(100, Math.max(0, value));

const toFiniteNumber = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;

const toObject = (value: unknown): Record<string, unknown> | null =>
  typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : null;

const pickMetricValue = (row: Record<string, unknown>, candidates: string[]): number => {
  for (const key of candidates) {
    const value = toFiniteNumber(row[key]);
    if (value !== null) return value;
  }
  return 0;
};

const toMetricPoint = (row: Record<string, unknown>, fallbackTimestamp: string): MonitoringMetricsPoint => {
  const timestampRaw = row.timestamp ?? row.ts ?? row.time ?? fallbackTimestamp;
  const timestamp = typeof timestampRaw === 'string'
    ? timestampRaw
    : new Date(fallbackTimestamp).toISOString();
  const parsedDate = new Date(timestamp);
  const isoTimestamp = Number.isNaN(parsedDate.valueOf())
    ? new Date(fallbackTimestamp).toISOString()
    : parsedDate.toISOString();
  const label = formatMonitoringXAxisLabel(isoTimestamp);

  const cpu = clampPercent(pickMetricValue(row, ['cpu', 'cpu_percent', 'cpu_usage', 'cpu_usage_percent']));
  const memory = clampPercent(pickMetricValue(row, ['memory', 'memory_percent', 'memory_usage', 'memory_usage_percent']));
  const diskUsage = clampPercent(pickMetricValue(row, ['diskUsage', 'disk_usage', 'disk_usage_percent', 'storage_usage_percent', 'storage_percent']));
  const throughput = Math.max(0, pickMetricValue(row, ['throughput', 'request_throughput', 'requests_per_second', 'rps']));
  const activeConnections = Math.max(0, pickMetricValue(row, ['activeConnections', 'active_connections', 'open_connections']));
  const queueDepth = Math.max(0, pickMetricValue(row, ['queueDepth', 'queue_depth', 'jobs_queue_depth', 'queued_jobs']));

  return {
    timestamp: isoTimestamp,
    label,
    cpu,
    memory,
    diskUsage,
    throughput,
    activeConnections,
    queueDepth,
  };
};

const expectedPointsForDuration = (durationMs: number, granularityMs: number): number =>
  Math.min(320, Math.max(1, Math.floor(durationMs / granularityMs) + 1));

const granularityMs = (granularity: string): number => {
  switch (granularity) {
    case '1m':
      return 60 * 1000;
    case '5m':
      return 5 * 60 * 1000;
    case '15m':
      return 15 * 60 * 1000;
    case '1h':
      return HOUR_MS;
    case '6h':
      return 6 * HOUR_MS;
    case '1d':
      return DAY_MS;
    default:
      return 15 * 60 * 1000;
  }
};

const pickGranularityForDuration = (durationMs: number): string => {
  if (durationMs <= HOUR_MS) return '1m';
  if (durationMs <= 6 * HOUR_MS) return '5m';
  if (durationMs <= DAY_MS) return '15m';
  if (durationMs <= 14 * DAY_MS) return '1h';
  if (durationMs <= 60 * DAY_MS) return '6h';
  return '1d';
};

const presetDuration = (range: MonitoringTimeRangeOption): number | null => {
  switch (range) {
    case '1h':
      return HOUR_MS;
    case '6h':
      return 6 * HOUR_MS;
    case '24h':
      return DAY_MS;
    case '7d':
      return 7 * DAY_MS;
    case '30d':
      return 30 * DAY_MS;
    default:
      return null;
  }
};

export const MONITORING_DEFAULT_SERIES_VISIBILITY: MonitoringMetricsSeriesVisibility = {
  cpu: true,
  memory: true,
  diskUsage: true,
  throughput: true,
  activeConnections: true,
  queueDepth: true,
};

export const toggleMonitoringSeriesVisibility = (
  current: MonitoringMetricsSeriesVisibility,
  key: MonitoringMetricSeriesKey
): MonitoringMetricsSeriesVisibility => ({
  ...current,
  [key]: !current[key],
});

export const formatMonitoringXAxisLabel = (timestamp: string): string => {
  const date = new Date(timestamp);
  if (Number.isNaN(date.valueOf())) return timestamp;
  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export const resolveMonitoringRangeParams = (
  range: MonitoringTimeRangeOption,
  customStart: string | undefined,
  customEnd: string | undefined,
  now: Date = new Date()
): MonitoringRangeResolution => {
  if (range !== 'custom') {
    const durationMs = presetDuration(range);
    if (durationMs === null) {
      return { ok: false, error: 'Invalid time range.' };
    }

    const granularity = pickGranularityForDuration(durationMs);
    const end = new Date(now);
    const start = new Date(end.getTime() - durationMs);
    return {
      ok: true,
      params: {
        start: start.toISOString(),
        end: end.toISOString(),
        granularity,
        rangeLabel: range,
        expectedPoints: expectedPointsForDuration(durationMs, granularityMs(granularity)),
      },
    };
  }

  if (!customStart || !customEnd) {
    return {
      ok: false,
      error: 'Custom range requires both start and end date-time values.',
    };
  }
  const start = new Date(customStart);
  const end = new Date(customEnd);
  if (Number.isNaN(start.valueOf()) || Number.isNaN(end.valueOf())) {
    return { ok: false, error: 'Custom range includes an invalid date-time value.' };
  }
  if (start.getTime() >= end.getTime()) {
    return { ok: false, error: 'Custom range start must be before end.' };
  }

  const durationMs = end.getTime() - start.getTime();
  const granularity = pickGranularityForDuration(durationMs);
  return {
    ok: true,
    params: {
      start: start.toISOString(),
      end: end.toISOString(),
      granularity,
      rangeLabel: 'Custom',
      expectedPoints: expectedPointsForDuration(durationMs, granularityMs(granularity)),
    },
  };
};

const parsePayloadRows = (payload: unknown): Record<string, unknown>[] => {
  if (Array.isArray(payload)) {
    return payload.filter((item): item is Record<string, unknown> => toObject(item) !== null);
  }
  const payloadObj = toObject(payload);
  if (!payloadObj) return [];
  const candidate = payloadObj.items ?? payloadObj.history ?? payloadObj.metrics;
  if (!Array.isArray(candidate)) return [];
  return candidate.filter((item): item is Record<string, unknown> => toObject(item) !== null);
};

export const normalizeMonitoringMetricsPayload = (
  payload: unknown,
  fallbackTimestamp: string
): MonitoringMetricsPoint[] => {
  const rows = parsePayloadRows(payload);
  const normalized = rows.map((row) => toMetricPoint(row, fallbackTimestamp));
  normalized.sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
  return normalized;
};

export const extractAdditionalMetricSnapshot = (payload: unknown): {
  diskUsage: number;
  throughput: number;
  activeConnections: number;
  queueDepth: number;
} => {
  const obj = toObject(payload);
  if (!obj) {
    return { diskUsage: 0, throughput: 0, activeConnections: 0, queueDepth: 0 };
  }
  return {
    diskUsage: clampPercent(pickMetricValue(obj, [
      'disk_usage_percent',
      'disk_usage',
      'storage_usage_percent',
      'storage_percent',
      'disk_percent',
    ])),
    throughput: Math.max(0, pickMetricValue(obj, [
      'request_throughput',
      'requests_per_second',
      'throughput',
      'rps',
    ])),
    activeConnections: Math.max(0, pickMetricValue(obj, [
      'active_connections',
      'open_connections',
      'active_ws_connections',
      'active_websocket_connections',
    ])),
    queueDepth: Math.max(0, pickMetricValue(obj, [
      'queue_depth',
      'jobs_queue_depth',
      'queued_jobs',
      'pending_jobs',
    ])),
  };
};

export const buildSyntheticMonitoringMetricsHistory = (
  base: Omit<MonitoringMetricsPoint, 'timestamp' | 'label'>,
  params: MonitoringRangeParams
): MonitoringMetricsPoint[] => {
  const start = Date.parse(params.start);
  const end = Date.parse(params.end);
  if (!Number.isFinite(start) || !Number.isFinite(end) || start >= end) {
    const fallbackTimestamp = new Date().toISOString();
    return [{
      ...base,
      timestamp: fallbackTimestamp,
      label: formatMonitoringXAxisLabel(fallbackTimestamp),
    }];
  }

  const pointCount = Math.max(1, params.expectedPoints);
  const step = pointCount > 1 ? (end - start) / (pointCount - 1) : 0;
  return Array.from({ length: pointCount }, (_, index) => {
    const timestamp = new Date(start + (step * index)).toISOString();
    return {
      ...base,
      timestamp,
      label: formatMonitoringXAxisLabel(timestamp),
    };
  });
};

