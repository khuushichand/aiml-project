import { afterEach, describe, it, expect, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { UpgradePrompt } from '../UpgradePrompt';

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

afterEach(() => {
  cleanup();
});

describe('UpgradePrompt', () => {
  it('displays required plan name', () => {
    render(<UpgradePrompt requiredPlan="pro" featureName="Advanced Analytics" />);
    expect(screen.getByText(/Pro/)).toBeInTheDocument();
    expect(screen.getByText(/Advanced Analytics/)).toBeInTheDocument();
  });

  it('shows upgrade link when showUpgradeLink is true', () => {
    render(<UpgradePrompt requiredPlan="enterprise" featureName="SSO" showUpgradeLink />);
    expect(screen.getByRole('link', { name: /upgrade/i })).toBeInTheDocument();
  });

  it('hides upgrade link by default', () => {
    render(<UpgradePrompt requiredPlan="pro" featureName="Feature X" />);
    expect(screen.queryByRole('link', { name: /upgrade/i })).not.toBeInTheDocument();
  });
});
