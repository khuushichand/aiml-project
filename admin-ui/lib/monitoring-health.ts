import type {
  SystemHealthStatus,
  SystemStatusItem,
  SystemStatusKey,
} from '@/app/monitoring/types';

type RecordLike = Record<string, unknown>;

type TimedEndpointPayload<T> = {
  payload: T;
  checkedAt: string;
  responseTimeMs: number;
};

export type TimedEndpointResult<T> = PromiseSettledResult<TimedEndpointPayload<T>>;

export interface BuildMonitoringSystemStatusArgs {
  healthResult: TimedEndpointResult<unknown>;
  llmHealthResult: TimedEndpointResult<unknown>;
  ragHealthResult: TimedEndpointResult<unknown>;
  ttsHealthResult: TimedEndpointResult<unknown>;
  sttHealthResult: TimedEndpointResult<unknown>;
  embeddingsHealthResult: TimedEndpointResult<unknown>;
  metricsSnapshotResult?: PromiseSettledResult<unknown>;
  metricsTextResult?: PromiseSettledResult<unknown>;
  referenceTime?: string;
}

export const MONITORING_SUBSYSTEMS: Array<{ key: SystemStatusKey; label: string }> = [
  { key: 'api', label: 'API Server' },
  { key: 'database', label: 'Database' },
  { key: 'llm', label: 'LLM Services' },
  { key: 'rag', label: 'RAG Service' },
  { key: 'tts', label: 'TTS Service' },
  { key: 'stt', label: 'STT Service' },
  { key: 'embeddings', label: 'Embeddings' },
  { key: 'cache', label: 'Cache' },
  { key: 'queue', label: 'Queue' },
];

const STATUS_DETAIL_MAP: Record<SystemStatusKey, Record<SystemHealthStatus, string>> = {
  api: {
    healthy: 'Operational',
    warning: 'Degraded',
    critical: 'Unhealthy',
    unknown: 'Unavailable',
  },
  database: {
    healthy: 'Connected',
    warning: 'Degraded',
    critical: 'Unreachable',
    unknown: 'Unavailable',
  },
  llm: {
    healthy: 'Available',
    warning: 'Degraded',
    critical: 'Unavailable',
    unknown: 'Unavailable',
  },
  rag: {
    healthy: 'Available',
    warning: 'Degraded',
    critical: 'Unavailable',
    unknown: 'Unavailable',
  },
  tts: {
    healthy: 'Available',
    warning: 'Degraded',
    critical: 'Unavailable',
    unknown: 'Unavailable',
  },
  stt: {
    healthy: 'Available',
    warning: 'Degraded',
    critical: 'Unavailable',
    unknown: 'Unavailable',
  },
  embeddings: {
    healthy: 'Available',
    warning: 'Degraded',
    critical: 'Unavailable',
    unknown: 'Unavailable',
  },
  cache: {
    healthy: 'Healthy',
    warning: 'Degraded',
    critical: 'Miss-heavy',
    unknown: 'Unavailable',
  },
  queue: {
    healthy: 'Normal',
    warning: 'Elevated depth',
    critical: 'High depth',
    unknown: 'Unavailable',
  },
};

const toRecord = (value: unknown): RecordLike | null =>
  value && typeof value === 'object'
    ? (value as RecordLike)
    : null;

const normalizeTimestamp = (value: unknown, fallback: string): string => {
  if (typeof value !== 'string' || !value.trim()) return fallback;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? fallback : parsed.toISOString();
};

const toFiniteNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

export const normalizeMonitoringHealthStatus = (status?: string): SystemHealthStatus => {
  const normalized = (status || '').toLowerCase();
  if (['ok', 'healthy', 'ready', 'alive', 'available', 'enabled'].includes(normalized)) {
    return 'healthy';
  }
  if (['degraded', 'warning', 'limited', 'partial'].includes(normalized)) {
    return 'warning';
  }
  if (['unhealthy', 'error', 'critical', 'down', 'not_ready', 'failed', 'unavailable'].includes(normalized)) {
    return 'critical';
  }
  return 'unknown';
};

const parsePrometheusMetricTotals = (metricsText: string): Record<string, number> => {
  const totals: Record<string, number> = {};
  const pattern = /^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{[^}]*\})?\s+([+-]?(?:\d+\.?\d*|\d*\.?\d+)(?:[eE][+-]?\d+)?)\s*(?:\d+)?$/;
  metricsText.split('\n').forEach((lineRaw) => {
    const line = lineRaw.trim();
    if (!line || line.startsWith('#')) return;
    const match = line.match(pattern);
    if (!match) return;
    const metric = match[1];
    const value = Number.parseFloat(match[2]);
    if (!Number.isFinite(value)) return;
    totals[metric] = (totals[metric] ?? 0) + value;
  });
  return totals;
};

const firstMetricValue = (metrics: Record<string, number>, names: string[]): number | null => {
  for (const name of names) {
    if (Number.isFinite(metrics[name])) {
      return metrics[name];
    }
  }
  return null;
};

