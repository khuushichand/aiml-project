/* @vitest-environment jsdom */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BackupsSection } from './BackupsSection';
import { api } from '@/lib/api-client';

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
    getUsers: vi.fn(),
    listBackupSchedules: vi.fn(),
    createBackupSchedule: vi.fn(),
    updateBackupSchedule: vi.fn(),
    pauseBackupSchedule: vi.fn(),
    resumeBackupSchedule: vi.fn(),
    deleteBackupSchedule: vi.fn(),
  },
}));

type ApiMock = {
  getBackups: ReturnType<typeof vi.fn>;
  createBackup: ReturnType<typeof vi.fn>;
  restoreBackup: ReturnType<typeof vi.fn>;
  getUsers: ReturnType<typeof vi.fn>;
  listBackupSchedules: ReturnType<typeof vi.fn>;
  createBackupSchedule: ReturnType<typeof vi.fn>;
  updateBackupSchedule: ReturnType<typeof vi.fn>;
  pauseBackupSchedule: ReturnType<typeof vi.fn>;
  resumeBackupSchedule: ReturnType<typeof vi.fn>;
  deleteBackupSchedule: ReturnType<typeof vi.fn>;
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

const usersPayload = [
  {
    id: 7,
    username: 'alice',
    email: 'alice@example.com',
    is_active: true,
  },
];

const schedulePayload = {
  items: [
    {
      id: 'sched-1',
      dataset: 'media',
      target_user_id: 7,
      frequency: 'daily',
      time_of_day: '09:30',
      timezone: 'UTC',
      anchor_day_of_week: null,
      anchor_day_of_month: null,
      retention_count: 14,
      is_paused: false,
      schedule_description: 'Daily at 09:30 UTC',
      next_run_at: '2026-03-11T09:30:00Z',
      last_run_at: '2026-03-10T09:30:00Z',
      last_status: 'queued',
      last_job_id: 'job-1',
      last_error: null,
      created_at: '2026-03-10T00:00:00Z',
      updated_at: '2026-03-10T00:00:00Z',
      deleted_at: null,
    },
  ],
  total: 1,
  limit: 100,
  offset: 0,
};

beforeEach(() => {
  confirmMock.mockResolvedValue(true);
  toastSuccessMock.mockClear();
  toastErrorMock.mockClear();

  apiMock.getBackups.mockResolvedValue(backupsPayload);
  apiMock.createBackup.mockResolvedValue({ item: backupsPayload.items[0] });
  apiMock.restoreBackup.mockResolvedValue({ status: 'ok' });
  apiMock.getUsers.mockResolvedValue(usersPayload);
  apiMock.listBackupSchedules.mockResolvedValue(schedulePayload);
  apiMock.createBackupSchedule.mockResolvedValue({ item: schedulePayload.items[0] });
  apiMock.updateBackupSchedule.mockResolvedValue({ item: schedulePayload.items[0] });
  apiMock.pauseBackupSchedule.mockResolvedValue({
    item: { ...schedulePayload.items[0], is_paused: true, last_status: 'paused' },
  });
  apiMock.resumeBackupSchedule.mockResolvedValue({
    item: { ...schedulePayload.items[0], is_paused: false, last_status: 'queued' },
  });
  apiMock.deleteBackupSchedule.mockResolvedValue({ status: 'deleted' });

  localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  localStorage.clear();
});

describe('BackupsSection', () => {
  it('loads schedule rows from the backend instead of local storage', async () => {
    localStorage.setItem('data_ops_backup_schedules_v1', JSON.stringify([
      {
        id: 'local-only',
        dataset: 'audit',
        frequency: 'weekly',
        time_of_day: '03:00',
        retention_count: 5,
        is_paused: true,
        created_at: '2026-03-01T00:00:00Z',
        updated_at: '2026-03-01T00:00:00Z',
      },
    ]));

    render(<BackupsSection refreshSignal={0} />);

    await userEvent.click(screen.getByRole('button', { name: 'Schedule' }));

    expect(await screen.findByTestId('backup-schedule-row-sched-1')).toBeInTheDocument();
    expect(screen.queryByTestId('backup-schedule-row-local-only')).not.toBeInTheDocument();
    expect(apiMock.listBackupSchedules).toHaveBeenCalledTimes(1);
  });

  it('requires a target user for per-user dataset schedules', async () => {
    const user = userEvent.setup();
    render(<BackupsSection refreshSignal={0} />);

    await user.click(screen.getByRole('button', { name: 'Schedule' }));
    await user.selectOptions(screen.getByLabelText('Dataset'), 'media');
    await user.click(screen.getByRole('button', { name: 'Create schedule' }));

    expect(await screen.findByText('Select a target user.')).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText('Frequency'), 'daily');
    await user.selectOptions(screen.getByLabelText('Target user'), '7');
    await user.type(screen.getByLabelText('Time of day'), '09:30');
    await user.clear(screen.getByLabelText('Retention count'));
    await user.type(screen.getByLabelText('Retention count'), '14');
    await user.click(screen.getByRole('button', { name: 'Create schedule' }));

    await waitFor(() => {
      expect(apiMock.createBackupSchedule).toHaveBeenCalledWith({
        dataset: 'media',
        target_user_id: 7,
        frequency: 'daily',
        time_of_day: '09:30',
        retention_count: 14,
      });
    });
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

  it('hides target user selection for authnz schedules', async () => {
    const user = userEvent.setup();
    render(<BackupsSection refreshSignal={0} />);

    await user.click(screen.getByRole('button', { name: 'Schedule' }));
    await user.selectOptions(screen.getByLabelText('Dataset'), 'authnz');

    expect(screen.queryByLabelText('Target user')).not.toBeInTheDocument();
  });

  it('supports pause, resume, and delete schedule mutations via backend APIs', async () => {
    const user = userEvent.setup();
    render(<BackupsSection refreshSignal={0} />);

    await user.click(screen.getByRole('button', { name: 'Schedule' }));

    const scheduleRow = await screen.findByTestId('backup-schedule-row-sched-1');
    expect(within(scheduleRow).getByText('Active')).toBeInTheDocument();

    await user.click(within(scheduleRow).getByTitle('Pause schedule'));
    await waitFor(() => {
      expect(apiMock.pauseBackupSchedule).toHaveBeenCalledWith('sched-1');
    });
    expect(await within(scheduleRow).findByText('Paused')).toBeInTheDocument();

    await user.click(within(scheduleRow).getByTitle('Resume schedule'));
    await waitFor(() => {
      expect(apiMock.resumeBackupSchedule).toHaveBeenCalledWith('sched-1');
    });
    expect(await within(scheduleRow).findByText('Active')).toBeInTheDocument();

    await user.click(within(scheduleRow).getByTitle('Delete schedule'));
    await waitFor(() => {
      expect(apiMock.deleteBackupSchedule).toHaveBeenCalledWith('sched-1');
    });
    await waitFor(() => {
      expect(screen.queryByTestId('backup-schedule-row-sched-1')).not.toBeInTheDocument();
    });
  });

  it('renders backend schedule mutation failures without a local success fallback', async () => {
    const user = userEvent.setup();
    apiMock.createBackupSchedule.mockRejectedValueOnce(new Error('schedule create failed'));

    render(<BackupsSection refreshSignal={0} />);

    await user.click(screen.getByRole('button', { name: 'Schedule' }));
    await user.selectOptions(screen.getByLabelText('Dataset'), 'media');
    await user.selectOptions(screen.getByLabelText('Target user'), '7');
    await user.selectOptions(screen.getByLabelText('Frequency'), 'daily');
    await user.type(screen.getByLabelText('Time of day'), '09:30');
    await user.clear(screen.getByLabelText('Retention count'));
    await user.type(screen.getByLabelText('Retention count'), '14');
    await user.click(screen.getByRole('button', { name: 'Create schedule' }));

    await waitFor(() => {
      expect(toastErrorMock).toHaveBeenCalled();
    });
    expect(toastSuccessMock).not.toHaveBeenCalledWith('Schedule created', expect.any(String));
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
