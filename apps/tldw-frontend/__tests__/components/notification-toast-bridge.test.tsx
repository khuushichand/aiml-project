import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';

const mocks = vi.hoisted(() => ({
  listNotifications: vi.fn(),
  subscribeNotificationsStream: vi.fn(),
  showToast: vi.fn(),
}));

vi.mock('@web/lib/api/notifications', () => ({
  listNotifications: (...args: unknown[]) => mocks.listNotifications(...args),
  subscribeNotificationsStream: (...args: unknown[]) => mocks.subscribeNotificationsStream(...args),
}));

vi.mock('@web/components/ui/ToastProvider', () => ({
  useToast: () => ({ show: mocks.showToast }),
}));

import { NotificationToastBridge } from '@web/components/notifications/NotificationToastBridge';

describe('NotificationToastBridge', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.listNotifications.mockResolvedValue({
      items: [
        {
          id: 50,
          kind: 'job_completed',
          title: 'Older notification',
          message: 'Already in the inbox.',
          severity: 'info',
          created_at: '2026-03-08T00:00:00Z',
        },
      ],
      total: 1,
    });
    mocks.subscribeNotificationsStream.mockImplementation(() => () => {});
  });

  it('subscribes after the latest inbox notification and toasts new incoming events', async () => {
    let onEvent: ((event: { event: string; id?: number; payload?: unknown }) => void) | null = null;
    mocks.subscribeNotificationsStream.mockImplementation((options: { after?: number; onEvent: typeof onEvent }) => {
      onEvent = options.onEvent;
      return () => {};
    });

    render(<NotificationToastBridge />);

    await waitFor(() => {
      expect(mocks.subscribeNotificationsStream).toHaveBeenCalledWith(
        expect.objectContaining({
          after: 50,
        })
      );
    });

    onEvent?.({
      event: 'notification',
      id: 51,
      payload: {
        notification_id: 51,
        kind: 'deep_research_completed',
        title: 'Deep research completed',
        message: 'Open the report in Deep Research.',
        severity: 'info',
        created_at: '2026-03-08T01:00:00Z',
      },
    });

    await waitFor(() => {
      expect(mocks.showToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Deep research completed',
          description: 'Open the report in Deep Research.',
          variant: 'info',
        })
      );
    });
  });
});
