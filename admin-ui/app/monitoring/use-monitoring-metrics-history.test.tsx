/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  useMonitoringMetricsHistory,
  type MonitoringMetricsApiClient,
} from './use-monitoring-metrics-history';

type HarnessProps = {
  apiClient: MonitoringMetricsApiClient;
  pollIntervalMs?: number;
  onManualRangeLoadSuccess?: () => void;
};

function Harness({
  apiClient,
  pollIntervalMs = 1000,
  onManualRangeLoadSuccess,
}: HarnessProps) {
  const {
    metricsHistory,
    timeRange,
    customRangeStart,
    customRangeEnd,
    rangeValidationError,
    setCustomRangeStart,
    setCustomRangeEnd,
    handleSelectTimeRange,
    handleApplyCustomTimeRange,
  } = useMonitoringMetricsHistory({
    apiClient,
    pollIntervalMs,
    onManualRangeLoadSuccess,
  });

  return (
    <div>
      <div data-testid="history-count">{metricsHistory.length}</div>
      <div data-testid="time-range">{timeRange}</div>
      <div data-testid="range-error">{rangeValidationError}</div>
      <input
        data-testid="custom-start"
        value={customRangeStart}
        onChange={(event) => setCustomRangeStart(event.target.value)}
      />
      <input
        data-testid="custom-end"
        value={customRangeEnd}
        onChange={(event) => setCustomRangeEnd(event.target.value)}
      />
      <button onClick={() => { void handleSelectTimeRange('1h'); }}>
        Select 1h
      </button>
      <button onClick={() => { void handleSelectTimeRange('custom'); }}>
        Select Custom
      </button>
      <button onClick={() => { void handleApplyCustomTimeRange(); }}>
        Apply Custom
      </button>
    </div>
  );
}

type MonitoringMetricsApiClientMock = MonitoringMetricsApiClient & {
  getMonitoringMetrics: ReturnType<typeof vi.fn>;
  getHealthMetrics: ReturnType<typeof vi.fn>;
  getMetrics: ReturnType<typeof vi.fn>;
};

const buildApiClient = (): MonitoringMetricsApiClientMock => ({
  getMonitoringMetrics: vi.fn().mockResolvedValue([
    {
      timestamp: '2026-02-27T12:00:00.000Z',
      cpu: 12,
      memory: 24,
      disk_usage: 36,
      throughput: 4,
      active_connections: 3,
      queue_depth: 2,
    },
  ]),
  getHealthMetrics: vi.fn().mockResolvedValue({
    cpu: { percent: 20 },
    memory: { percent: 30 },
  }),
  getMetrics: vi.fn().mockResolvedValue({
    disk_usage: 40,
    throughput: 5,
    active_connections: 4,
    queue_depth: 3,
  }),
});

const flushPromises = async () => {
  await Promise.resolve();
  await Promise.resolve();
};

