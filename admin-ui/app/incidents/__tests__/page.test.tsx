/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import IncidentsPage from '../page';
import { api } from '@/lib/api-client';
import { usePagedResource } from '@/lib/use-paged-resource';

const confirmMock = vi.hoisted(() => vi.fn());
const toastSuccessMock = vi.hoisted(() => vi.fn());
const toastErrorMock = vi.hoisted(() => vi.fn());
const reloadMock = vi.hoisted(() => vi.fn());

vi.mock('@/components/PermissionGuard', () => ({
  PermissionGuard: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/ResponsiveLayout', () => ({
  ResponsiveLayout: ({ children }: { children: ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}));

vi.mock('@/components/ui/confirm-dialog', () => ({
  useConfirm: () => confirmMock,
}));

vi.mock('@/components/ui/toast', () => ({
  useToast: () => ({
    success: toastSuccessMock,
    error: toastErrorMock,
  }),
}));

vi.mock('@/lib/use-url-state', () => ({
  useUrlPagination: () => ({
    page: 1,
    pageSize: 20,
    setPage: vi.fn(),
    setPageSize: vi.fn(),
    resetPagination: vi.fn(),
  }),
}));

vi.mock('@/lib/use-paged-resource', () => ({
  usePagedResource: vi.fn(),
}));

vi.mock('@/lib/api-client', () => ({
  api: {
    getUsers: vi.fn(),
    createIncident: vi.fn(),
    updateIncident: vi.fn(),
    addIncidentEvent: vi.fn(),
    deleteIncident: vi.fn(),
  },
}));

const apiMock = vi.mocked(api);
const usePagedResourceMock = vi.mocked(usePagedResource);

beforeEach(() => {
  localStorage.clear();
  confirmMock.mockResolvedValue(true);
  toastSuccessMock.mockClear();
  toastErrorMock.mockClear();
  reloadMock.mockResolvedValue(undefined);

  apiMock.getUsers.mockResolvedValue([
    { id: 1, email: 'alice@example.com', username: 'alice' },
    { id: 2, email: 'bob@example.com', username: 'bob' },
  ]);
  apiMock.createIncident.mockResolvedValue({});
  apiMock.updateIncident.mockResolvedValue({});
  apiMock.addIncidentEvent.mockResolvedValue({});
  apiMock.deleteIncident.mockResolvedValue({});
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  localStorage.clear();
});

describe('IncidentsPage Stage 3 workflows', () => {
  it('updates incident assignment through the backend incident patch route', async () => {
    usePagedResourceMock.mockReturnValue({
      items: [{
        id: 'inc-1',
        title: 'Queue latency spike',
        status: 'resolved',
        severity: 'high',
        summary: 'Elevated queue latency',
        tags: ['queue'],
        created_at: '2026-02-17T10:00:00Z',
        updated_at: '2026-02-17T10:00:00Z',
        resolved_at: '2026-02-17T10:00:00Z',
        assigned_to_user_id: null,
        assigned_to_label: null,
        root_cause: null,
        impact: null,
        action_items: [],
        timeline: [],
      }],
      total: 1,
      loading: false,
      error: '',
      reload: reloadMock,
    });
    apiMock.updateIncident.mockResolvedValue({
      id: 'inc-1',
      title: 'Queue latency spike',
      status: 'resolved',
      severity: 'high',
      summary: 'Elevated queue latency',
      tags: ['queue'],
      created_at: '2026-02-17T10:00:00Z',
      updated_at: '2026-02-17T10:05:00Z',
      resolved_at: '2026-02-17T10:00:00Z',
      assigned_to_user_id: 2,
      assigned_to_label: 'bob@example.com',
      root_cause: null,
      impact: null,
      action_items: [],
      timeline: [],
    });

    const user = userEvent.setup();
    render(<IncidentsPage />);

    await waitFor(() => {
      expect(apiMock.getUsers).toHaveBeenCalledWith({ limit: '100', admin_capable: 'true' });
    });

    const assigneeSelect = await screen.findByTestId('incident-assigned-to-inc-1');
    await user.selectOptions(assigneeSelect, '2');

    await waitFor(() => {
      expect(apiMock.updateIncident).toHaveBeenCalledWith('inc-1', {
        assigned_to_user_id: 2,
        update_message: 'Assigned to bob',
      });
    });
    expect(apiMock.addIncidentEvent).not.toHaveBeenCalled();
    expect(reloadMock).toHaveBeenCalled();
  });

  it('preserves unsaved post-mortem draft when assignment changes', async () => {
    usePagedResourceMock.mockReturnValue({
      items: [{
        id: 'inc-1',
        title: 'Queue latency spike',
        status: 'resolved',
        severity: 'high',
        summary: 'Elevated queue latency',
        tags: ['queue'],
        created_at: '2026-02-17T10:00:00Z',
        updated_at: '2026-02-17T10:00:00Z',
        resolved_at: '2026-02-17T10:00:00Z',
        assigned_to_user_id: null,
        assigned_to_label: null,
        root_cause: null,
        impact: null,
        action_items: [],
        timeline: [],
      }],
      total: 1,
      loading: false,
      error: '',
      reload: reloadMock,
    });
    apiMock.updateIncident.mockResolvedValue({
      id: 'inc-1',
      title: 'Queue latency spike',
      status: 'resolved',
      severity: 'high',
      summary: 'Elevated queue latency',
      tags: ['queue'],
      created_at: '2026-02-17T10:00:00Z',
      updated_at: '2026-02-17T10:05:00Z',
      resolved_at: '2026-02-17T10:00:00Z',
      assigned_to_user_id: 2,
      assigned_to_label: 'bob@example.com',
      root_cause: null,
      impact: null,
      action_items: [],
      timeline: [],
    });

    const user = userEvent.setup();
    render(<IncidentsPage />);

    const rootCause = await screen.findByTestId('incident-root-cause-inc-1');
    const impact = screen.getByTestId('incident-impact-inc-1');

    await user.type(rootCause, 'Keep this draft root cause');
    await user.type(impact, 'Keep this draft impact');
    await user.click(screen.getByRole('button', { name: 'Add Action Item' }));
    const actionItemInput = screen.getByPlaceholderText('Describe follow-up action');
    await user.type(actionItemInput, 'Keep this draft action item');

    const assigneeSelect = screen.getByTestId('incident-assigned-to-inc-1');
    await user.selectOptions(assigneeSelect, '2');

    await waitFor(() => {
      expect(apiMock.updateIncident).toHaveBeenCalledWith('inc-1', {
        assigned_to_user_id: 2,
        update_message: 'Assigned to bob',
      });
    });

    expect((rootCause as HTMLTextAreaElement).value).toBe('Keep this draft root cause');
    expect((impact as HTMLTextAreaElement).value).toBe('Keep this draft impact');
    expect((actionItemInput as HTMLInputElement).value).toBe('Keep this draft action item');
  });

  it('preserves unsaved post-mortem draft when assignment update fails', async () => {
    usePagedResourceMock.mockReturnValue({
      items: [{
        id: 'inc-1',
        title: 'Queue latency spike',
        status: 'resolved',
        severity: 'high',
        summary: 'Elevated queue latency',
        tags: ['queue'],
        created_at: '2026-02-17T10:00:00Z',
        updated_at: '2026-02-17T10:00:00Z',
        resolved_at: '2026-02-17T10:00:00Z',
        assigned_to_user_id: 1,
        assigned_to_label: 'alice@example.com',
        root_cause: null,
        impact: null,
        action_items: [],
        timeline: [],
      }],
      total: 1,
      loading: false,
      error: '',
      reload: reloadMock,
    });
    apiMock.updateIncident.mockRejectedValue(new Error('Failed to update assignment'));

    const user = userEvent.setup();
    render(<IncidentsPage />);

    const rootCause = await screen.findByTestId('incident-root-cause-inc-1');
    const impact = screen.getByTestId('incident-impact-inc-1');

    await user.type(rootCause, 'Retain this root cause draft');
    await user.type(impact, 'Retain this impact draft');
    await user.click(screen.getByRole('button', { name: 'Add Action Item' }));
    const actionItemInput = screen.getByPlaceholderText('Describe follow-up action');
    await user.type(actionItemInput, 'Retain this action item draft');

    const assigneeSelect = screen.getByTestId('incident-assigned-to-inc-1');
    await user.selectOptions(assigneeSelect, '2');

    await waitFor(() => {
      expect(toastErrorMock).toHaveBeenCalledWith('Failed to update assignment');
    });

    expect((assigneeSelect as HTMLSelectElement).value).toBe('1');
    expect((rootCause as HTMLTextAreaElement).value).toBe('Retain this root cause draft');
    expect((impact as HTMLTextAreaElement).value).toBe('Retain this impact draft');
    expect((actionItemInput as HTMLInputElement).value).toBe('Retain this action item draft');
  });

  it('renders backend workflow fields and assignee labels from the incident payload', async () => {
    usePagedResourceMock.mockReturnValue({
      items: [{
        id: 'inc-2',
        title: 'Database outage',
        status: 'resolved',
        severity: 'critical',
        summary: 'Primary DB unavailable for 4 minutes',
        tags: ['database'],
        created_at: '2026-02-17T08:00:00Z',
        updated_at: '2026-02-17T09:00:00Z',
        resolved_at: '2026-02-17T09:00:00Z',
        assigned_to_user_id: 77,
        assigned_to_label: 'oncall-admin@example.com',
        root_cause: 'Connection pool exhaustion under failover.',
        impact: 'Writes failed for 4 minutes in one region.',
        action_items: [
          { id: 'ai_keep', text: 'Add failover pool saturation alert.', done: false },
        ],
        timeline: [],
      }],
      total: 1,
      loading: false,
      error: '',
      reload: reloadMock,
    });

    render(<IncidentsPage />);

    const rootCause = await screen.findByTestId('incident-root-cause-inc-2');
    const impact = screen.getByTestId('incident-impact-inc-2');
    const assigneeSelect = screen.getByTestId('incident-assigned-to-inc-2');
    const actionItemInput = screen.getByDisplayValue('Add failover pool saturation alert.');

    expect((assigneeSelect as HTMLSelectElement).value).toBe('77');
    expect(screen.getByRole('option', { name: 'oncall-admin@example.com' })).toBeInTheDocument();
    expect((rootCause as HTMLTextAreaElement).value).toBe('Connection pool exhaustion under failover.');
    expect((impact as HTMLTextAreaElement).value).toBe('Writes failed for 4 minutes in one region.');
    expect(actionItemInput).toBeInTheDocument();
  });

  it('saves structured post-mortem fields through the backend incident patch route', async () => {
    usePagedResourceMock.mockReturnValue({
      items: [{
        id: 'inc-2',
        title: 'Database outage',
        status: 'resolved',
        severity: 'critical',
        summary: 'Primary DB unavailable for 4 minutes',
        tags: ['database'],
        created_at: '2026-02-17T08:00:00Z',
        updated_at: '2026-02-17T09:00:00Z',
        resolved_at: '2026-02-17T09:00:00Z',
        assigned_to_user_id: null,
        assigned_to_label: null,
        root_cause: null,
        impact: null,
        action_items: [],
        timeline: [],
      }],
      total: 1,
      loading: false,
      error: '',
      reload: reloadMock,
    });
    apiMock.updateIncident.mockResolvedValue({
      id: 'inc-2',
      title: 'Database outage',
      status: 'resolved',
      severity: 'critical',
      summary: 'Primary DB unavailable for 4 minutes',
      tags: ['database'],
      created_at: '2026-02-17T08:00:00Z',
      updated_at: '2026-02-17T09:05:00Z',
      resolved_at: '2026-02-17T09:00:00Z',
      assigned_to_user_id: null,
      assigned_to_label: null,
      root_cause: 'Connection pool exhaustion under failover.',
      impact: 'Writes failed for 4 minutes in one region.',
      action_items: [
        { id: 'ai_keep', text: 'Add failover pool saturation alert.', done: false },
      ],
      timeline: [],
    });

    const user = userEvent.setup();
    render(<IncidentsPage />);

    const rootCause = await screen.findByTestId('incident-root-cause-inc-2');
    const impact = screen.getByTestId('incident-impact-inc-2');

    await user.type(rootCause, 'Connection pool exhaustion under failover.');
    await user.type(impact, 'Writes failed for 4 minutes in one region.');
    await user.click(screen.getByRole('button', { name: 'Add Action Item' }));
    const actionItemInput = screen.getByPlaceholderText('Describe follow-up action');
    await user.type(actionItemInput, 'Add failover pool saturation alert.');

    await user.click(screen.getByTestId('incident-save-postmortem-inc-2'));

    await waitFor(() => {
      expect(apiMock.updateIncident).toHaveBeenCalledWith(
        'inc-2',
        expect.objectContaining({
          root_cause: 'Connection pool exhaustion under failover.',
          impact: 'Writes failed for 4 minutes in one region.',
          action_items: [
            expect.objectContaining({
              text: 'Add failover pool saturation alert.',
              done: false,
            }),
          ],
          update_message: expect.stringContaining('Post-mortem updated'),
        }),
      );
    });
    expect(apiMock.addIncidentEvent).not.toHaveBeenCalled();
    expect(localStorage.getItem('admin.incidents.workflow.v1')).toBeNull();
  });
});
