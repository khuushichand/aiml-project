import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const mocks = vi.hoisted(() => ({
  listNotifications: vi.fn(),
  getUnreadCount: vi.fn(),
  markNotificationsRead: vi.fn(),
  dismissNotification: vi.fn(),
  snoozeNotification: vi.fn(),
  subscribeNotificationsStream: vi.fn(),
  showToast: vi.fn(),
}));

vi.mock('@web/lib/api/notifications', () => ({
  listNotifications: (...args: unknown[]) => mocks.listNotifications(...args),
  getUnreadCount: (...args: unknown[]) => mocks.getUnreadCount(...args),
  markNotificationsRead: (...args: unknown[]) => mocks.markNotificationsRead(...args),
  dismissNotification: (...args: unknown[]) => mocks.dismissNotification(...args),
  snoozeNotification: (...args: unknown[]) => mocks.snoozeNotification(...args),
  subscribeNotificationsStream: (...args: unknown[]) => mocks.subscribeNotificationsStream(...args),
}));

vi.mock('@web/components/ui/ToastProvider', () => ({
  useToast: () => ({ show: mocks.showToast }),
}));

import NotificationsPage from '@web/pages/notifications';

describe('NotificationsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.listNotifications.mockResolvedValue({
      items: [
        {
          id: 101,
          kind: 'job_failed',
          title: 'Job failed',
          message: 'chatbooks/export failed.',
          severity: 'error',
          created_at: '2026-02-26T00:00:00+00:00',
          read_at: null,
          dismissed_at: null,
        },
      ],
      total: 1,
    });
    mocks.getUnreadCount.mockResolvedValue({ unread_count: 2 });
    mocks.markNotificationsRead.mockResolvedValue({ updated: 1 });
    mocks.dismissNotification.mockResolvedValue({ dismissed: true });
    mocks.snoozeNotification.mockResolvedValue({
      task_id: 'task-123',
      run_at: '2026-02-26T00:15:00+00:00',
    });
    mocks.subscribeNotificationsStream.mockImplementation(() => () => {});
  });

  it('renders unread count and marks notification read', async () => {
    const user = userEvent.setup();

    render(<NotificationsPage />);

    expect(await screen.findByText('Unread: 2')).toBeInTheDocument();
    const markReadButton = await screen.findByRole('button', { name: 'Mark read' });
    await user.click(markReadButton);

    await waitFor(() => {
      expect(mocks.markNotificationsRead).toHaveBeenCalledWith([101]);
    });
    expect(screen.getByText('Unread: 1')).toBeInTheDocument();
  });

  it('updates the inbox from stream events without showing a duplicate toast', async () => {
    let onEvent: ((event: { event: string; id?: number; payload?: unknown }) => void) | null = null;
    mocks.subscribeNotificationsStream.mockImplementation((options: { onEvent: typeof onEvent }) => {
      onEvent = options.onEvent;
      return () => {};
    });

    render(<NotificationsPage />);

    expect(await screen.findByText('Unread: 2')).toBeInTheDocument();

    onEvent?.({
      event: 'notification',
      id: 102,
      payload: {
        notification_id: 102,
        kind: 'deep_research_completed',
        title: 'Deep research completed',
        message: 'Open the report in Deep Research.',
        severity: 'info',
        created_at: '2026-03-08T01:00:00Z',
      },
    });

    expect(await screen.findByText('Open the report in Deep Research.')).toBeInTheDocument();
    expect(mocks.showToast).not.toHaveBeenCalled();
  });
});
