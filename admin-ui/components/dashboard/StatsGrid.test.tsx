/* @vitest-environment jsdom */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { StatsGrid } from './StatsGrid';
import { DEFAULT_DASHBOARD_OPERATIONAL_KPIS, type DashboardOperationalKpis } from '@/lib/dashboard-kpis';
import type { DashboardUIStats } from '@/lib/dashboard';

const baseStats: DashboardUIStats = {
  users: 12,
  activeUsers: 9,
  organizations: 4,
  teams: 7,
  apiKeys: 10,
  activeApiKeys: 8,
  providers: 5,
  enabledProviders: 4,
  storageUsedMb: 2048,
  storageQuotaMb: 8192,
};

const baseOperationalKpis: DashboardOperationalKpis = {
  latencyP95Ms: 320,
  latencyTrend: { direction: 'down', delta: -25, percentChange: -7.2 },
  errorRatePct: 1.52,
  errorRateTrend: { direction: 'down', delta: -0.48, percentChange: -24 },
  dailyCostUsd: 18.23,
  dailyCostTrend: { direction: 'up', delta: 2.1, percentChange: 13.01 },
  activeJobs: 5,
  activeJobsTrend: { direction: 'up', delta: 1, percentChange: 25 },
  queuedJobs: 13,
  failedJobs: 3,
  queueDepth: 16,
  queueDepthTrend: { direction: 'down', delta: -4, percentChange: -20 },
};

afterEach(() => {
  cleanup();
});

describe('StatsGrid', () => {
  it('announces stat updates in a polite live region', () => {
    render(
      <StatsGrid
        loading={false}
        stats={baseStats}
        storagePercentage={25}
        operationalKpis={baseOperationalKpis}
      />
    );

    const liveRegion = screen.getByTestId('dashboard-stats-live-region');
    expect(liveRegion.getAttribute('role')).toBe('status');
    expect(liveRegion.getAttribute('aria-live')).toBe('polite');
    expect(screen.getByText(/Dashboard metrics updated\./)).toBeInTheDocument();
  });

  it('renders 8 dashboard cards including the Stage 1 operational KPI cards', () => {
    const { container } = render(
      <StatsGrid
        loading={false}
        stats={baseStats}
        storagePercentage={25}
        operationalKpis={baseOperationalKpis}
      />
    );

    expect(container.querySelectorAll('div.rounded-lg.border.bg-card').length).toBe(8);
    expect(screen.getByText('Request Latency (p95)')).toBeInTheDocument();
    expect(screen.getByText('Error Rate')).toBeInTheDocument();
    expect(screen.getByText('Daily LLM Cost')).toBeInTheDocument();
    expect(screen.getByText('Jobs & Queue')).toBeInTheDocument();
    expect(screen.getByText('5 / 13 / 3')).toBeInTheDocument();
    expect(screen.getByText('active / queued / failed')).toBeInTheDocument();
  });

  it('renders N/A fallback values when operational metrics are missing', () => {
    render(
      <StatsGrid
        loading={false}
        stats={baseStats}
        storagePercentage={25}
        operationalKpis={DEFAULT_DASHBOARD_OPERATIONAL_KPIS}
      />
    );

    expect(screen.getAllByText('N/A').length).toBeGreaterThanOrEqual(4);
    expect(screen.getByText('Requires /metrics histogram')).toBeInTheDocument();
    expect(screen.getByText('No prior queue snapshot')).toBeInTheDocument();
  });

  it.each([375, 768, 1280])('matches snapshot at viewport width %i', (width) => {
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      writable: true,
      value: width,
    });
    window.dispatchEvent(new Event('resize'));

    const { asFragment } = render(
      <div style={{ width: `${width}px` }}>
        <StatsGrid
          loading={false}
          stats={baseStats}
          storagePercentage={25}
          operationalKpis={baseOperationalKpis}
        />
      </div>
    );

    expect(asFragment()).toMatchSnapshot();
  });
});
