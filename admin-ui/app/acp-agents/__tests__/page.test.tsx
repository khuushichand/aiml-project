/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ACPAgentsPage from '../page';
import { api } from '@/lib/api-client';

const confirmMock = vi.hoisted(() => vi.fn());
const toastSuccessMock = vi.hoisted(() => vi.fn());
const toastErrorMock = vi.hoisted(() => vi.fn());

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

vi.mock('@/components/ui/toast', () => ({
  useToast: () => ({
    success: toastSuccessMock,
    error: toastErrorMock,
  }),
}));

vi.mock('@/lib/api-client', () => ({
  ApiError: class extends Error {
    status: number;

    constructor(status: number, message?: string) {
      super(message);
      this.status = status;
    }
  },
  api: {
    getACPAgentConfigs: vi.fn(),
    getACPPermissionPolicies: vi.fn(),
    createACPAgentConfig: vi.fn(),
    updateACPAgentConfig: vi.fn(),
    deleteACPAgentConfig: vi.fn(),
    createACPPermissionPolicy: vi.fn(),
    updateACPPermissionPolicy: vi.fn(),
    deleteACPPermissionPolicy: vi.fn(),
  },
}));

type ApiMock = {
  getACPAgentConfigs: ReturnType<typeof vi.fn>;
  getACPPermissionPolicies: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

beforeEach(() => {
  apiMock.getACPAgentConfigs.mockResolvedValue({
    agents: [],
    total: 0,
  });
  apiMock.getACPPermissionPolicies.mockResolvedValue({
    policies: [],
    total: 0,
  });
  confirmMock.mockResolvedValue(true);
  toastSuccessMock.mockClear();
  toastErrorMock.mockClear();
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('ACPAgentsPage', () => {
  it('loads agent configurations on mount', async () => {
    apiMock.getACPAgentConfigs.mockResolvedValue({
      agents: [
        {
          id: 1,
          type: 'codex',
          name: 'Code Agent',
          description: 'Handles implementation tasks',
          system_prompt: null,
          allowed_tools: ['fs.read', 'fs.write'],
          denied_tools: ['bash.run'],
          parameters: { model: 'gpt-5-codex' },
          requires_api_key: null,
          org_id: null,
          team_id: null,
          enabled: true,
          is_configured: true,
          created_at: '2024-01-01T00:00:00.000Z',
          updated_at: null,
        },
      ],
      total: 1,
    });

    render(<ACPAgentsPage />);

    await waitFor(() => {
      expect(apiMock.getACPAgentConfigs).toHaveBeenCalledTimes(1);
      expect(apiMock.getACPPermissionPolicies).toHaveBeenCalledTimes(1);
    });

    expect(screen.getByText('Code Agent')).toBeInTheDocument();
    expect(screen.getByText('Handles implementation tasks')).toBeInTheDocument();
    expect(screen.getByText('Enabled')).toBeInTheDocument();
    expect(screen.getByText('Configured')).toBeInTheDocument();
  });

  it('shows an empty state for the policies tab when no policies exist', async () => {
    const user = userEvent.setup();
    render(<ACPAgentsPage />);

    await waitFor(() => {
      expect(apiMock.getACPPermissionPolicies).toHaveBeenCalledTimes(1);
    });

    await user.click(screen.getByRole('button', { name: /Permission Policies \(0\)/i }));

    expect(screen.getByText('No Permission Policies')).toBeInTheDocument();
    expect(
      screen.getByText('Create policies to control which tools require approval.')
    ).toBeInTheDocument();
  });

  it('renders policy rules and actions when policies are loaded', async () => {
    const user = userEvent.setup();
    apiMock.getACPPermissionPolicies.mockResolvedValue({
      policies: [
        {
          id: 7,
          name: 'Write Guard',
          description: 'Require explicit approval for file writes',
          rules: [{ tool_pattern: 'fs.write*', tier: 'individual' }],
          org_id: null,
          team_id: null,
          priority: 10,
          created_at: '2024-01-01T00:00:00.000Z',
          updated_at: null,
        },
      ],
      total: 1,
    });

    render(<ACPAgentsPage />);

    await waitFor(() => {
      expect(apiMock.getACPPermissionPolicies).toHaveBeenCalledTimes(1);
    });

    await user.click(screen.getByRole('button', { name: /Permission Policies \(1\)/i }));

    expect(screen.getByText('Write Guard')).toBeInTheDocument();
    expect(screen.getByText('Require explicit approval for file writes')).toBeInTheDocument();
    expect(screen.getByText('fs.write*: individual')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Edit' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: 'Delete' }).length).toBeGreaterThan(0);
  });
});
