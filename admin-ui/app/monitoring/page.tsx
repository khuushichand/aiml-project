'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api-client';
import {
  buildAlertHistoryEntry,
  buildAlertRuleFromDraft,
  buildAssignableUsers,
  DEFAULT_ALERT_RULE_DRAFT,
  ensureTriggeredHistoryEntries,
  isAlertSnoozed,
  normalizeMonitoringAlertsPayload,
  readStoredAlertHistory,
  readStoredAlertRules,
  resolveSnoozedUntil,
  validateAlertRuleDraft,
  writeStoredAlertHistory,
  writeStoredAlertRules,
} from '@/lib/monitoring-alerts';
import {
  buildSyntheticMonitoringMetricsHistory,
  extractAdditionalMetricSnapshot,
  MONITORING_DEFAULT_SERIES_VISIBILITY,
  normalizeMonitoringMetricsPayload,
  resolveMonitoringRangeParams,
  toggleMonitoringSeriesVisibility,
  type MonitoringMetricSeriesKey,
  type MonitoringMetricsSeriesVisibility,
  type MonitoringTimeRangeOption,
} from '@/lib/monitoring-metrics';
import {
  buildMonitoringSystemStatus,
  measureTimedEndpoint,
  MONITORING_SUBSYSTEMS,
  normalizeMonitoringHealthStatus,
} from '@/lib/monitoring-health';
import AlertRulesPanel from './components/AlertRulesPanel';
import AlertsPanel from './components/AlertsPanel';
import MetricsChart from './components/MetricsChart';
import MetricsGrid from './components/MetricsGrid';
import NotificationsPanel from './components/NotificationsPanel';
import SystemStatusPanel from './components/SystemStatusPanel';
import WatchlistsPanel from './components/WatchlistsPanel';
import {
  escalateAlertSeverity,
  markAlertAcknowledged,
  mergeAlertsWithLocalState,
  removeAlertById,
  setAlertAssignment,
  setAlertSnoozeUntil,
} from './alert-state-utils';
import {
  buildNotificationSettingsUpdate,
  normalizeNotificationSettings,
  normalizeRecentNotifications,
} from './notification-utils';
import type {
  AlertAssignableUser,
  AlertHistoryEntry,
  AlertRule,
  AlertRuleDraft,
  AlertRuleValidationErrors,
  Metric,
  MetricsHistoryPoint,
  NotificationSettings,
  RecentNotification,
  SnoozeDurationOption,
  SystemAlert,
  SystemHealthStatus,
  SystemStatusItem,
  Watchlist,
  WatchlistDraft,
} from './types';

interface HealthMetricsResponse {
  cpu?: { percent?: number };
  memory?: { percent?: number };
}

