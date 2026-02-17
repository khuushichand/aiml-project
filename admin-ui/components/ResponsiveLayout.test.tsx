/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { ResponsiveLayout } from './ResponsiveLayout';

vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock('next/navigation', () => ({
  usePathname: () => '/',
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

vi.mock('@/lib/auth', () => ({
  logout: vi.fn().mockResolvedValue(undefined),
}));

vi.mock('@/components/PermissionGuard', () => ({
  usePermissions: () => ({
    user: {
      id: 1,
      uuid: 'user-1',
      username: 'Admin',
      email: 'admin@example.com',
      role: 'admin',
      is_active: true,
      is_verified: true,
      storage_quota_mb: 100,
      storage_used_mb: 10,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    },
    hasPermission: () => true,
    hasRole: () => true,
    loading: false,
    refresh: async () => {},
  }),
}));

vi.mock('@/components/ui/toast', () => ({
  useToast: () => ({
    error: vi.fn(),
  }),
}));

vi.mock('@/components/ThemeToggle', () => ({
  ThemeToggle: () => <div data-testid="theme-toggle" />,
}));

vi.mock('@/components/OrgContextSwitcher', () => ({
  OrgContextSwitcher: () => <div data-testid="org-switcher" />,
}));

afterEach(() => {
  cleanup();
});

describe('ResponsiveLayout mobile navigation', () => {
  it('opens as a modal dialog and closes on Escape', () => {
    render(
      <ResponsiveLayout>
        <div>Page content</div>
      </ResponsiveLayout>
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open navigation menu' }));
    expect(screen.getByRole('dialog', { name: 'Main navigation' })).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: 'Main navigation' })).toBeNull();
  });

  it('shows no-results state when nav search has no match', () => {
    render(
      <ResponsiveLayout>
        <div>Page content</div>
      </ResponsiveLayout>
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open navigation menu' }));
    const dialog = screen.getByRole('dialog', { name: 'Main navigation' });

    fireEvent.change(within(dialog).getByLabelText('Find navigation page'), {
      target: { value: 'no-such-admin-route' },
    });

    expect(within(dialog).getByText('No navigation matches your search.')).toBeInTheDocument();
  });
});