describe('useMonitoringMetricsHistory', () => {
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.resetAllMocks();
  });

  it('loads on mount and refreshes on the polling interval', async () => {
    vi.useFakeTimers();
    const apiClient = buildApiClient();
    render(<Harness apiClient={apiClient} pollIntervalMs={1000} />);

    await flushPromises();
    expect(apiClient.getMonitoringMetrics).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(1000);
    await flushPromises();
    expect(apiClient.getMonitoringMetrics).toHaveBeenCalledTimes(2);
  });

  it('selects preset ranges, loads immediately, and notifies on success', async () => {
    const apiClient = buildApiClient();
    const onManualRangeLoadSuccess = vi.fn();
    render(
      <Harness
        apiClient={apiClient}
        onManualRangeLoadSuccess={onManualRangeLoadSuccess}
        pollIntervalMs={60_000}
      />
    );

    await waitFor(() => {
      expect(apiClient.getMonitoringMetrics).toHaveBeenCalledTimes(1);
    });
    const baselineCalls = apiClient.getMonitoringMetrics.mock.calls.length;

    fireEvent.click(screen.getByRole('button', { name: 'Select 1h' }));

    await waitFor(() => {
      expect(apiClient.getMonitoringMetrics.mock.calls.length).toBe(baselineCalls + 1);
    });
    expect(onManualRangeLoadSuccess).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('time-range').textContent).toBe('1h');
  });

  it('validates invalid custom ranges without loading metrics', async () => {
    const apiClient = buildApiClient();
    const onManualRangeLoadSuccess = vi.fn();
    render(
      <Harness
        apiClient={apiClient}
        onManualRangeLoadSuccess={onManualRangeLoadSuccess}
        pollIntervalMs={60_000}
      />
    );

    await waitFor(() => {
      expect(apiClient.getMonitoringMetrics).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByTestId('custom-start'), {
      target: { value: '2026-02-28T12:00' },
    });
    fireEvent.change(screen.getByTestId('custom-end'), {
      target: { value: '2026-02-28T11:00' },
    });
    const callsBeforeApply = apiClient.getMonitoringMetrics.mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: 'Apply Custom' }));

    await waitFor(() => {
      expect(screen.getByTestId('range-error').textContent).toContain('Custom range start must be before end.');
    });
    expect(apiClient.getMonitoringMetrics).toHaveBeenCalledTimes(callsBeforeApply);
    expect(onManualRangeLoadSuccess).not.toHaveBeenCalled();
  });

  it('does not reload metrics while typing custom range drafts before apply', async () => {
    const apiClient = buildApiClient();
    render(<Harness apiClient={apiClient} pollIntervalMs={60_000} />);

    await waitFor(() => {
      expect(apiClient.getMonitoringMetrics).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByRole('button', { name: 'Select Custom' }));
    await waitFor(() => {
      expect(screen.getByTestId('time-range').textContent).toBe('custom');
    });
    expect(apiClient.getMonitoringMetrics).toHaveBeenCalledTimes(1);

    fireEvent.change(screen.getByTestId('custom-start'), {
      target: { value: '2026-02-27T10:00' },
    });
    fireEvent.change(screen.getByTestId('custom-end'), {
      target: { value: '2026-02-27T12:00' },
    });
    expect(apiClient.getMonitoringMetrics).toHaveBeenCalledTimes(1);
  });

  it('clears custom range validation error as soon as inputs are edited', async () => {
    const apiClient = buildApiClient();
    render(<Harness apiClient={apiClient} pollIntervalMs={60_000} />);

    await waitFor(() => {
      expect(apiClient.getMonitoringMetrics).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByRole('button', { name: 'Select Custom' }));
    fireEvent.change(screen.getByTestId('custom-start'), {
      target: { value: '2026-02-28T12:00' },
    });
    fireEvent.change(screen.getByTestId('custom-end'), {
      target: { value: '2026-02-28T11:00' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Apply Custom' }));

    await waitFor(() => {
      expect(screen.getByTestId('range-error').textContent).toContain('Custom range start must be before end.');
    });

    fireEvent.change(screen.getByTestId('custom-end'), {
      target: { value: '2026-02-28T12:30' },
    });
    expect(screen.getByTestId('range-error').textContent).toBe('');
  });

  it('falls back to synthetic history when the metrics endpoint fails', async () => {
    const apiClient = buildApiClient();
    apiClient.getMonitoringMetrics.mockRejectedValue(new Error('monitoring down'));
    const consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {});

    render(<Harness apiClient={apiClient} pollIntervalMs={60_000} />);

    await waitFor(() => {
      expect(apiClient.getHealthMetrics).toHaveBeenCalledTimes(1);
      expect(apiClient.getMetrics).toHaveBeenCalledTimes(1);
      expect(Number(screen.getByTestId('history-count').textContent)).toBeGreaterThan(0);
    });

    consoleWarn.mockRestore();
  });
});
