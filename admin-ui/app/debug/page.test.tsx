/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DebugPage from './page';

const permissionGuardMock = vi.hoisted(() => vi.fn(({ children }: { children: ReactNode }) => <>{children}</>));
const isSingleUserModeMock = vi.hoisted(() => vi.fn(() => false));

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

vi.mock('@/lib/auth', () => ({
  isSingleUserMode: isSingleUserModeMock,
}));

describe('DebugPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    isSingleUserModeMock.mockReturnValue(false);
  });

  it('requires super-admin or owner access in multi-user mode', () => {
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

  it('allows admin access in single-user mode', () => {
    isSingleUserModeMock.mockReturnValue(true);

    render(<DebugPage />);

    expect(permissionGuardMock).toHaveBeenCalledWith(
      expect.objectContaining({
        variant: 'route',
        requireAuth: true,
        role: ['admin', 'super_admin', 'owner'],
      }),
      undefined
    );
  });
});
