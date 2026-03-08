/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import FeatureRegistryPage from '../page';
import { api } from '@/lib/api-client';

const toastSuccessMock = vi.hoisted(() => vi.fn());
const toastErrorMock = vi.hoisted(() => vi.fn());
const toastWarningMock = vi.hoisted(() => vi.fn());

vi.mock('@/components/PermissionGuard', () => ({
  PermissionGuard: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/ResponsiveLayout', () => ({
  ResponsiveLayout: ({ children }: { children: ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}));

vi.mock('@/components/ui/toast', () => ({
  useToast: () => ({
    success: toastSuccessMock,
    error: toastErrorMock,
    warning: toastWarningMock,
  }),
}));

vi.mock('@/lib/api-client', () => ({
  api: {
    getFeatureRegistry: vi.fn(),
    updateFeatureRegistry: vi.fn(),
    getPlans: vi.fn(),
  },
}));

vi.mock('@/lib/billing', () => ({
  isBillingEnabled: vi.fn(() => true),
}));

type ApiMock = {
  getFeatureRegistry: ReturnType<typeof vi.fn>;
  updateFeatureRegistry: ReturnType<typeof vi.fn>;
  getPlans: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

const mockPlans = [
  {
    id: 'plan_free',
    name: 'Free',
    tier: 'free' as const,
    stripe_product_id: 'prod_1',
    stripe_price_id: 'price_1',
    monthly_price_cents: 0,
    included_token_credits: 1000,
    overage_rate_per_1k_tokens_cents: 0,
    features: [],
    is_default: true,
  },
  {
    id: 'plan_pro',
    name: 'Pro',
    tier: 'pro' as const,
    stripe_product_id: 'prod_2',
    stripe_price_id: 'price_2',
    monthly_price_cents: 2000,
    included_token_credits: 50000,
    overage_rate_per_1k_tokens_cents: 5,
    features: [],
    is_default: false,
  },
];

const mockFeatures = [
  {
    feature_key: 'transcription',
    display_name: 'Transcription',
    description: 'Audio and video transcription',
    plans: ['plan_free', 'plan_pro'],
    category: 'Media',
  },
  {
    feature_key: 'rag_search',
    display_name: 'RAG Search',
    description: 'Retrieval-augmented generation search',
    plans: ['plan_pro'],
    category: 'Search',
  },
  {
    feature_key: 'video_download',
    display_name: 'Video Download',
    description: 'Download videos from supported sites',
    plans: ['plan_free'],
    category: 'Media',
  },
];

beforeEach(() => {
  toastSuccessMock.mockReset();
  toastErrorMock.mockReset();
  toastWarningMock.mockReset();

  apiMock.getFeatureRegistry.mockResolvedValue(mockFeatures);
  apiMock.getPlans.mockResolvedValue(mockPlans);
  apiMock.updateFeatureRegistry.mockResolvedValue(mockFeatures);
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('FeatureRegistryPage', () => {
  it('renders feature names and plan column headers', async () => {
    render(<FeatureRegistryPage />);

    expect(await screen.findByText('Feature Registry')).toBeInTheDocument();

    // Plan column headers
    expect(await screen.findByText('Free')).toBeInTheDocument();
    expect(screen.getByText('Pro')).toBeInTheDocument();

    // Feature names
    expect(screen.getByText('Transcription')).toBeInTheDocument();
    expect(screen.getByText('RAG Search')).toBeInTheDocument();
    expect(screen.getByText('Video Download')).toBeInTheDocument();
  });

  it('renders category section headers', async () => {
    render(<FeatureRegistryPage />);

    expect(await screen.findByText('Media')).toBeInTheDocument();
    expect(screen.getByText('Search')).toBeInTheDocument();
  });

  it('shows billing not enabled message when billing is disabled', async () => {
    const { isBillingEnabled } = await import('@/lib/billing');
    vi.mocked(isBillingEnabled).mockReturnValue(false);

    render(<FeatureRegistryPage />);

    expect(await screen.findByText('Billing is not enabled')).toBeInTheDocument();
    expect(apiMock.getFeatureRegistry).not.toHaveBeenCalled();
  });

  it('shows Save Changes button after toggling a feature', async () => {
    const user = userEvent.setup();
    render(<FeatureRegistryPage />);

    await screen.findByText('Transcription');

    // No save button initially
    expect(screen.queryByText('Save Changes')).not.toBeInTheDocument();

    // Toggle RAG Search for Free plan (currently not included)
    const toggleBtn = screen.getByLabelText('Toggle RAG Search for Free');
    await user.click(toggleBtn);

    expect(screen.getByText('Save Changes')).toBeInTheDocument();
  });

  it('calls updateFeatureRegistry on save', async () => {
    const user = userEvent.setup();
    render(<FeatureRegistryPage />);

    await screen.findByText('Transcription');

    // Toggle a feature to make dirty
    const toggleBtn = screen.getByLabelText('Toggle RAG Search for Free');
    await user.click(toggleBtn);

    // Click save
    await user.click(screen.getByText('Save Changes'));

    await waitFor(() => {
      expect(apiMock.updateFeatureRegistry).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({
            feature_key: 'rag_search',
            plans: expect.arrayContaining(['plan_free', 'plan_pro']),
          }),
        ])
      );
    });

    expect(toastSuccessMock).toHaveBeenCalledWith('Changes Saved', expect.any(String));
  });

  it('shows error toast when load fails', async () => {
    apiMock.getFeatureRegistry.mockRejectedValue(new Error('Network error'));

    render(<FeatureRegistryPage />);

    await waitFor(() => {
      expect(toastErrorMock).toHaveBeenCalledWith('Failed to load data', 'Network error');
    });
  });
});
