/* @vitest-environment jsdom */
import * as React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { AlertRule } from './types';
import { type AlertRulesApiClient, useAlertRules } from './use-alert-rules';

type HarnessProps = {
  apiClient: AlertRulesApiClient;
  setError: (message: string) => void;
  setSuccess: (message: string) => void;
};

function Harness({ apiClient, setError, setSuccess }: HarnessProps) {
  const {
    alertRules,
    alertRuleDraft,
    alertRuleValidationErrors,
    alertRulesSaving,
    handleAlertRuleDraftChange,
    handleCreateAlertRule,
    handleDeleteAlertRule,
  } = useAlertRules({ apiClient, setError, setSuccess });

  return (
    <div>
      <div data-testid="rules-count">{alertRules.length}</div>
      <div data-testid="draft-threshold">{alertRuleDraft.threshold}</div>
      <div data-testid="threshold-error">{alertRuleValidationErrors.threshold ?? ''}</div>
      <div data-testid="saving">{String(alertRulesSaving)}</div>
      <button
        onClick={() => handleAlertRuleDraftChange({
          ...alertRuleDraft,
          threshold: 'abc',
        })}
      >
        Set Invalid Draft
      </button>
      <button
        onClick={() => handleAlertRuleDraftChange({
          metric: 'cpu',
          operator: '>',
          threshold: '85',
          durationMinutes: '5',
          severity: 'warning',
        })}
      >
        Set Valid Draft
      </button>
      <button onClick={() => handleCreateAlertRule()}>Create Rule</button>
      <button onClick={() => {
        if (alertRules[0]) {
          handleDeleteAlertRule(alertRules[0]);
        }
      }}
      >
        Delete First Rule
      </button>
    </div>
  );
}

const storedRule: AlertRule = {
  id: '1',
  metric: 'cpu',
  operator: '>',
  threshold: 90,
  durationMinutes: 5,
  severity: 'warning',
  createdAt: '2026-02-28T12:00:00.000Z',
};

type AlertRulesApiClientMock = AlertRulesApiClient & {
  getAdminAlertRules: ReturnType<typeof vi.fn>;
  createAdminAlertRule: ReturnType<typeof vi.fn>;
  deleteAdminAlertRule: ReturnType<typeof vi.fn>;
};

const buildApiClient = (): AlertRulesApiClientMock => ({
  getAdminAlertRules: vi.fn().mockResolvedValue({ items: [] }),
  createAdminAlertRule: vi.fn().mockResolvedValue({ item: storedRule }),
  deleteAdminAlertRule: vi.fn().mockResolvedValue({ status: 'deleted', id: Number(storedRule.id) }),
});

describe('useAlertRules', () => {
  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  it('hydrates alert rules from the backend on mount', async () => {
    const apiClient = buildApiClient();
    apiClient.getAdminAlertRules.mockResolvedValue({ items: [storedRule] });
    const setError = vi.fn();
    const setSuccess = vi.fn();

    render(<Harness apiClient={apiClient} setError={setError} setSuccess={setSuccess} />);

    await waitFor(() => {
      expect(screen.getByTestId('rules-count').textContent).toBe('1');
    });
    expect(apiClient.getAdminAlertRules).toHaveBeenCalledTimes(1);
    expect(setError).not.toHaveBeenCalledWith('Failed to load alert rules');
  });

  it('surfaces validation errors for invalid drafts', async () => {
    const apiClient = buildApiClient();
    const setError = vi.fn();
    const setSuccess = vi.fn();
    render(<Harness apiClient={apiClient} setError={setError} setSuccess={setSuccess} />);

    fireEvent.click(screen.getByRole('button', { name: 'Set Invalid Draft' }));
    fireEvent.click(screen.getByRole('button', { name: 'Create Rule' }));

    await waitFor(() => {
      expect(screen.getByTestId('threshold-error').textContent).toBe('Threshold must be a number.');
    });
    expect(screen.getByTestId('rules-count').textContent).toBe('0');
    expect(setSuccess).not.toHaveBeenCalledWith('Alert rule added');
  });

  it('creates a valid rule through the backend and reports success', async () => {
    const apiClient = buildApiClient();
    const setError = vi.fn();
    const setSuccess = vi.fn();
    render(<Harness apiClient={apiClient} setError={setError} setSuccess={setSuccess} />);

    fireEvent.click(screen.getByRole('button', { name: 'Set Valid Draft' }));
    fireEvent.click(screen.getByRole('button', { name: 'Create Rule' }));

    await waitFor(() => {
      expect(screen.getByTestId('rules-count').textContent).toBe('1');
    });
    expect(apiClient.createAdminAlertRule).toHaveBeenCalledWith({
      metric: 'cpu',
      operator: '>',
      threshold: 85,
      duration_minutes: 5,
      severity: 'warning',
      enabled: true,
    });
    expect(screen.getByTestId('draft-threshold').textContent).toBe('85');
    expect(screen.getByTestId('saving').textContent).toBe('false');
    expect(setSuccess).toHaveBeenCalledWith('Alert rule added');
    expect(setError).not.toHaveBeenCalledWith(expect.stringContaining('Failed to create'));
  });

  it('deletes rules through the backend', async () => {
    const apiClient = buildApiClient();
    apiClient.getAdminAlertRules.mockResolvedValue({ items: [storedRule] });
    const setError = vi.fn();
    const setSuccess = vi.fn();
    render(<Harness apiClient={apiClient} setError={setError} setSuccess={setSuccess} />);

    await waitFor(() => {
      expect(screen.getByTestId('rules-count').textContent).toBe('1');
    });
    fireEvent.click(screen.getByRole('button', { name: 'Delete First Rule' }));

    await waitFor(() => {
      expect(screen.getByTestId('rules-count').textContent).toBe('0');
    });
    expect(apiClient.deleteAdminAlertRule).toHaveBeenCalledWith('1');
    expect(setSuccess).toHaveBeenCalledWith('Alert rule deleted');
    expect(setError).not.toHaveBeenCalledWith(expect.stringContaining('Failed to delete'));
  });
});