const deriveCacheHitRatePct = (metrics: Record<string, number>): number | null => {
  const hits = firstMetricValue(metrics, ['rag_cache_hits_total']) ?? 0;
  const misses = firstMetricValue(metrics, ['rag_cache_misses_total']) ?? 0;
  const total = hits + misses;
  if (!Number.isFinite(total) || total <= 0) return null;
  return (hits / total) * 100;
};

const resolveQueueStatus = (queueDepth: number | null): {
  status: SystemHealthStatus;
  detail: string;
} => {
  if (queueDepth === null || !Number.isFinite(queueDepth)) {
    return { status: 'unknown', detail: STATUS_DETAIL_MAP.queue.unknown };
  }
  const normalizedDepth = Math.max(0, Math.round(queueDepth));
  if (normalizedDepth > 200) {
    return { status: 'critical', detail: `Depth ${normalizedDepth}` };
  }
  if (normalizedDepth > 50) {
    return { status: 'warning', detail: `Depth ${normalizedDepth}` };
  }
  return { status: 'healthy', detail: `Depth ${normalizedDepth}` };
};

const resolveQueueDepthFromMetricsSnapshot = (snapshot: unknown): number | null => {
  const obj = toRecord(snapshot);
  if (!obj) return null;
  const keys = ['queue_depth', 'jobs_queue_depth', 'queued_jobs', 'pending_jobs'];
  for (const key of keys) {
    const value = toFiniteNumber(obj[key]);
    if (value !== null) {
      return Math.max(0, value);
    }
  }
  return null;
};

const endpointItem = (
  key: SystemStatusKey,
  label: string,
  status: SystemHealthStatus,
  checkedAt: string,
  responseTimeMs: number,
  detail?: string
): SystemStatusItem => ({
  key,
  label,
  status,
  detail: detail ?? STATUS_DETAIL_MAP[key][status],
  lastCheckedAt: checkedAt,
  responseTimeMs,
  source: 'endpoint',
});

const fallbackItem = (
  key: SystemStatusKey,
  label: string,
  status: SystemHealthStatus,
  checkedAt: string,
  detail?: string
): SystemStatusItem => ({
  key,
  label,
  status,
  detail: detail ?? `${STATUS_DETAIL_MAP[key][status]} (metrics fallback)`,
  lastCheckedAt: checkedAt,
  responseTimeMs: null,
  source: 'metrics',
});

const normalizeTimedFailure = (
  key: SystemStatusKey,
  label: string,
  referenceTime: string
): SystemStatusItem => fallbackItem(key, label, 'unknown', referenceTime, STATUS_DETAIL_MAP[key].unknown);

const resolveServiceStatusFromTimedResult = (
  key: SystemStatusKey,
  label: string,
  result: TimedEndpointResult<unknown>,
  referenceTime: string,
  deriveStatus?: (payload: RecordLike) => SystemHealthStatus
): SystemStatusItem => {
  if (result.status !== 'fulfilled') {
    return normalizeTimedFailure(key, label, referenceTime);
  }
  const payloadRecord = toRecord(result.value.payload);
  const status = payloadRecord
    ? (deriveStatus ? deriveStatus(payloadRecord) : normalizeMonitoringHealthStatus(String(payloadRecord.status ?? '')))
    : 'unknown';
  return endpointItem(
    key,
    label,
    status,
    normalizeTimestamp(payloadRecord?.timestamp, result.value.checkedAt),
    result.value.responseTimeMs
  );
};

export const measureTimedEndpoint = async <T>(
  loader: () => Promise<T>,
  now: () => number = Date.now
): Promise<TimedEndpointPayload<T>> => {
  const startedAt = now();
  const payload = await loader();
  const finishedAt = now();
  return {
    payload,
    checkedAt: new Date(finishedAt).toISOString(),
    responseTimeMs: Math.max(0, Math.round(finishedAt - startedAt)),
  };
};

