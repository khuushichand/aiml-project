/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import CompliancePage from '../page';
import { api } from '@/lib/api-client';

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => '/compliance',
}));

vi.mock('@/components/PermissionGuard', () => ({
  PermissionGuard: ({ children }: { children: ReactNode }) => <>{children}</>,
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/ResponsiveLayout', () => ({
  ResponsiveLayout: ({ children }: { children: ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}));

vi.mock('@/lib/api-client', () => ({
  api: {
    getCompliancePosture: vi.fn(),
  },
}));

type ApiMock = {
  getCompliancePosture: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

const GOOD_POSTURE = {
  overall_score: 92.0,
  mfa_adoption_pct: 80.0,
  mfa_enabled_count: 8,
  total_users: 10,
  key_rotation_compliance_pct: 100.0,
  keys_needing_rotation: 0,
  keys_total: 5,
  rotation_threshold_days: 180,
  audit_logging_enabled: true,
};

const POOR_POSTURE = {
  overall_score: 36.0,
  mfa_adoption_pct: 20.0,
  mfa_enabled_count: 1,
  total_users: 5,
  key_rotation_compliance_pct: 20.0,
  keys_needing_rotation: 4,
  keys_total: 5,
  rotation_threshold_days: 180,
  audit_logging_enabled: true,
};

beforeEach(() => {
  apiMock.getCompliancePosture.mockReset();
});

afterEach(cleanup);

describe('CompliancePage', () => {
  it('renders overall score and grade for a healthy posture', async () => {
    apiMock.getCompliancePosture.mockResolvedValue(GOOD_POSTURE);
    render(<CompliancePage />);

    await waitFor(() => {
      expect(screen.getByText('92')).toBeInTheDocument();
    });

    const badge = screen.getByTestId('compliance-grade');
    expect(badge.textContent).toBe('A');
  });

  it('renders MFA adoption card with correct numbers', async () => {
    apiMock.getCompliancePosture.mockResolvedValue(GOOD_POSTURE);
    render(<CompliancePage />);

    await waitFor(() => {
      expect(screen.getByText('80%')).toBeInTheDocument();
    });

    expect(screen.getByText('8 of 10 users enabled')).toBeInTheDocument();
    expect(screen.getByText(/2 without MFA/)).toBeInTheDocument();
  });

  it('renders key rotation card with compliant count', async () => {
    apiMock.getCompliancePosture.mockResolvedValue(GOOD_POSTURE);
    render(<CompliancePage />);

    await waitFor(() => {
      expect(screen.getByText('100%')).toBeInTheDocument();
    });

    expect(screen.getByText(/5 of 5 keys compliant/)).toBeInTheDocument();
  });

  it('shows needing-rotation link when keys are stale', async () => {
    apiMock.getCompliancePosture.mockResolvedValue(POOR_POSTURE);
    render(<CompliancePage />);

    await waitFor(() => {
      expect(screen.getByText(/4 need rotation/)).toBeInTheDocument();
    });
  });

  it('shows audit logging as enabled', async () => {
    apiMock.getCompliancePosture.mockResolvedValue(GOOD_POSTURE);
    render(<CompliancePage />);

    await waitFor(() => {
      expect(screen.getByText('Enabled')).toBeInTheDocument();
    });

    expect(screen.getByText('All admin actions are being recorded')).toBeInTheDocument();
  });

  it('renders error state when API fails', async () => {
    apiMock.getCompliancePosture.mockRejectedValue(new Error('Network failure'));
    render(<CompliancePage />);

    await waitFor(() => {
      expect(screen.getByText(/Unable to load compliance data/)).toBeInTheDocument();
    });

    expect(screen.getByText(/Network failure/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Retry/ })).toBeInTheDocument();
  });

  it('shows F grade for very poor posture', async () => {
    apiMock.getCompliancePosture.mockResolvedValue({
      ...POOR_POSTURE,
      overall_score: 36.0,
    });
    render(<CompliancePage />);

    await waitFor(() => {
      expect(screen.getByTestId('compliance-grade').textContent).toBe('F');
    });
  });
});
