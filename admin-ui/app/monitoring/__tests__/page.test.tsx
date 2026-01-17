/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MonitoringPage, { normalizeHealthStatus } from '../page';
import { api } from '@/lib/api-client';

const confirmMock = vi.hoisted(() => vi.fn());

vi.mock('@/components/PermissionGuard', () => ({
  PermissionGuard: ({ children }: { children: ReactNode }) => <>{children}</>,
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/ResponsiveLayout', () => ({
  ResponsiveLayout: ({ children }: { children: ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}));

vi.mock('@/components/ui/confirm-dialog', () => ({
  useConfirm: () => confirmMock,
}));

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => (
    <div data-testid="chart">{children}</div>
  ),
  AreaChart: ({ data, children }: { data: unknown; children: ReactNode }) => (
    <div data-testid="area-chart" data-points={JSON.stringify(data)}>
      {children}
    </div>
  ),
  Area: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
}));

vi.mock('@/lib/api-client', () => ({
  api: {
    getMetrics: vi.fn(),
    getWatchlists: vi.fn(),
    getAlerts: vi.fn(),
    getHealth: vi.fn(),
    getHealthMetrics: vi.fn(),
    getLlmHealth: vi.fn(),
    getRagHealth: vi.fn(),
    createWatchlist: vi.fn(),
    deleteWatchlist: vi.fn(),
    acknowledgeAlert: vi.fn(),
    dismissAlert: vi.fn(),
  },
}));

