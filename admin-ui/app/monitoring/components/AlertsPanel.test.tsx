/* @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AlertsPanel from './AlertsPanel';
import type { SystemAlert } from '../types';

const baseAlert: SystemAlert = {
  id: 'alert-1',
  severity: 'warning',
  message: 'CPU above threshold',
  source: 'system',
  timestamp: '2026-02-17T12:00:00.000Z',
  acknowledged: false,
};

afterEach(() => {
  cleanup();
});

describe('AlertsPanel', () => {
  it('renders assignment dropdown and emits selection changes', async () => {
    const user = userEvent.setup();
    const onAssign = vi.fn();

    render(
      <AlertsPanel
        alerts={[baseAlert]}
        history={[]}
        showSnoozed={false}
        assignableUsers={[
          { id: '1', label: 'alice@example.com' },
          { id: '2', label: 'bob@example.com' },
        ]}
        loading={false}
        onToggleShowSnoozed={vi.fn()}
        onAcknowledge={vi.fn()}
        onDismiss={vi.fn()}
        onAssign={onAssign}
        onSnooze={vi.fn()}
        onEscalate={vi.fn()}
        localActionsEnabled
      />
    );

    const assigneeSelect = screen.getByTestId('alert-assignee-select-alert-1');
    await user.selectOptions(assigneeSelect, '2');

    expect(onAssign).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'alert-1' }),
      '2'
    );
  });

  it('renders alert history timeline entries', async () => {
    const user = userEvent.setup();

    render(
      <AlertsPanel
        alerts={[]}
        history={[
          {
            id: 'history-1',
            alertId: 'alert-1',
            timestamp: '2026-02-17T12:05:00.000Z',
            action: 'assigned',
            details: 'Assigned to alice@example.com',
          },
          {
            id: 'history-2',
            alertId: 'alert-1',
            timestamp: '2026-02-17T12:10:00.000Z',
            action: 'snoozed',
            details: 'Snoozed for 1h',
          },
        ]}
        showSnoozed={false}
        assignableUsers={[]}
        loading={false}
        onToggleShowSnoozed={vi.fn()}
        onAcknowledge={vi.fn()}
        onDismiss={vi.fn()}
        onAssign={vi.fn()}
        onSnooze={vi.fn()}
        onEscalate={vi.fn()}
        localActionsEnabled
      />
    );

    await user.click(screen.getByText('Alert History (2)'));

    expect(screen.getAllByTestId('alert-history-timeline').length).toBeGreaterThan(0);
    expect(screen.getByText('Assigned')).toBeTruthy();
    expect(screen.getByText('Assigned to alice@example.com')).toBeTruthy();
    expect(screen.getByText('Snoozed')).toBeTruthy();
    expect(screen.getByText('Snoozed for 1h')).toBeTruthy();
  });

  it('disables local-only alert action controls in safe mode', () => {
    render(
      <AlertsPanel
        alerts={[baseAlert]}
        history={[]}
        showSnoozed={false}
        assignableUsers={[
          { id: '1', label: 'alice@example.com' },
        ]}
        loading={false}
        onToggleShowSnoozed={vi.fn()}
        onAcknowledge={vi.fn()}
        onDismiss={vi.fn()}
        onAssign={vi.fn()}
        onSnooze={vi.fn()}
        onEscalate={vi.fn()}
        localActionsEnabled={false}
      />
    );

    expect(screen.getByTestId('alert-assignee-select-alert-1')).toBeDisabled();
    expect(screen.getByTestId('alert-snooze-duration-alert-1')).toBeDisabled();
    expect(screen.getByTestId('alert-snooze-button-alert-1')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Escalate' })).toBeDisabled();
  });

  it('renders the common-patterns CTA in a disabled state until presets are wired', () => {
    render(
      <AlertsPanel
        alerts={[baseAlert]}
        history={[]}
        showSnoozed={false}
        assignableUsers={[]}
        loading={false}
        onToggleShowSnoozed={vi.fn()}
        onAcknowledge={vi.fn()}
        onDismiss={vi.fn()}
        onAssign={vi.fn()}
        onSnooze={vi.fn()}
        onEscalate={vi.fn()}
        localActionsEnabled
      />
    );

    expect(screen.getByRole('button', { name: 'Create Alert Rule for common patterns' })).toBeDisabled();
  });
});
