/* @vitest-environment jsdom */
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import DataOpsPage from '../page';
import { formatAxeViolations, getCriticalAndSeriousAxeViolations } from '@/test-utils/axe';

vi.mock('@/components/PermissionGuard', () => ({
  PermissionGuard: ({ children }: { children: ReactNode }) => <>{children}</>,
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/ResponsiveLayout', () => ({
  ResponsiveLayout: ({ children }: { children: ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}));

vi.mock('@/components/data-ops/BackupsSection', () => ({
  BackupsSection: () => <section aria-label="Backups section">Backups</section>,
}));

vi.mock('@/components/data-ops/RetentionPoliciesSection', () => ({
  RetentionPoliciesSection: () => <section aria-label="Retention policies section">Retention</section>,
}));

vi.mock('@/components/data-ops/DataSubjectRequestsSection', () => ({
  DataSubjectRequestsSection: () => <section aria-label="Data subject requests section">DSR</section>,
}));

vi.mock('@/components/data-ops/ExportsSection', () => ({
  ExportsSection: () => <section aria-label="Exports section">Exports</section>,
}));

vi.mock('@/components/data-ops/MaintenanceSection', () => ({
  MaintenanceSection: () => <section aria-label="Maintenance section">Maintenance</section>,
}));

describe('DataOpsPage accessibility', () => {
  it('has no critical/serious axe violations', async () => {
    const { container } = render(<DataOpsPage />);
    await screen.findByRole('heading', { name: 'Data Ops' });

    const violations = await getCriticalAndSeriousAxeViolations(container);
    expect(violations, formatAxeViolations(violations)).toEqual([]);
  });
});
