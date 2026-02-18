import { describe, expect, it } from 'vitest';
import {
  parseEndpointUsageMetrics,
  parseMediaTypeStorageBreakdown,
  parseUserStorageMetrics,
} from './usage-insights';

describe('usage-insights', () => {
  it('parses endpoint request, error, avg latency, and p95 metrics', () => {
    const metricsText = [
      'http_requests_total{method="GET",endpoint="/health",status="200"} 80',
      'http_requests_total{method="GET",endpoint="/health",status="500"} 20',
      'http_requests_total{method="POST",endpoint="/api/v1/chat/completions",status="200"} 60',
      'http_requests_total{method="POST",endpoint="/api/v1/chat/completions",status="429"} 5',
      'http_request_duration_seconds_sum{method="GET",endpoint="/health"} 12',
      'http_request_duration_seconds_count{method="GET",endpoint="/health"} 100',
      'http_request_duration_seconds_bucket{method="GET",endpoint="/health",le="0.1"} 30',
      'http_request_duration_seconds_bucket{method="GET",endpoint="/health",le="0.2"} 80',
      'http_request_duration_seconds_bucket{method="GET",endpoint="/health",le="0.5"} 95',
      'http_request_duration_seconds_bucket{method="GET",endpoint="/health",le="+Inf"} 100',
      'http_request_duration_seconds_sum{method="POST",endpoint="/api/v1/chat/completions"} 39',
      'http_request_duration_seconds_count{method="POST",endpoint="/api/v1/chat/completions"} 65',
      'http_request_duration_seconds_bucket{method="POST",endpoint="/api/v1/chat/completions",le="0.1"} 5',
      'http_request_duration_seconds_bucket{method="POST",endpoint="/api/v1/chat/completions",le="0.5"} 40',
      'http_request_duration_seconds_bucket{method="POST",endpoint="/api/v1/chat/completions",le="1.0"} 63',
      'http_request_duration_seconds_bucket{method="POST",endpoint="/api/v1/chat/completions",le="+Inf"} 65',
    ].join('\n');

    const rows = parseEndpointUsageMetrics(metricsText);
    expect(rows).toHaveLength(2);

    const health = rows.find((row) => row.endpoint === '/health');
    expect(health).toMatchObject({
      method: 'GET',
      requestCount: 100,
    });
    expect(health?.errorRatePct).toBeCloseTo(20, 5);
    expect(health?.avgLatencyMs).toBeCloseTo(120, 5);
    expect(health?.p95LatencyMs).toBeCloseTo(500, 5);
  });

  it('parses storage breakdown by media type from upload bytes metrics', () => {
    const metricsText = [
      'upload_bytes_total{user_id="1",media_type="video"} 2048',
      'upload_bytes_total{user_id="2",media_type="audio"} 1024',
      'upload_bytes_total{user_id="1",media_type="video"} 256',
      'upload_bytes_total{user_id="3",media_type="document"} 512',
    ].join('\n');

    const rows = parseMediaTypeStorageBreakdown(metricsText);
    expect(rows).toEqual([
      { mediaType: 'video', bytesTotal: 2304 },
      { mediaType: 'audio', bytesTotal: 1024 },
      { mediaType: 'document', bytesTotal: 512 },
    ]);
  });

  it('parses user storage used/quota gauges', () => {
    const metricsText = [
      'user_storage_used_mb{user_id="1"} 120.5',
      'user_storage_quota_mb{user_id="1"} 500',
      'user_storage_used_mb{user_id="2"} 12',
      'user_storage_quota_mb{user_id="2"} 100',
    ].join('\n');

    const rows = parseUserStorageMetrics(metricsText);
    expect(rows).toEqual([
      { userId: '1', usedMb: 120.5, quotaMb: 500 },
      { userId: '2', usedMb: 12, quotaMb: 100 },
    ]);
  });
});
