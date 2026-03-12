/* @vitest-environment jsdom */
import * as React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  useAlertActions,
  type AlertActionsApiClient,
} from './use-alert-actions';
import type {
  AlertHistoryEntry,
  SystemAlert,
} from './types';

type HarnessProps = {
  apiClient: AlertActionsApiClient;
  confirm: (options: { title: string; message: string; confirmText?: string; variant?: string; icon?: string }) => Promise<boolean>;
  setError: (message: string) => void;
  setSuccess: (message: string) => void;
  onReloadRequested: () => void | Promise<void>;
};

const baseAlerts: SystemAlert[] = [
  {
    id: '1',
    alert_identity: 'alert:1',
    severity: 'warning',
    message: 'High CPU',
    source: 'system',
    timestamp: '2026-02-28T10:00:00Z',
    acknowledged: false,
  },
  {
    id: '2',
    alert_identity: 'alert:2',
    severity: 'critical',
    message: 'DB failure',
    source: 'database',
    timestamp: '2026-02-28T10:01:00Z',
    acknowledged: false,
  },
];

function Harness({
  apiClient,
  confirm,
  setError,
  setSuccess,
  onReloadRequested,
}: HarnessProps) {
  const [alerts, setAlerts] = React.useState<SystemAlert[]>(baseAlerts);
  const [history] = React.useState<AlertHistoryEntry[]>([]);

  const {
    handleAcknowledgeAlert,
    handleDismissAlert,
    handleAssignAlert,
    handleSnoozeAlert,
    handleEscalateAlert,
  } = useAlertActions({
    apiClient,
    confirm,
    setAlerts,
    setError,
    setSuccess,
    onReloadRequested,
  });

  const alertA1 = alerts.find((item) => item.id === '1');
  const alertA2 = alerts.find((item) => item.id === '2');

  return (
    <div>
      <div data-testid="alerts-json">{JSON.stringify(alerts)}</div>
      <div data-testid="history-json">{JSON.stringify(history)}</div>
      <button onClick={() => { if (alertA1) void handleAcknowledgeAlert(alertA1); }}>Ack A1</button>
      <button onClick={() => { if (alertA1) void handleDismissAlert(alertA1); }}>Dismiss A1</button>
      <button onClick={() => { if (alertA1) handleAssignAlert(alertA1, '1'); }}>Assign A1</button>
      <button onClick={() => { if (alertA1) handleAssignAlert(alertA1, ''); }}>Unassign A1</button>
      <button onClick={() => { if (alertA1) handleSnoozeAlert(alertA1, '15m'); }}>Snooze A1</button>
      <button onClick={() => { if (alertA1) handleEscalateAlert(alertA1); }}>Escalate A1</button>
      <button onClick={() => { if (alertA2) handleEscalateAlert(alertA2); }}>Escalate A2</button>
    </div>
  );
}

type AlertActionsApiClientMock = AlertActionsApiClient & {
  acknowledgeAlert: ReturnType<typeof vi.fn>;
  dismissAlert: ReturnType<typeof vi.fn>;
  assignAdminAlert: ReturnType<typeof vi.fn>;
  snoozeAdminAlert: ReturnType<typeof vi.fn>;
  escalateAdminAlert: ReturnType<typeof vi.fn>;
};

const buildApiClient = (): AlertActionsApiClientMock => ({
  acknowledgeAlert: vi.fn().mockResolvedValue({}),
  dismissAlert: vi.fn().mockResolvedValue({}),
  assignAdminAlert: vi.fn().mockResolvedValue({ item: { alert_identity: 'alert:1', assigned_to_user_id: 1 } }),
  snoozeAdminAlert: vi.fn().mockResolvedValue({ item: { alert_identity: 'alert:1', snoozed_until: '2026-02-28T10:15:00Z' } }),
  escalateAdminAlert: vi.fn().mockResolvedValue({ item: { alert_identity: 'alert:1', escalated_severity: 'critical' } }),
});

const readAlerts = (): SystemAlert[] => JSON.parse(screen.getByTestId('alerts-json').textContent ?? '[]');
const readHistory = (): AlertHistoryEntry[] => JSON.parse(screen.getByTestId('history-json').textContent ?? '[]');

