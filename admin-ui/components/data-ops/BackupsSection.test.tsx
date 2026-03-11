/* @vitest-environment jsdom */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BackupsSection } from './BackupsSection';
import { api } from '@/lib/api-client';

const unsafeLocalToolsEnabledMock = vi.hoisted(() => vi.fn(() => false));
const confirmMock = vi.hoisted(() => vi.fn());
const toastSuccessMock = vi.hoisted(() => vi.fn());
const toastErrorMock = vi.hoisted(() => vi.fn());

vi.mock('@/lib/admin-ui-flags', () => ({
  isUnsafeLocalToolsEnabled: unsafeLocalToolsEnabledMock,
}));

vi.mock('@/components/ui/toast', () => ({
  useToast: () => ({
    success: toastSuccessMock,
    error: toastErrorMock,
  }),
}));

vi.mock('@/components/ui/confirm-dialog', () => ({
  useConfirm: () => confirmMock,
}));

vi.mock('@/lib/use-url-state', async () => {
  const React = await import('react');
  return {
    useUrlPagination: () => {
      const [page, setPage] = React.useState(1);
      const [pageSize, setPageSize] = React.useState(25);
      return {
        page,
        pageSize,
        setPage,
        setPageSize,
        resetPagination: () => setPage(1),
      };
    },
  };
});

vi.mock('@/lib/api-client', () => ({
  api: {
    getBackups: vi.fn(),
    createBackup: vi.fn(),
    restoreBackup: vi.fn(),
  },
}));

type ApiMock = {
  getBackups: ReturnType<typeof vi.fn>;
  createBackup: ReturnType<typeof vi.fn>;
  restoreBackup: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

const backupsPayload = {
  items: [
    {
      id: 'backup-success',
      dataset: 'media',
      user_id: 1,
      status: 'ready',
      size_bytes: 1024,
      created_at: '2026-02-18T09:00:00Z',
      duration_seconds: 45,
    },
    {
      id: 'backup-failed',
      dataset: 'audit',
      user_id: null,
      status: 'failed',
      size_bytes: 2048,
      created_at: '2026-02-18T08:00:00Z',
      error_message: 'Disk full',
      duration_seconds: 18,
    },
    {
      id: 'backup-running',
      dataset: 'prompts',
      user_id: null,
      status: 'running',
      size_bytes: 512,
      created_at: '2026-02-18T07:00:00Z',
      duration_seconds: 12,
    },
  ],
  total: 3,
  limit: 25,
  offset: 0,
};

beforeEach(() => {
  unsafeLocalToolsEnabledMock.mockReturnValue(false);
  confirmMock.mockResolvedValue(true);
  toastSuccessMock.mockClear();
  toastErrorMock.mockClear();

  apiMock.getBackups.mockResolvedValue(backupsPayload);
  apiMock.createBackup.mockResolvedValue({ item: backupsPayload.items[0] });
  apiMock.restoreBackup.mockResolvedValue({ status: 'ok' });

  localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  localStorage.clear();
});

describe('BackupsSection', () => {
  it('disables local-only backup scheduling in safe mode', async () => {
    const user = userEvent.setup();
    localStorage.setItem('data_ops_backup_schedules_v1', JSON.stringify([
      {
        id: 'sched-local',
        dataset: 'media',
        frequency: 'daily',
        time_of_day: '09:30',
        retention_count: 30,
        is_paused: false,
        created_at: '2026-03-01T12:00:00.000Z',
        updated_at: '2026-03-01T12:00:00.000Z',
      },
    ]));

    render(<BackupsSection refreshSignal={0} />);

    await user.click(screen.getByRole('button', { name: 'Schedule' }));

    expect(
      screen.getByText('Backup scheduling is unavailable until backend schedule APIs are available.')
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create schedule' })).toBeDisabled();
    expect(screen.queryByTestId('backup-schedule-row-sched-local')).not.toBeInTheDocument();
    expect(screen.getByText('Scheduling controls are disabled in production-safe mode.')).toBeInTheDocument();
  });

  it('validates schedule form frequency and time before creation', async () => {
    unsafeLocalToolsEnabledMock.mockReturnValue(true);
    const user = userEvent.setup();
    render(<BackupsSection refreshSignal={0} />);

    await user.click(screen.getByRole('button', { name: 'Schedule' }));
    await user.click(screen.getByRole('button', { name: 'Create schedule' }));

    expect(await screen.findByText('Frequency is required.')).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText('Frequency'), 'daily');
    await user.click(screen.getByRole('button', { name: 'Create schedule' }));

    expect(await screen.findByText('Time of day is required.')).toBeInTheDocument();
  });

  it('renders backup history table with mixed status rows', async () => {
    render(<BackupsSection refreshSignal={0} />);

    const historySection = await screen.findByTestId('backup-history-section');
    await waitFor(() => {
      expect(within(historySection).getAllByTestId('backup-history-row').length).toBe(3);
    });

    expect(within(historySection).getAllByTestId('backup-status-failed')).toHaveLength(1);
    expect(within(historySection).getAllByTestId('backup-status-in-progress')).toHaveLength(1);
    expect(within(historySection).getAllByTestId('backup-status-success')).toHaveLength(1);
  });

  it('supports schedule pause and resume toggle', async () => {
    unsafeLocalToolsEnabledMock.mockReturnValue(true);
    const user = userEvent.setup();
    render(<BackupsSection refreshSignal={0} />);

    await user.click(screen.getByRole('button', { name: 'Schedule' }));
    await user.selectOptions(screen.getByLabelText('Frequency'), 'daily');
    await user.type(screen.getByLabelText('Time of day'), '09:30');
    await user.click(screen.getByRole('button', { name: 'Create schedule' }));

    const scheduleRow = await screen.findByTestId(/backup-schedule-row-/);
    expect(within(scheduleRow).getByText('Active')).toBeInTheDocument();

    await user.click(within(scheduleRow).getByTitle('Pause schedule'));
    expect(await within(scheduleRow).findByText('Paused')).toBeInTheDocument();

    await user.click(within(scheduleRow).getByTitle('Resume schedule'));
    expect(await within(scheduleRow).findByText('Active')).toBeInTheDocument();
  });

  it('renders storage trending growth-rate text from backup history', async () => {
    const MB = 1024 * 1024;
    apiMock.getBackups
      .mockResolvedValueOnce({
        items: [backupsPayload.items[0]],
        total: 1,
        limit: 25,
        offset: 0,
      })
      .mockResolvedValueOnce({
        items: [
          {
            id: 'media-1',
            dataset: 'media',
            user_id: null,
            status: 'ready',
            size_bytes: 100 * MB,
            created_at: '2026-01-01T00:00:00Z',
            duration_seconds: 20,
          },
          {
            id: 'media-2',
            dataset: 'media',
            user_id: null,
            status: 'ready',
            size_bytes: 300 * MB,
            created_at: '2026-01-16T00:00:00Z',
            duration_seconds: 22,
          },
          {
            id: 'media-3',
            dataset: 'media',
            user_id: null,
            status: 'ready',
            size_bytes: 500 * MB,
            created_at: '2026-01-31T00:00:00Z',
            duration_seconds: 24,
          },
        ],
        total: 3,
        limit: 200,
        offset: 0,
      });

    render(<BackupsSection refreshSignal={0} />);

    const trending = await screen.findByTestId('backup-storage-trending');
    const growthText = within(trending).getByTestId('backup-trend-growth-media');
    expect(growthText.textContent).toContain('Storage growing at 400.0 MB/month.');
  });
});
