/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import UsersPage from '../page';
import { api } from '@/lib/api-client';
import { formatAxeViolations, getCriticalAndSeriousAxeViolations } from '@/test-utils/axe';
import { getScopedItem } from '@/lib/scoped-storage';

const confirmMock = vi.hoisted(() => vi.fn());
const privilegedActionMock = vi.hoisted(() => vi.fn());
const toastSuccessMock = vi.hoisted(() => vi.fn());
const toastErrorMock = vi.hoisted(() => vi.fn());

const permissionUser = vi.hoisted(() => ({
  id: 1,
  uuid: 'user-1',
  username: 'Alice',
  email: 'alice@example.com',
  role: 'admin',
  is_active: true,
  is_verified: true,
  storage_quota_mb: 100,
  storage_used_mb: 12,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}));

vi.mock('@/components/PermissionGuard', () => ({
  PermissionGuard: ({ children }: { children: ReactNode }) => <>{children}</>,
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
  usePermissions: () => ({
    user: permissionUser,
    permissions: [],
    permissionHints: [],
    roles: ['admin'],
    loading: false,
    hasPermission: () => true,
    hasRole: () => true,
    hasAnyPermission: () => true,
    hasAllPermissions: () => true,
    isAdmin: () => true,
    isSuperAdmin: () => false,
    refresh: async () => {},
  }),
}));

