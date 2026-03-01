import { useCallback } from 'react';
import { buildAlertHistoryEntry, resolveSnoozedUntil } from '@/lib/monitoring-alerts';
import {
  escalateAlertSeverity,
  markAlertAcknowledged,
  removeAlertById,
  setAlertAssignment,
  setAlertSnoozeUntil,
} from './alert-state-utils';
import type {
  AlertAssignableUser,
  AlertHistoryEntry,
  SnoozeDurationOption,
  SystemAlert,
} from './types';

type ConfirmVariant = 'danger' | 'warning' | 'default';
type ConfirmIcon = 'delete' | 'warning' | 'rotate' | 'remove-user' | 'key';

type ConfirmOptions = {
  title: string;
  message: string;
  confirmText?: string;
  variant?: ConfirmVariant;
  icon?: ConfirmIcon;
};

type ConfirmFn = (options: ConfirmOptions) => Promise<boolean>;

type StateSetter<T> = (next: T | ((prev: T) => T)) => void;

export type AlertActionsApiClient = {
  acknowledgeAlert: (alertId: string) => Promise<unknown>;
  dismissAlert: (alertId: string) => Promise<unknown>;
};

type UseAlertActionsArgs = {
  apiClient: AlertActionsApiClient;
  confirm: ConfirmFn;
  setAlerts: StateSetter<SystemAlert[]>;
  setAlertHistory: StateSetter<AlertHistoryEntry[]>;
  setError: (message: string) => void;
  setSuccess: (message: string) => void;
  onReloadRequested: () => void | Promise<void>;
  assignableUsers: AlertAssignableUser[];
};

export const useAlertActions = ({
  apiClient,
  confirm,
  setAlerts,
  setAlertHistory,
  setError,
  setSuccess,
  onReloadRequested,
  assignableUsers,
}: UseAlertActionsArgs) => {
  const appendAlertHistory = useCallback((
    alertId: string,
    action: AlertHistoryEntry['action'],
    details: string,
    actor?: string
  ) => {
    setAlertHistory((prev) => [
      buildAlertHistoryEntry(alertId, action, details, { actor }),
      ...prev,
    ]);
  }, [setAlertHistory]);

  const handleAcknowledgeAlert = useCallback(async (alert: SystemAlert) => {
    try {
      setError('');
      await apiClient.acknowledgeAlert(alert.id);
      setAlerts((prev) => markAlertAcknowledged(prev, alert.id, new Date().toISOString()));
      appendAlertHistory(alert.id, 'acknowledged', 'Alert acknowledged');
      setSuccess('Alert acknowledged');
      void onReloadRequested();
    } catch (err: unknown) {
      console.error('Failed to acknowledge alert:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to acknowledge alert');
    }
  }, [apiClient, appendAlertHistory, onReloadRequested, setAlerts, setError, setSuccess]);

  const handleDismissAlert = useCallback(async (alert: SystemAlert) => {
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
      await apiClient.dismissAlert(alert.id);
      appendAlertHistory(alert.id, 'dismissed', 'Alert dismissed');
      setAlerts((prev) => removeAlertById(prev, alert.id));
      setSuccess('Alert dismissed');
      void onReloadRequested();
    } catch (err: unknown) {
      console.error('Failed to dismiss alert:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to dismiss alert');
    }
  }, [apiClient, appendAlertHistory, confirm, onReloadRequested, setAlerts, setError, setSuccess]);

  const handleAssignAlert = useCallback((alert: SystemAlert, userId: string) => {
    setAlerts((prev) => setAlertAssignment(prev, alert.id, userId || undefined));
    const assignedLabel = userId
      ? (assignableUsers.find((user) => user.id === userId)?.label ?? userId)
      : 'Unassigned';
    appendAlertHistory(alert.id, 'assigned', `Assigned to ${assignedLabel}`);
    setSuccess(userId ? 'Alert assigned' : 'Alert unassigned');
  }, [appendAlertHistory, assignableUsers, setAlerts, setSuccess]);

  const handleSnoozeAlert = useCallback((alert: SystemAlert, duration: SnoozeDurationOption) => {
    const snoozedUntil = resolveSnoozedUntil(duration);
    setAlerts((prev) => setAlertSnoozeUntil(prev, alert.id, snoozedUntil));
    appendAlertHistory(alert.id, 'snoozed', `Snoozed for ${duration}`);
    setSuccess(`Alert snoozed for ${duration}`);
  }, [appendAlertHistory, setAlerts, setSuccess]);

  const handleEscalateAlert = useCallback((alert: SystemAlert) => {
    if (alert.severity === 'critical') {
      return;
    }
    setAlerts((prev) => escalateAlertSeverity(prev, alert.id));
    appendAlertHistory(alert.id, 'escalated', 'Severity escalated to critical');
    setSuccess('Alert escalated to critical');
  }, [appendAlertHistory, setAlerts, setSuccess]);

  return {
    handleAcknowledgeAlert,
    handleDismissAlert,
    handleAssignAlert,
    handleSnoozeAlert,
    handleEscalateAlert,
  };
};
