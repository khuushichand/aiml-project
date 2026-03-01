/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import UsagePage from '../page';
import {
  getRouterAnalyticsMeta,
  getRouterAnalyticsStatus,
  getRouterAnalyticsStatusBreakdowns,
} from '@/lib/router-analytics-client';

vi.mock('@/components/PermissionGuard', () => ({
  PermissionGuard: ({ children }: { children: ReactNode }) => <>{children}</>,
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/ResponsiveLayout', () => ({
  ResponsiveLayout: ({ children }: { children: ReactNode }) => <div data-testid="layout">{children}</div>,
}));

vi.mock('@/lib/router-analytics-client', () => ({
  getRouterAnalyticsStatus: vi.fn(),
  getRouterAnalyticsStatusBreakdowns: vi.fn(),
  getRouterAnalyticsMeta: vi.fn(),
}));

type RouterClientMock = {
  getRouterAnalyticsStatus: ReturnType<typeof vi.fn>;
  getRouterAnalyticsStatusBreakdowns: ReturnType<typeof vi.fn>;
  getRouterAnalyticsMeta: ReturnType<typeof vi.fn>;
};

const routerClientMock = {
  getRouterAnalyticsStatus: getRouterAnalyticsStatus,
  getRouterAnalyticsStatusBreakdowns: getRouterAnalyticsStatusBreakdowns,
  getRouterAnalyticsMeta: getRouterAnalyticsMeta,
} as unknown as RouterClientMock;

beforeEach(() => {
  routerClientMock.getRouterAnalyticsStatus.mockResolvedValue({
    kpis: {
      requests: 4,
      prompt_tokens: 52,
      generated_tokens: 32,
      total_tokens: 84,
      avg_latency_ms: 500,
      avg_gen_toks_per_s: 16,
    },
    series: [
      {
        ts: '2026-03-01T10:20:00Z',
        provider: 'openai',
        model: 'gpt-4o-mini',
        requests: 1,
        prompt_tokens: 10,
        completion_tokens: 20,
        total_tokens: 30,
      },
      {
        ts: '2026-03-01T10:25:00Z',
        provider: 'groq',
        model: 'llama-3.3-70b',
        requests: 2,
        prompt_tokens: 35,
        completion_tokens: 10,
        total_tokens: 45,
      },
    ],
    providers_available: 3,
    providers_online: 2,
    generated_at: '2026-03-01T10:30:00Z',
    data_window: {
      start: '2026-03-01T09:30:00Z',
      end: '2026-03-01T10:30:00Z',
      range: '1h',
    },
    partial: false,
  });

  routerClientMock.getRouterAnalyticsStatusBreakdowns.mockResolvedValue({
    providers: [
      { key: 'groq', label: 'groq', requests: 2, prompt_tokens: 35, completion_tokens: 10, total_tokens: 45, errors: 1 },
      { key: 'openai', label: 'openai', requests: 1, prompt_tokens: 10, completion_tokens: 20, total_tokens: 30, errors: 0 },
    ],
    models: [
      { key: 'llama-3.3-70b', label: 'llama-3.3-70b', requests: 2, prompt_tokens: 35, completion_tokens: 10, total_tokens: 45, errors: 1 },
      { key: 'gpt-4o-mini', label: 'gpt-4o-mini', requests: 1, prompt_tokens: 10, completion_tokens: 20, total_tokens: 30, errors: 0 },
    ],
    token_names: [
      { key: 'Admin', label: 'Admin', requests: 1, prompt_tokens: 10, completion_tokens: 20, total_tokens: 30, errors: 0 },
      { key: 'Ops', label: 'Ops', requests: 2, prompt_tokens: 35, completion_tokens: 10, total_tokens: 45, errors: 1 },
    ],
    remote_ips: [
      { key: '127.0.0.1', label: '127.0.0.1', requests: 1, prompt_tokens: 10, completion_tokens: 20, total_tokens: 30, errors: 0 },
      { key: 'unknown', label: 'unknown', requests: 1, prompt_tokens: 7, completion_tokens: 2, total_tokens: 9, errors: 1 },
    ],
    user_agents: [
      { key: 'curl/8.8.0', label: 'curl/8.8.0', requests: 1, prompt_tokens: 10, completion_tokens: 20, total_tokens: 30, errors: 0 },
      { key: 'unknown', label: 'unknown', requests: 1, prompt_tokens: 7, completion_tokens: 2, total_tokens: 9, errors: 1 },
    ],
    generated_at: '2026-03-01T10:30:00Z',
    data_window: {
      start: '2026-03-01T09:30:00Z',
      end: '2026-03-01T10:30:00Z',
      range: '1h',
    },
    partial: false,
  });

  routerClientMock.getRouterAnalyticsMeta.mockResolvedValue({
    providers: [{ value: 'openai', label: 'openai' }, { value: 'groq', label: 'groq' }],
    models: [{ value: 'gpt-4o-mini', label: 'gpt-4o-mini' }, { value: 'llama-3.3-70b', label: 'llama-3.3-70b' }],
    tokens: [{ value: 'Admin', label: 'Admin' }, { value: 'Ops', label: 'Ops' }],
    ranges: ['realtime', '1h', '8h', '24h', '7d', '30d'],
    granularities: ['1m', '5m', '15m', '1h'],
    generated_at: '2026-03-01T10:30:00Z',
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('UsagePage router analytics status shell', () => {
  it('renders status cards, timeline, and breakdown tables', async () => {
    render(<UsagePage />);

    expect(await screen.findByRole('heading', { name: 'Usage Stats' })).toBeInTheDocument();
    expect(screen.getByText('Providers available: 3 • Online: 2')).toBeInTheDocument();

    expect(screen.getAllByText('Requests').length).toBeGreaterThan(0);
    expect(screen.getByText('4')).toBeInTheDocument();
    expect(screen.getByText('Prompt / Generated')).toBeInTheDocument();
    expect(screen.getByText('52 / 32')).toBeInTheDocument();

    expect(screen.getByText('Usage by model (tokens / bucket)')).toBeInTheDocument();
    expect(screen.getAllByText('llama-3.3-70b').length).toBeGreaterThan(0);

    expect(screen.getByRole('heading', { name: 'Providers' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Models' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Token Names' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Remote IPs' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'User Agents' })).toBeInTheDocument();
  });

  it('re-fetches with new range selection', async () => {
    const user = userEvent.setup();
    render(<UsagePage />);

    await screen.findByRole('heading', { name: 'Usage Stats' });
    const rangeSelect = screen.getByLabelText('Time Range');
    await user.selectOptions(rangeSelect, '24h');

    await waitFor(() => {
      expect(routerClientMock.getRouterAnalyticsStatus).toHaveBeenLastCalledWith(
        expect.objectContaining({ range: '24h' })
      );
    });
  });

  it('shows coming soon for non-status tabs', async () => {
    const user = userEvent.setup();
    render(<UsagePage />);

    await screen.findByRole('heading', { name: 'Usage Stats' });
    await user.click(screen.getByRole('tab', { name: /Quota/i }));

    expect(screen.getByText('Quota tab is coming soon.')).toBeInTheDocument();
  });
});
