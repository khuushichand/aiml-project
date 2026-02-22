/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DependenciesPage from '../page';
import { api } from '@/lib/api-client';

vi.mock('@/components/PermissionGuard', () => ({
  PermissionGuard: ({ children }: { children: ReactNode }) => <>{children}</>,
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/ResponsiveLayout', () => ({
  ResponsiveLayout: ({ children }: { children: ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}));

vi.mock('@/lib/api-client', () => ({
  api: {
    getLLMProviders: vi.fn(),
    getLlmUsageSummary: vi.fn(),
    getMetricsText: vi.fn(),
    testLLMProvider: vi.fn(),
  },
}));

type ApiMock = {
  getLLMProviders: ReturnType<typeof vi.fn>;
  getLlmUsageSummary: ReturnType<typeof vi.fn>;
  getMetricsText: ReturnType<typeof vi.fn>;
  testLLMProvider: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

beforeEach(() => {
  apiMock.getLLMProviders.mockResolvedValue({
    providers: [
      {
        name: 'openai',
        enabled: true,
        default_model: 'gpt-4o-mini',
        models: ['gpt-4o-mini'],
      },
      {
        name: 'anthropic',
        enabled: true,
        default_model: 'claude-3-5-sonnet',
        models: ['claude-3-5-sonnet'],
      },
    ],
  });

  apiMock.getLlmUsageSummary.mockImplementation(async (params?: { group_by?: string | string[] }) => {
    if (Array.isArray(params?.group_by)) {
      return [
        { group_value: 'openai', group_value_secondary: '2026-02-12', requests: 20, errors: 1 },
        { group_value: 'openai', group_value_secondary: '2026-02-13', requests: 18, errors: 0 },
        { group_value: 'openai', group_value_secondary: '2026-02-14', requests: 15, errors: 2 },
        { group_value: 'anthropic', group_value_secondary: '2026-02-14', requests: 11, errors: 0 },
      ];
    }
    return [
      { group_value: 'openai', requests: 80, errors: 4, latency_avg_ms: 142 },
      { group_value: 'anthropic', requests: 30, errors: 1, latency_avg_ms: 201 },
    ];
  });

  apiMock.getMetricsText.mockResolvedValue(
    'llm_provider_requests_total{provider="openai",status="ok"} 80'
  );

  apiMock.testLLMProvider.mockImplementation(async ({ provider }: { provider: string }) => {
    if (provider === 'anthropic') {
      throw new Error('timeout');
    }
    return { provider, status: 'ok', model: 'gpt-4o-mini' };
  });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('DependenciesPage', () => {
  it('renders dependency health grid with provider metrics', async () => {
    render(<DependenciesPage />);

    expect(await screen.findByRole('heading', { name: 'External Dependencies' })).toBeInTheDocument();
    const openaiRow = (await screen.findByText('Openai')).closest('tr');
    const anthropicRow = (await screen.findByText('Anthropic')).closest('tr');

    expect(openaiRow).not.toBeNull();
    expect(anthropicRow).not.toBeNull();
    expect(within(openaiRow as HTMLElement).getByText('Reachable')).toBeInTheDocument();
    expect(within(openaiRow as HTMLElement).getByText('5.0%')).toBeInTheDocument();
    expect(within(anthropicRow as HTMLElement).getByText('3.3%')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'openai availability trend' })).toBeInTheDocument();
  });

  it('runs per-provider connectivity test and updates displayed status', async () => {
    const user = userEvent.setup();

    apiMock.getLLMProviders.mockResolvedValueOnce({
      providers: [
        {
          name: 'openai',
          enabled: true,
          default_model: 'gpt-4o-mini',
          models: ['gpt-4o-mini'],
        },
      ],
    });

    let callCount = 0;
    apiMock.testLLMProvider.mockImplementation(async ({ provider }: { provider: string }) => {
      callCount += 1;
      if (provider === 'openai' && callCount === 1) {
        throw new Error('initial timeout');
      }
      return { provider, status: 'ok', model: 'gpt-4o-mini' };
    });

    render(<DependenciesPage />);

    const openaiRow = (await screen.findByText('Openai')).closest('tr');
    expect(openaiRow).not.toBeNull();
    expect(within(openaiRow as HTMLElement).getByText('Unreachable')).toBeInTheDocument();

    const testButton = within(openaiRow as HTMLElement).getByRole('button', {
      name: /test openai connectivity/i,
    });
    await user.click(testButton);

    await waitFor(() => {
      expect(within(openaiRow as HTMLElement).getByText('Reachable')).toBeInTheDocument();
    });
    expect(apiMock.testLLMProvider).toHaveBeenCalledWith(
      expect.objectContaining({
        provider: 'openai',
        use_override: true,
      })
    );
  });

  it('highlights unreachable providers with red row styling and last-success info', async () => {
    render(<DependenciesPage />);

    const anthropicLabel = await screen.findByText('Anthropic');
    const row = anthropicLabel.closest('tr');
    expect(row).not.toBeNull();
    expect(row?.className).toContain('bg-red-50');
    expect(within(row as HTMLElement).getByText('Unreachable')).toBeInTheDocument();
    expect(within(row as HTMLElement).getByText('Never')).toBeInTheDocument();
  });
});
