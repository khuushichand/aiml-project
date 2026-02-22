type PrometheusMetric = {
  name: string;
  labels: Record<string, string>;
  value: number;
};

type EndpointAccumulator = {
  method: string;
  endpoint: string;
  requests: number;
  errors: number;
  durationSumSeconds: number;
  durationCount: number;
  buckets: Map<number, number>;
};

const PROMETHEUS_LINE_PATTERN = /^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{([^}]*)\})?\s+([+-]?(?:\d+\.?\d*|\d*\.?\d+)(?:[eE][+-]?\d+)?)\s*(\d+)?$/;

const LABEL_PATTERN = /([a-zA-Z_][a-zA-Z0-9_]*)="((?:\\.|[^"\\])*)"/g;

const parsePrometheusLabels = (input: string): Record<string, string> => {
  const labels: Record<string, string> = {};
  let match = LABEL_PATTERN.exec(input);
  while (match) {
    const [, key, rawValue] = match;
    labels[key] = rawValue
      .replace(/\\"/g, '"')
      .replace(/\\\\/g, '\\')
      .replace(/\\n/g, '\n');
    match = LABEL_PATTERN.exec(input);
  }
  return labels;
};

const parsePrometheusMetric = (line: string): PrometheusMetric | null => {
  const match = line.match(PROMETHEUS_LINE_PATTERN);
  if (!match) return null;
  const [, name, labelsRaw, valueRaw] = match;
  const value = Number(valueRaw);
  if (!Number.isFinite(value)) return null;

  return {
    name,
    labels: parsePrometheusLabels(labelsRaw ?? ''),
    value,
  };
};

const parseHistogramLe = (value: string | undefined): number | null => {
  if (!value) return null;
  const normalized = value.trim();
  if (
    normalized === '+Inf'
    || normalized === 'Inf'
    || normalized === '+inf'
    || normalized === 'inf'
  ) {
    return Number.POSITIVE_INFINITY;
  }
  const parsed = Number.parseFloat(normalized);
  return Number.isFinite(parsed) ? parsed : null;
};

const computeP95Ms = (bucketCounts: Map<number, number>): number | null => {
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

  const lastFinite = [...sortedBuckets].reverse().find(([le]) => Number.isFinite(le));
  return lastFinite ? lastFinite[0] * 1000 : null;
};

const getEndpointKey = (method: string, endpoint: string) => `${method}|${endpoint}`;

const getEndpointAccumulator = (
  byKey: Map<string, EndpointAccumulator>,
  methodRaw: string | undefined,
  endpointRaw: string | undefined
): EndpointAccumulator => {
  const method = methodRaw?.trim() ? methodRaw.trim().toUpperCase() : 'UNKNOWN';
  const endpoint = endpointRaw?.trim() ? endpointRaw.trim() : 'unmatched';
  const key = getEndpointKey(method, endpoint);
  const existing = byKey.get(key);
  if (existing) return existing;
  const created: EndpointAccumulator = {
    method,
    endpoint,
    requests: 0,
    errors: 0,
    durationSumSeconds: 0,
    durationCount: 0,
    buckets: new Map<number, number>(),
  };
  byKey.set(key, created);
  return created;
};

const isErrorStatus = (statusRaw: string | undefined): boolean => {
  if (!statusRaw) return false;
  const statusCode = Number(statusRaw);
  return Number.isFinite(statusCode) && statusCode >= 400;
};

export type EndpointUsageMetricsRow = {
  endpoint: string;
  method: string;
  requestCount: number;
  avgLatencyMs: number | null;
  errorRatePct: number | null;
  p95LatencyMs: number | null;
};

export type MediaTypeStorageBreakdownRow = {
  mediaType: string;
  bytesTotal: number;
};

export type UserStorageMetricRow = {
  userId: string;
  usedMb: number;
  quotaMb: number | null;
};

export const parseEndpointUsageMetrics = (metricsText: string): EndpointUsageMetricsRow[] => {
  const byKey = new Map<string, EndpointAccumulator>();
  metricsText.split('\n').forEach((lineRaw) => {
    const line = lineRaw.trim();
    if (!line || line.startsWith('#')) return;
    const metric = parsePrometheusMetric(line);
    if (!metric) return;

    if (metric.name === 'http_requests_total') {
      const acc = getEndpointAccumulator(byKey, metric.labels.method, metric.labels.endpoint);
      acc.requests += metric.value;
      if (isErrorStatus(metric.labels.status)) {
        acc.errors += metric.value;
      }
      return;
    }

    if (metric.name === 'http_request_duration_seconds_sum') {
      const acc = getEndpointAccumulator(byKey, metric.labels.method, metric.labels.endpoint);
      acc.durationSumSeconds += metric.value;
      return;
    }

    if (metric.name === 'http_request_duration_seconds_count') {
      const acc = getEndpointAccumulator(byKey, metric.labels.method, metric.labels.endpoint);
      acc.durationCount += metric.value;
      return;
    }

    if (metric.name === 'http_request_duration_seconds_bucket') {
      const acc = getEndpointAccumulator(byKey, metric.labels.method, metric.labels.endpoint);
      const boundary = parseHistogramLe(metric.labels.le);
      if (boundary === null) return;
      acc.buckets.set(boundary, (acc.buckets.get(boundary) ?? 0) + metric.value);
    }
  });

  return [...byKey.values()]
    .filter((entry) => entry.requests > 0)
    .map((entry) => {
      const requestCount = Math.max(0, Math.round(entry.requests));
      const avgLatencyMs = entry.durationCount > 0
        ? (entry.durationSumSeconds / entry.durationCount) * 1000
        : null;
      const errorRatePct = requestCount > 0
        ? (Math.max(0, Math.round(entry.errors)) / requestCount) * 100
        : null;
      return {
        endpoint: entry.endpoint,
        method: entry.method,
        requestCount,
        avgLatencyMs,
        errorRatePct,
        p95LatencyMs: computeP95Ms(entry.buckets),
      };
    })
    .sort((a, b) => {
      if (a.requestCount !== b.requestCount) return b.requestCount - a.requestCount;
      if (a.endpoint !== b.endpoint) return a.endpoint.localeCompare(b.endpoint);
      return a.method.localeCompare(b.method);
    });
};

export const parseMediaTypeStorageBreakdown = (metricsText: string): MediaTypeStorageBreakdownRow[] => {
  const byMediaType = new Map<string, number>();
  metricsText.split('\n').forEach((lineRaw) => {
    const line = lineRaw.trim();
    if (!line || line.startsWith('#')) return;
    const metric = parsePrometheusMetric(line);
    if (!metric || metric.name !== 'upload_bytes_total') return;

    const mediaType = metric.labels.media_type?.trim() || 'unknown';
    byMediaType.set(mediaType, (byMediaType.get(mediaType) ?? 0) + metric.value);
  });

  return [...byMediaType.entries()]
    .map(([mediaType, bytesTotal]) => ({
      mediaType,
      bytesTotal: Math.max(0, Math.round(bytesTotal)),
    }))
    .sort((a, b) => b.bytesTotal - a.bytesTotal);
};

export const parseUserStorageMetrics = (metricsText: string): UserStorageMetricRow[] => {
  const byUserId = new Map<string, UserStorageMetricRow>();
  metricsText.split('\n').forEach((lineRaw) => {
    const line = lineRaw.trim();
    if (!line || line.startsWith('#')) return;
    const metric = parsePrometheusMetric(line);
    if (!metric) return;

    if (metric.name !== 'user_storage_used_mb' && metric.name !== 'user_storage_quota_mb') {
      return;
    }

    const userId = metric.labels.user_id?.trim();
    if (!userId) return;

    const current = byUserId.get(userId) ?? {
      userId,
      usedMb: 0,
      quotaMb: null,
    };

    if (metric.name === 'user_storage_used_mb') {
      current.usedMb = Math.max(0, metric.value);
    } else {
      current.quotaMb = Math.max(0, metric.value);
    }

    byUserId.set(userId, current);
  });

  return [...byUserId.values()].sort((a, b) => b.usedMb - a.usedMb);
};
