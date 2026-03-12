import {
  buildAssignableUsers,
  normalizeAdminAlertHistoryPayload,
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
  adminAlertHistoryData: PromiseSettledResult<unknown>;
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

export type MonitoringApiClient = {
  getMetrics: () => Promise<unknown>;
  getWatchlists: () => Promise<unknown>;
  getAlerts: () => Promise<unknown>;
  getAdminAlertHistory: (params: { limit: string }) => Promise<unknown>;
  getHealth: () => Promise<unknown>;
  getLlmHealth: () => Promise<unknown>;
  getRagHealth: () => Promise<unknown>;
  getTtsHealth: () => Promise<unknown>;
  getSttHealth: () => Promise<unknown>;
  getEmbeddingsHealth: () => Promise<unknown>;
  getMetricsText: () => Promise<unknown>;
  getNotificationSettings: () => Promise<unknown>;
  getRecentNotifications: () => Promise<unknown>;
  getUsers: (params: { limit: string }) => Promise<unknown>;
};

type TimedRequestLoader = <T>(loader: () => Promise<T>) => Promise<{
  payload: T;
  checkedAt: string;
  responseTimeMs: number;
}>;

type FetchMonitoringSettledResultsArgs = {
  apiClient: MonitoringApiClient;
  measureTimedRequest: TimedRequestLoader;
};

export const fetchMonitoringSettledResults = async ({
  apiClient,
  measureTimedRequest,
}: FetchMonitoringSettledResultsArgs): Promise<MonitoringSettledResults> => {
  const [
    metricsData,
    watchlistsData,
    alertsData,
    adminAlertHistoryData,
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
    apiClient.getMetrics(),
    apiClient.getWatchlists(),
    apiClient.getAlerts(),
    apiClient.getAdminAlertHistory({ limit: '100' }),
    measureTimedRequest(() => apiClient.getHealth()),
    measureTimedRequest(() => apiClient.getLlmHealth()),
    measureTimedRequest(() => apiClient.getRagHealth()),
    measureTimedRequest(() => apiClient.getTtsHealth()),
    measureTimedRequest(() => apiClient.getSttHealth()),
    measureTimedRequest(() => apiClient.getEmbeddingsHealth()),
    apiClient.getMetricsText(),
    apiClient.getNotificationSettings(),
    apiClient.getRecentNotifications(),
    apiClient.getUsers({ limit: '100' }),
  ]);

  return {
    metricsData,
    watchlistsData,
    alertsData,
    adminAlertHistoryData,
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
  };
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
  { name: 'adminAlertHistory', result: settledResults.adminAlertHistoryData },
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
  metricWarningThreshold: number;
  metricCriticalThreshold: number;
};

export const resolveMonitoringLoadState = ({
  settledResults,
  previousAlerts,
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

  const alertsResult = settledResults.alertsData;
  const normalizedAlerts = alertsResult.status === 'fulfilled'
    ? normalizeMonitoringAlertsPayload(alertsResult.value)
    : null;

  const alerts = normalizedAlerts
    ? mergeAlertsWithLocalState(
      normalizedAlerts.filter((alert) => !alert.dismissed_at),
      previousAlerts
    )
    : null;

  const alertHistory = settledResults.adminAlertHistoryData.status === 'fulfilled'
    ? normalizeAdminAlertHistoryPayload(settledResults.adminAlertHistoryData.value)
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
