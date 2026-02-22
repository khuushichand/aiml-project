import { describe, expect, it } from 'vitest';
import {
  buildProviderTokenTrendMap,
  buildRecentUtcDayKeys,
  buildSparklinePoints,
} from './provider-token-trends';

describe('provider-token-trends', () => {
  it('builds recent UTC day keys in ascending order', () => {
    const keys = buildRecentUtcDayKeys(7, new Date('2026-02-17T14:30:00.000Z'));
    expect(keys).toEqual([
      '2026-02-11',
      '2026-02-12',
      '2026-02-13',
      '2026-02-14',
      '2026-02-15',
      '2026-02-16',
      '2026-02-17',
    ]);
  });

  it('aggregates token trends by provider and day', () => {
    const trends = buildProviderTokenTrendMap(
      [
        { group_value: 'openai', group_value_secondary: '2026-02-15', total_tokens: 120 },
        { group_value: 'openai', group_value_secondary: '2026-02-15', total_tokens: 80 },
        { group_value: 'openai', group_value_secondary: '2026-02-17', total_tokens: 200 },
        { group_value: 'anthropic', group_value_secondary: '2026-02-16', total_tokens: 95 },
      ],
      { days: 7, endDate: new Date('2026-02-17T05:00:00.000Z') }
    );

    expect(trends.openai).toEqual([0, 0, 0, 0, 200, 0, 200]);
    expect(trends.anthropic).toEqual([0, 0, 0, 0, 0, 95, 0]);
  });

  it('builds svg sparkline points with one point per value', () => {
    const points = buildSparklinePoints([10, 30, 20, 40], { width: 80, height: 20, padding: 2 });
    const coordinates = points.split(' ');
    expect(coordinates).toHaveLength(4);
    expect(coordinates[0]).toContain(',');
    expect(coordinates[3]).toContain(',');
  });
});

