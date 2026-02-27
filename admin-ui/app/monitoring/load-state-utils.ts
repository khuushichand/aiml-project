import {
  buildAssignableUsers,
  ensureTriggeredHistoryEntries,
  normalizeMonitoringAlertsPayload,
} from '@/lib/monitoring-alerts';
import { buildMonitoringSystemStatus, type TimedEndpointResult } from '@/lib/monitoring-health';
import { mergeAlertsWithLocalState } from './alert-state-utils';
import { buildMetricsFromSnapshot, normalizeWatchlistsPayload } from './metrics-state-utils';
import { normalizeNotificationSettings, normalizeRecentNotifications } from './notification-utils';
import type {
  AlertAssignableUser,
  AlertHistoryEntry,
  Metric,
  NotificationSettings,
  RecentNotification,
  SystemAlert,
  SystemStatusItem,
  Watchlist,
} from './types';

export type MonitoringSettledResults = {
  metricsData: PromiseSettledResult<unknown>;
  watchlistsData: PromiseSettledResult<unknown>;
  alertsData: PromiseSettledResult<unknown>;
  healthTimedResult: TimedEndpointResult<unknown>;
  llmHealthTimedResult: TimedEndpointResult<unknown>;
  ragHealthTimedResult: TimedEndpointResult<unknown>;
  ttsHealthTimedResult: TimedEndpointResult<unknown>;
  sttHealthTimedResult: TimedEndpointResult<unknown>;
  embeddingsHealthTimedResult: TimedEndpointResult<unknown>;
  metricsTextData: PromiseSettledResult<unknown>;
  notificationSettingsData: PromiseSettledResult<unknown>;
  recentNotificationsData: PromiseSettledResult<unknown>;
  usersData: PromiseSettledResult<unknown>;
};

export type MonitoringNamedResult = {
  name: string;
  result: PromiseSettledResult<unknown>;
};

export const monitoringLoadResultEntries = (
  settledResults: MonitoringSettledResults
): MonitoringNamedResult[] => [
  { name: 'metrics', result: settledResults.metricsData },
  { name: 'watchlists', result: settledResults.watchlistsData },
  { name: 'alerts', result: settledResults.alertsData },
  { name: 'health', result: settledResults.healthTimedResult },
  { name: 'llmHealth', result: settledResults.llmHealthTimedResult },
  { name: 'ragHealth', result: settledResults.ragHealthTimedResult },
  { name: 'ttsHealth', result: settledResults.ttsHealthTimedResult },
  { name: 'sttHealth', result: settledResults.sttHealthTimedResult },
  { name: 'embeddingsHealth', result: settledResults.embeddingsHealthTimedResult },
  { name: 'metricsText', result: settledResults.metricsTextData },
  { name: 'notificationSettings', result: settledResults.notificationSettingsData },
  { name: 'recentNotifications', result: settledResults.recentNotificationsData },
  { name: 'users', result: settledResults.usersData },
];

export type MonitoringLoadResolution = {
  notificationSettingsStatus: 'fulfilled' | 'rejected';
  notificationSettings: NotificationSettings | null;
  recentNotifications: RecentNotification[];
  metrics: Metric[] | null;
  watchlists: Watchlist[] | null;
  alerts: SystemAlert[] | null;
  alertHistory: AlertHistoryEntry[] | null;
  assignableUsers: AlertAssignableUser[];
  systemStatus: SystemStatusItem[];
};

type ResolveMonitoringLoadStateArgs = {
  settledResults: MonitoringSettledResults;
  previousAlerts: SystemAlert[];
  previousAlertHistory: AlertHistoryEntry[];
  metricWarningThreshold: number;
  metricCriticalThreshold: number;
};

export const resolveMonitoringLoadState = ({
  settledResults,
  previousAlerts,
  previousAlertHistory,
  metricWarningThreshold,
  metricCriticalThreshold,
}: ResolveMonitoringLoadStateArgs): MonitoringLoadResolution => {
  const notificationSettingsStatus = settledResults.notificationSettingsData.status;
  const notificationSettings = notificationSettingsStatus === 'fulfilled'
    ? normalizeNotificationSettings(settledResults.notificationSettingsData.value)
    : null;

  const recentNotifications = settledResults.recentNotificationsData.status === 'fulfilled'
    ? normalizeRecentNotifications(settledResults.recentNotificationsData.value)
    : [];

  const metrics = settledResults.metricsData.status === 'fulfilled' && settledResults.metricsData.value
    ? buildMetricsFromSnapshot(
      settledResults.metricsData.value,
      metricWarningThreshold,
      metricCriticalThreshold
    )
    : null;

  const watchlists = settledResults.watchlistsData.status === 'fulfilled'
    ? normalizeWatchlistsPayload(settledResults.watchlistsData.value)
    : null;

  const alertsDataFulfilled = settledResults.alertsData.status === 'fulfilled';
  const normalizedAlerts = alertsDataFulfilled
    ? normalizeMonitoringAlertsPayload(settledResults.alertsData.value)
    : null;

  const alerts = normalizedAlerts
    ? mergeAlertsWithLocalState(normalizedAlerts, previousAlerts)
    : null;

  const alertHistory = normalizedAlerts
    ? ensureTriggeredHistoryEntries(previousAlertHistory, normalizedAlerts)
    : null;

  const assignableUsers = settledResults.usersData.status === 'fulfilled'
    ? buildAssignableUsers(settledResults.usersData.value)
    : [];

  const systemStatus = buildMonitoringSystemStatus({
    healthResult: settledResults.healthTimedResult,
    llmHealthResult: settledResults.llmHealthTimedResult,
    ragHealthResult: settledResults.ragHealthTimedResult,
    ttsHealthResult: settledResults.ttsHealthTimedResult,
    sttHealthResult: settledResults.sttHealthTimedResult,
    embeddingsHealthResult: settledResults.embeddingsHealthTimedResult,
    metricsSnapshotResult: settledResults.metricsData,
    metricsTextResult: settledResults.metricsTextData,
  });

  return {
    notificationSettingsStatus,
    notificationSettings,
    recentNotifications,
    metrics,
    watchlists,
    alerts,
    alertHistory,
    assignableUsers,
    systemStatus,
  };
};
