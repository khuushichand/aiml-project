import { useEffect, useState, type ComponentProps } from 'react';
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

  const activeAlertsCount = alerts.filter(
    (alert) => !alert.acknowledged && !isAlertSnoozed(alert)
  ).length;

  return {
    headerProps: {
      lastUpdated,
      loading,
      onRefresh: loadData,
    },
    feedbackBannersProps: {
      error,
      success,
      activeAlertsCount,
    },
    metricsSectionProps: {
      timeRangeControlsProps: {
        options: MONITORING_TIME_RANGE_OPTIONS,
        timeRange,
        customRangeStart,
        customRangeEnd,
        rangeValidationError,
        onSelectTimeRange: handleSelectTimeRange,
        onCustomRangeStartChange: setCustomRangeStart,
        onCustomRangeEndChange: setCustomRangeEnd,
        onApplyCustomRange: handleApplyCustomTimeRange,
      },
      metricsChartProps: {
        metricsHistory,
        rangeLabel: activeRangeLabel,
        seriesVisibility,
        onToggleSeries: handleToggleSeries,
      },
      metricsGridProps: {
        metrics,
        loading,
      },
    },
    managementPanelsProps: {
      alertRulesPanelProps: {
        rules: alertRules,
        draft: alertRuleDraft,
        errors: alertRuleValidationErrors,
        saving: alertRulesSaving,
        onDraftChange: handleAlertRuleDraftChange,
        onCreateRule: handleCreateAlertRule,
        onDeleteRule: handleDeleteAlertRule,
      },
      alertsPanelProps: {
        alerts,
        history: alertHistory,
        showSnoozed: showSnoozedAlerts,
        assignableUsers,
        loading,
        onToggleShowSnoozed: () => setShowSnoozedAlerts((prev) => !prev),
        onAcknowledge: handleAcknowledgeAlert,
        onDismiss: handleDismissAlert,
        onAssign: handleAssignAlert,
        onSnooze: handleSnoozeAlert,
        onEscalate: handleEscalateAlert,
      },
      watchlistsPanelProps: {
        watchlists,
        loading,
        showCreateWatchlist,
        setShowCreateWatchlist,
        newWatchlist,
        setNewWatchlist,
        onCreate: handleCreateWatchlist,
        onDelete: handleDeleteWatchlist,
        deletingWatchlistId,
      },
      notificationsPanelProps: {
        settings: notificationSettings,
        recentNotifications,
        loading,
        saving: notificationsSaving,
        canSave: canSaveNotificationSettings,
        onSave: handleSaveNotificationSettings,
        onTest: handleTestNotification,
      },
      systemStatusPanelProps: {
        systemStatus,
      },
    },
  };
};
