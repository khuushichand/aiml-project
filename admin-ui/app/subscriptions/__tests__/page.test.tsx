/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import SubscriptionsPage from '../page';
import { api } from '@/lib/api-client';

const toastSuccessMock = vi.hoisted(() => vi.fn());
const toastErrorMock = vi.hoisted(() => vi.fn());

vi.mock('@/components/PermissionGuard', () => ({
  PermissionGuard: ({ children }: { children: ReactNode }) => <>{children}</>,
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

vi.mock('@/components/ui/toast', () => ({
  useToast: () => ({
    success: toastSuccessMock,
    error: toastErrorMock,
  }),
}));

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock('@/lib/billing', () => ({
  isBillingEnabled: () => true,
}));

vi.mock('@/lib/api-client', () => ({
  api: {
    getSubscriptions: vi.fn(),
  },
}));

type ApiMock = {
  getSubscriptions: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

const sampleSubscription = {
  id: 'sub_1',
  org_id: 42,
  plan_id: 'plan_pro',
  plan: {
    id: 'plan_pro',
    name: 'Pro',
    tier: 'pro' as const,
    stripe_product_id: 'prod_1',
    stripe_price_id: 'price_1',
    monthly_price_cents: 2900,
    included_token_credits: 100000,
    overage_rate_per_1k_tokens_cents: 5,
    features: ['feature_a'],
    is_default: false,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  stripe_subscription_id: 'sub_stripe_1',
  status: 'active' as const,
  current_period_start: '2024-06-01T00:00:00Z',
  current_period_end: '2024-07-01T00:00:00Z',
  created_at: '2024-01-15T00:00:00Z',
  updated_at: '2024-06-01T00:00:00Z',
};

describe('SubscriptionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(cleanup);

  it('renders subscriptions in the table', async () => {
    apiMock.getSubscriptions.mockResolvedValue([sampleSubscription]);

    render(<SubscriptionsPage />);

    await waitFor(() => {
      expect(screen.getByText('Org 42')).toBeInTheDocument();
    });

    // Plan badge
    expect(screen.getByText('Pro')).toBeInTheDocument();
    // Status badge
    expect(screen.getByText('active')).toBeInTheDocument();
    // Organization link
    const link = screen.getByText('Org 42').closest('a');
    expect(link?.getAttribute('href')).toBe('/organizations/42');
  });

  it('shows empty state when no subscriptions', async () => {
    apiMock.getSubscriptions.mockResolvedValue([]);

    render(<SubscriptionsPage />);

    await waitFor(() => {
      expect(screen.getByText('No subscriptions found')).toBeInTheDocument();
    });
  });

  it('shows error when fetch fails', async () => {
    apiMock.getSubscriptions.mockRejectedValue(new Error('Network error'));

    render(<SubscriptionsPage />);

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    expect(toastErrorMock).toHaveBeenCalledWith('Network error');
  });
});
