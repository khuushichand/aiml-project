/* @vitest-environment jsdom */
import * as React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type {
  AlertHistoryEntry,
  SystemAlert,
} from './types';
import { useMonitoringAlertState } from './use-monitoring-alert-state';

const seedHistoryEntry: AlertHistoryEntry = {
  id: 'history-1',
  alertId: 'alert-1',
  action: 'triggered',
  details: 'Seeded history',
  timestamp: '2026-02-28T12:00:00.000Z',
};

const seedAlert: SystemAlert = {
  id: 'alert-1',
  severity: 'warning',
  message: 'High CPU',
  source: 'system',
  timestamp: '2026-02-28T12:00:00.000Z',
  acknowledged: false,
};

function Harness() {
  const {
    alerts,
    setAlerts,
    alertsRef,
    alertHistory,
    setAlertHistory,
    alertHistoryRef,
    showSnoozedAlerts,
    setShowSnoozedAlerts,
    assignableUsers,
    setAssignableUsers,
  } = useMonitoringAlertState();
  const [alertsRefCountSnapshot, setAlertsRefCountSnapshot] = React.useState<number>(0);
  const [historyRefCountSnapshot, setHistoryRefCountSnapshot] = React.useState<number>(0);

  return (
    <div>
      <div data-testid="alerts-count">{alerts.length}</div>
      <div data-testid="alerts-ref-count">{alertsRefCountSnapshot}</div>
      <div data-testid="history-count">{alertHistory.length}</div>
      <div data-testid="history-ref-count">{historyRefCountSnapshot}</div>
      <div data-testid="show-snoozed">{String(showSnoozedAlerts)}</div>
      <div data-testid="assignable-count">{assignableUsers.length}</div>
      <button onClick={() => setAlerts([seedAlert])}>Set Alerts</button>
      <button onClick={() => setAlertHistory([seedHistoryEntry])}>Set History</button>
      <button onClick={() => setShowSnoozedAlerts((prev) => !prev)}>Toggle Snoozed</button>
      <button onClick={() => setAssignableUsers([{ id: 'u1', label: 'Alice' }])}>Set Assignable</button>
      <button
        onClick={() => {
          setAlertsRefCountSnapshot(alertsRef.current.length);
          setHistoryRefCountSnapshot(alertHistoryRef.current.length);
        }}
      >
        Snapshot Refs
      </button>
    </div>
  );
}

describe('useMonitoringAlertState', () => {
  afterEach(() => {
    cleanup();
  });

  it('starts with empty alert history until backend data is loaded', async () => {
    render(<Harness />);

    await waitFor(() => {
      expect(screen.getByTestId('history-count').textContent).toBe('0');
    });
    fireEvent.click(screen.getByRole('button', { name: 'Snapshot Refs' }));
    expect(screen.getByTestId('history-ref-count').textContent).toBe('0');
  });

  it('keeps alert/history refs synced and manages additional alert state', async () => {
    render(<Harness />);

    fireEvent.click(screen.getByRole('button', { name: 'Set Alerts' }));
    fireEvent.click(screen.getByRole('button', { name: 'Set History' }));
    fireEvent.click(screen.getByRole('button', { name: 'Toggle Snoozed' }));
    fireEvent.click(screen.getByRole('button', { name: 'Set Assignable' }));
    fireEvent.click(screen.getByRole('button', { name: 'Snapshot Refs' }));

    await waitFor(() => {
      expect(screen.getByTestId('alerts-count').textContent).toBe('1');
      expect(screen.getByTestId('alerts-ref-count').textContent).toBe('1');
      expect(screen.getByTestId('history-count').textContent).toBe('1');
      expect(screen.getByTestId('history-ref-count').textContent).toBe('1');
      expect(screen.getByTestId('show-snoozed').textContent).toBe('true');
      expect(screen.getByTestId('assignable-count').textContent).toBe('1');
    });
  });
});
