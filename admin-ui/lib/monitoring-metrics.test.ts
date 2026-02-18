import { describe, expect, it } from 'vitest';
import {
  MONITORING_DEFAULT_SERIES_VISIBILITY,
  resolveMonitoringRangeParams,
  toggleMonitoringSeriesVisibility,
} from './monitoring-metrics';

describe('monitoring-metrics', () => {
  it('builds range params for preset windows', () => {
    const result = resolveMonitoringRangeParams('7d', undefined, undefined, new Date('2026-02-17T12:00:00.000Z'));
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.params.granularity).toBe('1h');
    expect(result.params.rangeLabel).toBe('7d');
  });

  it('rejects invalid custom ranges where start is not before end', () => {
    const result = resolveMonitoringRangeParams('custom', '2026-02-17T12:00', '2026-02-17T08:00');
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.error).toContain('start must be before end');
  });

  it('toggles metric series visibility immutably', () => {
    const next = toggleMonitoringSeriesVisibility(MONITORING_DEFAULT_SERIES_VISIBILITY, 'cpu');
    expect(next.cpu).toBe(false);
    expect(MONITORING_DEFAULT_SERIES_VISIBILITY.cpu).toBe(true);
  });
});

