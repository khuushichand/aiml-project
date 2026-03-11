/* @vitest-environment jsdom */
import * as React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  readStoredAlertRules,
  writeStoredAlertRules,
} from '@/lib/monitoring-alerts';
import type { AlertRule } from './types';
import { useAlertRules } from './use-alert-rules';

type HarnessProps = {
  setSuccess: (message: string) => void;
  unsafeLocalToolsEnabled?: boolean;
};

function Harness({ setSuccess, unsafeLocalToolsEnabled = false }: HarnessProps) {
  const {
    alertRules,
    alertRuleDraft,
    alertRuleValidationErrors,
    alertRulesSaving,
    handleAlertRuleDraftChange,
    handleCreateAlertRule,
    handleDeleteAlertRule,
  } = useAlertRules({ setSuccess, unsafeLocalToolsEnabled });

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
  id: 'rule-seeded',
  metric: 'cpu',
  operator: '>',
  threshold: 90,
  durationMinutes: 5,
  severity: 'warning',
  createdAt: '2026-02-28T12:00:00.000Z',
};

describe('useAlertRules', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
    localStorage.clear();
  });

  it('hydrates alert rules from local storage on mount', async () => {
    writeStoredAlertRules([storedRule], localStorage);
    const setSuccess = vi.fn();

    render(<Harness setSuccess={setSuccess} unsafeLocalToolsEnabled />);

    await waitFor(() => {
      expect(screen.getByTestId('rules-count').textContent).toBe('1');
    });
  });

  it('surfaces validation errors for invalid drafts', async () => {
    const setSuccess = vi.fn();
    render(<Harness setSuccess={setSuccess} unsafeLocalToolsEnabled />);

    fireEvent.click(screen.getByRole('button', { name: 'Set Invalid Draft' }));
    fireEvent.click(screen.getByRole('button', { name: 'Create Rule' }));

    await waitFor(() => {
      expect(screen.getByTestId('threshold-error').textContent).toBe('Threshold must be a number.');
    });
    expect(screen.getByTestId('rules-count').textContent).toBe('0');
    expect(setSuccess).not.toHaveBeenCalledWith('Alert rule added');
  });

  it('creates a valid rule, resets draft, persists, and reports success', async () => {
    const setSuccess = vi.fn();
    render(<Harness setSuccess={setSuccess} unsafeLocalToolsEnabled />);

    fireEvent.click(screen.getByRole('button', { name: 'Set Valid Draft' }));
    fireEvent.click(screen.getByRole('button', { name: 'Create Rule' }));

    await waitFor(() => {
      expect(screen.getByTestId('rules-count').textContent).toBe('1');
    });
    expect(screen.getByTestId('draft-threshold').textContent).toBe('85');
    expect(screen.getByTestId('saving').textContent).toBe('false');
    expect(setSuccess).toHaveBeenCalledWith('Alert rule added');
    expect(readStoredAlertRules(localStorage)).toHaveLength(1);
  });

  it('deletes rules and persists removal', async () => {
    writeStoredAlertRules([storedRule], localStorage);
    const setSuccess = vi.fn();
    render(<Harness setSuccess={setSuccess} unsafeLocalToolsEnabled />);

    await waitFor(() => {
      expect(screen.getByTestId('rules-count').textContent).toBe('1');
    });
    fireEvent.click(screen.getByRole('button', { name: 'Delete First Rule' }));

    await waitFor(() => {
      expect(screen.getByTestId('rules-count').textContent).toBe('0');
    });
    expect(setSuccess).toHaveBeenCalledWith('Alert rule deleted');
    expect(readStoredAlertRules(localStorage)).toHaveLength(0);
  });

  it('does not hydrate or mutate locally stored rules in safe mode', async () => {
    writeStoredAlertRules([storedRule], localStorage);
    const setSuccess = vi.fn();

    render(<Harness setSuccess={setSuccess} unsafeLocalToolsEnabled={false} />);

    await waitFor(() => {
      expect(screen.getByTestId('rules-count').textContent).toBe('0');
    });

    fireEvent.click(screen.getByRole('button', { name: 'Set Valid Draft' }));
    fireEvent.click(screen.getByRole('button', { name: 'Create Rule' }));

    await waitFor(() => {
      expect(screen.getByTestId('rules-count').textContent).toBe('0');
    });
    expect(setSuccess).not.toHaveBeenCalled();
    expect(readStoredAlertRules(localStorage)).toHaveLength(1);
  });
});
