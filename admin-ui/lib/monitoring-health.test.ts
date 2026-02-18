import { describe, expect, it } from 'vitest';
import {
  buildMonitoringSystemStatus,
  measureTimedEndpoint,
} from './monitoring-health';

describe('measureTimedEndpoint', () => {
  it('captures response time and checked-at timestamp', async () => {
    const values = [1000, 1065];
    let idx = 0;
    const now = () => {
      const value = values[Math.min(idx, values.length - 1)];
      idx += 1;
      return value;
    };
    const result = await measureTimedEndpoint(async () => ({ status: 'ok' }), now);
    expect(result.responseTimeMs).toBe(65);
    expect(result.checkedAt).toBe('1970-01-01T00:00:01.065Z');
    expect(result.payload).toEqual({ status: 'ok' });
  });
});

describe('buildMonitoringSystemStatus', () => {
  const referenceTime = '2026-02-17T12:00:00.000Z';
  const fulfilled = <T,>(payload: T, responseTimeMs = 25) => ({
    status: 'fulfilled' as const,
    value: {
      payload,
      responseTimeMs,
      checkedAt: referenceTime,
    },
  });
  const rejected = (reason: unknown = new Error('unavailable')) => ({
    status: 'rejected' as const,
    reason,
  });

  it('returns 9 subsystem cards with response times for endpoint-backed checks', () => {
    const items = buildMonitoringSystemStatus({
      healthResult: fulfilled({ status: 'ok', checks: { database: { status: 'ok' } } }, 40),
      llmHealthResult: fulfilled({ status: 'ok' }, 18),
      ragHealthResult: fulfilled({ status: 'ok', components: { cache: { status: 'ok', hit_rate: 0.82 } } }, 22),
      ttsHealthResult: fulfilled({ status: 'ok' }, 14),
      sttHealthResult: fulfilled({ status: 'ok' }, 16),
      embeddingsHealthResult: fulfilled({ status: 'ok' }, 12),
      metricsSnapshotResult: { status: 'fulfilled', value: { queue_depth: 6 } },
      metricsTextResult: { status: 'fulfilled', value: '' },
      referenceTime,
    });

    expect(items).toHaveLength(9);
    const api = items.find((item) => item.key === 'api');
    const queue = items.find((item) => item.key === 'queue');
    expect(api?.responseTimeMs).toBe(40);
    expect(api?.lastCheckedAt).toBe(referenceTime);
    expect(queue?.status).toBe('healthy');
    expect(queue?.detail).toContain('Depth 6');
  });

  it('falls back to metrics when subsystem endpoints are unavailable', () => {
    const metricsText = [
      'tts_requests_total 12',
      'stt_transcriptions_total 5',
      'embeddings_requests_total 44',
      'rag_cache_hits_total 80',
      'rag_cache_misses_total 20',
      'jobs_queue_depth 140',
    ].join('\n');

    const items = buildMonitoringSystemStatus({
      healthResult: fulfilled({ status: 'ok', checks: { database: { status: 'ok' } } }),
      llmHealthResult: fulfilled({ status: 'ok' }),
      ragHealthResult: rejected(),
      ttsHealthResult: rejected(),
      sttHealthResult: rejected(),
      embeddingsHealthResult: rejected(),
      metricsSnapshotResult: { status: 'fulfilled', value: {} },
      metricsTextResult: { status: 'fulfilled', value: metricsText },
      referenceTime,
    });

    expect(items.find((item) => item.key === 'tts')?.source).toBe('metrics');
    expect(items.find((item) => item.key === 'stt')?.source).toBe('metrics');
    expect(items.find((item) => item.key === 'embeddings')?.source).toBe('metrics');
    expect(items.find((item) => item.key === 'cache')?.detail).toContain('Hit rate 80.0%');
    expect(items.find((item) => item.key === 'queue')?.status).toBe('warning');
    expect(items.find((item) => item.key === 'queue')?.detail).toContain('Depth 140');
  });
});
