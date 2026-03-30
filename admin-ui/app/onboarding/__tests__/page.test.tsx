/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import OnboardingPage from '../page';
import type { Plan } from '@/types';

const toastSuccessMock = vi.hoisted(() => vi.fn());
const toastErrorMock = vi.hoisted(() => vi.fn());

vi.mock('@/components/PermissionGuard', () => ({
  PermissionGuard: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/ui/toast', () => ({
  useToast: () => ({
    success: toastSuccessMock,
    error: toastErrorMock,
  }),
}));

vi.mock('@/lib/billing', () => ({
  isBillingEnabled: vi.fn(() => true),
}));

vi.mock('@/components/PlanBadge', () => ({
  PlanBadge: ({ tier }: { tier: string }) => <span data-testid="plan-badge">{tier}</span>,
}));

const samplePlans: Plan[] = [
  {
    id: 'plan-free',
    name: 'Free',
    tier: 'free',
    stripe_product_id: 'prod_free',
    stripe_price_id: 'price_free',
    monthly_price_cents: 0,
    included_token_credits: 1000,
    overage_rate_per_1k_tokens_cents: 0,
    features: ['basic'],
    is_default: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'plan-pro',
    name: 'Pro',
    tier: 'pro',
    stripe_product_id: 'prod_pro',
    stripe_price_id: 'price_pro',
    monthly_price_cents: 2000,
    included_token_credits: 100000,
    overage_rate_per_1k_tokens_cents: 5,
    features: ['basic', 'advanced'],
    is_default: false,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

vi.mock('@/lib/api-client', () => ({
  api: {
    getPlans: vi.fn(),
    getOrganizations: vi.fn(),
    createOnboardingSession: vi.fn(),
  },
}));

// Import the mocked module after mock setup
import { api } from '@/lib/api-client';
import { isBillingEnabled } from '@/lib/billing';

const mockedGetPlans = api.getPlans as ReturnType<typeof vi.fn>;
const mockedGetOrganizations = api.getOrganizations as ReturnType<typeof vi.fn>;
const mockedIsBillingEnabled = isBillingEnabled as ReturnType<typeof vi.fn>;

describe('OnboardingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetPlans.mockResolvedValue(samplePlans);
    mockedGetOrganizations.mockResolvedValue([]);
    mockedIsBillingEnabled.mockReturnValue(true);
  });

  afterEach(cleanup);

  it('renders billing not enabled message when billing is disabled', async () => {
    mockedIsBillingEnabled.mockReturnValue(false);
    render(<OnboardingPage />);
    expect(screen.getByText('Billing is not enabled')).toBeInTheDocument();
  });

  it('renders step 1 with organization name input', async () => {
    render(<OnboardingPage />);
    await waitFor(() => {
      expect(screen.getByTestId('org-name-input')).toBeInTheDocument();
    });
    expect(screen.getByTestId('org-slug-input')).toBeInTheDocument();
    expect(screen.getByTestId('step-indicator')).toBeInTheDocument();
    expect(screen.getByText('Organization Details')).toBeInTheDocument();
  });

  it('advances to step 2 when Next is clicked with valid data', async () => {
    const user = userEvent.setup();
    render(<OnboardingPage />);

    await waitFor(() => {
      expect(screen.getByTestId('org-name-input')).toBeInTheDocument();
    });

    await user.type(screen.getByTestId('org-name-input'), 'Test Org');
    await user.type(screen.getByTestId('org-slug-input'), 'test-org');

    await user.click(screen.getByRole('button', { name: /next/i }));

    await waitFor(() => {
      expect(screen.getByText('Select a Plan')).toBeInTheDocument();
    });
  });

  it('does not advance to step 2 when org name is empty', async () => {
    const user = userEvent.setup();
    render(<OnboardingPage />);

    await waitFor(() => {
      expect(screen.getByTestId('org-name-input')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /next/i }));

    // Should still be on step 1
    await waitFor(() => {
      expect(screen.getByText('Organization Details')).toBeInTheDocument();
    });
    expect(screen.queryByText('Select a Plan')).not.toBeInTheDocument();
  });

  it('shows plan cards on step 2', async () => {
    const user = userEvent.setup();
    render(<OnboardingPage />);

    await waitFor(() => {
      expect(screen.getByTestId('org-name-input')).toBeInTheDocument();
    });

    await user.type(screen.getByTestId('org-name-input'), 'Test Org');
    await user.type(screen.getByTestId('org-slug-input'), 'test-org');
    await user.click(screen.getByRole('button', { name: /next/i }));

    await waitFor(() => {
      expect(screen.getByTestId('plan-card-plan-free')).toBeInTheDocument();
      expect(screen.getByTestId('plan-card-plan-pro')).toBeInTheDocument();
    });
  });

  it('does not advance when the organization slug is already taken', async () => {
    const user = userEvent.setup();
    mockedGetOrganizations.mockResolvedValueOnce([{ slug: 'test-org' }]);
    render(<OnboardingPage />);

    await waitFor(() => {
      expect(screen.getByTestId('org-name-input')).toBeInTheDocument();
    });

    await user.type(screen.getByTestId('org-name-input'), 'Test Org');
    await user.type(screen.getByTestId('org-slug-input'), 'test-org');
    await user.click(screen.getByRole('button', { name: /next/i }));

    await waitFor(() => {
      expect(toastErrorMock).toHaveBeenCalledWith('Slug is already taken');
    });
    expect(screen.getByText('Organization Details')).toBeInTheDocument();
    expect(screen.queryByText('Select a Plan')).not.toBeInTheDocument();
  });

  it('ignores stale slug availability responses from older requests', async () => {
    const user = userEvent.setup();
    let resolveFirst: ((value: Array<{ slug?: string }>) => void) | undefined;
    let resolveSecond: ((value: Array<{ slug?: string }>) => void) | undefined;

    mockedGetOrganizations
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirst = resolve;
          })
      )
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveSecond = resolve;
          })
      );

    render(<OnboardingPage />);

    const slugInput = await screen.findByTestId('org-slug-input');

    await user.type(slugInput, 'alpha');
    slugInput.blur();

    await user.clear(slugInput);
    await user.type(slugInput, 'beta');
    slugInput.blur();

    resolveSecond?.([]);
    await waitFor(() => {
      expect(screen.getByText('Slug is available')).toBeInTheDocument();
    });

    resolveFirst?.([{ slug: 'alpha' }]);

    await waitFor(() => {
      expect(screen.getByText('Slug is available')).toBeInTheDocument();
    });
    expect(screen.queryByText('Slug is already taken')).not.toBeInTheDocument();
  });
});
