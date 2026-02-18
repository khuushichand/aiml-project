/* @vitest-environment jsdom */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RetentionPoliciesSection } from './RetentionPoliciesSection';
import { api } from '@/lib/api-client';

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
    getRetentionPolicies: vi.fn(),
    previewRetentionPolicyImpact: vi.fn(),
    updateRetentionPolicy: vi.fn(),
  },
}));

type ApiMock = {
  getRetentionPolicies: ReturnType<typeof vi.fn>;
  previewRetentionPolicyImpact: ReturnType<typeof vi.fn>;
  updateRetentionPolicy: ReturnType<typeof vi.fn>;
};

const apiMock = api as unknown as ApiMock;

beforeEach(() => {
  toastSuccessMock.mockClear();
  toastErrorMock.mockClear();

  apiMock.getRetentionPolicies.mockResolvedValue({
    policies: [
      {
        key: 'audit_logs',
        description: 'Audit log retention',
        days: 90,
      },
    ],
  });
  apiMock.previewRetentionPolicyImpact.mockResolvedValue({
    estimate: {
      audit_log_entries: 125,
      job_records: 60,
      backup_files: 8,
    },
  });
  apiMock.updateRetentionPolicy.mockResolvedValue({ status: 'ok' });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('RetentionPoliciesSection', () => {
  it('renders impact preview text with parsed counts', async () => {
    const user = userEvent.setup();
    render(<RetentionPoliciesSection refreshSignal={0} />);

    const daysInput = await screen.findByDisplayValue('90');
    await user.clear(daysInput);
    await user.type(daysInput, '30');

    await user.click(screen.getByRole('button', { name: 'Preview impact' }));

    const previewText = await screen.findByTestId('retention-preview-text-audit_logs');
    expect(previewText.textContent).toContain('Changing from 90 to 30 days');
    expect(previewText.textContent).toContain('125 audit log entries');
    expect(previewText.textContent).toContain('60 job records');
    expect(previewText.textContent).toContain('8 backup files');
  });

  it('requires acknowledgment checkbox before save is enabled', async () => {
    const user = userEvent.setup();
    render(<RetentionPoliciesSection refreshSignal={0} />);

    const daysInput = await screen.findByDisplayValue('90');
    await user.clear(daysInput);
    await user.type(daysInput, '30');

    await user.click(screen.getByRole('button', { name: 'Preview impact' }));
    await screen.findByTestId('retention-preview-row-audit_logs');

    const saveButton = screen.getByRole('button', { name: 'Save' }) as HTMLButtonElement;
    expect(saveButton.disabled).toBe(true);

    await user.click(screen.getByLabelText(/I understand this change can permanently delete historical data/i));

    await waitFor(() => {
      expect(saveButton.disabled).toBe(false);
    });

    await user.click(saveButton);

    await waitFor(() => {
      expect(apiMock.updateRetentionPolicy).toHaveBeenCalledWith('audit_logs', { days: 30 });
    });
  });
});
