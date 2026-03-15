/* @vitest-environment jsdom */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';

import { OrgContextProvider } from './OrgContextSwitcher';

const apiMock = vi.hoisted(() => ({
  getOrganizations: vi.fn(),
}));

const usePermissionsMock = vi.hoisted(() => vi.fn());

vi.mock('@/lib/api-client', () => ({
  api: apiMock,
}));

vi.mock('@/components/PermissionGuard', () => ({
  usePermissions: () => usePermissionsMock(),
}));

describe('OrgContextProvider', () => {
  beforeEach(() => {
    cleanup();
    localStorage.clear();
    apiMock.getOrganizations.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it('does not fetch organizations before a user is authenticated', async () => {
    usePermissionsMock.mockReturnValue({
      isSuperAdmin: () => false,
      user: null,
      loading: false,
    });

    render(
      <OrgContextProvider>
        <div data-testid="child">ready</div>
      </OrgContextProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('child')).toBeInTheDocument();
    });

    expect(apiMock.getOrganizations).not.toHaveBeenCalled();
  });

  it('loads organizations once an authenticated user is present', async () => {
    apiMock.getOrganizations.mockResolvedValue([{ id: 1, name: 'Admin E2E', slug: 'admin-e2e' }]);
    usePermissionsMock.mockReturnValue({
      isSuperAdmin: () => true,
      user: {
        id: 1,
        uuid: 'user-1',
        username: 'admin',
        email: 'admin@example.com',
        role: 'admin',
        is_active: true,
        is_verified: true,
        storage_quota_mb: 1024,
        storage_used_mb: 0,
        created_at: '2026-03-11T00:00:00Z',
        updated_at: '2026-03-11T00:00:00Z',
      },
      loading: false,
    });

    render(
      <OrgContextProvider>
        <div data-testid="child">ready</div>
      </OrgContextProvider>,
    );

    await waitFor(() => {
      expect(apiMock.getOrganizations).toHaveBeenCalledTimes(1);
    });
  });
});
