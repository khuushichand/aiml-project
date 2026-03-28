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
    getDependenciesUptimeHistory: vi.fn(),
    testLLMProvider: vi.fn(),
  },
}));

type ApiMock = {
  getLLMProviders: ReturnType<typeof vi.fn>;
  getLlmUsageSummary: ReturnType<typeof vi.fn>;
  getMetricsText: ReturnType<typeof vi.fn>;
  getDependenciesUptimeHistory: ReturnType<typeof vi.fn>;
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
  apiMock.getDependenciesUptimeHistory.mockResolvedValue({ services: {} });

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

const getProviderRow = async (providerName: string) => {
  const label = await screen.findByText(providerName);
  const row = label.closest('tr');
  expect(row).not.toBeNull();
  return row as HTMLElement;
};

describe('DependenciesPage', () => {
  it('renders dependency health grid with passive telemetry and unknown initial status', async () => {
    render(<DependenciesPage />);

    expect(await screen.findByRole('heading', { name: 'External Dependencies' })).toBeInTheDocument();
    const openaiRow = await getProviderRow('Openai');
    const anthropicRow = await getProviderRow('Anthropic');

    expect(within(openaiRow).getByText('Unknown')).toBeInTheDocument();
    expect(within(openaiRow).getByText('5.0%')).toBeInTheDocument();
    expect(within(openaiRow).getAllByText('Never')).toHaveLength(2);
    expect(within(anthropicRow).getByText('Unknown')).toBeInTheDocument();
    expect(within(anthropicRow).getByText('3.3%')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'openai availability trend' })).toBeInTheDocument();
    expect(apiMock.testLLMProvider).not.toHaveBeenCalled();
  });

  it('refreshes passive telemetry without running provider connectivity checks', async () => {
    const user = userEvent.setup();

    render(<DependenciesPage />);

    await getProviderRow('Openai');

    expect(apiMock.getLLMProviders).toHaveBeenCalledTimes(1);
    expect(apiMock.getLlmUsageSummary).toHaveBeenCalledTimes(2);
    expect(apiMock.getMetricsText).toHaveBeenCalledTimes(1);
    expect(apiMock.testLLMProvider).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: /refresh data/i }));

    await waitFor(() => {
      expect(apiMock.getLLMProviders).toHaveBeenCalledTimes(2);
    });
    expect(apiMock.getLlmUsageSummary).toHaveBeenCalledTimes(4);
    expect(apiMock.getMetricsText).toHaveBeenCalledTimes(2);
    expect(apiMock.testLLMProvider).not.toHaveBeenCalled();
  });

  it('runs all enabled provider checks only after clicking run all checks', async () => {
    const user = userEvent.setup();

    apiMock.getLLMProviders.mockResolvedValueOnce({
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
        {
          name: 'groq',
          enabled: false,
          default_model: 'llama-3.1-8b-instant',
          models: ['llama-3.1-8b-instant'],
        },
      ],
    });

    render(<DependenciesPage />);

    const openaiRow = await getProviderRow('Openai');
    const anthropicRow = await getProviderRow('Anthropic');
    const groqRow = await getProviderRow('Groq');

    expect(apiMock.testLLMProvider).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: /run all checks/i }));

    await waitFor(() => {
      expect(within(openaiRow).getByText('Reachable')).toBeInTheDocument();
    });
    expect(within(anthropicRow).getByText('Unreachable')).toBeInTheDocument();
    expect(within(groqRow).getByText('Unknown')).toBeInTheDocument();
    expect(apiMock.testLLMProvider).toHaveBeenCalledTimes(2);
    expect(apiMock.testLLMProvider).toHaveBeenCalledWith(
      expect.objectContaining({
        provider: 'openai',
        use_override: true,
      })
    );
    expect(apiMock.testLLMProvider).toHaveBeenCalledWith(
      expect.objectContaining({
        provider: 'anthropic',
        use_override: true,
      })
    );
  });

  it('runs per-provider connectivity test and updates displayed status only after click', async () => {
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

    apiMock.testLLMProvider.mockResolvedValue({
      provider: 'openai',
      status: 'ok',
      model: 'gpt-4o-mini',
    });

    render(<DependenciesPage />);

    const openaiRow = await getProviderRow('Openai');
    expect(within(openaiRow).getByText('Unknown')).toBeInTheDocument();
    expect(apiMock.testLLMProvider).not.toHaveBeenCalled();

    const testButton = within(openaiRow).getByRole('button', {
      name: /test openai connectivity/i,
    });
    await user.click(testButton);

    await waitFor(() => {
      expect(within(openaiRow).getByText('Reachable')).toBeInTheDocument();
    });
    expect(apiMock.testLLMProvider).toHaveBeenCalledWith(
      expect.objectContaining({
        provider: 'openai',
        use_override: true,
      })
    );
  });

  it('highlights unreachable providers with red row styling and last-success info', async () => {
    const user = userEvent.setup();

    render(<DependenciesPage />);

    const row = await getProviderRow('Anthropic');
    expect(row.className).not.toContain('bg-red-50');
    expect(within(row).getByText('Unknown')).toBeInTheDocument();

    await user.click(within(row).getByRole('button', { name: /test anthropic connectivity/i }));

    await waitFor(() => {
      expect(within(row).getByText('Unreachable')).toBeInTheDocument();
    });
    expect(row.className).toContain('bg-red-50');
    expect(within(row).getAllByText('Never')).toHaveLength(1);
  });

  it('surfaces uptime history failures instead of silently falling back to no data', async () => {
    apiMock.getDependenciesUptimeHistory.mockRejectedValue(new Error('uptime endpoint down'));

    render(<DependenciesPage />);

    expect(await screen.findByText(/Some dependency telemetry is unavailable:/i)).toBeInTheDocument();
    expect(screen.getByText('Uptime history unavailable: uptime endpoint down')).toBeInTheDocument();
  });
});
