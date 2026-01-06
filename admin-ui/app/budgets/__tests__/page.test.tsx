/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import BudgetsPage from '../page';
import { api } from '@/lib/api-client';

const setPageMock = vi.hoisted(() => vi.fn());
const setPageSizeMock = vi.hoisted(() => vi.fn());
const resetPaginationMock = vi.hoisted(() => vi.fn());

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

vi.mock('@/lib/use-url-state', () => ({
  useUrlPagination: () => ({
    page: 1,
    pageSize: 20,
    setPage: setPageMock,
    setPageSize: setPageSizeMock,
    resetPagination: resetPaginationMock,
  }),
}));

vi.mock('@/lib/api-client', () => ({
  api: {
    getBudgets: vi.fn(),
  },
}));

type ApiMock = {
  getBudgets: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

beforeEach(() => {
  apiMock.getBudgets.mockResolvedValue({
    items: [
      {
        org_id: 11,
        org_name: 'Acme Co',
        org_slug: 'acme',
        plan_name: 'pro',
        plan_display_name: 'Pro Plan',
        budgets: {
          budget_day_usd: 100,
          budget_month_usd: 200,
          budget_day_tokens: 300,
          budget_month_tokens: 400,
          alert_thresholds: { global: [80, 95] },
          enforcement_mode: { global: 'soft' },
        },
        updated_at: '2024-01-01T00:00:00Z',
      },
    ],
    total: 1,
    page: 1,
    limit: 20,
  });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('BudgetsPage', () => {
  it('shows loading skeleton while fetching', async () => {
    apiMock.getBudgets.mockImplementation(() => new Promise(() => {}));

    render(<BudgetsPage />);

    expect(await screen.findByTestId('table-skeleton')).toBeTruthy();
  });

  it('renders budget rows with plan and caps', async () => {
    render(<BudgetsPage />);

    expect(await screen.findByText('Acme Co')).toBeTruthy();
    expect(screen.getByText('Pro Plan')).toBeTruthy();
    expect(screen.getByText('$100.00')).toBeTruthy();
    expect(screen.getByText('$200.00')).toBeTruthy();
    expect(screen.getByText('300')).toBeTruthy();
    expect(screen.getByText('400')).toBeTruthy();
    expect(screen.getByText('Read-only')).toBeTruthy();
  });

  it('displays empty state when no budgets exist', async () => {
    apiMock.getBudgets.mockResolvedValue({ items: [], total: 0, page: 1, limit: 20 });

    render(<BudgetsPage />);

    expect(await screen.findByText('No budgets found for the selected scope.')).toBeTruthy();
  });

  it('displays error message on API failure', async () => {
    apiMock.getBudgets.mockRejectedValue(new Error('Network error'));

    render(<BudgetsPage />);

    expect(await screen.findByText('Network error')).toBeTruthy();
  });

  it('updates pagination controls', async () => {
    apiMock.getBudgets.mockResolvedValue({
      items: [
        {
          org_id: 11,
          org_name: 'Acme Co',
          org_slug: 'acme',
          plan_name: 'pro',
          plan_display_name: 'Pro Plan',
          budgets: {
            budget_day_usd: 100,
            budget_month_usd: 200,
            budget_day_tokens: 300,
            budget_month_tokens: 400,
            alert_thresholds: { global: [80, 95] },
            enforcement_mode: { global: 'soft' },
          },
          updated_at: '2024-01-01T00:00:00Z',
        },
      ],
      total: 60,
      page: 1,
      limit: 20,
    });

    render(<BudgetsPage />);

    await screen.findByText('Acme Co');
    setPageMock.mockClear();
    setPageSizeMock.mockClear();
    resetPaginationMock.mockClear();

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: '2' }));
    expect(setPageMock).toHaveBeenCalledWith(2);

    await user.selectOptions(screen.getByRole('combobox'), '50');
    expect(setPageSizeMock).toHaveBeenCalledWith(50);
    expect(resetPaginationMock).toHaveBeenCalled();
  });
});
