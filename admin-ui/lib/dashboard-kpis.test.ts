import { describe, expect, it } from 'vitest';
import {
  DEFAULT_DASHBOARD_OPERATIONAL_KPIS,
  buildDashboardOperationalKpis,
  buildTrend,
  extractRequestLatencyP95Ms,
} from './dashboard-kpis';

describe('extractRequestLatencyP95Ms', () => {
  it('computes p95 from histogram bucket lines', () => {
    const metricsText = [
      'http_request_duration_seconds_bucket{endpoint="/chat",le="0.1",method="GET"} 50',
      'http_request_duration_seconds_bucket{endpoint="/chat",le="0.2",method="GET"} 90',
      'http_request_duration_seconds_bucket{endpoint="/chat",le="0.5",method="GET"} 100',
      'http_request_duration_seconds_bucket{endpoint="/chat",le="+Inf",method="GET"} 100',
    ].join('\n');

    const p95 = extractRequestLatencyP95Ms(metricsText);
    expect(p95).not.toBeNull();
    expect(p95 as number).toBeCloseTo(350, 0);
  });
});

describe('buildTrend', () => {
  it('returns up/down/flat trend deltas', () => {
    expect(buildTrend(12, 10)?.direction).toBe('up');
    expect(buildTrend(8, 10)?.direction).toBe('down');
    expect(buildTrend(10, 10)?.direction).toBe('flat');
  });
});

describe('buildDashboardOperationalKpis', () => {
  it('builds KPI values and trends from endpoint payloads', () => {
    const usageDaily = {
      items: [
        { day: '2026-02-16', user_id: 1, requests: 100, errors: 5, bytes_total: 1000, latency_avg_ms: 200 },
        { day: '2026-02-16', user_id: 2, requests: 50, errors: 2, bytes_total: 500, latency_avg_ms: 300 },
        { day: '2026-02-15', user_id: 1, requests: 100, errors: 10, bytes_total: 1000, latency_avg_ms: 250 },
      ],
    };
    const llmUsageSummary = {
      items: [
        {
          group_value: '2026-02-16',
          requests: 300,
          errors: 3,
          input_tokens: 1000,
          output_tokens: 500,
          total_tokens: 1500,
          total_cost_usd: 12.75,
        },
        {
          group_value: '2026-02-15',
          requests: 250,
          errors: 4,
          input_tokens: 900,
          output_tokens: 400,
          total_tokens: 1300,
          total_cost_usd: 9.25,
        },
      ],
    };
    const jobsStats = [
      { domain: 'core', queue: 'default', job_type: 'sync', queued: 12, scheduled: 3, processing: 5, quarantined: 1 },
    ];
    const metricsText = [
      'http_request_duration_seconds_bucket{endpoint="/api/v1/chat",le="0.1",method="POST"} 40',
      'http_request_duration_seconds_bucket{endpoint="/api/v1/chat",le="0.2",method="POST"} 90',
      'http_request_duration_seconds_bucket{endpoint="/api/v1/chat",le="0.5",method="POST"} 100',
      'http_request_duration_seconds_bucket{endpoint="/api/v1/chat",le="+Inf",method="POST"} 100',
    ].join('\n');

    const result = buildDashboardOperationalKpis({
      usageDaily,
      llmUsageSummary,
      jobsStats,
      metricsText,
      previousJobsSnapshot: { activeJobs: 3, queuedJobs: 8, failedJobs: 2, queueDepth: 10 },
    });

    expect(result.kpis.latencyP95Ms).toBeCloseTo(350, 0);
    expect(result.kpis.errorRatePct).toBeCloseTo((7 / 150) * 100, 4);
    expect(result.kpis.dailyCostUsd).toBeCloseTo(12.75, 2);
    expect(result.kpis.activeJobs).toBe(5);
    expect(result.kpis.queuedJobs).toBe(15);
    expect(result.kpis.failedJobs).toBe(1);
    expect(result.kpis.queueDepth).toBe(16);
    expect(result.kpis.errorRateTrend?.direction).toBe('down');
    expect(result.kpis.dailyCostTrend?.direction).toBe('up');
    expect(result.kpis.activeJobsTrend?.direction).toBe('up');
    expect(result.kpis.queueDepthTrend?.direction).toBe('up');
    expect(result.jobsSnapshot).toEqual({ activeJobs: 5, queuedJobs: 15, failedJobs: 1, queueDepth: 16 });
  });

  it('returns N/A-compatible null values when operational endpoints are unavailable', () => {
    const result = buildDashboardOperationalKpis({});
    expect(result.kpis).toEqual(DEFAULT_DASHBOARD_OPERATIONAL_KPIS);
    expect(result.jobsSnapshot).toBeNull();
  });
});
