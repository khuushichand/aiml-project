/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import RoleComparisonPage from '../page';
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
  },
}));

type ApiMock = {
  getRoles: ReturnType<typeof vi.fn>;
  getPermissions: ReturnType<typeof vi.fn>;
  getRolePermissions: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

beforeEach(() => {
  apiMock.getRoles.mockResolvedValue([
    { id: 1, name: 'Admin', is_system: false },
    { id: 2, name: 'Editor', is_system: false },
    { id: 3, name: 'Viewer', is_system: false },
  ]);
  apiMock.getPermissions.mockResolvedValue([
    { id: 101, name: 'read:users' },
    { id: 102, name: 'write:users' },
  ]);
  apiMock.getRolePermissions.mockImplementation(async (roleId: string) => {
    if (roleId === '1') return [{ id: 101, name: 'read:users' }, { id: 102, name: 'write:users' }];
    if (roleId === '2') return [{ id: 101, name: 'read:users' }];
    return [];
  });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('RoleComparisonPage', () => {
  it('highlights role diffs and matches snapshot', async () => {
    const { container } = render(<RoleComparisonPage />);

    expect(await screen.findByText('Permission Comparison')).toBeInTheDocument();

    const onlyHasCell = await screen.findByTestId('compare-cell-1-102');
    const onlyMissingCell = await screen.findByTestId('compare-cell-2-102');
    expect(onlyHasCell.className).toContain('bg-emerald-50');
    expect(onlyMissingCell.className).toContain('bg-rose-50');

    expect(container.querySelector('table')).toMatchSnapshot();
  });
});
