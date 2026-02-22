/* @vitest-environment jsdom */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MaintenanceSection } from './MaintenanceSection';
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
    rotateJobCrypto: vi.fn(),
    getCurrentUser: vi.fn(),
  },
}));

type ApiMock = {
  getCleanupSettings: ReturnType<typeof vi.fn>;
  updateCleanupSettings: ReturnType<typeof vi.fn>;
  getNotesTitleSettings: ReturnType<typeof vi.fn>;
  updateNotesTitleSettings: ReturnType<typeof vi.fn>;
  runKanbanFtsMaintenance: ReturnType<typeof vi.fn>;
  rotateJobCrypto: ReturnType<typeof vi.fn>;
  getCurrentUser: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

beforeEach(() => {
  vi.useFakeTimers();
  localStorage.clear();

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
  apiMock.getCurrentUser.mockResolvedValue({ username: 'alice_admin' });
  apiMock.rotateJobCrypto.mockResolvedValue({
    total_batches: 3,
    records_total: 900,
  });
});

afterEach(() => {
  cleanup();
  vi.runOnlyPendingTimers();
  vi.useRealTimers();
  vi.resetAllMocks();
  localStorage.clear();
});

describe('MaintenanceSection', () => {
  it('progresses through rotation wizard steps and records completion metadata', async () => {
    render(<MaintenanceSection refreshSignal={0} />);
    await act(async () => {
      await Promise.resolve();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Start rotation wizard' }));

    expect(screen.getByTestId('rotation-confirm-step')).toBeInTheDocument();
    const beginButton = screen.getByRole('button', { name: 'Begin rotation' }) as HTMLButtonElement;
    expect(beginButton.disabled).toBe(true);

    fireEvent.click(screen.getByLabelText(/I understand this operation is sensitive/i));
    expect(beginButton.disabled).toBe(false);

    await act(async () => {
      fireEvent.click(beginButton);
      await Promise.resolve();
    });

    expect(screen.getByTestId('rotation-progress-step')).toBeTruthy();
    expect(screen.getByTestId('rotation-status-message').textContent).toContain('Re-encrypting batch 1 of 3');

    await act(async () => {
      vi.advanceTimersByTime(2400);
      await Promise.resolve();
    });

    expect(screen.getByTestId('rotation-complete-step')).toBeTruthy();
    expect(screen.getByText(/Re-encrypted 900 records/i)).toBeTruthy();

    const historySection = screen.getByTestId('rotation-history');
    expect(within(historySection).getAllByTestId('rotation-history-row')).toHaveLength(1);
    expect(within(historySection).getByText('alice_admin')).toBeTruthy();
  });

  it('updates rotation progress bar and batch status message over time', async () => {
    apiMock.rotateJobCrypto.mockResolvedValueOnce({
      total_batches: 5,
      records_total: 1000,
    });

    render(<MaintenanceSection refreshSignal={0} />);

    fireEvent.click(screen.getByRole('button', { name: 'Start rotation wizard' }));
    fireEvent.click(screen.getByLabelText(/I understand this operation is sensitive/i));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Begin rotation' }));
      await Promise.resolve();
    });

    expect(screen.getByTestId('rotation-progress-step')).toBeTruthy();
    expect(screen.getByTestId('rotation-progress-bar').getAttribute('aria-valuenow')).toBe('20');
    expect(screen.getByTestId('rotation-status-message').textContent).toContain('Re-encrypting batch 1 of 5');

    await act(async () => {
      vi.advanceTimersByTime(1200);
      await Promise.resolve();
    });

    expect(screen.getByTestId('rotation-status-message').textContent).toContain('Re-encrypting batch 2 of 5');
    expect(screen.getByTestId('rotation-progress-bar').getAttribute('aria-valuenow')).toBe('40');
  });
});
