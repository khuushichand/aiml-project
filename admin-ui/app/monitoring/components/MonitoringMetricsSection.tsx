import type { ComponentProps } from 'react';
import MetricsChart from './MetricsChart';
import MetricsGrid from './MetricsGrid';
import TimeRangeControls from './TimeRangeControls';

type MonitoringMetricsSectionProps = {
  timeRangeControlsProps: ComponentProps<typeof TimeRangeControls>;
  metricsChartProps: ComponentProps<typeof MetricsChart>;
  metricsGridProps: ComponentProps<typeof MetricsGrid>;
};

export default function MonitoringMetricsSection({
  timeRangeControlsProps,
  metricsChartProps,
  metricsGridProps,
}: MonitoringMetricsSectionProps) {
  return (
    <>
      <TimeRangeControls {...timeRangeControlsProps} />
      <MetricsChart {...metricsChartProps} />
      <MetricsGrid {...metricsGridProps} />
    </>
  );
}
