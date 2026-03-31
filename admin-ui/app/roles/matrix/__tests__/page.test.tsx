/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PermissionMatrixPage from '../page';
import { api } from '@/lib/api-client';

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

vi.mock('@/components/PermissionGuard', () => ({
  PermissionGuard: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/ResponsiveLayout', () => ({
  ResponsiveLayout: ({ children }: { children: ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}));

vi.mock('@/lib/api-client', () => ({
  api: {
    getRoles: vi.fn(),
    getPermissions: vi.fn(),
    getRolePermissions: vi.fn(),
    assignPermissionToRole: vi.fn(),
    removePermissionFromRole: vi.fn(),
  },
}));

type ApiMock = {
  getRoles: ReturnType<typeof vi.fn>;
  getPermissions: ReturnType<typeof vi.fn>;
  getRolePermissions: ReturnType<typeof vi.fn>;
  assignPermissionToRole: ReturnType<typeof vi.fn>;
  removePermissionFromRole: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

beforeEach(() => {
  apiMock.getRoles.mockResolvedValue([
    { id: 1, name: 'Admin', is_system: false },
    { id: 2, name: 'System', is_system: true },
  ]);
  apiMock.getPermissions.mockResolvedValue([
    { id: 101, name: 'read:users' },
    { id: 102, name: 'write:users' },
  ]);
  apiMock.getRolePermissions.mockImplementation(async (roleId: string) => {
    if (roleId === '1') {
      return [{ id: 101, name: 'read:users' }];
    }
    return [{ id: 101, name: 'read:users' }, { id: 102, name: 'write:users' }];
  });
  apiMock.assignPermissionToRole.mockResolvedValue({});
  apiMock.removePermissionFromRole.mockResolvedValue({});
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('PermissionMatrixPage', () => {
  it('tracks unsaved toggles and supports discard', async () => {
    const user = userEvent.setup();
    render(<PermissionMatrixPage />);

    const writeUsersCheckbox = await screen.findByRole('checkbox', {
      name: 'Toggle write:users for Admin',
    });

    await user.click(writeUsersCheckbox);
    expect(screen.getByRole('button', { name: 'Discard (1)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save Changes' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Discard (1)' }));
    expect(screen.queryByRole('button', { name: 'Discard (1)' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Save Changes' })).toBeNull();
  });

  it('saves batched permission updates', async () => {
    const user = userEvent.setup();
    render(<PermissionMatrixPage />);

    const readUsersCheckbox = await screen.findByRole('checkbox', {
      name: 'Toggle read:users for Admin',
    });
    const writeUsersCheckbox = await screen.findByRole('checkbox', {
      name: 'Toggle write:users for Admin',
    });

    await user.click(readUsersCheckbox);
    await user.click(writeUsersCheckbox);
    await user.click(screen.getByRole('button', { name: 'Save Changes' }));

    await waitFor(() => {
      expect(apiMock.removePermissionFromRole).toHaveBeenCalledWith('1', '101');
      expect(apiMock.assignPermissionToRole).toHaveBeenCalledWith('1', '102');
    });

    expect(await screen.findByText('Saved 2 permission changes.')).toBeInTheDocument();
  });

  it('exposes the differences-only toggle state to assistive tech', async () => {
    const user = userEvent.setup();
    render(<PermissionMatrixPage />);

    const toggle = await screen.findByRole('button', { name: 'Differences only' });
    expect(toggle.getAttribute('aria-pressed')).toBe('false');

    await user.click(toggle);

    expect(toggle.getAttribute('aria-pressed')).toBe('true');
  });
});