vi.mock('@/components/ResponsiveLayout', () => ({
  ResponsiveLayout: ({ children }: { children: ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}));

vi.mock('@/components/ui/confirm-dialog', () => ({
  useConfirm: () => confirmMock,
}));

vi.mock('@/components/ui/privileged-action-dialog', () => ({
  usePrivilegedActionDialog: () => privilegedActionMock,
}));

vi.mock('@/components/ui/toast', () => ({
  useToast: () => ({
    success: toastSuccessMock,
    error: toastErrorMock,
  }),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => '/users',
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/components/OrgContextSwitcher', () => ({
  useOrgContext: () => ({ selectedOrg: null }),
  OrgContextSwitcher: () => <div data-testid="org-switcher" />,
}));

vi.mock('@/lib/use-url-state', async () => {
  const React = await import('react');
  return {
    useUrlState: (_key: string, options?: { defaultValue?: unknown }) => {
      const [value, setValue] = React.useState(options?.defaultValue);
      return [value, setValue];
    },
    useUrlPagination: () => {
      const [page, setPage] = React.useState(1);
      const [pageSize, setPageSize] = React.useState(25);
      return {
        page,
        pageSize,
        setPage,
        setPageSize,
        resetPagination: () => setPage(1),
      };
    },
  };
});

vi.mock('@/lib/api-client', () => ({
  api: {
    getUsers: vi.fn(),
    getOrganizations: vi.fn(),
    getOrgInvites: vi.fn(),
    getUserMfaStatus: vi.fn(),
    deleteUser: vi.fn(),
    updateUser: vi.fn(),
    createUser: vi.fn(),
    resetUserPassword: vi.fn(),
    setUserMfaRequirement: vi.fn(),
  },
}));

const apiMock = vi.mocked(api);

const makeUser = (overrides: Partial<Record<string, unknown>> = {}) => ({
  id: 1,
  uuid: 'user-1',
  username: 'Alice',
  email: 'alice@example.com',
  role: 'admin',
  is_active: true,
  is_verified: true,
  storage_quota_mb: 100,
  storage_used_mb: 12,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  ...overrides,
});

beforeEach(() => {
  confirmMock.mockResolvedValue(true);
  privilegedActionMock.mockResolvedValue({
    reason: 'Customer requested this change',
    adminPassword: 'AdminPass123!',
  });
  toastSuccessMock.mockClear();
  toastErrorMock.mockClear();

  apiMock.getUsers.mockResolvedValue([
    makeUser({ id: 1, username: 'Alice', email: 'alice@example.com', role: 'admin', is_active: true, is_verified: true }),
    makeUser({ id: 2, uuid: 'user-2', username: 'Bob', email: 'bob@example.com', role: 'user', is_active: false, is_verified: true }),
    makeUser({ id: 3, uuid: 'user-3', username: 'Carol', email: 'carol@example.com', role: 'service', is_active: true, is_verified: false }),
  ]);
  apiMock.getOrganizations.mockResolvedValue([
    { id: 11, name: 'Core Org' },
  ]);
  apiMock.getOrgInvites.mockResolvedValue({
    items: [
      {
        id: 1001,
        org_id: 11,
        org_name: 'Core Org',
        role_to_grant: 'member',
        email: 'pending@example.com',
        created_by: 1,
        created_at: '2026-02-17T10:00:00Z',
        expires_at: '2099-02-20T10:00:00Z',
        uses_count: 0,
      },
      {
        id: 1002,
        org_id: 11,
        org_name: 'Core Org',
        role_to_grant: 'admin',
        email: 'accepted@example.com',
        created_by: 1,
        created_at: '2026-02-16T10:00:00Z',
        expires_at: '2099-02-20T10:00:00Z',
        uses_count: 1,
      },
      {
        id: 1003,
        org_id: 11,
        org_name: 'Core Org',
        role_to_grant: 'member',
        email: 'expired@example.com',
        created_by: 1,
        created_at: '2026-01-01T10:00:00Z',
        expires_at: '2026-01-05T10:00:00Z',
        uses_count: 0,
      },
    ],
  });
  apiMock.getUserMfaStatus.mockImplementation(async (userId: string) => {
    if (userId === '2') return { enabled: false };
    if (userId === '3') return { enabled: true };
    return { enabled: true };
  });
  apiMock.deleteUser.mockResolvedValue({});
  apiMock.updateUser.mockResolvedValue({});
  apiMock.createUser.mockResolvedValue({});
  apiMock.resetUserPassword.mockResolvedValue({});
  apiMock.setUserMfaRequirement.mockResolvedValue({});
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('UsersPage', () => {
  it('has no critical/serious axe violations in the default state', async () => {
    const { container } = render(<UsersPage />);

    await screen.findByText('Invitations');
    const violations = await getCriticalAndSeriousAxeViolations(container);
    expect(violations, formatAxeViolations(violations)).toEqual([]);
  });

  it('renders invitation funnel metrics and mixed invitation statuses', async () => {
    render(<UsersPage />);

    await screen.findByText('Invitations');
    expect(screen.getByTestId('invitation-total-sent').textContent).toContain('3');
    expect(screen.getByTestId('invitation-total-accepted').textContent).toContain('1');
    expect(screen.getByTestId('invitation-conversion-rate').textContent).toContain('33.3%');

    expect(screen.getByText('pending@example.com')).toBeInTheDocument();
    expect(screen.getByText('accepted@example.com')).toBeInTheDocument();
    expect(screen.getByText('expired@example.com')).toBeInTheDocument();
    expect(screen.getByText('sent')).toBeInTheDocument();
    expect(screen.getByText('accepted')).toBeInTheDocument();
    expect(screen.getByText('expired')).toBeInTheDocument();
  });

  it('disables selection and deletion for the current user', async () => {
    render(<UsersPage />);

    const checkbox = await screen.findByRole('checkbox', {
      name: /select user alice/i,
    });
    const row = checkbox.closest('tr');
    expect(row).not.toBeNull();

    const currentUserCheckbox = within(row as HTMLElement).getByRole('checkbox', {
      name: /select user alice/i,
    });
    expect(currentUserCheckbox).toBeDisabled();

    const deleteButton = within(row as HTMLElement).getByTitle('Cannot delete yourself');
    expect(deleteButton).toBeDisabled();
  });

  it('sends combined search and filter params to user API', async () => {
    const user = userEvent.setup();
    render(<UsersPage />);

    await screen.findByText('Bob');
    await user.type(screen.getByLabelText(/search users by username, email, or role/i), 'bob');
    await user.selectOptions(screen.getByLabelText(/filter by user status/i), 'inactive');
    await user.selectOptions(screen.getByLabelText(/filter by verification state/i), 'verified');
    await user.selectOptions(screen.getByLabelText(/filter by mfa status/i), 'disabled');

    await waitFor(() => {
      expect(apiMock.getUsers).toHaveBeenLastCalledWith(
        expect.objectContaining({
          limit: '200',
          search: 'bob',
          is_active: 'false',
          is_verified: 'true',
          mfa_enabled: 'false',
        })
      );
    });
  });

  it('applies search and filters together with AND logic', async () => {
    const user = userEvent.setup();
    render(<UsersPage />);

    await screen.findByText('Bob');
    await user.type(screen.getByLabelText(/search users by username, email, or role/i), 'bob');
    await user.selectOptions(screen.getByLabelText(/filter by user status/i), 'inactive');
    await user.selectOptions(screen.getByLabelText(/filter by verification state/i), 'verified');
    await user.selectOptions(screen.getByLabelText(/filter by mfa status/i), 'disabled');

    expect(await screen.findByText('Bob')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByRole('checkbox', { name: /select user alice/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('checkbox', { name: /select user carol/i })).not.toBeInTheDocument();
    });
  });

  it('supports bulk role assignment from the selected role dropdown', async () => {
    const user = userEvent.setup();
    render(<UsersPage />);

    await screen.findByText('Bob');
    await user.click(screen.getByRole('checkbox', { name: /select user bob/i }));
    await user.selectOptions(screen.getByLabelText(/bulk role selection/i), 'admin');
    await user.click(screen.getByRole('button', { name: 'Assign Role' }));

    await waitFor(() => {
      expect(privilegedActionMock).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Assign role to selected users' })
      );
    });
    await waitFor(() => {
      expect(apiMock.updateUser).toHaveBeenCalledWith('2', {
        role: 'admin',
        reason: 'Customer requested this change',
        admin_password: 'AdminPass123!',
      });
    });
  });

  it('does not offer bulk password reset from the list view', async () => {
    const user = userEvent.setup();
    render(<UsersPage />);

    await screen.findByText('Bob');
    await user.click(screen.getByRole('checkbox', { name: /select user bob/i }));

    expect(screen.queryByRole('button', { name: 'Reset Passwords' })).not.toBeInTheDocument();
  });

  it('supports bulk MFA requirement updates for selected users', async () => {
    const user = userEvent.setup();
    render(<UsersPage />);

    await screen.findByText('Bob');
    await user.click(screen.getByRole('checkbox', { name: /select user bob/i }));
    await user.click(screen.getByRole('button', { name: 'Require MFA' }));

    await waitFor(() => {
      expect(privilegedActionMock).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Require MFA for selected users' })
      );
    });
    await waitFor(() => {
      expect(apiMock.setUserMfaRequirement).toHaveBeenCalledWith('2', {
        require_mfa: true,
        reason: 'Customer requested this change',
        admin_password: 'AdminPass123!',
      });
    });
  });

  it('round-trips a saved view through save, apply, and delete', async () => {
    const user = userEvent.setup();
    render(<UsersPage />);

    const searchInput = screen.getByLabelText(/search users by username, email, or role/i) as HTMLInputElement;

    await screen.findByText('Bob');
    await user.type(searchInput, 'bob');
    await user.click(screen.getByRole('button', { name: 'Save view' }));
    await user.type(screen.getByLabelText('View name'), 'Bob only');
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Save view' }));

    await waitFor(() => {
      expect(toastSuccessMock).toHaveBeenCalledWith('Saved view', 'Bob only has been added.');
    });
    expect(getScopedItem('admin_users_saved_views')).toContain('Bob only');

    await user.clear(searchInput);
    await waitFor(() => {
      expect(searchInput.value).toBe('');
    });

    await user.selectOptions(
      screen.getByLabelText('Saved views'),
      await screen.findByRole('option', { name: 'Bob only' })
    );

    await waitFor(() => {
      expect(searchInput.value).toBe('bob');
    });
    expect(await screen.findByText('Bob')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Delete view' }));

    await waitFor(() => {
      expect(confirmMock).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Delete saved view' })
      );
    });
    await waitFor(() => {
      expect(getScopedItem('admin_users_saved_views') ?? '').not.toContain('Bob only');
    });
  });
});