type ApiMock = {
  getMetrics: ReturnType<typeof vi.fn>;
  getWatchlists: ReturnType<typeof vi.fn>;
  getAlerts: ReturnType<typeof vi.fn>;
  getHealth: ReturnType<typeof vi.fn>;
  getHealthMetrics: ReturnType<typeof vi.fn>;
  getLlmHealth: ReturnType<typeof vi.fn>;
  getRagHealth: ReturnType<typeof vi.fn>;
  createWatchlist: ReturnType<typeof vi.fn>;
  deleteWatchlist: ReturnType<typeof vi.fn>;
  acknowledgeAlert: ReturnType<typeof vi.fn>;
  dismissAlert: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

const setDefaultApiMocks = () => {
  apiMock.getMetrics.mockResolvedValue({ cpu_usage: 45, memory_usage: 67 });
  apiMock.getWatchlists.mockResolvedValue([]);
  apiMock.getAlerts.mockResolvedValue([]);
  apiMock.getHealth.mockResolvedValue({
    status: 'ok',
    checks: { database: { status: 'ok' } },
  });
  apiMock.getLlmHealth.mockResolvedValue({ status: 'ok' });
  apiMock.getRagHealth.mockResolvedValue({ status: 'ok' });
  apiMock.getHealthMetrics.mockResolvedValue({
    cpu: { percent: 10 },
    memory: { percent: 20 },
  });
  apiMock.createWatchlist.mockResolvedValue({});
  apiMock.acknowledgeAlert.mockResolvedValue({});
  apiMock.dismissAlert.mockResolvedValue({});
};

const expectLoadDataCalls = () => {
  expect(apiMock.getMetrics).toHaveBeenCalled();
  expect(apiMock.getWatchlists).toHaveBeenCalled();
  expect(apiMock.getAlerts).toHaveBeenCalled();
  expect(apiMock.getHealth).toHaveBeenCalled();
  expect(apiMock.getLlmHealth).toHaveBeenCalled();
  expect(apiMock.getRagHealth).toHaveBeenCalled();
};

const createDeferred = <T,>() => {
  let resolve: (value: T) => void = () => {};
  let reject: (reason?: unknown) => void = () => {};
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

const flushPromises = async () => {
  await Promise.resolve();
  await Promise.resolve();
};

beforeEach(() => {
  confirmMock.mockResolvedValue(true);
  setDefaultApiMocks();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.resetAllMocks();
});

describe('normalizeHealthStatus', () => {
  it('maps known statuses to normalized values', () => {
    expect(normalizeHealthStatus('OK')).toBe('healthy');
    expect(normalizeHealthStatus('healthy')).toBe('healthy');
    expect(normalizeHealthStatus('READY')).toBe('healthy');
    expect(normalizeHealthStatus('alive')).toBe('healthy');
    expect(normalizeHealthStatus('degraded')).toBe('warning');
    expect(normalizeHealthStatus('warning')).toBe('warning');
    expect(normalizeHealthStatus('critical')).toBe('critical');
    expect(normalizeHealthStatus('error')).toBe('critical');
    expect(normalizeHealthStatus('not_ready')).toBe('critical');
  });

  it('returns unknown for empty or unexpected values', () => {
    expect(normalizeHealthStatus()).toBe('unknown');
    expect(normalizeHealthStatus('mystery')).toBe('unknown');
  });
});

describe('MonitoringPage', () => {
  it('renders loading state while data is fetching', async () => {
    const metricsDeferred = createDeferred<Record<string, unknown>>();
    const watchlistsDeferred = createDeferred<unknown[]>();
    const alertsDeferred = createDeferred<unknown[]>();
    const healthDeferred = createDeferred<Record<string, unknown>>();
    const llmDeferred = createDeferred<Record<string, unknown>>();
    const ragDeferred = createDeferred<Record<string, unknown>>();

    apiMock.getMetrics.mockReturnValue(metricsDeferred.promise);
    apiMock.getWatchlists.mockReturnValue(watchlistsDeferred.promise);
    apiMock.getAlerts.mockReturnValue(alertsDeferred.promise);
    apiMock.getHealth.mockReturnValue(healthDeferred.promise);
    apiMock.getLlmHealth.mockReturnValue(llmDeferred.promise);
    apiMock.getRagHealth.mockReturnValue(ragDeferred.promise);

    render(<MonitoringPage />);

    expect(screen.getByText('Loading metrics...')).toBeTruthy();
    expect(screen.getAllByText('Loading...').length).toBeGreaterThan(0);

    metricsDeferred.resolve({});
    watchlistsDeferred.resolve([]);
    alertsDeferred.resolve([]);
    healthDeferred.resolve({ status: 'ok', checks: { database: { status: 'ok' } } });
    llmDeferred.resolve({ status: 'ok' });
    ragDeferred.resolve({ status: 'ok' });

    await flushPromises();
  });

  it('renders empty state when no data is returned', async () => {
    apiMock.getMetrics.mockResolvedValue({});
    apiMock.getWatchlists.mockResolvedValue([]);
    apiMock.getAlerts.mockResolvedValue([]);

    render(<MonitoringPage />);

    expect(await screen.findByText('No metrics available. The server may not expose metrics.')).toBeTruthy();
    expect(screen.getByText('No watchlists configured')).toBeTruthy();
    expect(screen.getByText('No alerts - system is healthy')).toBeTruthy();

    expectLoadDataCalls();
  });

  it('renders success state with metrics and watchlists', async () => {
    apiMock.getMetrics.mockResolvedValue({ cpu_usage: 55, active_users: 12 });
    apiMock.getWatchlists.mockResolvedValue([
      {
        id: 'watch-1',
        name: 'API Response Time',
        description: 'Latency watch',
        target: '/api/v1/chat',
        type: 'resource',
        threshold: 80,
        status: 'healthy',
        last_checked: '2024-05-01T12:00:00Z',
        created_at: '2024-05-01T12:00:00Z',
      },
    ]);
    apiMock.getAlerts.mockResolvedValue([
      {
        id: 'alert-1',
        severity: 'warning',
        message: 'High CPU usage',
        source: 'system',
        timestamp: '2024-05-01T12:00:00Z',
        acknowledged: true,
        acknowledged_at: '2024-05-01T12:05:00Z',
        acknowledged_by: 'admin',
      },
    ]);

    render(<MonitoringPage />);

    expect(await screen.findByText('Cpu Usage')).toBeTruthy();
    expect(screen.getByText('API Response Time')).toBeTruthy();
    expect(screen.getByText('High CPU usage')).toBeTruthy();

    expectLoadDataCalls();
  });

  it('renders error state when initial load fails', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    apiMock.getMetrics.mockImplementation(() => {
      throw new Error('Load failed');
    });

    render(<MonitoringPage />);

    expect(await screen.findByText('Load failed')).toBeTruthy();
    consoleError.mockRestore();
  });

  it('appends metrics history on interval polling', async () => {
    vi.useFakeTimers();
    apiMock.getHealthMetrics
      .mockResolvedValueOnce({ cpu: { percent: 5 }, memory: { percent: 10 } })
      .mockResolvedValueOnce({ cpu: { percent: 15 }, memory: { percent: 20 } })
      .mockResolvedValueOnce({ cpu: { percent: 25 }, memory: { percent: 30 } });

    render(<MonitoringPage />);

    await flushPromises();
    await flushPromises();

    const chart = screen.getByTestId('area-chart');
    const initialPoints = JSON.parse(chart.getAttribute('data-points') || '[]');
    expect(initialPoints).toHaveLength(2);
    expect(apiMock.getHealthMetrics).toHaveBeenCalledTimes(2);

    await vi.advanceTimersByTimeAsync(5 * 60 * 1000);
    await flushPromises();

    const updatedPoints = JSON.parse(chart.getAttribute('data-points') || '[]');
    expect(updatedPoints).toHaveLength(3);
    expect(apiMock.getHealthMetrics).toHaveBeenCalledTimes(3);

    expectLoadDataCalls();
  });

  it('creates a watchlist and reloads data', async () => {
    const user = userEvent.setup();
    apiMock.getWatchlists
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        {
          id: 'watch-2',
          name: 'CPU Usage',
          description: 'CPU threshold',
          target: 'cpu_usage',
          type: 'metric',
          threshold: 85,
          status: 'warning',
          last_checked: '2024-05-01T12:10:00Z',
          created_at: '2024-05-01T12:00:00Z',
        },
      ]);

    render(<MonitoringPage />);

    expect(await screen.findByText('No watchlists configured')).toBeTruthy();
    expectLoadDataCalls();

    await user.click(screen.getByRole('button', { name: 'Add' }));
    await user.type(screen.getByLabelText('Name'), 'CPU Usage');
    await user.type(screen.getByLabelText('Description'), 'CPU threshold');
    await user.type(screen.getByLabelText('Target'), 'cpu_usage');
    await user.click(screen.getByRole('button', { name: 'Create Watchlist' }));

    await waitFor(() => {
      expect(apiMock.createWatchlist).toHaveBeenCalledWith({
        name: 'CPU Usage',
        description: 'CPU threshold',
        target: 'cpu_usage',
        type: 'resource',
        threshold: 80,
      });
    });

    await waitFor(() => {
      expect(apiMock.getWatchlists).toHaveBeenCalledTimes(2);
      expect(apiMock.getMetrics).toHaveBeenCalledTimes(2);
    });

    expect(screen.getByText('CPU Usage')).toBeTruthy();
    expect(screen.queryByText('Configure a new resource or metric to monitor')).toBeNull();
  });

  it('acknowledges alerts and reloads data', async () => {
    const user = userEvent.setup();
    apiMock.getAlerts
      .mockResolvedValueOnce([
        {
          id: 'alert-2',
          severity: 'warning',
          message: 'High memory usage',
          source: 'system',
          timestamp: '2024-05-01T12:00:00Z',
          acknowledged: false,
        },
      ])
      .mockResolvedValueOnce([
        {
          id: 'alert-2',
          severity: 'warning',
          message: 'High memory usage',
          source: 'system',
          timestamp: '2024-05-01T12:00:00Z',
          acknowledged: true,
          acknowledged_at: '2024-05-01T12:05:00Z',
          acknowledged_by: 'admin',
        },
      ]);

    render(<MonitoringPage />);

    expect(await screen.findByText('High memory usage')).toBeTruthy();
    expectLoadDataCalls();

    await user.click(screen.getByTitle('Acknowledge'));

    await waitFor(() => {
      expect(apiMock.acknowledgeAlert).toHaveBeenCalledWith('alert-2');
      expect(apiMock.getAlerts).toHaveBeenCalledTimes(2);
    });

    expect(screen.getByText('Acknowledged')).toBeTruthy();
  });

  it('dismisses alerts after confirmation', async () => {
    const user = userEvent.setup();
    apiMock.getAlerts
      .mockResolvedValueOnce([
        {
          id: 'alert-3',
          severity: 'critical',
          message: 'Service unavailable',
          source: 'rag',
          timestamp: '2024-05-01T12:00:00Z',
          acknowledged: false,
        },
      ])
      .mockResolvedValueOnce([]);

    render(<MonitoringPage />);

    expect(await screen.findByText('Service unavailable')).toBeTruthy();
    expectLoadDataCalls();

    await user.click(screen.getByTitle('Dismiss'));

    await waitFor(() => {
      expect(apiMock.dismissAlert).toHaveBeenCalledWith('alert-3');
      expect(apiMock.getAlerts).toHaveBeenCalledTimes(2);
    });

    expect(screen.getByText('No alerts - system is healthy')).toBeTruthy();
  });

  it('shows error alert when watchlist creation fails', async () => {
    const user = userEvent.setup();
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    apiMock.createWatchlist.mockRejectedValue(new Error('Create failed'));

    render(<MonitoringPage />);

    await user.click(screen.getByRole('button', { name: 'Add' }));
    await user.type(screen.getByLabelText('Name'), 'Disk Usage');
    await user.type(screen.getByLabelText('Target'), 'disk_usage');
    await user.click(screen.getByRole('button', { name: 'Create Watchlist' }));

    expect(await screen.findByText('Create failed')).toBeTruthy();
    consoleError.mockRestore();
  });
});
