import { useCallback, useState } from 'react';
import type { Metric, SystemStatusItem, Watchlist } from './types';

type UseMonitoringDashboardStateArgs = {
  initialSystemStatus: SystemStatusItem[];
};

export const useMonitoringDashboardState = ({
  initialSystemStatus,
}: UseMonitoringDashboardStateArgs) => {
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatusItem[]>(initialSystemStatus);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const markMonitoringDataUpdated = useCallback(() => {
    setLastUpdated(new Date());
  }, []);

  return {
    metrics,
    setMetrics,
    watchlists,
    setWatchlists,
    systemStatus,
    setSystemStatus,
    loading,
    setLoading,
    lastUpdated,
    setLastUpdated,
    markMonitoringDataUpdated,
  };
};
