/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { NotificationSettings, RecentNotification } from './types';
import { useMonitoringNotificationState } from './use-monitoring-notification-state';

const sampleNotificationSettings: NotificationSettings = {
  email: {
    enabled: true,
    recipients: ['ops@example.com'],
    threshold: 'warning',
  },
  slack: {
    enabled: false,
    webhook: '',
    channel: '',
    threshold: 'critical',
  },
  discord: {
    enabled: false,
    webhook: '',
    channel: '',
    threshold: 'critical',
  },
  pagerduty: {
    enabled: false,
    integrationKey: '',
    severity: 'critical',
  },
};

const sampleRecentNotifications: RecentNotification[] = [
  {
    id: 'notification-1',
    channel: 'email',
    recipient: 'ops@example.com',
    severity: 'warning',
    status: 'sent',
    sentAt: '2026-02-28T12:00:00.000Z',
    message: 'CPU is elevated',
  },
];

function Harness() {
  const {
    notificationSettings,
    setNotificationSettings,
    recentNotifications,
    setRecentNotifications,
    notificationSettingsStatus,
    setNotificationSettingsStatus,
    canSaveNotificationSettings,
  } = useMonitoringNotificationState();

  return (
    <div>
      <div data-testid="status">{notificationSettingsStatus}</div>
      <div data-testid="can-save">{String(canSaveNotificationSettings)}</div>
      <div data-testid="has-settings">{String(notificationSettings !== null)}</div>
      <div data-testid="recent-count">{recentNotifications.length}</div>

      <button
        onClick={() => {
          setNotificationSettings(sampleNotificationSettings);
          setRecentNotifications(sampleRecentNotifications);
        }}
      >
        Set Data
      </button>
      <button onClick={() => setNotificationSettingsStatus('fulfilled')}>Set Fulfilled</button>
      <button onClick={() => setNotificationSettingsStatus('rejected')}>Set Rejected</button>
    </div>
  );
}

describe('useMonitoringNotificationState', () => {
  afterEach(() => {
    cleanup();
  });

  it('initializes with pending status and empty notification data', () => {
    render(<Harness />);

    expect(screen.getByTestId('status').textContent).toBe('pending');
    expect(screen.getByTestId('can-save').textContent).toBe('false');
    expect(screen.getByTestId('has-settings').textContent).toBe('false');
    expect(screen.getByTestId('recent-count').textContent).toBe('0');
  });

  it('updates notification data and status-driven can-save flag', () => {
    render(<Harness />);

    fireEvent.click(screen.getByRole('button', { name: 'Set Data' }));
    expect(screen.getByTestId('has-settings').textContent).toBe('true');
    expect(screen.getByTestId('recent-count').textContent).toBe('1');

    fireEvent.click(screen.getByRole('button', { name: 'Set Fulfilled' }));
    expect(screen.getByTestId('status').textContent).toBe('fulfilled');
    expect(screen.getByTestId('can-save').textContent).toBe('true');

    fireEvent.click(screen.getByRole('button', { name: 'Set Rejected' }));
    expect(screen.getByTestId('status').textContent).toBe('rejected');
    expect(screen.getByTestId('can-save').textContent).toBe('false');
  });
});
