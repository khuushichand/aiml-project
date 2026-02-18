/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ApiKeysPage from '../page';
import { api } from '@/lib/api-client';

const confirmMock = vi.hoisted(() => vi.fn());
const toastSuccessMock = vi.hoisted(() => vi.fn());
const toastErrorMock = vi.hoisted(() => vi.fn());
const setPageMock = vi.hoisted(() => vi.fn());
const setPageSizeMock = vi.hoisted(() => vi.fn());
const resetPaginationMock = vi.hoisted(() => vi.fn());

vi.mock('next/link', () => ({
  default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
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

vi.mock('@/components/OrgContextSwitcher', () => ({
  useOrgContext: () => ({ selectedOrg: null }),
  OrgContextSwitcher: () => <div data-testid="org-switcher" />,
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

vi.mock('@/lib/use-url-state', () => ({
  useUrlState: (_key: string, options?: { defaultValue?: string }) => [options?.defaultValue ?? '', vi.fn()],
  useUrlPagination: () => ({
    page: 1,
    pageSize: 25,
    setPage: setPageMock,
    setPageSize: setPageSizeMock,
    resetPagination: resetPaginationMock,
  }),
}));

vi.mock('@/lib/api-client', () => ({
  api: {
    getUsersPage: vi.fn(),
    getUserApiKeys: vi.fn(),
    rotateApiKey: vi.fn(),
  },
}));

type ApiMock = {
  getUsersPage: ReturnType<typeof vi.fn>;
  getUserApiKeys: ReturnType<typeof vi.fn>;
  rotateApiKey: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

beforeEach(() => {
  confirmMock.mockResolvedValue(true);
  toastSuccessMock.mockClear();
  toastErrorMock.mockClear();

  apiMock.getUsersPage.mockResolvedValue({
    items: [
      { id: 1, username: 'alice', email: 'alice@example.com' },
      { id: 2, username: 'bob', email: 'bob@example.com' },
    ],
    total: 2,
    page: 1,
    pages: 1,
    limit: 100,
  });

  apiMock.getUserApiKeys.mockImplementation(async (userId: string) => {
    if (userId === '1') {
      return [{
        id: 101,
        key_prefix: 'sk-alice',
        status: 'active',
        created_at: '2026-02-15T00:00:00Z',
        expires_at: null,
        last_used_at: '2026-02-16T00:00:00Z',
      }];
    }
    return [{
      id: 202,
      key_prefix: 'sk-bob',
      status: 'active',
      created_at: '2026-02-14T00:00:00Z',
      expires_at: null,
      last_used_at: '2026-02-16T00:00:00Z',
    }];
  });

  apiMock.rotateApiKey.mockResolvedValue({ status: 'stored' });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('ApiKeysPage', () => {
  it('supports bulk key rotation with selection and confirmation', async () => {
    const user = userEvent.setup();

    render(<ApiKeysPage />);

    expect(await screen.findByLabelText('Select key sk-alice')).toBeInTheDocument();
    expect(screen.getByLabelText('Select key sk-bob')).toBeInTheDocument();

    await user.click(screen.getByLabelText('Select all keys'));
    expect(screen.getByRole('button', { name: 'Rotate Selected (2)' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Rotate Selected (2)' }));

    await waitFor(() => {
      expect(confirmMock).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Rotate selected keys',
          message: 'Rotate 2 key(s)? Existing keys will stop working immediately.',
        })
      );
    });

    await waitFor(() => {
      expect(apiMock.rotateApiKey).toHaveBeenCalledWith('1', '101');
      expect(apiMock.rotateApiKey).toHaveBeenCalledWith('2', '202');
    });

    expect(toastSuccessMock).toHaveBeenCalledWith(
      'Bulk rotation complete',
      '2 key(s) rotated successfully.'
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Rotate Selected (0)' })).toBeDisabled();
    });
  });
});
