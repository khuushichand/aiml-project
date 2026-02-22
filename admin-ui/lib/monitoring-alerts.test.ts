import { describe, expect, it } from 'vitest';
import {
  DEFAULT_ALERT_RULE_DRAFT,
  ensureTriggeredHistoryEntries,
  formatSnoozeCountdown,
  validateAlertRuleDraft,
} from './monitoring-alerts';

describe('validateAlertRuleDraft', () => {
  it('rejects invalid threshold and duration values', () => {
    const result = validateAlertRuleDraft({
      ...DEFAULT_ALERT_RULE_DRAFT,
      threshold: '120',
      durationMinutes: '2',
    });
    expect(result.valid).toBe(false);
    expect(result.errors.threshold).toBe(
      'Threshold for utilization metrics must be between 0 and 100.'
    );
    expect(result.errors.durationMinutes).toBe('Select a valid duration.');
  });

  it('accepts valid rule drafts', () => {
    const result = validateAlertRuleDraft({
      ...DEFAULT_ALERT_RULE_DRAFT,
      metric: 'throughput',
      threshold: '150',
      durationMinutes: '15',
      severity: 'critical',
    });
    expect(result.valid).toBe(true);
    expect(result.errors).toEqual({});
  });
});

describe('formatSnoozeCountdown', () => {
  it('formats minute-based countdowns', () => {
    const now = new Date('2026-02-17T12:00:00.000Z');
    expect(formatSnoozeCountdown('2026-02-17T12:15:00.000Z', now)).toBe('15m remaining');
  });

  it('formats hour+minute countdowns', () => {
    const now = new Date('2026-02-17T12:00:00.000Z');
    expect(formatSnoozeCountdown('2026-02-17T13:30:00.000Z', now)).toBe('1h 30m remaining');
  });

  it('returns expired for completed snoozes', () => {
    const now = new Date('2026-02-17T12:00:00.000Z');
    expect(formatSnoozeCountdown('2026-02-17T11:59:00.000Z', now)).toBe('Expired');
  });
});

describe('ensureTriggeredHistoryEntries', () => {
  it('adds one triggered event per alert id if missing', () => {
    const history = ensureTriggeredHistoryEntries([], [
      {
        id: 'alert-1',
        severity: 'warning',
        message: 'CPU high',
        timestamp: '2026-02-17T10:00:00.000Z',
        acknowledged: false,
      },
      {
        id: 'alert-2',
        severity: 'critical',
        message: 'Queue depth rising',
        timestamp: '2026-02-17T10:05:00.000Z',
        acknowledged: false,
      },
    ]);
    expect(history).toHaveLength(2);
    expect(history.every((entry) => entry.action === 'triggered')).toBe(true);
  });
});
