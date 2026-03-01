/* @vitest-environment jsdom */
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useMonitoringMetricsSectionProps } from './use-monitoring-metrics-section-props';

const createArgs = () => ({
  options: [
    { value: '1h' as const, label: '1h' },
    { value: '24h' as const, label: '24h' },
    { value: 'custom' as const, label: 'Custom' },
  ],
  timeRange: '24h' as const,
  customRangeStart: '',
  customRangeEnd: '',
  rangeValidationError: '',
  onSelectTimeRange: vi.fn(),
  onCustomRangeStartChange: vi.fn(),
  onCustomRangeEndChange: vi.fn(),
  onApplyCustomRange: vi.fn(),
  metricsHistory: [],
  rangeLabel: '24h',
  seriesVisibility: {
    cpu: true,
    memory: true,
    diskUsage: true,
    throughput: true,
    activeConnections: true,
    queueDepth: true,
  },
  onToggleSeries: vi.fn(),
  metrics: [{ name: 'cpu', value: 80, unit: '%', status: 'warning' as const }],
  loading: false,
});

describe('useMonitoringMetricsSectionProps', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('maps metrics/time-range inputs into section props and forwards callbacks', () => {
    const args = createArgs();
    const { result } = renderHook(() => useMonitoringMetricsSectionProps(args));

    expect(result.current.timeRangeControlsProps.options).toHaveLength(3);
    expect(result.current.timeRangeControlsProps.timeRange).toBe('24h');
    expect(result.current.metricsChartProps.rangeLabel).toBe('24h');
    expect(result.current.metricsGridProps.metrics).toHaveLength(1);

    act(() => {
      void result.current.timeRangeControlsProps.onSelectTimeRange('1h');
      result.current.metricsChartProps.onToggleSeries('cpu');
    });

    expect(args.onSelectTimeRange).toHaveBeenCalledWith('1h');
    expect(args.onToggleSeries).toHaveBeenCalledWith('cpu');
  });

  it('returns stable references on rerender when args are unchanged', () => {
    const args = createArgs();
    const { result, rerender } = renderHook(() => useMonitoringMetricsSectionProps(args));

    const initial = result.current;
    const initialToggleSeries = result.current.metricsChartProps.onToggleSeries;

    rerender();

    expect(result.current).toBe(initial);
    expect(result.current.metricsChartProps.onToggleSeries).toBe(initialToggleSeries);
  });
});
