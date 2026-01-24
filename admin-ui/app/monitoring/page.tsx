'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api-client';
import AlertsPanel from './components/AlertsPanel';
import MetricsChart from './components/MetricsChart';
import MetricsGrid from './components/MetricsGrid';
import SystemStatusPanel from './components/SystemStatusPanel';
import WatchlistsPanel from './components/WatchlistsPanel';
import type {
  Metric,
  MetricsHistoryPoint,
  SystemAlert,
  SystemHealthStatus,
  SystemStatusItem,
  SystemStatusKey,
  Watchlist,
  WatchlistDraft,
} from './types';

interface ApiHealthResponse {
  status?: string;
  checks?: {
    database?: { status?: string };
  };
}

interface ServiceHealthResponse {
  status?: string;
}

interface HealthMetricsResponse {
  cpu?: { percent?: number };
  memory?: { percent?: number };
}

const METRICS_HISTORY_MAX_POINTS = 288;
const METRICS_HISTORY_POLL_MS = 5 * 60 * 1000;
const METRIC_CRITICAL_THRESHOLD = 90;
const METRIC_WARNING_THRESHOLD = 70;
const DEFAULT_SYSTEM_STATUS: SystemStatusItem[] = [
  { key: 'api', label: 'API Server', status: 'unknown', detail: 'Checking...' },
  { key: 'database', label: 'Database', status: 'unknown', detail: 'Checking...' },
  { key: 'llm', label: 'LLM Services', status: 'unknown', detail: 'Checking...' },
  { key: 'rag', label: 'RAG Service', status: 'unknown', detail: 'Checking...' },
];
const SYSTEM_STATUS_DETAILS: Record<SystemStatusKey, Record<SystemHealthStatus, string>> = {
  api: {
    healthy: 'Operational',
    warning: 'Degraded',
    critical: 'Unhealthy',
    unknown: 'Unknown',
  },
  database: {
    healthy: 'Connected',
    warning: 'Degraded',
    critical: 'Unreachable',
    unknown: 'Unknown',
  },
  llm: {
    healthy: 'Available',
    warning: 'Degraded',
    critical: 'Unavailable',
    unknown: 'Unknown',
  },
  rag: {
    healthy: 'Available',
    warning: 'Degraded',
    critical: 'Unavailable',
    unknown: 'Unknown',
  },
};

const normalizeHealthStatus = (status?: string): SystemHealthStatus => {
  const value = (status || '').toLowerCase();
  if (['ok', 'healthy', 'ready', 'alive'].includes(value)) {
    return 'healthy';
  }
  if (['degraded', 'warning'].includes(value)) {
    return 'warning';
  }
  if (['unhealthy', 'error', 'critical', 'not_ready'].includes(value)) {
    return 'critical';
  }
  return 'unknown';
};

