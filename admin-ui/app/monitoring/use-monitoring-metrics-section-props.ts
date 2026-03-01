import { useMemo, type ComponentProps } from 'react';
import type {
  MonitoringMetricSeriesKey,
  MonitoringMetricsSeriesVisibility,
  MonitoringTimeRangeOption,
} from '@/lib/monitoring-metrics';
import MonitoringMetricsSection from './components/MonitoringMetricsSection';
import type { Metric, MetricsHistoryPoint } from './types';

type TimeRangeOption = {
  value: MonitoringTimeRangeOption;
  label: string;
};

type UseMonitoringMetricsSectionPropsArgs = {
  options: TimeRangeOption[];
  timeRange: MonitoringTimeRangeOption;
  customRangeStart: string;
  customRangeEnd: string;
  rangeValidationError: string;
  onSelectTimeRange: (value: MonitoringTimeRangeOption) => Promise<void> | void;
  onCustomRangeStartChange: (value: string) => void;
  onCustomRangeEndChange: (value: string) => void;
  onApplyCustomRange: () => Promise<void> | void;
  metricsHistory: MetricsHistoryPoint[];
  rangeLabel: string;
  seriesVisibility: MonitoringMetricsSeriesVisibility;
  onToggleSeries: (seriesKey: MonitoringMetricSeriesKey) => void;
  metrics: Metric[];
  loading: boolean;
};

export const useMonitoringMetricsSectionProps = ({
  options,
  timeRange,
  customRangeStart,
  customRangeEnd,
  rangeValidationError,
  onSelectTimeRange,
  onCustomRangeStartChange,
  onCustomRangeEndChange,
  onApplyCustomRange,
  metricsHistory,
  rangeLabel,
  seriesVisibility,
  onToggleSeries,
  metrics,
  loading,
}: UseMonitoringMetricsSectionPropsArgs): ComponentProps<typeof MonitoringMetricsSection> =>
  useMemo(
    () => ({
      timeRangeControlsProps: {
        options,
        timeRange,
        customRangeStart,
        customRangeEnd,
        rangeValidationError,
        onSelectTimeRange,
        onCustomRangeStartChange,
        onCustomRangeEndChange,
        onApplyCustomRange,
      },
      metricsChartProps: {
        metricsHistory,
        rangeLabel,
        seriesVisibility,
        onToggleSeries,
      },
      metricsGridProps: {
        metrics,
        loading,
      },
    }),
    [
      customRangeEnd,
      customRangeStart,
      loading,
      metrics,
      metricsHistory,
      onApplyCustomRange,
      onCustomRangeEndChange,
      onCustomRangeStartChange,
      onSelectTimeRange,
      onToggleSeries,
      options,
      rangeLabel,
      rangeValidationError,
      seriesVisibility,
      timeRange,
    ]
  );
