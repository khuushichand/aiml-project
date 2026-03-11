/* @vitest-environment jsdom */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DataSubjectRequestsSection } from './DataSubjectRequestsSection';
import { api } from '@/lib/api-client';

const unsafeLocalToolsEnabledMock = vi.hoisted(() => vi.fn(() => false));
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

vi.mock('@/lib/api-client', () => ({
  api: {
    previewDataSubjectRequest: vi.fn(),
    createDataSubjectRequest: vi.fn(),
  },
}));

type ApiMock = {
  previewDataSubjectRequest: ReturnType<typeof vi.fn>;
  createDataSubjectRequest: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

beforeEach(() => {
  unsafeLocalToolsEnabledMock.mockReturnValue(false);
  toastSuccessMock.mockClear();
  toastErrorMock.mockClear();

  apiMock.previewDataSubjectRequest.mockResolvedValue({
    summary: {
      media_records: 12,
      chat_messages: 20,
      notes: 8,
      audit_events: 31,
      embeddings: 4,
    },
  });
  apiMock.createDataSubjectRequest.mockResolvedValue({ status: 'ok' });

  localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  localStorage.clear();
});

describe('DataSubjectRequestsSection', () => {
  it('disables request actions and ignores local-only request history in safe mode', async () => {
    localStorage.setItem('data_ops_data_subject_requests_log_v1', JSON.stringify([
      {
        id: 'local-entry',
        requester: 'seeded@example.com',
        request_type: 'access',
        status: 'completed',
        requested_at: '2026-03-01T12:00:00.000Z',
      },
    ]));

    render(<DataSubjectRequestsSection refreshSignal={0} />);

    expect(
      screen.getByText('Data subject request workflows are unavailable until server-backed APIs are available.')
    ).toBeInTheDocument();
    expect(screen.getByLabelText('User identifier (email or user ID)')).toBeDisabled();
    expect(screen.getByLabelText('Request type')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Submit request' })).toBeDisabled();
    expect(screen.queryByText('seeded@example.com')).not.toBeInTheDocument();
  });

  it('validates requester identifier before submission', async () => {
    unsafeLocalToolsEnabledMock.mockReturnValue(true);
    const user = userEvent.setup();
    render(<DataSubjectRequestsSection refreshSignal={0} />);

    await user.click(screen.getByRole('button', { name: 'Submit request' }));

    expect(await screen.findByText('User identifier (email or user ID) is required.')).toBeInTheDocument();
  });

  it('enforces erasure category selection and irreversible-action confirmation', async () => {
    unsafeLocalToolsEnabledMock.mockReturnValue(true);
    const user = userEvent.setup();
    render(<DataSubjectRequestsSection refreshSignal={0} />);

    await user.type(screen.getByLabelText('User identifier (email or user ID)'), 'erasure@example.com');
    await user.selectOptions(screen.getByLabelText('Request type'), 'erasure');

    await user.click(screen.getByRole('button', { name: 'Preview user data' }));
    await screen.findByTestId('dsr-erasure-preview');

    await user.click(screen.getByRole('button', { name: 'Submit request' }));
    expect(await screen.findByText('Select at least one data category to erase.')).toBeInTheDocument();

    await user.click(screen.getByText('Media records'));
    await user.click(screen.getByRole('button', { name: 'Submit request' }));
    expect(await screen.findByText('Confirm that this action cannot be undone before submitting erasure.')).toBeInTheDocument();

    await user.click(screen.getByLabelText('I understand this action cannot be undone.'));
    await user.click(screen.getByRole('button', { name: 'Submit request' }));

    await waitFor(() => {
      expect(apiMock.createDataSubjectRequest).toHaveBeenCalledWith(
        expect.objectContaining({
          requester_identifier: 'erasure@example.com',
          request_type: 'erasure',
          categories: ['media_records'],
        })
      );
    });

    const log = screen.getByTestId('dsr-request-log');
    const row = within(log).getAllByTestId('dsr-request-log-row')[0];
    expect(within(row).getByText('erasure')).toBeInTheDocument();
    expect(within(row).getByText('erasure@example.com')).toBeInTheDocument();
  });

  it('renders request log row after an access request', async () => {
    unsafeLocalToolsEnabledMock.mockReturnValue(true);
    const user = userEvent.setup();
    render(<DataSubjectRequestsSection refreshSignal={0} />);

    await user.type(screen.getByLabelText('User identifier (email or user ID)'), 'access@example.com');
    await user.click(screen.getByRole('button', { name: 'Submit request' }));

    expect(await screen.findByTestId('dsr-access-summary')).toBeInTheDocument();

    const requestLog = screen.getByTestId('dsr-request-log');
    await waitFor(() => {
      expect(within(requestLog).getAllByTestId('dsr-request-log-row').length).toBe(1);
    });
    expect(within(requestLog).getByText('access@example.com')).toBeInTheDocument();
    expect(within(requestLog).getByText('completed')).toBeInTheDocument();
  });
});
