/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Breadcrumbs } from './Breadcrumbs';

let pathname = '/';

vi.mock('next/navigation', () => ({
  usePathname: () => pathname,
}));

vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

afterEach(() => {
  cleanup();
  pathname = '/';
});

describe('Breadcrumbs', () => {
  it('renders breadcrumb trail for nested static routes', () => {
    pathname = '/roles/matrix';
    render(<Breadcrumbs />);

    const nav = screen.getByTestId('breadcrumbs-nav');
    expect(nav.textContent).toContain('Dashboard');
    expect(nav.textContent).toContain('Roles & Permissions');
    expect(nav.textContent).toContain('Permission Matrix');

    expect(screen.getByRole('link', { name: 'Dashboard' }).getAttribute('href')).toBe('/');
    expect(screen.getByRole('link', { name: 'Roles & Permissions' }).getAttribute('href')).toBe('/roles');
    expect(screen.getByText('Permission Matrix').getAttribute('aria-current')).toBe('page');
  });

  it('renders dynamic segment breadcrumbs for user detail', () => {
    pathname = '/users/123';
    render(<Breadcrumbs />);

    expect(screen.getByRole('link', { name: 'Users' }).getAttribute('href')).toBe('/users');
    expect(screen.getByText('User 123')).toBeTruthy();
  });

  it('does not render on top-level routes', () => {
    pathname = '/users';
    render(<Breadcrumbs />);

    expect(screen.queryByTestId('breadcrumbs-nav')).toBeNull();
  });
});
