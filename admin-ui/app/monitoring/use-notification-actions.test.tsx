/* @vitest-environment jsdom */
import * as React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  useNotificationActions,
  type NotificationActionsApiClient,
} from './use-notification-actions';
import type {
  NotificationSettings,
  RecentNotification,
} from './types';

type HarnessProps = {
  apiClient: NotificationActionsApiClient;
  canSave: boolean;
  setError: (message: string) => void;
  setSuccess: (message: string) => void;
};

const baseSettings: NotificationSettings = {
  channels: [
    {
      type: 'email',
      enabled: true,
      config: { address: 'ops@example.com' },
    },
  ],
  alert_threshold: 'critical',
  digest_enabled: false,
  digest_frequency: 'daily',
};

function Harness({
  apiClient,
  canSave,
  setError,
  setSuccess,
}: HarnessProps) {
  const [settings, setNotificationSettings] = React.useState<NotificationSettings | null>(baseSettings);
  const [recentNotifications, setRecentNotifications] = React.useState<RecentNotification[]>([]);
  const [saveResult, setSaveResult] = React.useState<string>('');

  const {
    notificationsSaving,
    handleSaveNotificationSettings,
    handleTestNotification,
  } = useNotificationActions({
    apiClient,
    canSave,
    setNotificationSettings,
    setRecentNotifications,
    setError,
    setSuccess,
  });

  return (
    <div>
      <div data-testid="saving">{String(notificationsSaving)}</div>
      <div data-testid="save-result">{saveResult}</div>
      <div data-testid="settings-json">{JSON.stringify(settings)}</div>
      <div data-testid="recent-json">{JSON.stringify(recentNotifications)}</div>
      <button
        onClick={() => {
          void handleSaveNotificationSettings(baseSettings).then((result) => {
            setSaveResult(String(result));
          });
        }}
      >
        Save
      </button>
      <button
        onClick={() => {
          void handleTestNotification({ message: 'hello', severity: 'warning' });
        }}
      >
        Test
      </button>
    </div>
  );
}

type NotificationActionsApiClientMock = NotificationActionsApiClient & {
  updateNotificationSettings: ReturnType<typeof vi.fn>;
  testNotification: ReturnType<typeof vi.fn>;
  getRecentNotifications: ReturnType<typeof vi.fn>;
};

const buildApiClient = (): NotificationActionsApiClientMock => ({
  updateNotificationSettings: vi.fn().mockResolvedValue({
    enabled: true,
    min_severity: 'critical',
    email_to: 'ops@example.com',
  }),
  testNotification: vi.fn().mockResolvedValue({}),
  getRecentNotifications: vi.fn().mockResolvedValue({
    items: [
      {
        id: 'n1',
        channel: 'email',
        message: 'sent',
        status: 'sent',
        timestamp: '2026-02-28T12:00:00Z',
      },
    ],
  }),
});

describe('useNotificationActions', () => {
  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  it('returns false and skips save when canSave is false', async () => {
    const apiClient = buildApiClient();
    const setError = vi.fn();
    const setSuccess = vi.fn();

    render(
      <Harness
        apiClient={apiClient}
        canSave={false}
        setError={setError}
        setSuccess={setSuccess}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(screen.getByTestId('save-result').textContent).toBe('false');
    });
    expect(apiClient.updateNotificationSettings).not.toHaveBeenCalled();
  });

  it('saves settings, normalizes updated payload, and clears saving state', async () => {
    const apiClient = buildApiClient();
    const setError = vi.fn();
    const setSuccess = vi.fn();

    render(
      <Harness
        apiClient={apiClient}
        canSave
        setError={setError}
        setSuccess={setSuccess}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(apiClient.updateNotificationSettings).toHaveBeenCalledWith({
        enabled: true,
        min_severity: 'critical',
        email_to: 'ops@example.com',
        webhook_url: '',
      });
      expect(screen.getByTestId('save-result').textContent).toBe('true');
    });

    const settings = JSON.parse(screen.getByTestId('settings-json').textContent ?? '{}');
    expect(settings.alert_threshold).toBe('critical');
    expect(screen.getByTestId('saving').textContent).toBe('false');
    expect(setError).toHaveBeenCalledWith('');
    expect(setSuccess).toHaveBeenCalledWith('Notification settings saved');
  });

  it('returns false and reports error when save fails', async () => {
    const apiClient = buildApiClient();
    apiClient.updateNotificationSettings.mockRejectedValue(new Error('save failed'));
    const setError = vi.fn();
    const setSuccess = vi.fn();

    render(
      <Harness
        apiClient={apiClient}
        canSave
        setError={setError}
        setSuccess={setSuccess}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(screen.getByTestId('save-result').textContent).toBe('false');
    });
    expect(setError).toHaveBeenCalledWith('save failed');
    expect(setSuccess).not.toHaveBeenCalledWith('Notification settings saved');
  });

  it('tests notifications and refreshes recent notification list', async () => {
    const apiClient = buildApiClient();
    const setError = vi.fn();
    const setSuccess = vi.fn();

    render(
      <Harness
        apiClient={apiClient}
        canSave
        setError={setError}
        setSuccess={setSuccess}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Test' }));

    await waitFor(() => {
      expect(apiClient.testNotification).toHaveBeenCalledWith({
        message: 'hello',
        severity: 'warning',
      });
      expect(apiClient.getRecentNotifications).toHaveBeenCalledTimes(1);
    });

    const recent = JSON.parse(screen.getByTestId('recent-json').textContent ?? '[]');
    expect(recent).toHaveLength(1);
    expect(setSuccess).toHaveBeenCalledWith('Test notification sent');
    expect(setError).toHaveBeenCalledWith('');
  });

  it('ignores recent-notification refresh failures after successful test send', async () => {
    const apiClient = buildApiClient();
    apiClient.getRecentNotifications.mockRejectedValue(new Error('reload failed'));
    const setError = vi.fn();
    const setSuccess = vi.fn();

    render(
      <Harness
        apiClient={apiClient}
        canSave
        setError={setError}
        setSuccess={setSuccess}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Test' }));

    await waitFor(() => {
      expect(apiClient.testNotification).toHaveBeenCalledTimes(1);
      expect(setSuccess).toHaveBeenCalledWith('Test notification sent');
    });
    expect(setError).not.toHaveBeenCalledWith('reload failed');
  });
});
