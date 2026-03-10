import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PlanGuard } from '../PlanGuard';

const mockIsBillingEnabled = vi.hoisted(() => vi.fn());
const mockGetOrgSubscription = vi.hoisted(() => vi.fn());
const mockUseOrgContext = vi.hoisted(() => vi.fn());

vi.mock('@/lib/billing', () => ({
  isBillingEnabled: mockIsBillingEnabled,
}));

vi.mock('@/lib/api-client', () => ({
  api: { getOrgSubscription: mockGetOrgSubscription },
  ApiError: class extends Error {},
}));

vi.mock('@/components/OrgContextSwitcher', () => ({
  useOrgContext: mockUseOrgContext,
}));

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

describe('PlanGuard', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('renders children when billing is disabled (self-hosted)', () => {
    mockIsBillingEnabled.mockReturnValue(false);
    mockUseOrgContext.mockReturnValue({ selectedOrg: null, loading: false });
    render(<PlanGuard requiredPlan="pro"><div>Protected Content</div></PlanGuard>);
    expect(screen.getByText('Protected Content')).toBeInTheDocument();
    expect(mockGetOrgSubscription).not.toHaveBeenCalled();
  });

  it('renders children when org has required plan', async () => {
    mockIsBillingEnabled.mockReturnValue(true);
    mockUseOrgContext.mockReturnValue({ selectedOrg: { id: 1, name: 'Test' }, loading: false });
    mockGetOrgSubscription.mockResolvedValue({
      plan: { tier: 'pro' },
      status: 'active',
    });
    render(<PlanGuard requiredPlan="pro"><div>Protected Content</div></PlanGuard>);
    expect(await screen.findByText('Protected Content')).toBeInTheDocument();
  });

  it('renders upgrade prompt when org lacks required plan', async () => {
    mockIsBillingEnabled.mockReturnValue(true);
    mockUseOrgContext.mockReturnValue({ selectedOrg: { id: 1, name: 'Test' }, loading: false });
    mockGetOrgSubscription.mockResolvedValue({
      plan: { tier: 'free' },
      status: 'active',
    });
    render(<PlanGuard requiredPlan="pro" featureName="Analytics"><div>Hidden</div></PlanGuard>);
    expect(await screen.findByText('Upgrade Plan')).toBeInTheDocument();
    expect(screen.queryByText('Hidden')).not.toBeInTheDocument();
  });

  it('accepts array of plans', async () => {
    mockIsBillingEnabled.mockReturnValue(true);
    mockUseOrgContext.mockReturnValue({ selectedOrg: { id: 1, name: 'Test' }, loading: false });
    mockGetOrgSubscription.mockResolvedValue({
      plan: { tier: 'enterprise' },
      status: 'active',
    });
    render(<PlanGuard requiredPlan={['pro', 'enterprise']}><div>Visible</div></PlanGuard>);
    expect(await screen.findByText('Visible')).toBeInTheDocument();
  });

  it('renders custom fallback when provided and plan insufficient', async () => {
    mockIsBillingEnabled.mockReturnValue(true);
    mockUseOrgContext.mockReturnValue({ selectedOrg: { id: 1, name: 'Test' }, loading: false });
    mockGetOrgSubscription.mockResolvedValue({
      plan: { tier: 'free' },
      status: 'active',
    });
    render(
      <PlanGuard requiredPlan="enterprise" fallback={<div>Custom Fallback</div>}>
        <div>Hidden</div>
      </PlanGuard>
    );
    expect(await screen.findByText('Custom Fallback')).toBeInTheDocument();
    expect(screen.queryByText('Hidden')).not.toBeInTheDocument();
  });

  it('fails closed on API error', async () => {
    mockIsBillingEnabled.mockReturnValue(true);
    mockUseOrgContext.mockReturnValue({ selectedOrg: { id: 1, name: 'Test' }, loading: false });
    mockGetOrgSubscription.mockRejectedValue(new Error('Network error'));
    render(<PlanGuard requiredPlan="pro" featureName="Analytics"><div>Hidden</div></PlanGuard>);
    expect(await screen.findByText('Upgrade Plan')).toBeInTheDocument();
    expect(screen.queryByText('Hidden')).not.toBeInTheDocument();
  });
});
