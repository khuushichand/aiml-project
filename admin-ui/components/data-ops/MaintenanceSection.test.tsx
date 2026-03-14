/* @vitest-environment jsdom */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MaintenanceSection } from './MaintenanceSection';
import { ApiError, api } from '@/lib/api-client';

const confirmMock = vi.hoisted(() => vi.fn());
const toastSuccessMock = vi.hoisted(() => vi.fn());
const toastErrorMock = vi.hoisted(() => vi.fn());

vi.mock('@/components/ui/toast', () => ({
  useToast: () => ({
    success: toastSuccessMock,
    error: toastErrorMock,
  }),
}));

vi.mock('@/components/ui/confirm-dialog', () => ({
  useConfirm: () => confirmMock,
}));

vi.mock('@/lib/api-client', () => ({
  ApiError: class extends Error {
    status: number;

    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
  api: {
    getCleanupSettings: vi.fn(),
    updateCleanupSettings: vi.fn(),
    getNotesTitleSettings: vi.fn(),
    updateNotesTitleSettings: vi.fn(),
    runKanbanFtsMaintenance: vi.fn(),
    createMaintenanceRotationRun: vi.fn(),
    getMaintenanceRotationRuns: vi.fn(),
    getMaintenanceRotationRun: vi.fn(),
  },
}));

type ApiMock = {
  getCleanupSettings: ReturnType<typeof vi.fn>;
  updateCleanupSettings: ReturnType<typeof vi.fn>;
  getNotesTitleSettings: ReturnType<typeof vi.fn>;
  updateNotesTitleSettings: ReturnType<typeof vi.fn>;
  runKanbanFtsMaintenance: ReturnType<typeof vi.fn>;
  createMaintenanceRotationRun: ReturnType<typeof vi.fn>;
  getMaintenanceRotationRuns: ReturnType<typeof vi.fn>;
  getMaintenanceRotationRun: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

const buildRun = (overrides: Record<string, unknown> = {}) => ({
  id: 'run-1',
  mode: 'dry_run',
  status: 'complete',
  domain: 'jobs',
  queue: 'default',
  job_type: 'encryption_rotation',
  fields_json: '["payload","result"]',
  limit: 100,
  affected_count: 42,
  requested_by_user_id: 1,
  requested_by_label: 'ops-admin@example.com',
  confirmation_recorded: false,
  job_id: 'job-1',
  scope_summary: 'domain=jobs, queue=default, job_type=encryption_rotation, fields=payload,result, limit=100',
  key_source: 'env:jobs_crypto_rotate',
  error_message: null,
  created_at: '2026-03-12T20:00:00+00:00',
  started_at: '2026-03-12T20:00:05+00:00',
  completed_at: '2026-03-12T20:00:15+00:00',
  ...overrides,
});

beforeEach(() => {
  vi.useFakeTimers();

  confirmMock.mockResolvedValue(true);
  toastSuccessMock.mockClear();
  toastErrorMock.mockClear();

  apiMock.getCleanupSettings.mockResolvedValue({
    auto_cleanup_enabled: false,
    retention_days: 30,
  });
  apiMock.getNotesTitleSettings.mockResolvedValue({
    auto_generate_titles: true,
    max_title_length: 100,
  });
  apiMock.getMaintenanceRotationRuns.mockResolvedValue({
    items: [],
    total: 0,
    limit: 10,
    offset: 0,
  });
  apiMock.createMaintenanceRotationRun.mockResolvedValue({
    item: buildRun({ status: 'queued', affected_count: null, job_id: null, completed_at: null }),
  });
  apiMock.getMaintenanceRotationRun.mockResolvedValue(
    buildRun({ status: 'complete' }),
  );
});

afterEach(() => {
  cleanup();
  vi.runOnlyPendingTimers();
  vi.useRealTimers();
  vi.resetAllMocks();
});

async function renderSection() {
  render(<MaintenanceSection refreshSignal={0} />);
  await act(async () => {
    await Promise.resolve();
  });
}

describe('MaintenanceSection', () => {
  it('submits the real scoped rotation request body', async () => {
    await renderSection();

    fireEvent.change(screen.getByLabelText(/Mode/i), { target: { value: 'execute' } });
    fireEvent.change(screen.getByLabelText(/Domain/i), { target: { value: ' jobs ' } });
    fireEvent.change(screen.getByLabelText(/Queue/i), { target: { value: ' default ' } });
    fireEvent.change(screen.getByLabelText(/Job type/i), { target: { value: ' encryption_rotation ' } });
    fireEvent.click(screen.getByLabelText(/Rotate result field/i));
    fireEvent.change(screen.getByLabelText(/Limit/i), { target: { value: '250' } });
    fireEvent.click(screen.getByLabelText(/I confirm this will execute live key rotation/i));

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Submit rotation request/i }));
      await Promise.resolve();
    });

    expect(apiMock.createMaintenanceRotationRun).toHaveBeenCalledWith({
      mode: 'execute',
      domain: 'jobs',
      queue: 'default',
      job_type: 'encryption_rotation',
      fields: ['payload'],
      limit: 250,
      confirmed: true,
    });
  });

  it('does not use localStorage for rotation state or history', async () => {
    const getItemSpy = vi.spyOn(Storage.prototype, 'getItem');
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem');
    const removeItemSpy = vi.spyOn(Storage.prototype, 'removeItem');

    await renderSection();

    expect(getItemSpy).not.toHaveBeenCalled();
    expect(setItemSpy).not.toHaveBeenCalled();
    expect(removeItemSpy).not.toHaveBeenCalled();
  });

  it('shows backend failure without creating a fake fallback run', async () => {
    apiMock.createMaintenanceRotationRun.mockRejectedValueOnce(
      new ApiError(503, 'rotation unavailable'),
    );

    await renderSection();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Submit rotation request/i }));
      await Promise.resolve();
    });

    expect(toastErrorMock).toHaveBeenCalled();
    expect(screen.queryByTestId('maintenance-rotation-current')).not.toBeInTheDocument();
    expect(within(screen.getByTestId('maintenance-rotation-history')).queryAllByTestId('maintenance-rotation-history-row')).toHaveLength(0);
  });

  it('renders backend-provided run history and current detail', async () => {
    apiMock.getMaintenanceRotationRuns.mockResolvedValueOnce({
      items: [buildRun()],
      total: 1,
      limit: 10,
      offset: 0,
    });

    await renderSection();

    const current = screen.getByTestId('maintenance-rotation-current');
    expect(current).toBeInTheDocument();
    expect(screen.getByTestId('maintenance-rotation-status').textContent).toContain('complete');
    expect(within(current).getByText(/ops-admin@example.com/i)).toBeInTheDocument();

    const history = screen.getByTestId('maintenance-rotation-history');
    expect(within(history).getAllByTestId('maintenance-rotation-history-row')).toHaveLength(1);
    expect(within(history).getByText(/42/i)).toBeInTheDocument();
  });

  it('polls the backend while a run is queued or running', async () => {
    apiMock.createMaintenanceRotationRun.mockResolvedValueOnce({
      item: buildRun({
        status: 'queued',
        affected_count: null,
        job_id: null,
        completed_at: null,
      }),
    });
    apiMock.getMaintenanceRotationRun
      .mockResolvedValueOnce(buildRun({
        status: 'running',
        affected_count: null,
        job_id: 'job-1',
        completed_at: null,
      }))
      .mockResolvedValueOnce(buildRun({
        status: 'complete',
        affected_count: 77,
      }));

    await renderSection();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Submit rotation request/i }));
      await Promise.resolve();
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(apiMock.getMaintenanceRotationRun).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId('maintenance-rotation-status').textContent).toContain('complete');
    expect(screen.getByText(/77/i)).toBeInTheDocument();
  });
});
