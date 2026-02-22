import { describe, expect, it } from 'vitest';
import {
  buildDashboardUptimeSummary,
  DEFAULT_DASHBOARD_UPTIME_WINDOW_DAYS,
} from './dashboard-uptime';

describe('buildDashboardUptimeSummary', () => {
  it('returns 100% uptime when there are no incidents', () => {
    const result = buildDashboardUptimeSummary({
      incidentsPayload: { items: [] },
      now: new Date('2026-02-17T12:00:00Z'),
    });

    expect(result.uptimePercent).toBe(100);
    expect(result.lastIncidentAt).toBeNull();
    expect(result.windowDays).toBe(DEFAULT_DASHBOARD_UPTIME_WINDOW_DAYS);
  });

  it('calculates uptime from merged downtime windows and exposes last incident timestamp', () => {
    const result = buildDashboardUptimeSummary({
      now: new Date('2026-02-17T12:00:00Z'),
      windowDays: 1,
      incidentsPayload: {
        items: [
          {
            id: 'inc-1',
            title: 'Database degradation',
            status: 'resolved',
            severity: 'high',
            created_at: '2026-02-17T00:00:00Z',
            updated_at: '2026-02-17T02:00:00Z',
            resolved_at: '2026-02-17T02:00:00Z',
          },
          {
            id: 'inc-2',
            title: 'Queue backlog',
            status: 'resolved',
            severity: 'medium',
            created_at: '2026-02-17T01:00:00Z',
            updated_at: '2026-02-17T03:00:00Z',
            resolved_at: '2026-02-17T03:00:00Z',
          },
        ],
      },
    });

    // Downtime interval is 3 hours total once merged (00:00-03:00) over a 24h window.
    expect(result.uptimePercent).toBeCloseTo(87.5, 2);
    expect(result.lastIncidentAt).toBe('2026-02-17T01:00:00.000Z');
  });

  it('clips downtime to the selected window', () => {
    const result = buildDashboardUptimeSummary({
      now: new Date('2026-02-17T12:00:00Z'),
      windowDays: 1,
      incidentsPayload: {
        items: [
          {
            id: 'inc-3',
            title: 'Long outage',
            status: 'resolved',
            severity: 'critical',
            created_at: '2026-02-15T00:00:00Z',
            updated_at: '2026-02-16T18:00:00Z',
            resolved_at: '2026-02-16T18:00:00Z',
          },
        ],
      },
    });

    // Window starts at 2026-02-16T12:00:00Z, so only 6 hours of downtime are counted.
    expect(result.uptimePercent).toBeCloseTo(75, 2);
  });
});
