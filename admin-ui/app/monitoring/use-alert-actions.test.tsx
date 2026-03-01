/* @vitest-environment jsdom */
import * as React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  useAlertActions,
  type AlertActionsApiClient,
} from './use-alert-actions';
import type {
  AlertAssignableUser,
  AlertHistoryEntry,
  SystemAlert,
} from './types';

type HarnessProps = {
  apiClient: AlertActionsApiClient;
  confirm: (options: { title: string; message: string; confirmText?: string; variant?: string; icon?: string }) => Promise<boolean>;
  setError: (message: string) => void;
  setSuccess: (message: string) => void;
  onReloadRequested: () => void | Promise<void>;
  assignableUsers: AlertAssignableUser[];
};

const baseAlerts: SystemAlert[] = [
  {
    id: 'a1',
    severity: 'warning',
    message: 'High CPU',
    source: 'system',
    timestamp: '2026-02-28T10:00:00Z',
    acknowledged: false,
  },
  {
    id: 'a2',
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
  assignableUsers,
}: HarnessProps) {
  const [alerts, setAlerts] = React.useState<SystemAlert[]>(baseAlerts);
  const [history, setAlertHistory] = React.useState<AlertHistoryEntry[]>([]);

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
    setAlertHistory,
    setError,
    setSuccess,
    onReloadRequested,
    assignableUsers,
  });

  const alertA1 = alerts.find((item) => item.id === 'a1');
  const alertA2 = alerts.find((item) => item.id === 'a2');

  return (
    <div>
      <div data-testid="alerts-json">{JSON.stringify(alerts)}</div>
      <div data-testid="history-json">{JSON.stringify(history)}</div>
      <button onClick={() => { if (alertA1) void handleAcknowledgeAlert(alertA1); }}>Ack A1</button>
      <button onClick={() => { if (alertA1) void handleDismissAlert(alertA1); }}>Dismiss A1</button>
      <button onClick={() => { if (alertA1) handleAssignAlert(alertA1, 'u1'); }}>Assign A1</button>
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
};

const buildApiClient = (): AlertActionsApiClientMock => ({
  acknowledgeAlert: vi.fn().mockResolvedValue({}),
  dismissAlert: vi.fn().mockResolvedValue({}),
});

const readAlerts = (): SystemAlert[] => JSON.parse(screen.getByTestId('alerts-json').textContent ?? '[]');
const readHistory = (): AlertHistoryEntry[] => JSON.parse(screen.getByTestId('history-json').textContent ?? '[]');

describe('useAlertActions', () => {
  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  it('acknowledges an alert, records history, and reloads', async () => {
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
        assignableUsers={[]}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Ack A1' }));

    await waitFor(() => {
      expect(apiClient.acknowledgeAlert).toHaveBeenCalledWith('a1');
      expect(onReloadRequested).toHaveBeenCalledTimes(1);
    });

    const updatedA1 = readAlerts().find((item) => item.id === 'a1');
    expect(updatedA1?.acknowledged).toBe(true);
    expect(updatedA1?.acknowledged_at).toBeTruthy();
    expect(readHistory()[0]?.action).toBe('acknowledged');
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
        assignableUsers={[]}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss A1' }));

    await waitFor(() => {
      expect(confirm).toHaveBeenCalledTimes(1);
    });
    expect(apiClient.dismissAlert).not.toHaveBeenCalled();
    expect(onReloadRequested).not.toHaveBeenCalled();
    expect(readAlerts().some((item) => item.id === 'a1')).toBe(true);
  });

  it('dismisses confirmed alerts and records history', async () => {
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
        assignableUsers={[]}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss A1' }));

    await waitFor(() => {
      expect(apiClient.dismissAlert).toHaveBeenCalledWith('a1');
      expect(readAlerts().some((item) => item.id === 'a1')).toBe(false);
    });
    expect(readHistory()[0]?.action).toBe('dismissed');
    expect(setSuccess).toHaveBeenCalledWith('Alert dismissed');
    expect(onReloadRequested).toHaveBeenCalledTimes(1);
  });

  it('assigns and unassigns alerts with user labels in history', async () => {
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
        assignableUsers={[{ id: 'u1', label: 'Alice' }]}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Assign A1' }));
    await waitFor(() => {
      expect(readAlerts().find((item) => item.id === 'a1')?.assigned_to).toBe('u1');
    });
    expect(readHistory()[0]?.details).toBe('Assigned to Alice');
    expect(setSuccess).toHaveBeenCalledWith('Alert assigned');

    fireEvent.click(screen.getByRole('button', { name: 'Unassign A1' }));
    await waitFor(() => {
      expect(readAlerts().find((item) => item.id === 'a1')?.assigned_to).toBeUndefined();
    });
    expect(readHistory()[0]?.details).toBe('Assigned to Unassigned');
    expect(setSuccess).toHaveBeenCalledWith('Alert unassigned');
  });

  it('handles snooze and escalations, with no-op for already critical alerts', async () => {
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
        assignableUsers={[]}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Snooze A1' }));
    await waitFor(() => {
      expect(readAlerts().find((item) => item.id === 'a1')?.snoozed_until).toBeTruthy();
    });
    expect(readHistory()[0]?.action).toBe('snoozed');
    expect(setSuccess).toHaveBeenCalledWith('Alert snoozed for 15m');

    fireEvent.click(screen.getByRole('button', { name: 'Escalate A1' }));
    await waitFor(() => {
      expect(readAlerts().find((item) => item.id === 'a1')?.severity).toBe('critical');
    });
    expect(readHistory()[0]?.action).toBe('escalated');
    expect(setSuccess).toHaveBeenCalledWith('Alert escalated to critical');

    const historyLengthBeforeNoop = readHistory().length;
    const successCallCountBeforeNoop = setSuccess.mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: 'Escalate A2' }));

    expect(readHistory().length).toBe(historyLengthBeforeNoop);
    expect(setSuccess.mock.calls.length).toBe(successCallCountBeforeNoop);
  });
});
