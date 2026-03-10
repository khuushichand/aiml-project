/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import DebugPage from './page';

const permissionGuardMock = vi.hoisted(() => vi.fn(({ children }: { children: ReactNode }) => <>{children}</>));

vi.mock('@/components/PermissionGuard', () => ({
  PermissionGuard: permissionGuardMock,
}));

vi.mock('@/components/ResponsiveLayout', () => ({
  ResponsiveLayout: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/lib/api-client', () => ({
  api: {
    debugResolveApiKey: vi.fn(),
    debugGetBudgetSummary: vi.fn(),
  },
}));

describe('DebugPage', () => {
  it('requires super-admin or owner access', () => {
    render(<DebugPage />);

    expect(permissionGuardMock).toHaveBeenCalledWith(
      expect.objectContaining({
        variant: 'route',
        requireAuth: true,
        role: ['super_admin', 'owner'],
      }),
      undefined
    );
  });
});
