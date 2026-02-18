/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import UsagePage from '../page';
import { api } from '@/lib/api-client';

const toastSuccessMock = vi.hoisted(() => vi.fn());
const toastErrorMock = vi.hoisted(() => vi.fn());

vi.mock('@/components/PermissionGuard', () => ({
  PermissionGuard: ({ children }: { children: ReactNode }) => <>{children}</>,
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
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

vi.mock('@/lib/api-client', () => ({
  api: {
    getUsageDaily: vi.fn(),
    getUsageTop: vi.fn(),
    getLlmUsageSummary: vi.fn(),
    getLlmTopSpenders: vi.fn(),
    getBudgets: vi.fn(),
    getOrganizations: vi.fn(),
    getUserOrgMemberships: vi.fn(),
    getMetricsText: vi.fn(),
    getUsersPage: vi.fn(),
    getRateLimitEvents: vi.fn(),
  },
}));

type ApiMock = {
  getUsageDaily: ReturnType<typeof vi.fn>;
  getUsageTop: ReturnType<typeof vi.fn>;
  getLlmUsageSummary: ReturnType<typeof vi.fn>;
  getLlmTopSpenders: ReturnType<typeof vi.fn>;
  getBudgets: ReturnType<typeof vi.fn>;
  getOrganizations: ReturnType<typeof vi.fn>;
  getUserOrgMemberships: ReturnType<typeof vi.fn>;
  getMetricsText: ReturnType<typeof vi.fn>;
  getUsersPage: ReturnType<typeof vi.fn>;
  getRateLimitEvents: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

beforeEach(() => {
  toastSuccessMock.mockReset();
  toastErrorMock.mockReset();

  apiMock.getUsageDaily.mockResolvedValue({
    items: [
      {
        user_id: 1,
        day: '2026-02-10',
        requests: 10,
        errors: 0,
        bytes_total: 1024,
      },
    ],
  });
  apiMock.getUsageTop.mockResolvedValue({
    items: [
      {
        user_id: 1,
        requests: 10,
        errors: 0,
        bytes_total: 2048,
      },
    ],
  });
  apiMock.getLlmUsageSummary.mockImplementation(async (params?: Record<string, string>) => {
    if (params?.group_by === 'day') {
      return {
        items: [
          { group_value: '2026-02-10', requests: 5, errors: 0, input_tokens: 100, output_tokens: 150, total_tokens: 250, total_cost_usd: 10, latency_avg_ms: 100 },
          { group_value: '2026-02-11', requests: 6, errors: 0, input_tokens: 120, output_tokens: 170, total_tokens: 290, total_cost_usd: 12, latency_avg_ms: 100 },
          { group_value: '2026-02-12', requests: 7, errors: 0, input_tokens: 140, output_tokens: 190, total_tokens: 330, total_cost_usd: 14, latency_avg_ms: 100 },
          { group_value: '2026-02-13', requests: 8, errors: 0, input_tokens: 160, output_tokens: 210, total_tokens: 370, total_cost_usd: 16, latency_avg_ms: 100 },
          { group_value: '2026-02-14', requests: 9, errors: 0, input_tokens: 180, output_tokens: 230, total_tokens: 410, total_cost_usd: 18, latency_avg_ms: 100 },
        ],
      };
    }

    if (params?.group_by === 'user') {
      return {
        items: [
          { group_value: '1', requests: 10, errors: 1, input_tokens: 1000, output_tokens: 800, total_tokens: 1800, total_cost_usd: 70, latency_avg_ms: 120 },
          { group_value: '2', requests: 5, errors: 0, input_tokens: 400, output_tokens: 300, total_tokens: 700, total_cost_usd: 30, latency_avg_ms: 90 },
        ],
      };
    }

    return {
      items: [
        { group_value: 'openai', requests: 15, errors: 1, input_tokens: 1400, output_tokens: 1100, total_tokens: 2500, total_cost_usd: 100, latency_avg_ms: 110 },
      ],
    };
  });
  apiMock.getLlmTopSpenders.mockResolvedValue({
    items: [{ user_id: 1, total_cost_usd: 70, requests: 10 }],
  });
  apiMock.getBudgets.mockResolvedValue({
    items: [
      {
        org_id: 1,
        budgets: {
          budget_month_usd: 100,
        },
      },
    ],
  });
  apiMock.getOrganizations.mockResolvedValue({
    items: [
      { id: 1, name: 'Org Alpha' },
      { id: 2, name: 'Org Beta' },
    ],
  });
  apiMock.getUserOrgMemberships.mockImplementation(async (userId: string) => {
    if (userId === '1') return [{ org_id: 1, role: 'member' }];
    return [{ org_id: 2, role: 'member' }];
  });
  apiMock.getMetricsText.mockResolvedValue([
    'http_requests_total{method="GET",endpoint="/health",status="200"} 40',
    'http_requests_total{method="GET",endpoint="/health",status="500"} 10',
    'http_requests_total{method="POST",endpoint="/api/v1/chat/completions",status="200"} 60',
    'http_requests_total{method="POST",endpoint="/api/v1/chat/completions",status="429"} 10',
    'http_request_duration_seconds_sum{method="GET",endpoint="/health"} 5',
    'http_request_duration_seconds_count{method="GET",endpoint="/health"} 50',
    'http_request_duration_seconds_bucket{method="GET",endpoint="/health",le="0.1"} 20',
    'http_request_duration_seconds_bucket{method="GET",endpoint="/health",le="0.2"} 40',
    'http_request_duration_seconds_bucket{method="GET",endpoint="/health",le="0.5"} 49',
    'http_request_duration_seconds_bucket{method="GET",endpoint="/health",le="+Inf"} 50',
    'http_request_duration_seconds_sum{method="POST",endpoint="/api/v1/chat/completions"} 35',
    'http_request_duration_seconds_count{method="POST",endpoint="/api/v1/chat/completions"} 70',
    'http_request_duration_seconds_bucket{method="POST",endpoint="/api/v1/chat/completions",le="0.1"} 10',
    'http_request_duration_seconds_bucket{method="POST",endpoint="/api/v1/chat/completions",le="0.5"} 50',
    'http_request_duration_seconds_bucket{method="POST",endpoint="/api/v1/chat/completions",le="1.0"} 66',
    'http_request_duration_seconds_bucket{method="POST",endpoint="/api/v1/chat/completions",le="+Inf"} 70',
    'upload_bytes_total{user_id="1",media_type="video"} 2048',
    'upload_bytes_total{user_id="2",media_type="audio"} 1024',
    'upload_bytes_total{user_id="3",media_type="document"} 512',
  ].join('\n'));
  apiMock.getUsersPage.mockResolvedValue({
    items: [
      { id: 1, username: 'alice', email: 'alice@example.com', storage_used_mb: 512, storage_quota_mb: 1024 },
      { id: 2, username: 'bob', email: 'bob@example.com', storage_used_mb: 256, storage_quota_mb: 1024 },
      { id: 3, username: 'carol', email: 'carol@example.com', storage_used_mb: 128, storage_quota_mb: 1024 },
    ],
    page: 1,
    pages: 1,
    limit: 200,
    total: 3,
  });
  apiMock.getRateLimitEvents.mockResolvedValue({
    items: [
      {
        entity: 'user:1',
        policy: 'chat.default',
        rejections_24h: 5,
        rejections_7d: 9,
        last_rejection_at: '2026-02-14T12:00:00Z',
      },
      {
        entity: 'role:admin',
        policy: 'admin.default',
        rejections_24h: 2,
        rejections_7d: 4,
        last_rejection_at: '2026-02-13T12:00:00Z',
      },
    ],
  });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('UsagePage', () => {
  it('renders forecast bands and projected budget exceedance warning', async () => {
    const user = userEvent.setup();
    render(<UsagePage />);

    await user.click(await screen.findByRole('tab', { name: 'LLM Usage' }));
    expect(await screen.findByText('Cost forecast')).toBeInTheDocument();
    expect(await screen.findByText('7 days')).toBeInTheDocument();
    expect(await screen.findByText('30 days')).toBeInTheDocument();
    expect(await screen.findByText('90 days')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/monthly budget will be exceeded by/i)).toBeInTheDocument();
    });
  });

  it('renders per-organization attribution sorted by cost with org links', async () => {
    const user = userEvent.setup();
    render(<UsagePage />);

    await user.click(await screen.findByRole('tab', { name: 'LLM Usage' }));
    expect(await screen.findByText('Per-organization cost attribution')).toBeInTheDocument();
    const orgLinks = await screen.findAllByRole('link', { name: /Org /i });

    expect(orgLinks[0]?.textContent).toBe('Org Alpha');
    expect(orgLinks[1]?.textContent).toBe('Org Beta');
    expect(orgLinks[0]?.getAttribute('href')).toBe('/organizations/1');
    expect(orgLinks[1]?.getAttribute('href')).toBe('/organizations/2');
    expect(screen.getByText('70.00%')).toBeInTheDocument();
    expect(screen.getByText('30.00%')).toBeInTheDocument();
  });

  it('renders endpoint usage table with sorting and method filter', async () => {
    const user = userEvent.setup();
    render(<UsagePage />);

    await user.click(await screen.findByRole('tab', { name: 'Endpoints' }));
    expect(await screen.findByText('Endpoint usage')).toBeInTheDocument();
    expect(await screen.findByText('/api/v1/chat/completions')).toBeInTheDocument();

    const methodSortButton = screen.getByRole('button', { name: /Method/ });
    const endpointTable = methodSortButton.closest('table');
    expect(endpointTable).not.toBeNull();

    const beforeRows = within(endpointTable as HTMLElement).getAllByRole('row');
    expect(within(beforeRows[1] as HTMLElement).getByText('POST')).toBeInTheDocument();

    await user.click(methodSortButton);
    await user.click(methodSortButton);
    const afterRows = within(endpointTable as HTMLElement).getAllByRole('row');
    expect(within(afterRows[1] as HTMLElement).getByText('GET')).toBeInTheDocument();

    const methodFilter = screen.getByLabelText('Method filter');
    await user.selectOptions(methodFilter, 'GET');
    expect(await screen.findByText('/health')).toBeInTheDocument();
    expect(screen.queryByText('/api/v1/chat/completions')).not.toBeInTheDocument();
  });

  it('renders storage breakdown and rate limit monitoring sections', async () => {
    const user = userEvent.setup();
    render(<UsagePage />);

    await user.click(await screen.findByRole('tab', { name: 'Endpoints' }));

    expect(await screen.findByText('Storage breakdown')).toBeInTheDocument();
    expect(await screen.findByText('Top storage consumers')).toBeInTheDocument();
    expect(await screen.findByText('alice')).toBeInTheDocument();
    expect(await screen.findByText('Media type upload volume')).toBeInTheDocument();
    expect(await screen.findByText('video')).toBeInTheDocument();

    expect(await screen.findByText('Rate limit monitoring')).toBeInTheDocument();
    const rateLimitRow = (await screen.findByText('User 1')).closest('tr');
    expect(rateLimitRow).not.toBeNull();
    expect(within(rateLimitRow as HTMLElement).getByText('chat.default')).toBeInTheDocument();
    expect(within(rateLimitRow as HTMLElement).getByText(/^5$/)).toBeInTheDocument();
    expect(within(rateLimitRow as HTMLElement).getByText(/^9$/)).toBeInTheDocument();
    expect(within(rateLimitRow as HTMLElement).getByText('Top throttled')).toBeInTheDocument();
  });
});
