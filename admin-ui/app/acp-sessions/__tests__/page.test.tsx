/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ACPSessionsPage from '../page';
import { api } from '@/lib/api-client';

const confirmMock = vi.hoisted(() => vi.fn());
const toastSuccessMock = vi.hoisted(() => vi.fn());
const toastErrorMock = vi.hoisted(() => vi.fn());

vi.mock('@/components/PermissionGuard', () => ({
  PermissionGuard: ({ children }: { children: ReactNode }) => <>{children}</>,
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/ResponsiveLayout', () => ({
  ResponsiveLayout: ({ children }: { children: ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}));

vi.mock('@/components/ui/confirm-dialog', () => ({
  useConfirm: () => confirmMock,
}));

vi.mock('@/components/ui/toast', () => ({
  useToast: () => ({
    success: toastSuccessMock,
    error: toastErrorMock,
  }),
}));

vi.mock('@/lib/api-client', () => ({
  ApiError: class extends Error {
    status: number;

    constructor(status: number, message?: string) {
      super(message);
      this.status = status;
    }
  },
  api: {
    getACPSessions: vi.fn(),
    closeACPSession: vi.fn(),
  },
}));

type ApiMock = {
  getACPSessions: ReturnType<typeof vi.fn>;
  closeACPSession: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

beforeEach(() => {
  apiMock.getACPSessions.mockResolvedValue({
    sessions: [],
    total: 0,
  });
  apiMock.closeACPSession.mockResolvedValue({});
  confirmMock.mockResolvedValue(true);
  toastSuccessMock.mockClear();
  toastErrorMock.mockClear();
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('ACPSessionsPage filters', () => {
  it('does not refetch while typing filters until apply is clicked', async () => {
    const user = userEvent.setup();
    render(<ACPSessionsPage />);

    await waitFor(() => {
      expect(apiMock.getACPSessions).toHaveBeenCalledTimes(1);
    });

    await user.type(screen.getByPlaceholderText('Agent type...'), 'assistant');
    await user.type(screen.getByPlaceholderText('User ID...'), '42');

    expect(apiMock.getACPSessions).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole('button', { name: 'Apply' }));

    await waitFor(() => {
      expect(apiMock.getACPSessions).toHaveBeenCalledTimes(2);
    });
    expect(apiMock.getACPSessions).toHaveBeenLastCalledWith({
      agent_type: 'assistant',
      user_id: '42',
    });
  });
});
