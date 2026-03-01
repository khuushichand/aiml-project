import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  buildSyntheticMonitoringMetricsHistory,
  extractAdditionalMetricSnapshot,
  normalizeMonitoringMetricsPayload,
  resolveMonitoringRangeParams,
  type MonitoringTimeRangeOption,
} from '@/lib/monitoring-metrics';
import type { MetricsHistoryPoint } from './types';

interface HealthMetricsResponse {
  cpu?: { percent?: number };
  memory?: { percent?: number };
}

export type MonitoringMetricsApiClient = {
  getMonitoringMetrics: (params: {
    start: string;
    end: string;
    granularity: string;
  }) => Promise<unknown>;
  getHealthMetrics: () => Promise<unknown>;
  getMetrics: () => Promise<unknown>;
};

type UseMonitoringMetricsHistoryArgs = {
  apiClient: MonitoringMetricsApiClient;
  pollIntervalMs?: number;
  onManualRangeLoadSuccess?: () => void;
};

const DEFAULT_METRICS_HISTORY_POLL_MS = 5 * 60 * 1000;

const toDatetimeLocalInputValue = (value: Date): string => {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  const hours = String(value.getHours()).padStart(2, '0');
  const minutes = String(value.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}`;
};

export const useMonitoringMetricsHistory = ({
  apiClient,
  pollIntervalMs = DEFAULT_METRICS_HISTORY_POLL_MS,
  onManualRangeLoadSuccess,
}: UseMonitoringMetricsHistoryArgs) => {
  const defaultCustomRange = useMemo(() => {
    const now = new Date();
    return {
      start: toDatetimeLocalInputValue(new Date(now.getTime() - (24 * 60 * 60 * 1000))),
      end: toDatetimeLocalInputValue(now),
    };
  }, []);

  const [metricsHistory, setMetricsHistory] = useState<MetricsHistoryPoint[]>([]);
  const [timeRange, setTimeRange] = useState<MonitoringTimeRangeOption>('24h');
  const [customRangeStart, setCustomRangeStart] = useState<string>(defaultCustomRange.start);
  const [customRangeEnd, setCustomRangeEnd] = useState<string>(defaultCustomRange.end);
  const [rangeValidationError, setRangeValidationError] = useState('');
  const [activeRangeLabel, setActiveRangeLabel] = useState('24h');

  const loadMetricsHistoryForRange = useCallback(async (
    selectedRange: MonitoringTimeRangeOption,
    customStart: string,
    customEnd: string
  ): Promise<boolean> => {
    const resolvedRange = resolveMonitoringRangeParams(selectedRange, customStart, customEnd);
    if (!resolvedRange.ok) {
      setRangeValidationError(resolvedRange.error);
      return false;
    }

    setRangeValidationError('');
    const rangeParams = resolvedRange.params;
    setActiveRangeLabel(rangeParams.rangeLabel);

    try {
      const historyPayload = await apiClient.getMonitoringMetrics({
        start: rangeParams.start,
        end: rangeParams.end,
        granularity: rangeParams.granularity,
      });
      const normalized = normalizeMonitoringMetricsPayload(historyPayload, rangeParams.end);
      if (normalized.length > 0) {
        setMetricsHistory(normalized);
        return true;
      }
      throw new Error('No monitoring metrics history returned');
    } catch (historyErr: unknown) {
      console.warn('Failed to load monitoring metrics history endpoint, using fallback sample.', historyErr);
      try {
        const [healthResult, metricsResult] = await Promise.allSettled([
          apiClient.getHealthMetrics(),
          apiClient.getMetrics(),
        ]);
        const healthPayload = healthResult.status === 'fulfilled'
          ? (healthResult.value as HealthMetricsResponse)
          : {};
        const metricsPayload = metricsResult.status === 'fulfilled' ? metricsResult.value : {};
        const additional = extractAdditionalMetricSnapshot(metricsPayload);
        const cpu = Number(healthPayload?.cpu?.percent ?? 0);
        const memory = Number(healthPayload?.memory?.percent ?? 0);
        const fallbackHistory = buildSyntheticMonitoringMetricsHistory(
          {
            cpu,
            memory,
            diskUsage: additional.diskUsage,
            throughput: additional.throughput,
            activeConnections: additional.activeConnections,
            queueDepth: additional.queueDepth,
          },
          rangeParams
        );
        setMetricsHistory(fallbackHistory);
      } catch (fallbackErr: unknown) {
        console.warn('Failed to load fallback metrics history:', fallbackErr);
        setMetricsHistory([]);
      }
      return false;
    }
  }, [apiClient]);

  useEffect(() => {
    void loadMetricsHistoryForRange(timeRange, customRangeStart, customRangeEnd);
    const intervalId = window.setInterval(() => {
      void loadMetricsHistoryForRange(timeRange, customRangeStart, customRangeEnd);
    }, pollIntervalMs);
    return () => window.clearInterval(intervalId);
  }, [customRangeEnd, customRangeStart, loadMetricsHistoryForRange, pollIntervalMs, timeRange]);

  const handleSelectTimeRange = useCallback(async (nextRange: MonitoringTimeRangeOption): Promise<boolean> => {
    setTimeRange(nextRange);
    if (nextRange === 'custom') {
      return false;
    }
    const loaded = await loadMetricsHistoryForRange(nextRange, customRangeStart, customRangeEnd);
    if (loaded) {
      onManualRangeLoadSuccess?.();
    }
    return loaded;
  }, [customRangeEnd, customRangeStart, loadMetricsHistoryForRange, onManualRangeLoadSuccess]);

  const handleApplyCustomTimeRange = useCallback(async (): Promise<boolean> => {
    setTimeRange('custom');
    const loaded = await loadMetricsHistoryForRange('custom', customRangeStart, customRangeEnd);
    if (loaded) {
      onManualRangeLoadSuccess?.();
    }
    return loaded;
  }, [customRangeEnd, customRangeStart, loadMetricsHistoryForRange, onManualRangeLoadSuccess]);

  return {
    metricsHistory,
    timeRange,
    customRangeStart,
    customRangeEnd,
    rangeValidationError,
    activeRangeLabel,
    setCustomRangeStart,
    setCustomRangeEnd,
    loadMetricsHistoryForRange,
    handleSelectTimeRange,
    handleApplyCustomTimeRange,
  };
};
