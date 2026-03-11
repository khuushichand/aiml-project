/* @vitest-environment jsdom */
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useMonitoringManagementPanelsProps } from './use-monitoring-management-panels-props';

const createArgs = () => ({
  alertRules: [
    {
      id: 'rule-1',
      metric: 'cpu' as const,
      operator: '>' as const,
      threshold: 90,
      durationMinutes: 5 as const,
      severity: 'critical' as const,
      createdAt: '2026-03-01T12:00:00.000Z',
    },
  ],
  alertRuleDraft: {
    metric: 'cpu' as const,
    operator: '>' as const,
    threshold: '90',
    durationMinutes: '5',
    severity: 'critical' as const,
  },
  alertRuleValidationErrors: {},
  alertRulesSaving: false,
  unsafeLocalToolsEnabled: false,
  handleAlertRuleDraftChange: vi.fn(),
  handleCreateAlertRule: vi.fn(),
  handleDeleteAlertRule: vi.fn(),
  alerts: [
    {
      id: 'alert-1',
      severity: 'warning' as const,
      message: 'CPU high',
      timestamp: '2026-03-01T12:00:00.000Z',
      acknowledged: false,
    },
  ],
  alertHistory: [
    {
      id: 'history-1',
      alertId: 'alert-1',
      timestamp: '2026-03-01T12:00:00.000Z',
      action: 'triggered' as const,
    },
  ],
  showSnoozedAlerts: false,
  setShowSnoozedAlerts: vi.fn(),
  assignableUsers: [{ id: 'user-1', label: 'Alice' }],
  loading: false,
  handleAcknowledgeAlert: vi.fn(),
  handleDismissAlert: vi.fn(),
  handleAssignAlert: vi.fn(),
  handleSnoozeAlert: vi.fn(),
  handleEscalateAlert: vi.fn(),
  watchlists: [
    {
      id: 'watchlist-1',
      name: 'Core',
      target: '/api/v1/chat',
      type: 'endpoint',
      status: 'healthy',
    },
  ],
  showCreateWatchlist: false,
  setShowCreateWatchlist: vi.fn(),
  newWatchlist: {
    name: '',
    description: '',
    target: '',
    type: 'resource',
    threshold: 80,
  },
  setNewWatchlist: vi.fn(),
  handleCreateWatchlist: vi.fn(),
  handleDeleteWatchlist: vi.fn(),
  deletingWatchlistId: null,
  notificationSettings: null,
  recentNotifications: [
    {
      id: 'notification-1',
      channel: 'email',
      message: 'CPU warning',
      status: 'sent' as const,
      timestamp: '2026-03-01T12:00:00.000Z',
      severity: 'warning',
    },
  ],
  notificationsSaving: false,
  canSaveNotificationSettings: true,
  handleSaveNotificationSettings: vi.fn(),
  handleTestNotification: vi.fn(),
  systemStatus: [{ key: 'api', label: 'API', status: 'healthy' as const, detail: 'Operational' }],
});

describe('useMonitoringManagementPanelsProps', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('builds management panel props and forwards snoozed toggle updates', () => {
    const args = createArgs();
    const { result } = renderHook(() => useMonitoringManagementPanelsProps(args));

    expect(result.current.alertRulesPanelProps.rules).toHaveLength(1);
    expect(result.current.alertRulesPanelProps.mutationsEnabled).toBe(false);
    expect(result.current.alertsPanelProps.alerts).toHaveLength(1);
    expect(result.current.alertsPanelProps.localActionsEnabled).toBe(false);
    expect(result.current.watchlistsPanelProps.watchlists).toHaveLength(1);
    expect(result.current.notificationsPanelProps.recentNotifications).toHaveLength(1);
    expect(result.current.systemStatusPanelProps.systemStatus).toHaveLength(1);

    act(() => {
      result.current.alertsPanelProps.onToggleShowSnoozed();
    });
    expect(args.setShowSnoozedAlerts).toHaveBeenCalledTimes(1);
    const updater = args.setShowSnoozedAlerts.mock.calls[0][0] as (prev: boolean) => boolean;
    expect(updater(false)).toBe(true);
    expect(updater(true)).toBe(false);
  });

  it('returns stable object references on rerender when args are unchanged', () => {
    const args = createArgs();
    const { result, rerender } = renderHook(() => useMonitoringManagementPanelsProps(args));

    const initial = result.current;
    const initialToggle = result.current.alertsPanelProps.onToggleShowSnoozed;

    rerender();

    expect(result.current).toBe(initial);
    expect(result.current.alertsPanelProps.onToggleShowSnoozed).toBe(initialToggle);
  });
});