export default function MonitoringPage() {
  const confirm = useConfirm();
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [alerts, setAlerts] = useState<SystemAlert[]>([]);
  const [metricsHistory, setMetricsHistory] = useState<MetricsHistoryPoint[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatusItem[]>(DEFAULT_SYSTEM_STATUS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const successTimerRef = useRef<number | null>(null);

  // Create watchlist dialog
  const [showCreateWatchlist, setShowCreateWatchlist] = useState(false);
  const [newWatchlist, setNewWatchlist] = useState<WatchlistDraft>({
    name: '',
    description: '',
    target: '',
    type: 'resource',
    threshold: 80,
  });

  const appendMetricsHistory = useCallback((cpu: number, memory: number) => {
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    setMetricsHistory((prev) => {
      const next = [...prev, { time, cpu, memory }];
      if (next.length <= METRICS_HISTORY_MAX_POINTS) {
        return next;
      }
      return next.slice(-METRICS_HISTORY_MAX_POINTS);
    });
  }, []);

  const loadMetricsHistorySample = useCallback(async () => {
    try {
      const health = (await api.getHealthMetrics()) as HealthMetricsResponse;
      const cpu = Number(health?.cpu?.percent ?? 0);
      const memory = Number(health?.memory?.percent ?? 0);
      appendMetricsHistory(cpu, memory);
    } catch (err: unknown) {
      console.warn('Failed to load health metrics history:', err);
    }
  }, [appendMetricsHistory]);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');

      const [
        metricsData,
        watchlistsData,
        alertsData,
        healthData,
        llmHealthData,
        ragHealthData,
      ] = await Promise.allSettled([
        api.getMetrics(),
        api.getWatchlists(),
        api.getAlerts(),
        api.getHealth(),
        api.getLlmHealth(),
        api.getRagHealth(),
      ]);

      [
        { name: 'metrics', result: metricsData },
        { name: 'watchlists', result: watchlistsData },
        { name: 'alerts', result: alertsData },
        { name: 'health', result: healthData },
        { name: 'llmHealth', result: llmHealthData },
        { name: 'ragHealth', result: ragHealthData },
      ].forEach(({ name, result }) => {
        if (result.status === 'rejected') {
          console.warn(`Failed to load ${name}:`, result.reason);
        }
      });

      // Process metrics
      if (metricsData.status === 'fulfilled' && metricsData.value) {
        const rawMetrics = metricsData.value;
        const metricsArray: Metric[] = [];
        if (typeof rawMetrics === 'object') {
          Object.entries(rawMetrics).forEach(([key, value]) => {
            if (typeof value === 'number' || typeof value === 'string') {
              metricsArray.push({
                name: key,
                value,
                status: typeof value === 'number' && value > METRIC_CRITICAL_THRESHOLD
                  ? 'critical'
                  : typeof value === 'number' && value > METRIC_WARNING_THRESHOLD
                    ? 'warning'
                    : 'healthy',
              });
            }
          });
        }
        setMetrics(metricsArray);
      }

      // Process watchlists
      if (watchlistsData.status === 'fulfilled') {
        setWatchlists(Array.isArray(watchlistsData.value) ? watchlistsData.value : []);
      }

      // Process alerts
      if (alertsData.status === 'fulfilled') {
        setAlerts(Array.isArray(alertsData.value) ? alertsData.value : []);
      }

      const healthAvailable = healthData.status === 'fulfilled';
      const llmAvailable = llmHealthData.status === 'fulfilled';
      const ragAvailable = ragHealthData.status === 'fulfilled';
      const healthPayload = healthAvailable ? (healthData.value as ApiHealthResponse) : undefined;
      const llmPayload = llmAvailable ? (llmHealthData.value as ServiceHealthResponse) : undefined;
      const ragPayload = ragAvailable ? (ragHealthData.value as ServiceHealthResponse) : undefined;
      const apiStatus = healthAvailable
        ? normalizeHealthStatus(healthPayload?.status)
        : 'unknown';
      const dbStatus = healthAvailable
        ? normalizeHealthStatus(healthPayload?.checks?.database?.status)
        : 'unknown';
      const llmStatus = llmAvailable
        ? normalizeHealthStatus(llmPayload?.status)
        : 'unknown';
      const ragStatus = ragAvailable
        ? normalizeHealthStatus(ragPayload?.status)
        : 'unknown';
      const statusDetail = (
        key: SystemStatusKey,
        status: SystemHealthStatus,
        available: boolean
      ) => {
        if (!available) {
          return 'Unavailable';
        }
        return SYSTEM_STATUS_DETAILS[key][status];
      };
      setSystemStatus([
        {
          key: 'api',
          label: 'API Server',
          status: apiStatus,
          detail: statusDetail('api', apiStatus, healthAvailable),
        },
        {
          key: 'database',
          label: 'Database',
          status: dbStatus,
          detail: statusDetail('database', dbStatus, healthAvailable),
        },
        {
          key: 'llm',
          label: 'LLM Services',
          status: llmStatus,
          detail: statusDetail('llm', llmStatus, llmAvailable),
        },
        {
          key: 'rag',
          label: 'RAG Service',
          status: ragStatus,
          detail: statusDetail('rag', ragStatus, ragAvailable),
        },
      ]);

      void loadMetricsHistorySample();
    } catch (err: unknown) {
      console.error('Failed to load monitoring data:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to load monitoring data');
    } finally {
      setLoading(false);
    }
  }, [loadMetricsHistorySample]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (!success) {
      if (successTimerRef.current !== null) {
        window.clearTimeout(successTimerRef.current);
        successTimerRef.current = null;
      }
      return;
    }

    if (successTimerRef.current !== null) {
      window.clearTimeout(successTimerRef.current);
    }
    successTimerRef.current = window.setTimeout(() => {
      setSuccess('');
      successTimerRef.current = null;
    }, 4000);

    return () => {
      if (successTimerRef.current !== null) {
        window.clearTimeout(successTimerRef.current);
        successTimerRef.current = null;
      }
    };
  }, [success]);

  useEffect(() => {
    loadMetricsHistorySample();
    const intervalId = window.setInterval(loadMetricsHistorySample, METRICS_HISTORY_POLL_MS);
    return () => window.clearInterval(intervalId);
  }, [loadMetricsHistorySample]);

  const handleCreateWatchlist = async () => {
    if (!newWatchlist.name || !newWatchlist.target) {
      setError('Name and target are required');
      return;
    }

    try {
      setError('');
      await api.createWatchlist(newWatchlist);
      setSuccess('Watchlist created successfully');
      setShowCreateWatchlist(false);
      setNewWatchlist({ name: '', description: '', target: '', type: 'resource', threshold: 80 });
      loadData();
    } catch (err: unknown) {
      console.error('Failed to create watchlist:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to create watchlist');
    }
  };

  const handleDeleteWatchlist = async (watchlist: Watchlist) => {
    const confirmed = await confirm({
      title: 'Delete Watchlist',
      message: `Delete watchlist "${watchlist.name}"?`,
      confirmText: 'Delete',
      variant: 'danger',
      icon: 'delete',
    });
    if (!confirmed) return;

    try {
      setError('');
      await api.deleteWatchlist(watchlist.id);
      setSuccess('Watchlist deleted');
      loadData();
    } catch (err: unknown) {
      console.error('Failed to delete watchlist:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to delete watchlist');
    }
  };

  const handleAcknowledgeAlert = async (alert: SystemAlert) => {
    try {
      setError('');
      await api.acknowledgeAlert(alert.id);
      setSuccess('Alert acknowledged');
      loadData();
    } catch (err: unknown) {
      console.error('Failed to acknowledge alert:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to acknowledge alert');
    }
  };

  const handleDismissAlert = async (alert: SystemAlert) => {
    const confirmed = await confirm({
      title: 'Dismiss Alert',
      message: 'Dismiss this alert?',
      confirmText: 'Dismiss',
      variant: 'warning',
      icon: 'warning',
    });
    if (!confirmed) return;

    try {
      setError('');
      await api.dismissAlert(alert.id);
      setSuccess('Alert dismissed');
      loadData();
    } catch (err: unknown) {
      console.error('Failed to dismiss alert:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to dismiss alert');
    }
  };

  const activeAlerts = alerts.filter((a) => !a.acknowledged);

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="mb-8 flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold">Monitoring</h1>
                <p className="text-muted-foreground">
                  System health, metrics, and alerts
                </p>
              </div>
              <Button variant="outline" onClick={loadData} disabled={loading}>
                <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </div>

            {error && (
              <Alert variant="destructive" className="mb-6">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {success && (
              <Alert className="mb-6 bg-green-50 border-green-200">
                <AlertDescription className="text-green-800">{success}</AlertDescription>
              </Alert>
            )}

            {/* Active Alerts Banner */}
            {activeAlerts.length > 0 && (
              <Alert variant="destructive" className="mb-6">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  {activeAlerts.length} active alert{activeAlerts.length !== 1 ? 's' : ''} require attention
                </AlertDescription>
              </Alert>
            )}

            <MetricsChart metricsHistory={metricsHistory} />
            <MetricsGrid metrics={metrics} loading={loading} />

            <div className="grid gap-6 lg:grid-cols-2">
              <AlertsPanel
                alerts={alerts}
                loading={loading}
                onAcknowledge={handleAcknowledgeAlert}
                onDismiss={handleDismissAlert}
              />
              <WatchlistsPanel
                watchlists={watchlists}
                loading={loading}
                showCreateWatchlist={showCreateWatchlist}
                setShowCreateWatchlist={setShowCreateWatchlist}
                newWatchlist={newWatchlist}
                setNewWatchlist={setNewWatchlist}
                onCreate={handleCreateWatchlist}
                onDelete={handleDeleteWatchlist}
              />
            </div>

            <SystemStatusPanel systemStatus={systemStatus} />
          </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
