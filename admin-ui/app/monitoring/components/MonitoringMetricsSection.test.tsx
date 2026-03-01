/* @vitest-environment jsdom */
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { MonitoringMetricSeriesKey } from '@/lib/monitoring-metrics';
import MonitoringMetricsSection from './MonitoringMetricsSection';

vi.mock('./TimeRangeControls', () => ({
  default: ({
    options,
    timeRange,
    onSelectTimeRange,
  }: {
    options: Array<{ value: string; label: string }>;
    timeRange: string;
    onSelectTimeRange: (value: string) => void;
  }) => (
    <button
      data-testid="time-range-controls"
      onClick={() => onSelectTimeRange(options[0]?.value ?? '1h')}
    >
      {`${options.length}:${timeRange}`}
    </button>
  ),
}));

vi.mock('./MetricsChart', () => ({
  default: ({
    rangeLabel,
    onToggleSeries,
  }: {
    rangeLabel: string;
    onToggleSeries: (seriesKey: MonitoringMetricSeriesKey) => void;
  }) => (
    <button
      data-testid="metrics-chart"
      onClick={() => onToggleSeries('cpu')}
    >
      {rangeLabel}
    </button>
  ),
}));

vi.mock('./MetricsGrid', () => ({
  default: ({
    metrics,
    loading,
  }: {
    metrics: Array<{ name: string }>;
    loading: boolean;
  }) => (
    <div data-testid="metrics-grid">
      {`${metrics.length}:${String(loading)}`}
    </div>
  ),
}));

describe('MonitoringMetricsSection', () => {
  it('renders all metrics section child components with provided props', () => {
    const onSelectTimeRange = vi.fn();
    const onToggleSeries = vi.fn();

    render(
      <MonitoringMetricsSection
        timeRangeControlsProps={{
          options: [
            { value: '1h', label: '1h' },
            { value: '24h', label: '24h' },
          ],
          timeRange: '24h',
          customRangeStart: '',
          customRangeEnd: '',
          rangeValidationError: '',
          onSelectTimeRange,
          onCustomRangeStartChange: vi.fn(),
          onCustomRangeEndChange: vi.fn(),
          onApplyCustomRange: vi.fn(),
        }}
        metricsChartProps={{
          metricsHistory: [],
          rangeLabel: 'Last 24 hours',
          seriesVisibility: {
            cpu: true,
            memory: true,
            diskUsage: true,
            throughput: true,
            activeConnections: true,
            queueDepth: true,
          },
          onToggleSeries,
        }}
        metricsGridProps={{
          metrics: [{ name: 'cpu', value: 80, unit: '%', status: 'warning' }],
          loading: false,
        }}
      />
    );

    expect(screen.getByTestId('time-range-controls').textContent).toBe('2:24h');
    expect(screen.getByTestId('metrics-chart').textContent).toBe('Last 24 hours');
    expect(screen.getByTestId('metrics-grid').textContent).toBe('1:false');

    fireEvent.click(screen.getByTestId('time-range-controls'));
    expect(onSelectTimeRange).toHaveBeenCalledWith('1h');

    fireEvent.click(screen.getByTestId('metrics-chart'));
    expect(onToggleSeries).toHaveBeenCalledWith('cpu');
  });
});