export const buildMonitoringSystemStatus = ({
  healthResult,
  llmHealthResult,
  ragHealthResult,
  ttsHealthResult,
  sttHealthResult,
  embeddingsHealthResult,
  metricsSnapshotResult,
  metricsTextResult,
  referenceTime = new Date().toISOString(),
}: BuildMonitoringSystemStatusArgs): SystemStatusItem[] => {
  const metricsSnapshot = metricsSnapshotResult?.status === 'fulfilled'
    ? metricsSnapshotResult.value
    : null;
  const metricsText = metricsTextResult?.status === 'fulfilled' && typeof metricsTextResult.value === 'string'
    ? metricsTextResult.value
    : '';
  const metricsTotals = metricsText ? parsePrometheusMetricTotals(metricsText) : {};
  const queueDepthFromText = firstMetricValue(metricsTotals, [
    'queue_depth',
    'jobs_queue_depth',
    'queued_jobs',
    'pending_jobs',
  ]);
  const queueDepthFromSnapshot = resolveQueueDepthFromMetricsSnapshot(metricsSnapshot);
  const queueDepth = queueDepthFromSnapshot !== null
    ? queueDepthFromSnapshot
    : queueDepthFromText;
  const queueStatus = resolveQueueStatus(queueDepth);
  const cacheHitRatePct = deriveCacheHitRatePct(metricsTotals);

  const apiItem = (() => {
    if (healthResult.status !== 'fulfilled') {
      return normalizeTimedFailure('api', 'API Server', referenceTime);
    }
    const payload = toRecord(healthResult.value.payload);
    const status = payload
      ? normalizeMonitoringHealthStatus(String(payload.status ?? ''))
      : 'unknown';
    return endpointItem(
      'api',
      'API Server',
      status,
      normalizeTimestamp(payload?.timestamp, healthResult.value.checkedAt),
      healthResult.value.responseTimeMs
    );
  })();

  const databaseItem = (() => {
    if (healthResult.status !== 'fulfilled') {
      return normalizeTimedFailure('database', 'Database', referenceTime);
    }
    const payload = toRecord(healthResult.value.payload);
    const checks = toRecord(payload?.checks);
    const database = toRecord(checks?.database);
    const status = normalizeMonitoringHealthStatus(String(database?.status ?? ''));
    return endpointItem(
      'database',
      'Database',
      status,
      normalizeTimestamp(payload?.timestamp, healthResult.value.checkedAt),
      healthResult.value.responseTimeMs
    );
  })();

  const llmItem = resolveServiceStatusFromTimedResult('llm', 'LLM Services', llmHealthResult, referenceTime);
  const ragItem = resolveServiceStatusFromTimedResult('rag', 'RAG Service', ragHealthResult, referenceTime);

  const ttsMetricSeen = firstMetricValue(metricsTotals, [
    'tts_requests_total',
    'audio_tts_requests_total',
    'tts_synth_requests_total',
  ]) !== null;
  const sttMetricSeen = firstMetricValue(metricsTotals, [
    'stt_transcriptions_total',
    'audio_stt_requests_total',
    'audio_transcription_requests_total',
  ]) !== null;
  const embeddingsMetricSeen = firstMetricValue(metricsTotals, [
    'embeddings_requests_total',
    'embedding_requests_total',
  ]) !== null;

  const ttsItem = ttsHealthResult.status === 'fulfilled'
    ? resolveServiceStatusFromTimedResult('tts', 'TTS Service', ttsHealthResult, referenceTime)
    : fallbackItem('tts', 'TTS Service', ttsMetricSeen ? 'healthy' : 'unknown', referenceTime);

  const sttItem = sttHealthResult.status === 'fulfilled'
    ? resolveServiceStatusFromTimedResult(
      'stt',
      'STT Service',
      sttHealthResult,
      referenceTime,
      (payload) => {
        if (typeof payload.available === 'boolean') {
          return payload.available ? 'healthy' : 'critical';
        }
        return normalizeMonitoringHealthStatus(String(payload.status ?? ''));
      }
    )
    : fallbackItem('stt', 'STT Service', sttMetricSeen ? 'healthy' : 'unknown', referenceTime);

  const embeddingsItem = embeddingsHealthResult.status === 'fulfilled'
    ? resolveServiceStatusFromTimedResult('embeddings', 'Embeddings', embeddingsHealthResult, referenceTime)
    : fallbackItem('embeddings', 'Embeddings', embeddingsMetricSeen ? 'healthy' : 'unknown', referenceTime);

  const cacheItem = (() => {
    if (ragHealthResult.status === 'fulfilled') {
      const payload = toRecord(ragHealthResult.value.payload);
      const components = toRecord(payload?.components);
      const cache = toRecord(components?.cache);
      const cacheStatus = normalizeMonitoringHealthStatus(String(cache?.status ?? ''));
      const cacheHitRate = toFiniteNumber(cache?.hit_rate);
      const hitRateDetail = cacheHitRate !== null
        ? `Hit rate ${cacheHitRate <= 1 ? (cacheHitRate * 100).toFixed(1) : cacheHitRate.toFixed(1)}%`
        : undefined;
      return endpointItem(
        'cache',
        'Cache',
        cacheStatus,
        normalizeTimestamp(payload?.timestamp, ragHealthResult.value.checkedAt),
        ragHealthResult.value.responseTimeMs,
        hitRateDetail ?? STATUS_DETAIL_MAP.cache[cacheStatus]
      );
    }
    if (cacheHitRatePct !== null) {
      const status: SystemHealthStatus =
        cacheHitRatePct < 40 ? 'critical' :
        cacheHitRatePct < 70 ? 'warning' :
        'healthy';
      return fallbackItem(
        'cache',
        'Cache',
        status,
        referenceTime,
        `Hit rate ${cacheHitRatePct.toFixed(1)}% (metrics fallback)`
      );
    }
    return fallbackItem('cache', 'Cache', 'unknown', referenceTime);
  })();

  const queueItem = fallbackItem(
    'queue',
    'Queue',
    queueStatus.status,
    referenceTime,
    `${queueStatus.detail} (metrics fallback)`
  );

  return [
    apiItem,
    databaseItem,
    llmItem,
    ragItem,
    ttsItem,
    sttItem,
    embeddingsItem,
    cacheItem,
    queueItem,
  ];
};
