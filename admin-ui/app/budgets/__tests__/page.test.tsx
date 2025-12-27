/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import BudgetsPage from '../page';
import { api } from '@/lib/api-client';

vi.mock('@/components/ProtectedRoute', () => ({
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
    pageSize: 25,
    setPage: vi.fn(),
    setPageSize: vi.fn(),
    resetPagination: vi.fn(),
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
    limit: 25,
  });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('BudgetsPage', () => {
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
});