const METRICS_HISTORY_POLL_MS = 5 * 60 * 1000;
const METRIC_CRITICAL_THRESHOLD = 90;
const METRIC_WARNING_THRESHOLD = 70;
const DEFAULT_SYSTEM_STATUS: SystemStatusItem[] = [
  ...MONITORING_SUBSYSTEMS.map((subsystem) => ({
    key: subsystem.key,
    label: subsystem.label,
    status: 'unknown' as const,
    detail: 'Checking...',
  })),
];
const MONITORING_TIME_RANGE_OPTIONS: Array<{ value: MonitoringTimeRangeOption; label: string }> = [
  { value: '1h', label: '1h' },
  { value: '6h', label: '6h' },
  { value: '24h', label: '24h' },
  { value: '7d', label: '7d' },
  { value: '30d', label: '30d' },
  { value: 'custom', label: 'Custom' },
];
const toDatetimeLocalInputValue = (value: Date): string => {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  const hours = String(value.getHours()).padStart(2, '0');
  const minutes = String(value.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}`;
};

export const normalizeHealthStatus = (status?: string): SystemHealthStatus => {
  return normalizeMonitoringHealthStatus(status);
};

const normalizeWatchlistsPayload = (value: unknown): Watchlist[] => {
  if (Array.isArray(value)) return value as Watchlist[];
  if (value && typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    if (Array.isArray(obj.watchlists)) {
      return obj.watchlists as Watchlist[];
    }
  }
  return [];
};

export default function MonitoringPage() {
  const confirm = useConfirm();
  const now = new Date();
  const defaultCustomEnd = toDatetimeLocalInputValue(now);
  const defaultCustomStart = toDatetimeLocalInputValue(new Date(now.getTime() - (24 * 60 * 60 * 1000)));
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [alerts, setAlerts] = useState<SystemAlert[]>([]);
  const [metricsHistory, setMetricsHistory] = useState<MetricsHistoryPoint[]>([]);
  const [timeRange, setTimeRange] = useState<MonitoringTimeRangeOption>('24h');
  const [customRangeStart, setCustomRangeStart] = useState<string>(defaultCustomStart);
  const [customRangeEnd, setCustomRangeEnd] = useState<string>(defaultCustomEnd);
  const [rangeValidationError, setRangeValidationError] = useState('');
  const [activeRangeLabel, setActiveRangeLabel] = useState('24h');
  const [seriesVisibility, setSeriesVisibility] = useState<MonitoringMetricsSeriesVisibility>(
    MONITORING_DEFAULT_SERIES_VISIBILITY
  );
  const [systemStatus, setSystemStatus] = useState<SystemStatusItem[]>(DEFAULT_SYSTEM_STATUS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [deletingWatchlistId, setDeletingWatchlistId] = useState<string | null>(null);
  const successTimerRef = useRef<number | null>(null);
  const alertStorageHydratedRef = useRef(false);

  // Create watchlist dialog
  const [showCreateWatchlist, setShowCreateWatchlist] = useState(false);
  const [newWatchlist, setNewWatchlist] = useState<WatchlistDraft>({
    name: '',
    description: '',
    target: '',
    type: 'resource',
    threshold: 80,
  });

  // Notification settings
  const [notificationSettings, setNotificationSettings] = useState<NotificationSettings | null>(null);
  const [recentNotifications, setRecentNotifications] = useState<RecentNotification[]>([]);
  const [notificationsSaving, setNotificationsSaving] = useState(false);
  const [notificationSettingsStatus, setNotificationSettingsStatus] = useState<'pending' | 'fulfilled' | 'rejected'>('pending');

  // Stage 2: Alert rules + enhanced alert management
  const [alertRules, setAlertRules] = useState<AlertRule[]>([]);
  const [alertRuleDraft, setAlertRuleDraft] = useState<AlertRuleDraft>(DEFAULT_ALERT_RULE_DRAFT);
  const [alertRuleValidationErrors, setAlertRuleValidationErrors] = useState<AlertRuleValidationErrors>({});
  const [alertRulesSaving, setAlertRulesSaving] = useState(false);
  const [assignableUsers, setAssignableUsers] = useState<AlertAssignableUser[]>([]);
  const [showSnoozedAlerts, setShowSnoozedAlerts] = useState(false);
  const [alertHistory, setAlertHistory] = useState<AlertHistoryEntry[]>([]);

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
      const historyPayload = await api.getMonitoringMetrics({
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
          api.getHealthMetrics(),
          api.getMetrics(),
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
  }, []);

  const handleToggleSeries = (seriesKey: MonitoringMetricSeriesKey) => {
    setSeriesVisibility((prev) => toggleMonitoringSeriesVisibility(prev, seriesKey));
  };

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      setNotificationSettingsStatus('pending');

      const [
        metricsData,
        watchlistsData,
        alertsData,
        healthTimedResult,
        llmHealthTimedResult,
        ragHealthTimedResult,
        ttsHealthTimedResult,
        sttHealthTimedResult,
        embeddingsHealthTimedResult,
        metricsTextData,
        notificationSettingsData,
        recentNotificationsData,
        usersData,
      ] = await Promise.allSettled([
        api.getMetrics(),
        api.getWatchlists(),
        api.getAlerts(),
        measureTimedEndpoint(() => api.getHealth()),
        measureTimedEndpoint(() => api.getLlmHealth()),
        measureTimedEndpoint(() => api.getRagHealth()),
        measureTimedEndpoint(() => api.getTtsHealth()),
        measureTimedEndpoint(() => api.getSttHealth()),
        measureTimedEndpoint(() => api.getEmbeddingsHealth()),
        api.getMetricsText(),
        api.getNotificationSettings(),
        api.getRecentNotifications(),
        api.getUsers({ limit: '100' }),
      ]);

      [
        { name: 'metrics', result: metricsData },
        { name: 'watchlists', result: watchlistsData },
        { name: 'alerts', result: alertsData },
        { name: 'health', result: healthTimedResult },
        { name: 'llmHealth', result: llmHealthTimedResult },
        { name: 'ragHealth', result: ragHealthTimedResult },
        { name: 'ttsHealth', result: ttsHealthTimedResult },
        { name: 'sttHealth', result: sttHealthTimedResult },
        { name: 'embeddingsHealth', result: embeddingsHealthTimedResult },
        { name: 'metricsText', result: metricsTextData },
        { name: 'notificationSettings', result: notificationSettingsData },
        { name: 'recentNotifications', result: recentNotificationsData },
        { name: 'users', result: usersData },
      ].forEach(({ name, result }) => {
        if (result.status === 'rejected') {
          console.warn(`Failed to load ${name}:`, result.reason);
        }
      });

      // Process notification settings
      setNotificationSettingsStatus(notificationSettingsData.status);
      if (notificationSettingsData.status === 'fulfilled') {
        setNotificationSettings(normalizeNotificationSettings(notificationSettingsData.value));
      } else {
        setNotificationSettings(null);
      }

      // Process recent notifications
      if (recentNotificationsData.status === 'fulfilled') {
        setRecentNotifications(normalizeRecentNotifications(recentNotificationsData.value));
      } else {
        setRecentNotifications([]);
      }

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
        setWatchlists(normalizeWatchlistsPayload(watchlistsData.value));
      }

      // Process alerts
      if (alertsData.status === 'fulfilled') {
        const normalizedAlerts = normalizeMonitoringAlertsPayload(alertsData.value);
        setAlerts((prev) => mergeAlertsWithLocalState(normalizedAlerts, prev));
        setAlertHistory((prev) => ensureTriggeredHistoryEntries(prev, normalizedAlerts));
      }

      // Process assignable users
      if (usersData.status === 'fulfilled') {
        setAssignableUsers(buildAssignableUsers(usersData.value));
      } else {
        setAssignableUsers([]);
      }

      setSystemStatus(buildMonitoringSystemStatus({
        healthResult: healthTimedResult,
        llmHealthResult: llmHealthTimedResult,
        ragHealthResult: ragHealthTimedResult,
        ttsHealthResult: ttsHealthTimedResult,
        sttHealthResult: sttHealthTimedResult,
        embeddingsHealthResult: embeddingsHealthTimedResult,
        metricsSnapshotResult: metricsData,
        metricsTextResult: metricsTextData,
      }));

      void loadMetricsHistoryForRange(timeRange, customRangeStart, customRangeEnd);
      setLastUpdated(new Date());
    } catch (err: unknown) {
      console.error('Failed to load monitoring data:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to load monitoring data');
      setNotificationSettingsStatus('rejected');
      setNotificationSettings(null);
    } finally {
      setLoading(false);
    }
  }, [customRangeEnd, customRangeStart, loadMetricsHistoryForRange, timeRange]);

  useEffect(() => {
    setAlertRules(readStoredAlertRules());
    setAlertHistory(readStoredAlertHistory());
    alertStorageHydratedRef.current = true;
  }, []);

  useEffect(() => {
    if (!alertStorageHydratedRef.current) return;
    writeStoredAlertRules(alertRules);
  }, [alertRules]);

  useEffect(() => {
    if (!alertStorageHydratedRef.current) return;
    writeStoredAlertHistory(alertHistory);
  }, [alertHistory]);

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
    void loadMetricsHistoryForRange(timeRange, customRangeStart, customRangeEnd);
    const intervalId = window.setInterval(() => {
      void loadMetricsHistoryForRange(timeRange, customRangeStart, customRangeEnd);
    }, METRICS_HISTORY_POLL_MS);
    return () => window.clearInterval(intervalId);
  }, [customRangeEnd, customRangeStart, loadMetricsHistoryForRange, timeRange]);

  const handleSelectTimeRange = async (nextRange: MonitoringTimeRangeOption) => {
    setTimeRange(nextRange);
    if (nextRange === 'custom') {
      return;
    }
    const loaded = await loadMetricsHistoryForRange(nextRange, customRangeStart, customRangeEnd);
    if (loaded) {
      setLastUpdated(new Date());
    }
  };

  const handleApplyCustomTimeRange = async () => {
    setTimeRange('custom');
    const loaded = await loadMetricsHistoryForRange('custom', customRangeStart, customRangeEnd);
    if (loaded) {
      setLastUpdated(new Date());
    }
  };

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
    const watchlistId = String(watchlist.id);
    if (deletingWatchlistId === watchlistId) return;
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
      setDeletingWatchlistId(watchlistId);
      await api.deleteWatchlist(watchlist.id);
      setSuccess('Watchlist deleted');
      loadData();
    } catch (err: unknown) {
      console.error('Failed to delete watchlist:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to delete watchlist');
    } finally {
      setDeletingWatchlistId((prev) => (prev === watchlistId ? null : prev));
    }
  };

  const appendAlertHistory = (
    alertId: string,
    action: AlertHistoryEntry['action'],
    details: string,
    actor?: string
  ) => {
    setAlertHistory((prev) => [
      buildAlertHistoryEntry(alertId, action, details, { actor }),
      ...prev,
    ]);
  };

  const handleCreateAlertRule = () => {
    const validation = validateAlertRuleDraft(alertRuleDraft);
    if (!validation.valid) {
      setAlertRuleValidationErrors(validation.errors);
      return;
    }

    setAlertRulesSaving(true);
    try {
      const newRule = buildAlertRuleFromDraft(alertRuleDraft);
      setAlertRules((prev) => [newRule, ...prev]);
      setAlertRuleValidationErrors({});
      setAlertRuleDraft(DEFAULT_ALERT_RULE_DRAFT);
      setSuccess('Alert rule added');
    } finally {
      setAlertRulesSaving(false);
    }
  };

  const handleDeleteAlertRule = (rule: AlertRule) => {
    setAlertRules((prev) => prev.filter((item) => item.id !== rule.id));
    setSuccess('Alert rule deleted');
  };

  const handleAcknowledgeAlert = async (alert: SystemAlert) => {
    try {
      setError('');
      await api.acknowledgeAlert(alert.id);
      setAlerts((prev) => markAlertAcknowledged(prev, alert.id, new Date().toISOString()));
      appendAlertHistory(alert.id, 'acknowledged', 'Alert acknowledged');
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
      appendAlertHistory(alert.id, 'dismissed', 'Alert dismissed');
      setAlerts((prev) => removeAlertById(prev, alert.id));
      setSuccess('Alert dismissed');
      loadData();
    } catch (err: unknown) {
      console.error('Failed to dismiss alert:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to dismiss alert');
    }
  };

  const handleAssignAlert = (alert: SystemAlert, userId: string) => {
    setAlerts((prev) => setAlertAssignment(prev, alert.id, userId || undefined));
    const assignedLabel = userId
      ? (assignableUsers.find((user) => user.id === userId)?.label ?? userId)
      : 'Unassigned';
    appendAlertHistory(alert.id, 'assigned', `Assigned to ${assignedLabel}`);
    setSuccess(userId ? 'Alert assigned' : 'Alert unassigned');
  };

  const handleSnoozeAlert = (alert: SystemAlert, duration: SnoozeDurationOption) => {
    const snoozedUntil = resolveSnoozedUntil(duration);
    setAlerts((prev) => setAlertSnoozeUntil(prev, alert.id, snoozedUntil));
    appendAlertHistory(alert.id, 'snoozed', `Snoozed for ${duration}`);
    setSuccess(`Alert snoozed for ${duration}`);
  };

  const handleEscalateAlert = (alert: SystemAlert) => {
    if (alert.severity === 'critical') {
      return;
    }
    setAlerts((prev) => escalateAlertSeverity(prev, alert.id));
    appendAlertHistory(alert.id, 'escalated', 'Severity escalated to critical');
    setSuccess('Alert escalated to critical');
  };

  const handleSaveNotificationSettings = async (settings: NotificationSettings) => {
    if (notificationSettingsStatus !== 'fulfilled') {
      return false;
    }
    try {
      setNotificationsSaving(true);
      setError('');
      const payload = buildNotificationSettingsUpdate(settings);
      const updated = await api.updateNotificationSettings(payload as unknown as Record<string, unknown>);
      setNotificationSettings(normalizeNotificationSettings(updated));
      setSuccess('Notification settings saved');
      return true;
    } catch (err: unknown) {
      console.error('Failed to save notification settings:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to save notification settings');
      return false;
    } finally {
      setNotificationsSaving(false);
    }
  };

  const handleTestNotification = async (
    payload?: {
      message?: string;
      severity?: string;
    },
  ) => {
    try {
      setError('');
      await api.testNotification(payload ?? {});
      setSuccess('Test notification sent');
      // Reload recent notifications
      try {
        const data = await api.getRecentNotifications();
        setRecentNotifications(normalizeRecentNotifications(data));
      } catch {
        // Ignore reload errors
      }
    } catch (err: unknown) {
      console.error('Failed to send test notification:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to send test notification');
    }
  };

  const activeAlerts = alerts.filter((alert) => !alert.acknowledged && !isAlertSnoozed(alert));

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <p
              className="sr-only"
              role="status"
              aria-live="polite"
              aria-atomic="true"
              data-testid="monitoring-alert-count-live"
            >
              {activeAlerts.length} active alert{activeAlerts.length !== 1 ? 's' : ''} currently require attention.
            </p>
            <div className="mb-8 flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold">Monitoring</h1>
                <p className="text-muted-foreground">
                  System health, metrics, and alerts
                </p>
              </div>
              <div className="flex items-center gap-4">
                {lastUpdated && (
                  <span className="text-sm text-muted-foreground" aria-live="polite">
                    Last updated: {lastUpdated.toLocaleTimeString()}
                  </span>
                )}
                <Button variant="outline" onClick={loadData} disabled={loading}>
                  <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
                  Refresh
                </Button>
              </div>
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

            <div className="mb-4 rounded-lg border border-border/80 bg-muted/10 p-4">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium">Time Range</span>
                {MONITORING_TIME_RANGE_OPTIONS.map((option) => (
                  <Button
                    key={option.value}
                    type="button"
                    size="sm"
                    variant={timeRange === option.value ? 'secondary' : 'outline'}
                    onClick={() => { void handleSelectTimeRange(option.value); }}
                    data-testid={`monitoring-time-range-${option.value}`}
                  >
                    {option.label}
                  </Button>
                ))}
              </div>
              {timeRange === 'custom' && (
                <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto] md:items-end">
                  <div className="space-y-1">
                    <Label htmlFor="customRangeStart">Custom Start</Label>
                    <Input
                      id="customRangeStart"
                      type="datetime-local"
                      value={customRangeStart}
                      onChange={(event) => {
                        setCustomRangeStart(event.target.value);
                        setRangeValidationError('');
                      }}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="customRangeEnd">Custom End</Label>
                    <Input
                      id="customRangeEnd"
                      type="datetime-local"
                      value={customRangeEnd}
                      onChange={(event) => {
                        setCustomRangeEnd(event.target.value);
                        setRangeValidationError('');
                      }}
                    />
                  </div>
                  <Button
                    type="button"
                    onClick={() => { void handleApplyCustomTimeRange(); }}
                    data-testid="monitoring-time-range-apply-custom"
                  >
                    Apply
                  </Button>
                </div>
              )}
              {rangeValidationError && (
                <p className="mt-2 text-sm text-destructive">{rangeValidationError}</p>
              )}
            </div>

            <MetricsChart
              metricsHistory={metricsHistory}
              rangeLabel={activeRangeLabel}
              seriesVisibility={seriesVisibility}
              onToggleSeries={handleToggleSeries}
            />
            <MetricsGrid metrics={metrics} loading={loading} />

            <div className="mb-6">
              <AlertRulesPanel
                rules={alertRules}
                draft={alertRuleDraft}
                errors={alertRuleValidationErrors}
                saving={alertRulesSaving}
                onDraftChange={(draft) => {
                  setAlertRuleDraft(draft);
                  setAlertRuleValidationErrors({});
                }}
                onCreateRule={handleCreateAlertRule}
                onDeleteRule={handleDeleteAlertRule}
              />
              <p className="mt-2 text-xs text-muted-foreground">
                Alert rules are stored locally until a backend alert-rules endpoint is available.
              </p>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <AlertsPanel
                alerts={alerts}
                history={alertHistory}
                showSnoozed={showSnoozedAlerts}
                assignableUsers={assignableUsers}
                loading={loading}
                onToggleShowSnoozed={() => setShowSnoozedAlerts((prev) => !prev)}
                onAcknowledge={handleAcknowledgeAlert}
                onDismiss={handleDismissAlert}
                onAssign={handleAssignAlert}
                onSnooze={handleSnoozeAlert}
                onEscalate={handleEscalateAlert}
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
                deletingWatchlistId={deletingWatchlistId}
              />
            </div>

            <div className="grid gap-6 lg:grid-cols-2 mt-6">
              <NotificationsPanel
                settings={notificationSettings}
                recentNotifications={recentNotifications}
                loading={loading}
                saving={notificationsSaving}
                canSave={notificationSettingsStatus === 'fulfilled'}
                onSave={handleSaveNotificationSettings}
                onTest={handleTestNotification}
              />
              <SystemStatusPanel systemStatus={systemStatus} />
            </div>
          </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
