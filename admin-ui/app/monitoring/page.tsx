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
  isAlertSnoozed,
  readStoredAlertHistory,
  writeStoredAlertHistory,
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
import { useMonitoringMetricsHistory } from './use-monitoring-metrics-history';
import { useAlertActions } from './use-alert-actions';
import { useAlertRules } from './use-alert-rules';
import { useMonitoringMessages } from './use-monitoring-messages';
import { useNotificationActions } from './use-notification-actions';
import { useWatchlistActions } from './use-watchlist-actions';
import type {
  AlertAssignableUser,
  AlertHistoryEntry,
  Metric,
  NotificationSettings,
  RecentNotification,
  SystemAlert,
  SystemHealthStatus,
  SystemStatusItem,
  Watchlist,
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
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const alertStorageHydratedRef = useRef(false);

  // Notification settings
  const [notificationSettings, setNotificationSettings] = useState<NotificationSettings | null>(null);
  const [recentNotifications, setRecentNotifications] = useState<RecentNotification[]>([]);
  const [notificationSettingsStatus, setNotificationSettingsStatus] = useState<'pending' | 'fulfilled' | 'rejected'>('pending');

  // Stage 2: Alert rules + enhanced alert management
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

  const {
    error,
    setError,
    success,
    setSuccess,
  } = useMonitoringMessages();

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
  }, [customRangeEnd, customRangeStart, loadMetricsHistoryForRange, setError, timeRange]);

  const {
    showCreateWatchlist,
    setShowCreateWatchlist,
    newWatchlist,
    setNewWatchlist,
    deletingWatchlistId,
    handleCreateWatchlist,
    handleDeleteWatchlist,
  } = useWatchlistActions({
    apiClient: api,
    confirm,
    setError,
    setSuccess,
    onReloadRequested: loadData,
  });

  const {
    handleAcknowledgeAlert,
    handleDismissAlert,
    handleAssignAlert,
    handleSnoozeAlert,
    handleEscalateAlert,
  } = useAlertActions({
    apiClient: api,
    confirm,
    setAlerts,
    setAlertHistory,
    setError,
    setSuccess,
    onReloadRequested: loadData,
    assignableUsers,
  });

  const {
    notificationsSaving,
    handleSaveNotificationSettings,
    handleTestNotification,
  } = useNotificationActions({
    apiClient: api,
    canSave: notificationSettingsStatus === 'fulfilled',
    setNotificationSettings,
    setRecentNotifications,
    setError,
    setSuccess,
  });

  const {
    alertRules,
    alertRuleDraft,
    alertRuleValidationErrors,
    alertRulesSaving,
    handleAlertRuleDraftChange,
    handleCreateAlertRule,
    handleDeleteAlertRule,
  } = useAlertRules({
    setSuccess,
  });

  useEffect(() => {
    setAlertHistory(readStoredAlertHistory());
    alertStorageHydratedRef.current = true;
  }, []);

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
                onDraftChange={handleAlertRuleDraftChange}
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
