/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import UsersPage from '../page';
import { api } from '@/lib/api-client';

const confirmMock = vi.hoisted(() => vi.fn());
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

vi.mock('@/lib/use-url-state', () => ({
  useUrlState: () => ['', vi.fn()],
  useUrlPagination: () => ({
    page: 1,
    pageSize: 25,
    setPage: vi.fn(),
    setPageSize: vi.fn(),
    resetPagination: vi.fn(),
  }),
}));

vi.mock('@/lib/api-client', () => ({
  api: {
    getUsers: vi.fn(),
    deleteUser: vi.fn(),
    updateUser: vi.fn(),
    createUser: vi.fn(),
  },
}));

type ApiMock = {
  getUsers: ReturnType<typeof vi.fn>;
  deleteUser: ReturnType<typeof vi.fn>;
  updateUser: ReturnType<typeof vi.fn>;
  createUser: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

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
  toastSuccessMock.mockClear();
  toastErrorMock.mockClear();

  const currentUser = makeUser({ id: 1, username: 'Alice' });
  window.localStorage.setItem('user', JSON.stringify(currentUser));

  apiMock.getUsers.mockResolvedValue([
    currentUser,
    makeUser({ id: 2, username: 'Bob', email: 'bob@example.com' }),
  ]);
  apiMock.deleteUser.mockResolvedValue({});
});

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.resetAllMocks();
});

describe('UsersPage', () => {
  it('disables selection and deletion for the current user', async () => {
    render(<UsersPage />);

    const rowLabel = await screen.findByText('Alice');
    const row = rowLabel.closest('tr');
    expect(row).not.toBeNull();

    const checkbox = within(row as HTMLElement).getByRole('checkbox', {
      name: /select user alice/i,
    });
    expect(checkbox).toBeDisabled();

    const deleteButton = within(row as HTMLElement).getByTitle('Cannot delete yourself');
    expect(deleteButton).toBeDisabled();
  });

  it('allows deleting another user after confirmation', async () => {
    render(<UsersPage />);

    const rowLabel = await screen.findByText('Bob');
    const row = rowLabel.closest('tr');
    expect(row).not.toBeNull();

    const deleteButton = within(row as HTMLElement).getByTitle('Delete user');
    expect(deleteButton).not.toBeDisabled();

    const user = userEvent.setup();
    await user.click(deleteButton);

    expect(confirmMock).toHaveBeenCalled();
    await waitFor(() => {
      expect(apiMock.deleteUser).toHaveBeenCalledWith('2');
    });
  });
});
