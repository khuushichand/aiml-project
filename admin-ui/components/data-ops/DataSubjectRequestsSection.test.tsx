/* @vitest-environment jsdom */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { api } from '@/lib/api-client';
import { DataSubjectRequestsSection } from './DataSubjectRequestsSection';

const toastSuccessMock = vi.hoisted(() => vi.fn());
const toastErrorMock = vi.hoisted(() => vi.fn());

vi.mock('@/components/ui/toast', () => ({
  useToast: () => ({
    success: toastSuccessMock,
    error: toastErrorMock,
  }),
}));

vi.mock('@/lib/api-client', () => ({
  api: {
    listDataSubjectRequests: vi.fn(),
    previewDataSubjectRequest: vi.fn(),
    createDataSubjectRequest: vi.fn(),
  },
}));

type ApiMock = {
  listDataSubjectRequests: ReturnType<typeof vi.fn>;
  previewDataSubjectRequest: ReturnType<typeof vi.fn>;
  createDataSubjectRequest: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

const emptyListResponse = {
  items: [],
  total: 0,
  limit: 50,
  offset: 0,
};

beforeEach(() => {
  toastSuccessMock.mockClear();
  toastErrorMock.mockClear();

  apiMock.listDataSubjectRequests.mockResolvedValue(emptyListResponse);
  apiMock.previewDataSubjectRequest.mockResolvedValue({
    summary: [
      { key: 'media_records', label: 'Media records', count: 12 },
      { key: 'chat_messages', label: 'Chat sessions/messages', count: 20 },
      { key: 'notes', label: 'Notes', count: 8 },
      { key: 'audit_events', label: 'Audit log events', count: 31 },
    ],
  });
  apiMock.createDataSubjectRequest.mockResolvedValue({
    item: {
      id: 1,
      client_request_id: 'dsr-1',
      requester_identifier: 'user@example.com',
      request_type: 'access',
      status: 'recorded',
      requested_at: '2026-03-10T12:00:00Z',
      selected_categories: ['media_records', 'chat_messages', 'notes', 'audit_events'],
      preview_summary: [
        { key: 'media_records', label: 'Media records', count: 12 },
        { key: 'chat_messages', label: 'Chat sessions/messages', count: 20 },
      ],
      coverage_metadata: {},
    },
  });

  localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  localStorage.clear();
});

describe('DataSubjectRequestsSection', () => {
  it('loads request history from the backend instead of localStorage', async () => {
    localStorage.setItem(
      'data_ops_data_subject_requests_log_v1',
      JSON.stringify([
        {
          id: 'local-entry',
          requester: 'local-only@example.com',
          request_type: 'access',
          status: 'completed',
          requested_at: '2026-03-01T12:00:00.000Z',
        },
      ]),
    );
    apiMock.listDataSubjectRequests.mockResolvedValue({
      items: [
        {
          id: 1,
          client_request_id: 'dsr-1',
          requester_identifier: 'seeded@example.com',
          request_type: 'export',
          status: 'recorded',
          requested_at: '2026-03-01T12:00:00Z',
          selected_categories: ['media_records'],
          preview_summary: [{ key: 'media_records', label: 'Media records', count: 3 }],
          coverage_metadata: {},
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    });

    render(<DataSubjectRequestsSection refreshSignal={0} />);

    expect(await screen.findByText('seeded@example.com')).toBeInTheDocument();
    expect(screen.queryByText('local-only@example.com')).not.toBeInTheDocument();
    expect(apiMock.listDataSubjectRequests).toHaveBeenCalledWith({ limit: '50', offset: '0' });
  });

  it('validates requester identifier before submission', async () => {
    const user = userEvent.setup();
    render(<DataSubjectRequestsSection refreshSignal={0} />);

    await waitFor(() => {
      expect(apiMock.listDataSubjectRequests).toHaveBeenCalled();
    });

    await user.click(screen.getByRole('button', { name: 'Submit request' }));

    expect(await screen.findByText('User identifier (email or user ID) is required.')).toBeInTheDocument();
  });

  it('enforces erasure category selection and irreversible-action confirmation', async () => {
    apiMock.listDataSubjectRequests
      .mockResolvedValueOnce(emptyListResponse)
      .mockResolvedValueOnce({
        items: [
          {
            id: 7,
            client_request_id: 'dsr-erasure-1',
            requester_identifier: 'erasure@example.com',
            request_type: 'erasure',
            status: 'recorded',
            requested_at: '2026-03-10T12:00:00Z',
            selected_categories: ['media_records'],
            preview_summary: [{ key: 'media_records', label: 'Media records', count: 12 }],
            coverage_metadata: {},
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      });
    apiMock.createDataSubjectRequest.mockResolvedValue({
      item: {
        id: 7,
        client_request_id: 'dsr-erasure-1',
        requester_identifier: 'erasure@example.com',
        request_type: 'erasure',
        status: 'recorded',
        requested_at: '2026-03-10T12:00:00Z',
        selected_categories: ['media_records'],
        preview_summary: [{ key: 'media_records', label: 'Media records', count: 12 }],
        coverage_metadata: {},
      },
    });

    const user = userEvent.setup();
    render(<DataSubjectRequestsSection refreshSignal={0} />);

    await waitFor(() => {
      expect(apiMock.listDataSubjectRequests).toHaveBeenCalledTimes(1);
    });

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
          client_request_id: expect.stringMatching(/^dsr-/),
          requester_identifier: 'erasure@example.com',
          request_type: 'erasure',
          categories: ['media_records'],
        }),
      );
    });

    const log = await screen.findByTestId('dsr-request-log');
    const row = within(log).getAllByTestId('dsr-request-log-row')[0];
    expect(within(row).getByText('erasure')).toBeInTheDocument();
    expect(within(row).getByText('erasure@example.com')).toBeInTheDocument();
    expect(within(row).getByText('recorded')).toBeInTheDocument();
    expect(toastSuccessMock).toHaveBeenCalledWith(
      'Request recorded',
      'The request was recorded for review. Export and erasure are not executed automatically in this release.',
    );
  });

  it('renders request log row after an access request', async () => {
    apiMock.listDataSubjectRequests
      .mockResolvedValueOnce(emptyListResponse)
      .mockResolvedValueOnce({
        items: [
          {
            id: 11,
            client_request_id: 'dsr-access-1',
            requester_identifier: 'access@example.com',
            request_type: 'access',
            status: 'recorded',
            requested_at: '2026-03-10T12:00:00Z',
            selected_categories: ['media_records', 'chat_messages', 'notes', 'audit_events'],
            preview_summary: [
              { key: 'media_records', label: 'Media records', count: 12 },
              { key: 'chat_messages', label: 'Chat sessions/messages', count: 20 },
            ],
            coverage_metadata: {},
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      });
    apiMock.createDataSubjectRequest.mockResolvedValue({
      item: {
        id: 11,
        client_request_id: 'dsr-access-1',
        requester_identifier: 'access@example.com',
        request_type: 'access',
        status: 'recorded',
        requested_at: '2026-03-10T12:00:00Z',
        selected_categories: ['media_records', 'chat_messages', 'notes', 'audit_events'],
        preview_summary: [
          { key: 'media_records', label: 'Media records', count: 12 },
          { key: 'chat_messages', label: 'Chat sessions/messages', count: 20 },
        ],
        coverage_metadata: {},
      },
    });

    const user = userEvent.setup();
    render(<DataSubjectRequestsSection refreshSignal={0} />);

    await waitFor(() => {
      expect(apiMock.listDataSubjectRequests).toHaveBeenCalledTimes(1);
    });

    await user.type(screen.getByLabelText('User identifier (email or user ID)'), 'access@example.com');
    await user.click(screen.getByRole('button', { name: 'Submit request' }));

    expect(await screen.findByTestId('dsr-access-summary')).toBeInTheDocument();
    expect(apiMock.createDataSubjectRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        client_request_id: expect.stringMatching(/^dsr-/),
        requester_identifier: 'access@example.com',
        request_type: 'access',
      }),
    );

    const requestLog = screen.getByTestId('dsr-request-log');
    await waitFor(() => {
      expect(within(requestLog).getAllByTestId('dsr-request-log-row').length).toBe(1);
    });
    expect(within(requestLog).getByText('access@example.com')).toBeInTheDocument();
    expect(within(requestLog).getByText('recorded')).toBeInTheDocument();
    expect(toastSuccessMock).toHaveBeenCalledWith(
      'Request recorded',
      'The access request was recorded and the authoritative summary is shown below.',
    );
  });

  it('does not show success when request creation fails', async () => {
    apiMock.createDataSubjectRequest.mockRejectedValue(new Error('boom'));

    const user = userEvent.setup();
    render(<DataSubjectRequestsSection refreshSignal={0} />);

    await waitFor(() => {
      expect(apiMock.listDataSubjectRequests).toHaveBeenCalledTimes(1);
    });

    await user.type(screen.getByLabelText('User identifier (email or user ID)'), 'failure@example.com');
    await user.click(screen.getByRole('button', { name: 'Submit request' }));

    await waitFor(() => {
      expect(apiMock.createDataSubjectRequest).toHaveBeenCalled();
    });

    expect(toastSuccessMock).not.toHaveBeenCalled();
    expect(toastErrorMock).toHaveBeenCalledWith('Request failed', 'boom');
    expect(screen.queryByTestId('dsr-access-summary')).not.toBeInTheDocument();
    expect(screen.getByText('No recorded requests yet.')).toBeInTheDocument();
  });
});
