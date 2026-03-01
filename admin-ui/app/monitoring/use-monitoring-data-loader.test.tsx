/* @vitest-environment jsdom */
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { MutableRefObject } from 'react';
import type { MonitoringTimeRangeOption } from '@/lib/monitoring-metrics';
import type { AlertHistoryEntry, SystemAlert } from './types';
import { useMonitoringDataLoader } from './use-monitoring-data-loader';

const {
  fetchMonitoringSettledResultsMock,
  monitoringLoadResultEntriesMock,
  resolveMonitoringLoadStateMock,
} = vi.hoisted(() => ({
  fetchMonitoringSettledResultsMock: vi.fn(),
  monitoringLoadResultEntriesMock: vi.fn(),
  resolveMonitoringLoadStateMock: vi.fn(),
}));

vi.mock('@/lib/api-client', () => ({
  api: {},
}));

vi.mock('@/lib/monitoring-health', () => ({
  measureTimedEndpoint: vi.fn(),
}));

vi.mock('./load-state-utils', () => ({
  fetchMonitoringSettledResults: (...args: unknown[]) => fetchMonitoringSettledResultsMock(...args),
  monitoringLoadResultEntries: (...args: unknown[]) => monitoringLoadResultEntriesMock(...args),
  resolveMonitoringLoadState: (...args: unknown[]) => resolveMonitoringLoadStateMock(...args),
}));

const createCommonArgs = () => {
  const alertsRef: MutableRefObject<SystemAlert[]> = { current: [] };
  const alertHistoryRef: MutableRefObject<AlertHistoryEntry[]> = { current: [] };
  const timeRange: MonitoringTimeRangeOption = '24h';

  return {
    alertsRef,
    alertHistoryRef,
    customRangeStart: '2026-02-28T11:00',
    customRangeEnd: '2026-02-28T12:00',
    timeRange,
    loadMetricsHistoryForRange: vi.fn(),
    markMonitoringDataUpdated: vi.fn(),
    setLoading: vi.fn(),
    setError: vi.fn(),
    setNotificationSettingsStatus: vi.fn(),
    setNotificationSettings: vi.fn(),
    setRecentNotifications: vi.fn(),
    setMetrics: vi.fn(),
    setWatchlists: vi.fn(),
    setAlerts: vi.fn(),
    setAlertHistory: vi.fn(),
    setAssignableUsers: vi.fn(),
    setSystemStatus: vi.fn(),
    metricWarningThreshold: 70,
    metricCriticalThreshold: 90,
  };
};

describe('useMonitoringDataLoader', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('loads monitoring data and applies resolved state updates', async () => {
    const args = createCommonArgs();
    const settledResults = { request: 'ok' };
    const resolvedAlerts: SystemAlert[] = [
      {
        id: 'alert-1',
        severity: 'warning',
        message: 'CPU warning',
        source: 'metrics',
        timestamp: '2026-02-28T12:00:00.000Z',
        acknowledged: false,
      },
    ];
    const resolvedAlertHistory: AlertHistoryEntry[] = [
      {
        id: 'history-1',
        alertId: 'alert-1',
        action: 'triggered',
        details: 'Initial trigger',
        timestamp: '2026-02-28T12:00:00.000Z',
      },
    ];

    fetchMonitoringSettledResultsMock.mockResolvedValue(settledResults);
    monitoringLoadResultEntriesMock.mockReturnValue([]);
    resolveMonitoringLoadStateMock.mockReturnValue({
      notificationSettingsStatus: 'fulfilled',
      notificationSettings: {
        email: { enabled: true, recipients: ['ops@example.com'], threshold: 'warning' },
        slack: { enabled: false, webhook: '', channel: '', threshold: 'critical' },
        discord: { enabled: false, webhook: '', channel: '', threshold: 'critical' },
        pagerduty: { enabled: false, integrationKey: '', severity: 'critical' },
      },
      recentNotifications: [
        {
          id: 'notification-1',
          channel: 'email',
          recipient: 'ops@example.com',
          severity: 'warning',
          status: 'sent',
          sentAt: '2026-02-28T12:00:00.000Z',
          message: 'CPU warning',
        },
      ],
      metrics: [
        {
          name: 'cpu',
          value: 80,
          unit: '%',
          trend: 'up',
          status: 'warning',
        },
      ],
      watchlists: [
        {
          id: 'watchlist-1',
          name: 'Core',
          services: ['chat'],
          status: 'warning',
          uptime: 99.1,
          latency: 120,
          incidents: 1,
          sla: 99.5,
          description: 'Core services',
        },
      ],
      alerts: resolvedAlerts,
      alertHistory: resolvedAlertHistory,
      assignableUsers: [{ id: 'user-1', label: 'Alice' }],
      systemStatus: [{ key: 'api', label: 'API', status: 'healthy', detail: 'Operational' }],
    });

    const { result } = renderHook(() => useMonitoringDataLoader(args));

    await act(async () => {
      await result.current.loadData();
    });

    expect(args.setLoading).toHaveBeenNthCalledWith(1, true);
    expect(args.setLoading).toHaveBeenLastCalledWith(false);
    expect(args.setError).toHaveBeenCalledWith('');
    expect(args.setNotificationSettingsStatus).toHaveBeenNthCalledWith(1, 'pending');
    expect(args.setNotificationSettingsStatus).toHaveBeenNthCalledWith(2, 'fulfilled');
    expect(args.setMetrics).toHaveBeenCalledWith(
      expect.arrayContaining([expect.objectContaining({ name: 'cpu' })])
    );
    expect(args.setWatchlists).toHaveBeenCalledWith(
      expect.arrayContaining([expect.objectContaining({ id: 'watchlist-1' })])
    );
    expect(args.setAlerts).toHaveBeenCalledWith(resolvedAlerts);
    expect(args.setAlertHistory).toHaveBeenCalledWith(resolvedAlertHistory);
    expect(args.alertsRef.current).toEqual(resolvedAlerts);
    expect(args.alertHistoryRef.current).toEqual(resolvedAlertHistory);
    expect(args.loadMetricsHistoryForRange).toHaveBeenCalledWith(
      args.timeRange,
      args.customRangeStart,
      args.customRangeEnd
    );
    expect(args.markMonitoringDataUpdated).toHaveBeenCalledTimes(1);
  });

  it('handles loader failures and reports error state', async () => {
    const args = createCommonArgs();
    fetchMonitoringSettledResultsMock.mockRejectedValue(new Error('network down'));

    const { result } = renderHook(() => useMonitoringDataLoader(args));

    await act(async () => {
      await result.current.loadData();
    });

    expect(args.setLoading).toHaveBeenNthCalledWith(1, true);
    expect(args.setLoading).toHaveBeenLastCalledWith(false);
    expect(args.setNotificationSettingsStatus).toHaveBeenNthCalledWith(1, 'pending');
    expect(args.setNotificationSettingsStatus).toHaveBeenNthCalledWith(2, 'rejected');
    expect(args.setError).toHaveBeenCalledWith('network down');
    expect(args.setNotificationSettings).toHaveBeenCalledWith(null);
    expect(args.loadMetricsHistoryForRange).not.toHaveBeenCalled();
    expect(args.markMonitoringDataUpdated).not.toHaveBeenCalled();
  });
});
