'use client';

import { useEffect, useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api-client';
import { isAlertSnoozed } from '@/lib/monitoring-alerts';
import {
  MONITORING_DEFAULT_SERIES_VISIBILITY,
  toggleMonitoringSeriesVisibility,
  type MonitoringMetricSeriesKey,
  type MonitoringMetricsSeriesVisibility,
  type MonitoringTimeRangeOption,
} from '@/lib/monitoring-metrics';
import {
  MONITORING_SUBSYSTEMS,
  normalizeMonitoringHealthStatus,
} from '@/lib/monitoring-health';
import AlertRulesPanel from './components/AlertRulesPanel';
import AlertsPanel from './components/AlertsPanel';
import MetricsChart from './components/MetricsChart';
import MetricsGrid from './components/MetricsGrid';
import NotificationsPanel from './components/NotificationsPanel';
import SystemStatusPanel from './components/SystemStatusPanel';
import TimeRangeControls from './components/TimeRangeControls';
import WatchlistsPanel from './components/WatchlistsPanel';
import { useMonitoringDataLoader } from './use-monitoring-data-loader';
import { useMonitoringDashboardState } from './use-monitoring-dashboard-state';
import { useMonitoringMetricsHistory } from './use-monitoring-metrics-history';
import { useAlertActions } from './use-alert-actions';
import { useAlertRules } from './use-alert-rules';
import { useMonitoringAlertState } from './use-monitoring-alert-state';
import { useMonitoringMessages } from './use-monitoring-messages';
import { useMonitoringNotificationState } from './use-monitoring-notification-state';
import { useNotificationActions } from './use-notification-actions';
import { useWatchlistActions } from './use-watchlist-actions';
import type {
  SystemHealthStatus,
  SystemStatusItem,
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
  const {
    metrics,
    setMetrics,
    watchlists,
    setWatchlists,
    systemStatus,
    setSystemStatus,
    loading,
    setLoading,
    lastUpdated,
    markMonitoringDataUpdated,
  } = useMonitoringDashboardState({
    initialSystemStatus: DEFAULT_SYSTEM_STATUS,
  });
  const [seriesVisibility, setSeriesVisibility] = useState<MonitoringMetricsSeriesVisibility>(
    MONITORING_DEFAULT_SERIES_VISIBILITY
  );

  // Notification settings
  const {
    notificationSettings,
    setNotificationSettings,
    recentNotifications,
    setRecentNotifications,
    setNotificationSettingsStatus,
    canSaveNotificationSettings,
  } = useMonitoringNotificationState();

  // Stage 2: Alert rules + enhanced alert management
  const {
    alerts,
    setAlerts,
    alertsRef,
    assignableUsers,
    setAssignableUsers,
    showSnoozedAlerts,
    setShowSnoozedAlerts,
    alertHistory,
    setAlertHistory,
    alertHistoryRef,
  } = useMonitoringAlertState();

  const handleManualRangeLoadSuccess = markMonitoringDataUpdated;

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

  const { loadData } = useMonitoringDataLoader({
    alertsRef,
    alertHistoryRef,
    customRangeStart,
    customRangeEnd,
    timeRange,
    loadMetricsHistoryForRange,
    markMonitoringDataUpdated,
    setLoading,
    setError,
    setNotificationSettingsStatus,
    setNotificationSettings,
    setRecentNotifications,
    setMetrics,
    setWatchlists,
    setAlerts,
    setAlertHistory,
    setAssignableUsers,
    setSystemStatus,
    metricWarningThreshold: METRIC_WARNING_THRESHOLD,
    metricCriticalThreshold: METRIC_CRITICAL_THRESHOLD,
  });

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
    canSave: canSaveNotificationSettings,
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
    void loadData();
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

            <TimeRangeControls
              options={MONITORING_TIME_RANGE_OPTIONS}
              timeRange={timeRange}
              customRangeStart={customRangeStart}
              customRangeEnd={customRangeEnd}
              rangeValidationError={rangeValidationError}
              onSelectTimeRange={handleSelectTimeRange}
              onCustomRangeStartChange={setCustomRangeStart}
              onCustomRangeEndChange={setCustomRangeEnd}
              onApplyCustomRange={handleApplyCustomTimeRange}
            />

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
                canSave={canSaveNotificationSettings}
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
