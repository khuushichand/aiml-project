import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
  const [customRangeStart, setCustomRangeStartState] = useState<string>(defaultCustomRange.start);
  const [customRangeEnd, setCustomRangeEndState] = useState<string>(defaultCustomRange.end);
  const [appliedCustomRangeStart, setAppliedCustomRangeStart] = useState<string>(defaultCustomRange.start);
  const [appliedCustomRangeEnd, setAppliedCustomRangeEnd] = useState<string>(defaultCustomRange.end);
  const [hasAppliedCustomRange, setHasAppliedCustomRange] = useState(false);
  const [manualReloadNonce, setManualReloadNonce] = useState(0);
  const [rangeValidationError, setRangeValidationError] = useState('');
  const [activeRangeLabel, setActiveRangeLabel] = useState('24h');
  const pendingManualRangeLoadSuccessRef = useRef(false);

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

  const setCustomRangeStart = useCallback((value: string) => {
    setCustomRangeStartState(value);
    if (rangeValidationError) {
      setRangeValidationError('');
    }
  }, [rangeValidationError]);

  const setCustomRangeEnd = useCallback((value: string) => {
    setCustomRangeEndState(value);
    if (rangeValidationError) {
      setRangeValidationError('');
    }
  }, [rangeValidationError]);

  useEffect(() => {
    if (timeRange === 'custom' && !hasAppliedCustomRange) {
      return;
    }

    const executeLoad = async () => {
      const loaded = await loadMetricsHistoryForRange(
        timeRange,
        appliedCustomRangeStart,
        appliedCustomRangeEnd
      );
      if (pendingManualRangeLoadSuccessRef.current) {
        if (loaded) {
          onManualRangeLoadSuccess?.();
        }
        pendingManualRangeLoadSuccessRef.current = false;
      }
    };

    void executeLoad();
    const intervalId = window.setInterval(() => {
      void loadMetricsHistoryForRange(
        timeRange,
        appliedCustomRangeStart,
        appliedCustomRangeEnd
      );
    }, pollIntervalMs);
    return () => window.clearInterval(intervalId);
  }, [
    appliedCustomRangeEnd,
    appliedCustomRangeStart,
    hasAppliedCustomRange,
    loadMetricsHistoryForRange,
    manualReloadNonce,
    onManualRangeLoadSuccess,
    pollIntervalMs,
    timeRange
  ]);

  const handleSelectTimeRange = useCallback(async (nextRange: MonitoringTimeRangeOption): Promise<boolean> => {
    setTimeRange(nextRange);
    if (nextRange === 'custom') {
      setHasAppliedCustomRange(false);
      return false;
    }
    pendingManualRangeLoadSuccessRef.current = true;
    return true;
  }, []);

  const handleApplyCustomTimeRange = useCallback(async (): Promise<boolean> => {
    const resolvedRange = resolveMonitoringRangeParams('custom', customRangeStart, customRangeEnd);
    if (!resolvedRange.ok) {
      setRangeValidationError(resolvedRange.error);
      return false;
    }

    setRangeValidationError('');
    setAppliedCustomRangeStart(customRangeStart);
    setAppliedCustomRangeEnd(customRangeEnd);
    setHasAppliedCustomRange(true);
    setTimeRange('custom');
    pendingManualRangeLoadSuccessRef.current = true;
    setManualReloadNonce((value) => value + 1);
    return true;
  }, [customRangeEnd, customRangeStart]);

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
