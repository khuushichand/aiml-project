/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { Metric, SystemStatusItem, Watchlist } from './types';
import { useMonitoringDashboardState } from './use-monitoring-dashboard-state';

const sampleMetric: Metric = {
  name: 'cpu',
  value: 82,
  unit: '%',
  trend: 'up',
  status: 'warning',
};

const sampleWatchlist: Watchlist = {
  id: 'wl-1',
  name: 'Core APIs',
  services: ['chat'],
  status: 'warning',
  uptime: 99.1,
  latency: 120,
  incidents: 1,
  sla: 99.5,
  description: 'Critical path API monitoring',
};

const initialSystemStatus: SystemStatusItem[] = [
  {
    key: 'api',
    label: 'API',
    status: 'unknown',
    detail: 'Checking...',
  },
];

function Harness() {
  const {
    metrics,
    setMetrics,
    watchlists,
    setWatchlists,
    systemStatus,
    setSystemStatus,
    loading,
    setLoading,
    lastUpdated,
    markMonitoringDataUpdated,
  } = useMonitoringDashboardState({ initialSystemStatus });

  return (
    <div>
      <div data-testid="metrics-count">{metrics.length}</div>
      <div data-testid="watchlists-count">{watchlists.length}</div>
      <div data-testid="system-status">{systemStatus[0]?.status ?? 'none'}</div>
      <div data-testid="loading">{String(loading)}</div>
      <div data-testid="last-updated">{String(lastUpdated !== null)}</div>

      <button onClick={() => setMetrics([sampleMetric])}>Set Metrics</button>
      <button onClick={() => setWatchlists([sampleWatchlist])}>Set Watchlists</button>
      <button
        onClick={() =>
          setSystemStatus([
            {
              ...initialSystemStatus[0],
              status: 'healthy',
              detail: 'Operational',
            },
          ])
        }
      >
        Set System Healthy
      </button>
      <button onClick={() => setLoading(false)}>Set Loaded</button>
      <button onClick={() => markMonitoringDataUpdated()}>Mark Updated</button>
    </div>
  );
}

describe('useMonitoringDashboardState', () => {
  afterEach(() => {
    cleanup();
  });

  it('initializes with provided system status and default loading state', () => {
    render(<Harness />);

    expect(screen.getByTestId('metrics-count').textContent).toBe('0');
    expect(screen.getByTestId('watchlists-count').textContent).toBe('0');
    expect(screen.getByTestId('system-status').textContent).toBe('unknown');
    expect(screen.getByTestId('loading').textContent).toBe('true');
    expect(screen.getByTestId('last-updated').textContent).toBe('false');
  });

  it('updates dashboard state and marks data refresh timestamps', () => {
    render(<Harness />);

    fireEvent.click(screen.getByRole('button', { name: 'Set Metrics' }));
    fireEvent.click(screen.getByRole('button', { name: 'Set Watchlists' }));
    fireEvent.click(screen.getByRole('button', { name: 'Set System Healthy' }));
    fireEvent.click(screen.getByRole('button', { name: 'Set Loaded' }));
    fireEvent.click(screen.getByRole('button', { name: 'Mark Updated' }));

    expect(screen.getByTestId('metrics-count').textContent).toBe('1');
    expect(screen.getByTestId('watchlists-count').textContent).toBe('1');
    expect(screen.getByTestId('system-status').textContent).toBe('healthy');
    expect(screen.getByTestId('loading').textContent).toBe('false');
    expect(screen.getByTestId('last-updated').textContent).toBe('true');
  });
});
