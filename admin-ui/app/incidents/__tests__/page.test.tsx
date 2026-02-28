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
  it('supports incident assignment from admin user dropdown', async () => {
    usePagedResourceMock.mockReturnValue({
      items: [{
        id: 'inc-1',
        title: 'Queue latency spike',
        status: 'open',
        severity: 'high',
        summary: 'Elevated queue latency',
        tags: ['queue'],
        created_at: '2026-02-17T10:00:00Z',
        updated_at: '2026-02-17T10:00:00Z',
        resolved_at: null,
        timeline: [],
      }],
      total: 1,
      loading: false,
      error: '',
      reload: reloadMock,
    });

    const user = userEvent.setup();
    render(<IncidentsPage />);

    const assigneeSelect = await screen.findByTestId('incident-assigned-to-inc-1');
    await user.selectOptions(assigneeSelect, '2');

    await waitFor(() => {
      expect(apiMock.addIncidentEvent).toHaveBeenCalledWith('inc-1', {
        message: 'Assigned to bob',
      });
    });
    expect(reloadMock).toHaveBeenCalled();
  });

  it('renders and saves structured post-mortem fields for resolved incidents', async () => {
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
        timeline: [],
      }],
      total: 1,
      loading: false,
      error: '',
      reload: reloadMock,
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
      expect(apiMock.addIncidentEvent).toHaveBeenCalledWith(
        'inc-2',
        expect.objectContaining({
          message: expect.stringContaining('Post-mortem updated'),
        })
      );
    });

    const raw = localStorage.getItem('admin.incidents.workflow.v1');
    expect(raw).toBeTruthy();
    expect(raw).toContain('Connection pool exhaustion under failover.');
    expect(raw).toContain('Add failover pool saturation alert.');
  });
});