describe('useAlertActions', () => {
  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  it('acknowledges an alert and reloads without local history synthesis', async () => {
    const apiClient = buildApiClient();
    const confirm = vi.fn().mockResolvedValue(true);
    const setError = vi.fn();
    const setSuccess = vi.fn();
    const onReloadRequested = vi.fn();

    render(
      <Harness
        apiClient={apiClient}
        confirm={confirm}
        setError={setError}
        setSuccess={setSuccess}
        onReloadRequested={onReloadRequested}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Ack A1' }));

    await waitFor(() => {
      expect(apiClient.acknowledgeAlert).toHaveBeenCalledWith('1');
      expect(onReloadRequested).toHaveBeenCalledTimes(1);
    });

    const updatedA1 = readAlerts().find((item) => item.id === '1');
    expect(updatedA1?.acknowledged).toBe(true);
    expect(updatedA1?.acknowledged_at).toBeTruthy();
    expect(readHistory()).toEqual([]);
    expect(setError).toHaveBeenCalledWith('');
    expect(setSuccess).toHaveBeenCalledWith('Alert acknowledged');
  });

  it('aborts dismiss when confirmation is rejected', async () => {
    const apiClient = buildApiClient();
    const confirm = vi.fn().mockResolvedValue(false);
    const setError = vi.fn();
    const setSuccess = vi.fn();
    const onReloadRequested = vi.fn();

    render(
      <Harness
        apiClient={apiClient}
        confirm={confirm}
        setError={setError}
        setSuccess={setSuccess}
        onReloadRequested={onReloadRequested}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss A1' }));

    await waitFor(() => {
      expect(confirm).toHaveBeenCalledTimes(1);
    });
    expect(apiClient.dismissAlert).not.toHaveBeenCalled();
    expect(onReloadRequested).not.toHaveBeenCalled();
    expect(readAlerts().some((item) => item.id === '1')).toBe(true);
  });

  it('dismisses confirmed alerts and reloads without local history synthesis', async () => {
    const apiClient = buildApiClient();
    const confirm = vi.fn().mockResolvedValue(true);
    const setError = vi.fn();
    const setSuccess = vi.fn();
    const onReloadRequested = vi.fn();

    render(
      <Harness
        apiClient={apiClient}
        confirm={confirm}
        setError={setError}
        setSuccess={setSuccess}
        onReloadRequested={onReloadRequested}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss A1' }));

    await waitFor(() => {
      expect(apiClient.dismissAlert).toHaveBeenCalledWith('1');
      expect(readAlerts().some((item) => item.id === '1')).toBe(false);
    });
    expect(readHistory()).toEqual([]);
    expect(setSuccess).toHaveBeenCalledWith('Alert dismissed');
    expect(onReloadRequested).toHaveBeenCalledTimes(1);
  });

  it('assigns and unassigns alerts through the backend', async () => {
    const apiClient = buildApiClient();
    const confirm = vi.fn().mockResolvedValue(true);
    const setError = vi.fn();
    const setSuccess = vi.fn();
    const onReloadRequested = vi.fn();

    render(
      <Harness
        apiClient={apiClient}
        confirm={confirm}
        setError={setError}
        setSuccess={setSuccess}
        onReloadRequested={onReloadRequested}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Assign A1' }));
    await waitFor(() => {
      expect(apiClient.assignAdminAlert).toHaveBeenCalledWith('alert:1', {
        assigned_to_user_id: 1,
      });
      expect(readAlerts().find((item) => item.id === '1')?.assigned_to).toBe('1');
      expect(onReloadRequested).toHaveBeenCalledTimes(1);
    });
    expect(readHistory()).toEqual([]);
    expect(setSuccess).toHaveBeenCalledWith('Alert assigned');

    fireEvent.click(screen.getByRole('button', { name: 'Unassign A1' }));
    await waitFor(() => {
      expect(readAlerts().find((item) => item.id === '1')?.assigned_to).toBeUndefined();
      expect(onReloadRequested).toHaveBeenCalledTimes(2);
    });
    expect(apiClient.assignAdminAlert).toHaveBeenCalledWith('alert:1', {
      assigned_to_user_id: null,
    });
    expect(readHistory()).toEqual([]);
    expect(setSuccess).toHaveBeenCalledWith('Alert unassigned');
  });

  it('handles snooze and escalations through the backend, with no-op for already critical alerts', async () => {
    const apiClient = buildApiClient();
    const confirm = vi.fn().mockResolvedValue(true);
    const setError = vi.fn();
    const setSuccess = vi.fn();
    const onReloadRequested = vi.fn();

    render(
      <Harness
        apiClient={apiClient}
        confirm={confirm}
        setError={setError}
        setSuccess={setSuccess}
        onReloadRequested={onReloadRequested}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Snooze A1' }));
    await waitFor(() => {
      expect(apiClient.snoozeAdminAlert).toHaveBeenCalledWith('alert:1', expect.objectContaining({
        snoozed_until: expect.any(String),
      }));
      expect(readAlerts().find((item) => item.id === '1')?.snoozed_until).toBeTruthy();
      expect(onReloadRequested).toHaveBeenCalledTimes(1);
    });
    expect(readHistory()).toEqual([]);
    expect(setSuccess).toHaveBeenCalledWith('Alert snoozed for 15m');

    fireEvent.click(screen.getByRole('button', { name: 'Escalate A1' }));
    await waitFor(() => {
      expect(apiClient.escalateAdminAlert).toHaveBeenCalledWith('alert:1', { severity: 'critical' });
      expect(readAlerts().find((item) => item.id === '1')?.severity).toBe('critical');
      expect(onReloadRequested).toHaveBeenCalledTimes(2);
    });
    expect(readHistory()).toEqual([]);
    expect(setSuccess).toHaveBeenCalledWith('Alert escalated to critical');

    const historyLengthBeforeNoop = readHistory().length;
    const successCallCountBeforeNoop = setSuccess.mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: 'Escalate A2' }));

    expect(readHistory().length).toBe(historyLengthBeforeNoop);
    expect(setSuccess.mock.calls.length).toBe(successCallCountBeforeNoop);
    expect(apiClient.escalateAdminAlert).toHaveBeenCalledTimes(1);
  });

});
