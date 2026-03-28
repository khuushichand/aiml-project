import { useCallback, useEffect, useMemo, useRef, useState, type ComponentProps } from 'react';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { api } from '@/lib/api-client';
import { isAlertSnoozed } from '@/lib/monitoring-alerts';
import {
  MONITORING_DEFAULT_SERIES_VISIBILITY,
  toggleMonitoringSeriesVisibility,
  type MonitoringMetricSeriesKey,
  type MonitoringMetricsSeriesVisibility,
  type MonitoringTimeRangeOption,
} from '@/lib/monitoring-metrics';
import { MONITORING_SUBSYSTEMS } from '@/lib/monitoring-health';
import MonitoringFeedbackBanners from './components/MonitoringFeedbackBanners';
import MonitoringManagementPanels from './components/MonitoringManagementPanels';
import MonitoringMetricsSection from './components/MonitoringMetricsSection';
import MonitoringPageHeader from './components/MonitoringPageHeader';
import { useAlertActions } from './use-alert-actions';
import { useAlertRules } from './use-alert-rules';
import { useMonitoringAlertState } from './use-monitoring-alert-state';
import { useMonitoringDashboardState } from './use-monitoring-dashboard-state';
import { useMonitoringDataLoader } from './use-monitoring-data-loader';
import { useMonitoringMessages } from './use-monitoring-messages';
import { useMonitoringMetricsHistory } from './use-monitoring-metrics-history';
import { useMonitoringManagementPanelsProps } from './use-monitoring-management-panels-props';
import { useMonitoringMetricsSectionProps } from './use-monitoring-metrics-section-props';
import { useMonitoringNotificationState } from './use-monitoring-notification-state';
import { useNotificationActions } from './use-notification-actions';
import { useWatchlistActions } from './use-watchlist-actions';
import type { SystemStatusItem } from './types';

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

type MonitoringPageController = {
  headerProps: ComponentProps<typeof MonitoringPageHeader>;
  feedbackBannersProps: ComponentProps<typeof MonitoringFeedbackBanners>;
  metricsSectionProps: ComponentProps<typeof MonitoringMetricsSection>;
  managementPanelsProps: ComponentProps<typeof MonitoringManagementPanels>;
};

export const useMonitoringPageController = (): MonitoringPageController => {
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

  const {
    notificationSettings,
    setNotificationSettings,
    recentNotifications,
    setRecentNotifications,
    setNotificationSettingsStatus,
    canSaveNotificationSettings,
  } = useMonitoringNotificationState();

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
    onManualRangeLoadSuccess: markMonitoringDataUpdated,
  });

  const handleToggleSeries = useCallback((seriesKey: MonitoringMetricSeriesKey) => {
    setSeriesVisibility((prev) => toggleMonitoringSeriesVisibility(prev, seriesKey));
  }, []);

  const {
    error,
    setError,
    success,
    setSuccess,
  } = useMonitoringMessages();
  const loadInFlightRef = useRef<Promise<void> | null>(null);

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

  const guardedLoadData = useCallback(async () => {
    if (loadInFlightRef.current) {
      return loadInFlightRef.current;
    }
    const pendingLoad = Promise.resolve(loadData()).finally(() => {
      if (loadInFlightRef.current === pendingLoad) {
        loadInFlightRef.current = null;
      }
    });
    loadInFlightRef.current = pendingLoad;
    return pendingLoad;
  }, [loadData]);

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
    onReloadRequested: guardedLoadData,
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
    setError,
    setSuccess,
    onReloadRequested: guardedLoadData,
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
    apiClient: api,
    setError,
    setSuccess,
  });

  useEffect(() => {
    void guardedLoadData();
  }, [guardedLoadData]);

  // Auto-refresh dashboard data every 60 seconds
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true);
  useEffect(() => {
    if (!autoRefreshEnabled) return;
    const id = setInterval(() => { void guardedLoadData(); }, 60_000);
    return () => clearInterval(id);
  }, [autoRefreshEnabled, guardedLoadData]);

  const activeAlertsCount = useMemo(
    () =>
      alerts.filter((alert) => !alert.acknowledged && !isAlertSnoozed(alert)).length,
    [alerts]
  );

  const headerProps = useMemo<ComponentProps<typeof MonitoringPageHeader>>(
    () => ({
      lastUpdated,
      loading,
      onRefresh: guardedLoadData,
      autoRefreshEnabled,
      onToggleAutoRefresh: () => setAutoRefreshEnabled((prev) => !prev),
    }),
    [lastUpdated, loading, guardedLoadData, autoRefreshEnabled]
  );

  const feedbackBannersProps = useMemo<ComponentProps<typeof MonitoringFeedbackBanners>>(
    () => ({
      error,
      success,
      activeAlertsCount,
    }),
    [error, success, activeAlertsCount]
  );

  const metricsSectionProps = useMonitoringMetricsSectionProps({
    options: MONITORING_TIME_RANGE_OPTIONS,
    timeRange,
    customRangeStart,
    customRangeEnd,
    rangeValidationError,
    onSelectTimeRange: handleSelectTimeRange,
    onCustomRangeStartChange: setCustomRangeStart,
    onCustomRangeEndChange: setCustomRangeEnd,
    onApplyCustomRange: handleApplyCustomTimeRange,
    metricsHistory,
    rangeLabel: activeRangeLabel,
    seriesVisibility,
    onToggleSeries: handleToggleSeries,
    metrics,
    loading,
  });

  const managementPanelsProps = useMonitoringManagementPanelsProps({
    alertRules,
    alertRuleDraft,
    alertRuleValidationErrors,
    alertRulesSaving,
    handleAlertRuleDraftChange,
    handleCreateAlertRule,
    handleDeleteAlertRule,
    alerts,
    alertHistory,
    showSnoozedAlerts,
    setShowSnoozedAlerts,
    assignableUsers,
    loading,
    handleAcknowledgeAlert,
    handleDismissAlert,
    handleAssignAlert,
    handleSnoozeAlert,
    handleEscalateAlert,
    watchlists,
    showCreateWatchlist,
    setShowCreateWatchlist,
    newWatchlist,
    setNewWatchlist,
    handleCreateWatchlist,
    handleDeleteWatchlist,
    deletingWatchlistId,
    notificationSettings,
    recentNotifications,
    notificationsSaving,
    canSaveNotificationSettings,
    handleSaveNotificationSettings,
    handleTestNotification,
    systemStatus,
  });

  return {
    headerProps,
    feedbackBannersProps,
    metricsSectionProps,
    managementPanelsProps,
  };
};
