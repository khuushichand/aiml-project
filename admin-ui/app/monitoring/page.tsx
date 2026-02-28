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
  DEFAULT_ALERT_RULE_DRAFT,
  isAlertSnoozed,
  readStoredAlertHistory,
  readStoredAlertRules,
  resolveSnoozedUntil,
  validateAlertRuleDraft,
  writeStoredAlertHistory,
  writeStoredAlertRules,
} from '@/lib/monitoring-alerts';
import {
  MONITORING_DEFAULT_SERIES_VISIBILITY,
  toggleMonitoringSeriesVisibility,
  type MonitoringMetricSeriesKey,
  type MonitoringMetricsSeriesVisibility,
  type MonitoringTimeRangeOption,
} from '@/lib/monitoring-metrics';
import {
  measureTimedEndpoint,
  MONITORING_SUBSYSTEMS,
  normalizeMonitoringHealthStatus,
} from '@/lib/monitoring-health';
import {
  fetchMonitoringSettledResults,
  monitoringLoadResultEntries,
  resolveMonitoringLoadState,
} from './load-state-utils';
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
  removeAlertById,
  setAlertAssignment,
  setAlertSnoozeUntil,
} from './alert-state-utils';
import {
  buildNotificationSettingsUpdate,
  normalizeNotificationSettings,
  normalizeRecentNotifications,
} from './notification-utils';
import { useMonitoringMetricsHistory } from './use-monitoring-metrics-history';
import type {
  AlertAssignableUser,
  AlertHistoryEntry,
  AlertRule,
  AlertRuleDraft,
  AlertRuleValidationErrors,
  Metric,
  NotificationSettings,
  RecentNotification,
  SnoozeDurationOption,
  SystemAlert,
  SystemHealthStatus,
  SystemStatusItem,
  Watchlist,
  WatchlistDraft,
} from './types';

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

export const normalizeHealthStatus = (status?: string): SystemHealthStatus => {
  return normalizeMonitoringHealthStatus(status);
};

export default function MonitoringPage() {
  const confirm = useConfirm();
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [alerts, setAlerts] = useState<SystemAlert[]>([]);
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
  const alertsRef = useRef<SystemAlert[]>([]);
  const alertHistoryRef = useRef<AlertHistoryEntry[]>([]);

  const handleManualRangeLoadSuccess = useCallback(() => {
    setLastUpdated(new Date());
  }, []);

  const {
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
  } = useMonitoringMetricsHistory({
    apiClient: api,
    onManualRangeLoadSuccess: handleManualRangeLoadSuccess,
  });

  const handleToggleSeries = (seriesKey: MonitoringMetricSeriesKey) => {
    setSeriesVisibility((prev) => toggleMonitoringSeriesVisibility(prev, seriesKey));
  };

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      setNotificationSettingsStatus('pending');

      const settledResults = await fetchMonitoringSettledResults({
        apiClient: api,
        measureTimedRequest: measureTimedEndpoint,
      });

      monitoringLoadResultEntries(settledResults).forEach(({ name, result }) => {
        if (result.status === 'rejected') {
          console.warn(`Failed to load ${name}:`, result.reason);
        }
      });

      const resolvedState = resolveMonitoringLoadState({
        settledResults,
        previousAlerts: alertsRef.current,
        previousAlertHistory: alertHistoryRef.current,
        metricWarningThreshold: METRIC_WARNING_THRESHOLD,
        metricCriticalThreshold: METRIC_CRITICAL_THRESHOLD,
      });

      setNotificationSettingsStatus(resolvedState.notificationSettingsStatus);
      setNotificationSettings(resolvedState.notificationSettings);
      setRecentNotifications(resolvedState.recentNotifications);
      if (resolvedState.metrics) {
        setMetrics(resolvedState.metrics);
      }
      if (resolvedState.watchlists) {
        setWatchlists(resolvedState.watchlists);
      }
      if (resolvedState.alerts) {
        alertsRef.current = resolvedState.alerts;
        setAlerts(resolvedState.alerts);
      }
      if (resolvedState.alertHistory) {
        alertHistoryRef.current = resolvedState.alertHistory;
        setAlertHistory(resolvedState.alertHistory);
      }
      setAssignableUsers(resolvedState.assignableUsers);
      setSystemStatus(resolvedState.systemStatus);

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
    alertsRef.current = alerts;
  }, [alerts]);

  useEffect(() => {
    alertHistoryRef.current = alertHistory;
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
