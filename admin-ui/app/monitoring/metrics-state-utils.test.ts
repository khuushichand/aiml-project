import { describe, expect, it } from 'vitest';
import { buildMetricsFromSnapshot, normalizeWatchlistsPayload } from './metrics-state-utils';

describe('metrics-state-utils', () => {
  it('normalizes watchlists from direct array or watchlists wrapper', () => {
    const direct = [{ id: 'w1', name: 'CPU' }];
    const wrapped = { watchlists: [{ id: 'w2', name: 'Memory' }] };

    expect(normalizeWatchlistsPayload(direct)).toEqual(direct);
    expect(normalizeWatchlistsPayload(wrapped)).toEqual([{ id: 'w2', name: 'Memory' }]);
    expect(normalizeWatchlistsPayload({ items: [] })).toEqual([]);
    expect(normalizeWatchlistsPayload(null)).toEqual([]);
  });

  it('builds metric cards from numeric/string snapshot values', () => {
    const metrics = buildMetricsFromSnapshot(
      {
        cpu_usage: 95,
        memory_usage: 75,
        queue_depth: 5,
        mode: 'degraded',
        nested: { ignored: true },
      },
      70,
      90
    );

    expect(metrics).toEqual([
      { name: 'cpu_usage', value: 95, status: 'critical' },
      { name: 'memory_usage', value: 75, status: 'warning' },
      { name: 'queue_depth', value: 5, status: 'healthy' },
      { name: 'mode', value: 'degraded', status: 'healthy' },
    ]);
  });

  it('returns empty list for non-object snapshots', () => {
    expect(buildMetricsFromSnapshot(undefined, 70, 90)).toEqual([]);
    expect(buildMetricsFromSnapshot('invalid', 70, 90)).toEqual([]);
  });
});
