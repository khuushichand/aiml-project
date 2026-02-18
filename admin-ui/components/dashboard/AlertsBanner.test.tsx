/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { AlertsBanner, summarizeAlertSeverities } from './AlertsBanner';

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

describe('summarizeAlertSeverities', () => {
  it('groups alerts into critical, warning, and info buckets', () => {
    const summary = summarizeAlertSeverities([
      { severity: 'critical' },
      { severity: 'warning' },
      { severity: 'error' },
      { severity: 'info' },
      {},
    ]);

    expect(summary).toEqual({
      critical: 2,
      warning: 1,
      info: 2,
    });
  });
});

describe('AlertsBanner', () => {
  it('renders nothing when there are no active alerts', () => {
    const { container } = render(<AlertsBanner alerts={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('shows severity breakdown and critical red styling for mixed alerts', () => {
    render(
      <AlertsBanner
        alerts={[
          { severity: 'critical' },
          { severity: 'warning' },
          { severity: 'info' },
          { severity: 'error' },
        ]}
      />
    );

    expect(screen.getByText('2 critical')).toBeInTheDocument();
    expect(screen.getByText('1 warning')).toBeInTheDocument();
    expect(screen.getByText('1 info')).toBeInTheDocument();
    expect(screen.getByText('4 active alerts require attention.')).toBeInTheDocument();
    expect(screen.getByRole('alert').className).toContain('bg-red-50');
  });
});
