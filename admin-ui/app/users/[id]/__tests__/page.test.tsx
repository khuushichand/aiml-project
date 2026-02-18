/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import UserDetailPage from '../page';
import { api } from '@/lib/api-client';

const confirmMock = vi.hoisted(() => vi.fn());
const toastSuccessMock = vi.hoisted(() => vi.fn());
const toastErrorMock = vi.hoisted(() => vi.fn());
const pushMock = vi.hoisted(() => vi.fn());

vi.mock('next/link', () => ({
  default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: '42' }),
  useRouter: () => ({
    push: pushMock,
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

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

vi.mock('@/lib/api-client', () => {
  class MockApiError extends Error {
    status?: number;

    constructor(message: string, status?: number) {
      super(message);
      this.status = status;
    }
  }

  return {
    ApiError: MockApiError,
    api: {
      getUser: vi.fn(),
      getCurrentUser: vi.fn(),
      getUserOrgMemberships: vi.fn(),
      getUserTeamMemberships: vi.fn(),
      getUserMfaStatus: vi.fn(),
      getUserSessions: vi.fn(),
      getAuditLogs: vi.fn(),
      getUserEffectivePermissions: vi.fn(),
      getUserPermissionOverrides: vi.fn(),
      getPermissions: vi.fn(),
      getUserRateLimits: vi.fn(),
      resetUserPassword: vi.fn(),
    },
  };
});

type ApiMock = {
  getUser: ReturnType<typeof vi.fn>;
  getCurrentUser: ReturnType<typeof vi.fn>;
  getUserOrgMemberships: ReturnType<typeof vi.fn>;
  getUserTeamMemberships: ReturnType<typeof vi.fn>;
  getUserMfaStatus: ReturnType<typeof vi.fn>;
  getUserSessions: ReturnType<typeof vi.fn>;
  getAuditLogs: ReturnType<typeof vi.fn>;
  getUserEffectivePermissions: ReturnType<typeof vi.fn>;
  getUserPermissionOverrides: ReturnType<typeof vi.fn>;
  getPermissions: ReturnType<typeof vi.fn>;
  getUserRateLimits: ReturnType<typeof vi.fn>;
  resetUserPassword: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

beforeEach(() => {
  confirmMock.mockResolvedValue(true);
  toastSuccessMock.mockClear();
  toastErrorMock.mockClear();
  pushMock.mockClear();

  apiMock.getUser.mockResolvedValue({
    id: 42,
    uuid: 'user-42',
    username: 'demo-user',
    email: 'demo@example.com',
    role: 'member',
    is_active: true,
    is_verified: true,
    storage_quota_mb: 1024,
    storage_used_mb: 32,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    metadata: {
      force_password_change: true,
    },
  });
  apiMock.getCurrentUser.mockResolvedValue({ id: 1 });
  apiMock.getUserOrgMemberships.mockImplementation(async (requestedUserId: string) => {
    if (requestedUserId === '1') {
      return [{ org_id: 100, role: 'owner', org_name: 'Acme Org' }];
    }
    return [{ org_id: 100, role: 'member', org_name: 'Acme Org' }];
  });
  apiMock.getUserTeamMemberships.mockResolvedValue([
    {
      team_id: 200,
      team_name: 'Research Team',
      org_id: 100,
      org_name: 'Acme Org',
      role: 'lead',
    },
  ]);
  apiMock.getUserMfaStatus.mockResolvedValue({
    enabled: false,
    has_secret: false,
    has_backup_codes: false,
    method: null,
  });
  apiMock.getUserSessions.mockResolvedValue([]);
  apiMock.getAuditLogs.mockResolvedValue({
    entries: [
      {
        id: 'log-1',
        timestamp: '2026-01-02T10:00:00Z',
        user_id: 42,
        action: 'login',
        resource: 'auth',
        ip_address: '127.0.0.1',
        details: {
          user_agent: 'Chrome',
          success: true,
        },
      },
      {
        id: 'log-2',
        timestamp: '2026-01-02T09:00:00Z',
        user_id: 42,
        action: 'login',
        resource: 'auth',
        ip_address: '192.168.0.1',
        details: {
          user_agent: 'Firefox',
          success: false,
        },
      },
    ],
    total: 2,
    limit: 20,
    offset: 0,
  });
  apiMock.getUserEffectivePermissions.mockResolvedValue({
    permissions: [
      'reports.read',
      'admin.impersonate',
      {
        id: 3,
        name: 'team.manage',
        source: 'inherited',
      },
    ],
  });
  apiMock.getUserPermissionOverrides.mockResolvedValue({
    overrides: [
      {
        id: 1,
        permission_id: 2,
        permission_name: 'admin.impersonate',
        grant: true,
      },
    ],
  });
  apiMock.getPermissions.mockResolvedValue([]);
  apiMock.getUserRateLimits.mockResolvedValue({});
  apiMock.resetUserPassword.mockResolvedValue({
    temporary_password: 'TempP@ssw0rd123',
    force_password_change: false,
    message: 'Password reset successfully',
  });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('UserDetailPage password reset', () => {
  it('resets a password with selected force-password-change flag', async () => {
    const user = userEvent.setup();
    render(<UserDetailPage />);

    const resetButton = await screen.findByRole('button', { name: 'Reset Password' });
    await user.click(screen.getByLabelText('Force Password Change on Next Login'));
    await user.click(resetButton);

    await waitFor(() => {
      expect(confirmMock).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Reset Password' })
      );
    });

    await waitFor(() => {
      expect(apiMock.resetUserPassword).toHaveBeenCalledWith('42', {
        force_password_change: false,
      });
    });

    expect(toastSuccessMock).toHaveBeenCalledWith(
      'Password reset',
      'A new temporary password has been generated.'
    );
    expect(await screen.findByText('Temporary password (shown once)')).toBeInTheDocument();
    expect(screen.getByText('TempP@ssw0rd123')).toBeInTheDocument();
  });

  it('renders login history with success and failure badges', async () => {
    render(<UserDetailPage />);

    expect(await screen.findByText('Login History')).toBeInTheDocument();
    expect(await screen.findByText('Chrome')).toBeInTheDocument();
    expect(await screen.findByText('Firefox')).toBeInTheDocument();
    expect(await screen.findByText('Success')).toBeInTheDocument();
    expect(await screen.findByText('Failure')).toBeInTheDocument();

    expect(apiMock.getAuditLogs).toHaveBeenCalledWith(
      expect.objectContaining({
        user_id: '42',
        action: 'login',
        limit: '20',
      })
    );
  });

  it('opens organization and team membership dialogs from quick actions', async () => {
    const user = userEvent.setup();
    render(<UserDetailPage />);

    await user.click(await screen.findByRole('button', { name: 'View Organizations' }));
    expect(await screen.findByText('User Organizations')).toBeInTheDocument();
    expect(await screen.findByText('Acme Org')).toBeInTheDocument();

    await user.click(screen.getAllByRole('button', { name: 'Close' })[0]);

    await user.click(screen.getByRole('button', { name: 'View Teams' }));
    expect(await screen.findByText('User Teams')).toBeInTheDocument();
    expect(await screen.findByText('Research Team')).toBeInTheDocument();
    expect(await screen.findByText('lead')).toBeInTheDocument();
  });

  it('annotates effective permissions with role, direct override, and inherited badges', async () => {
    const user = userEvent.setup();
    render(<UserDetailPage />);

    const summary = await screen.findByText(/View effective permissions/i);
    await user.click(summary);

    expect(await screen.findByText('Direct override')).toBeInTheDocument();
    expect((await screen.findAllByText(/Role:/i)).length).toBeGreaterThan(0);
    expect(await screen.findByText('Inherited')).toBeInTheDocument();
  });
});
