/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { RecentActivityCard, getResourceTypeLabel } from './RecentActivityCard';
import type { AuditLog } from '@/types';

vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

afterEach(() => {
  cleanup();
});

const formatTimeAgo = () => '1m ago';

describe('getResourceTypeLabel', () => {
  it('normalizes resource identifiers into readable badge labels', () => {
    expect(getResourceTypeLabel('api_keys:123')).toBe('api keys');
    expect(getResourceTypeLabel('resource-governor')).toBe('resource governor');
    expect(getResourceTypeLabel(undefined)).toBe('system');
  });
});

describe('RecentActivityCard', () => {
  it('renders username and resource badge with expandable details', () => {
    const logs: AuditLog[] = [
      {
        id: '1',
        timestamp: '2026-02-17T10:00:00.000Z',
        user_id: 12,
        username: 'alice',
        action: 'login_failed',
        resource: 'auth:session',
        details: { reason: 'invalid_password' },
      },
    ];

    render(
      <RecentActivityCard
        loading={false}
        recentActivity={logs}
        formatTimeAgo={formatTimeAgo}
      />
    );

    expect(screen.getByText('login_failed')).toBeInTheDocument();
    expect(screen.getByText('auth')).toBeInTheDocument();
    expect(screen.getByText('alice')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Details' }));
    expect(
      screen.getByText((value) => value.includes('"reason": "invalid_password"'))
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Hide' })).toBeInTheDocument();
  });

  it('falls back to user id when username is not available', () => {
    const logs: AuditLog[] = [
      {
        id: '2',
        timestamp: '2026-02-17T11:00:00.000Z',
        user_id: 42,
        action: 'key_created',
        resource: 'api_keys:42',
      },
    ];

    render(
      <RecentActivityCard
        loading={false}
        recentActivity={logs}
        formatTimeAgo={formatTimeAgo}
      />
    );

    expect(screen.getByText('api keys')).toBeInTheDocument();
    expect(screen.getByText('User 42')).toBeInTheDocument();
  });
});
