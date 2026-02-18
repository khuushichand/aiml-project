import { describe, expect, it } from 'vitest';
import {
  buildDashboardActivityChartData,
  getDashboardActivityQuery,
  resolveDashboardActivityPoints,
} from './dashboard-activity';

describe('getDashboardActivityQuery', () => {
  it('maps Stage 3 ranges to expected day window and granularity', () => {
    expect(getDashboardActivityQuery('24h')).toEqual({ days: 1, granularity: 'hour' });
    expect(getDashboardActivityQuery('7d')).toEqual({ days: 7, granularity: 'day' });
    expect(getDashboardActivityQuery('30d')).toEqual({ days: 30, granularity: 'day' });
  });
});

describe('resolveDashboardActivityPoints', () => {
  it('returns a complete 24-hour zero-filled series when activity endpoint fails', () => {
    const points = resolveDashboardActivityPoints(
      { status: 'rejected', reason: new Error('network') },
      '24h',
      new Date('2026-02-17T12:34:56.000Z')
    );

    expect(points).toHaveLength(24);
    expect(points[0].requests).toBe(0);
    expect(points[23].users).toBe(0);
    expect(points[0].bucketStart).toBe('2026-02-16T13:00:00.000Z');
    expect(points[23].bucketStart).toBe('2026-02-17T12:00:00.000Z');
  });

  it('normalizes fulfilled hourly payloads into hourly buckets', () => {
    const points = resolveDashboardActivityPoints(
      {
        status: 'fulfilled',
        value: {
          points: [
            { bucket_start: '2026-02-17T10:17:00Z', requests: 5, users: 2 },
            { bucket_start: '2026-02-17T10:43:00Z', requests: 7, users: 1 },
            { bucket_start: '2026-02-17T11:05:00Z', requests: 3, users: 2 },
          ],
        },
      },
      '24h',
      new Date('2026-02-17T12:00:00.000Z')
    );

    expect(points).toHaveLength(24);
    const tenAm = points.find((point) => point.bucketStart === '2026-02-17T10:00:00.000Z');
    const elevenAm = points.find((point) => point.bucketStart === '2026-02-17T11:00:00.000Z');
    expect(tenAm).toEqual({
      bucketStart: '2026-02-17T10:00:00.000Z',
      requests: 12,
      users: 3,
    });
    expect(elevenAm).toEqual({
      bucketStart: '2026-02-17T11:00:00.000Z',
      requests: 3,
      users: 2,
    });
  });
});

describe('buildDashboardActivityChartData', () => {
  it('formats daily labels for 7-day and month-day labels for 30-day range', () => {
    const daily = [
      { bucketStart: '2026-02-15T00:00:00.000Z', requests: 15, users: 4 },
      { bucketStart: '2026-02-16T00:00:00.000Z', requests: 20, users: 6 },
    ];
    const sevenDay = buildDashboardActivityChartData(daily, '7d');
    const thirtyDay = buildDashboardActivityChartData(daily, '30d');

    expect(sevenDay.map((point) => point.name)).toEqual(['Sun', 'Mon']);
    expect(thirtyDay.map((point) => point.name)).toEqual(['Feb 15', 'Feb 16']);
  });
});
