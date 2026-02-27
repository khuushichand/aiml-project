import { describe, expect, it, vi } from 'vitest';
import {
  fetchMonitoringSettledResults,
  monitoringLoadResultEntries,
  resolveMonitoringLoadState,
  type MonitoringApiClient,
} from './load-state-utils';
import type { AlertHistoryEntry, SystemAlert } from './types';

const fulfilledTimed = (payload: unknown): PromiseFulfilledResult<{
  payload: unknown;
  checkedAt: string;
  responseTimeMs: number;
}> => ({
  status: 'fulfilled',
  value: {
    payload,
    checkedAt: '2026-02-27T12:00:00.000Z',
    responseTimeMs: 12,
  },
});

const rejected = (reason: unknown): PromiseRejectedResult => ({
  status: 'rejected',
  reason,
});

const baseAlert = (overrides: Partial<SystemAlert> = {}): SystemAlert => ({
  id: 'alert-1',
  severity: 'warning',
  message: 'High CPU',
  source: 'system',
  timestamp: '2026-02-27T12:00:00.000Z',
  acknowledged: false,
  ...overrides,
});

describe('load-state-utils', () => {
  it('fetches all monitoring domains through a single settled request batch', async () => {
    const apiClient: MonitoringApiClient = {
      getMetrics: vi.fn().mockResolvedValue({ ok: true }),
      getWatchlists: vi.fn().mockResolvedValue({ items: [] }),
      getAlerts: vi.fn().mockResolvedValue({ items: [] }),
      getHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
      getLlmHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
      getRagHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
      getTtsHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
      getSttHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
      getEmbeddingsHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
      getMetricsText: vi.fn().mockResolvedValue('queue_depth 2'),
      getNotificationSettings: vi.fn().mockResolvedValue({ enabled: true }),
      getRecentNotifications: vi.fn().mockResolvedValue({ items: [] }),
      getUsers: vi.fn().mockResolvedValue([]),
    };

    const measureTimedRequest = vi.fn(async <T,>(loader: () => Promise<T>) => ({
      payload: await loader(),
      checkedAt: '2026-02-27T12:00:00.000Z',
      responseTimeMs: 4,
    }));

    const result = await fetchMonitoringSettledResults({
      apiClient,
      measureTimedRequest,
    });

    expect(result.metricsData.status).toBe('fulfilled');
    expect(result.watchlistsData.status).toBe('fulfilled');
    expect(result.alertsData.status).toBe('fulfilled');
    expect(result.healthTimedResult.status).toBe('fulfilled');
    expect(result.llmHealthTimedResult.status).toBe('fulfilled');
    expect(result.ragHealthTimedResult.status).toBe('fulfilled');
    expect(result.ttsHealthTimedResult.status).toBe('fulfilled');
    expect(result.sttHealthTimedResult.status).toBe('fulfilled');
    expect(result.embeddingsHealthTimedResult.status).toBe('fulfilled');
    expect(result.metricsTextData.status).toBe('fulfilled');
    expect(result.notificationSettingsData.status).toBe('fulfilled');
    expect(result.recentNotificationsData.status).toBe('fulfilled');
    expect(result.usersData.status).toBe('fulfilled');

    expect(measureTimedRequest).toHaveBeenCalledTimes(6);
    expect(apiClient.getUsers).toHaveBeenCalledWith({ limit: '100' });
  });

  it('produces merged state for fulfilled monitoring data', () => {
    const previousAlerts = [baseAlert({ id: 'alert-1', assigned_to: 'u2' })];
    const previousHistory: AlertHistoryEntry[] = [];

    const result = resolveMonitoringLoadState({
      previousAlerts,
      previousAlertHistory: previousHistory,
      metricWarningThreshold: 70,
      metricCriticalThreshold: 90,
      settledResults: {
        metricsData: {
          status: 'fulfilled',
          value: { cpu_usage: 95, memory_usage: 75, mode: 'degraded' },
        },
        watchlistsData: {
          status: 'fulfilled',
          value: { watchlists: [{ id: 'w1', name: 'CPU', status: 'healthy' }] },
        },
        alertsData: {
          status: 'fulfilled',
          value: { items: [baseAlert({ id: 'alert-1' }), baseAlert({ id: 'alert-2' })] },
        },
        usersData: {
          status: 'fulfilled',
          value: [
            { id: '1', email: 'a@example.com', username: 'alice' },
          ],
        },
        healthTimedResult: fulfilledTimed({ status: 'ok', checks: { database: { status: 'ok' } } }),
        llmHealthTimedResult: fulfilledTimed({ status: 'ok' }),
        ragHealthTimedResult: fulfilledTimed({ status: 'ok' }),
        ttsHealthTimedResult: fulfilledTimed({ status: 'ok' }),
        sttHealthTimedResult: fulfilledTimed({ status: 'ok' }),
        embeddingsHealthTimedResult: fulfilledTimed({ status: 'ok' }),
        metricsTextData: {
          status: 'fulfilled',
          value: 'queue_depth 4',
        },
        notificationSettingsData: {
          status: 'fulfilled',
          value: {
            enabled: true,
            min_severity: 'critical',
            email_to: 'ops@example.com',
          },
        },
        recentNotificationsData: {
          status: 'fulfilled',
          value: { items: [{ id: 'n1', channel: 'email', message: 'sent', status: 'sent', timestamp: '2026-02-27T12:00:00Z' }] },
        },
      },
    });

    expect(result.notificationSettingsStatus).toBe('fulfilled');
    expect(result.notificationSettings?.alert_threshold).toBe('critical');
    expect(result.recentNotifications).toHaveLength(1);
    expect(result.metrics).toEqual([
      { name: 'cpu_usage', value: 95, status: 'critical' },
      { name: 'memory_usage', value: 75, status: 'warning' },
      { name: 'mode', value: 'degraded', status: 'healthy' },
    ]);
    expect(result.watchlists).toEqual([{ id: 'w1', name: 'CPU', status: 'healthy' }]);
    expect(result.alerts?.[0]?.assigned_to).toBe('u2');
    expect(result.alerts).toHaveLength(2);
    expect(result.alertHistory).not.toBeNull();
    expect(result.assignableUsers).toEqual([{ id: '1', label: 'alice' }]);
    expect(result.systemStatus).toHaveLength(9);
  });

  it('returns null patch values for rejected optional domains', () => {
    const result = resolveMonitoringLoadState({
      previousAlerts: [],
      previousAlertHistory: [],
      metricWarningThreshold: 70,
      metricCriticalThreshold: 90,
      settledResults: {
        metricsData: rejected(new Error('metrics down')),
        watchlistsData: rejected(new Error('watchlists down')),
        alertsData: rejected(new Error('alerts down')),
        usersData: rejected(new Error('users down')),
        healthTimedResult: rejected(new Error('health down')),
        llmHealthTimedResult: rejected(new Error('llm down')),
        ragHealthTimedResult: rejected(new Error('rag down')),
        ttsHealthTimedResult: rejected(new Error('tts down')),
        sttHealthTimedResult: rejected(new Error('stt down')),
        embeddingsHealthTimedResult: rejected(new Error('embeddings down')),
        metricsTextData: rejected(new Error('metrics text down')),
        notificationSettingsData: rejected(new Error('settings down')),
        recentNotificationsData: rejected(new Error('notifications down')),
      },
    });

    expect(result.notificationSettingsStatus).toBe('rejected');
    expect(result.notificationSettings).toBeNull();
    expect(result.recentNotifications).toEqual([]);
    expect(result.metrics).toBeNull();
    expect(result.watchlists).toBeNull();
    expect(result.alerts).toBeNull();
    expect(result.alertHistory).toBeNull();
    expect(result.assignableUsers).toEqual([]);
    expect(result.systemStatus).toHaveLength(9);
  });

  it('returns ordered named settled result entries for warning logs', () => {
    const entries = monitoringLoadResultEntries({
      metricsData: rejected('metrics'),
      watchlistsData: rejected('watchlists'),
      alertsData: rejected('alerts'),
      healthTimedResult: rejected('health'),
      llmHealthTimedResult: rejected('llm'),
      ragHealthTimedResult: rejected('rag'),
      ttsHealthTimedResult: rejected('tts'),
      sttHealthTimedResult: rejected('stt'),
      embeddingsHealthTimedResult: rejected('embeddings'),
      metricsTextData: rejected('metricsText'),
      notificationSettingsData: rejected('notificationSettings'),
      recentNotificationsData: rejected('recentNotifications'),
      usersData: rejected('users'),
    });

    expect(entries.map((entry) => entry.name)).toEqual([
      'metrics',
      'watchlists',
      'alerts',
      'health',
      'llmHealth',
      'ragHealth',
      'ttsHealth',
      'sttHealth',
      'embeddingsHealth',
      'metricsText',
      'notificationSettings',
      'recentNotifications',
      'users',
    ]);
  });
});
