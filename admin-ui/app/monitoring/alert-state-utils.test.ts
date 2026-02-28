import { describe, expect, it } from 'vitest';
import {
  escalateAlertSeverity,
  markAlertAcknowledged,
  mergeAlertsWithLocalState,
  removeAlertById,
  setAlertAssignment,
  setAlertSnoozeUntil,
} from './alert-state-utils';
import type { SystemAlert } from './types';

const makeAlert = (overrides: Partial<SystemAlert> = {}): SystemAlert => ({
  id: 'alert-1',
  severity: 'warning',
  message: 'High CPU',
  source: 'system',
  timestamp: '2026-02-27T10:00:00Z',
  acknowledged: false,
  ...overrides,
});

describe('alert-state-utils', () => {
  it('preserves local assignment/snooze/metadata when refreshing alerts', () => {
    const existing = [
      makeAlert({
        id: 'a1',
        assigned_to: 'user-2',
        snoozed_until: '2026-02-27T12:00:00Z',
        metadata: { escalation: 'manual' },
      }),
    ];
    const incoming = [
      makeAlert({
        id: 'a1',
        assigned_to: 'user-1',
        snoozed_until: undefined,
        metadata: { escalation: 'auto' },
      }),
      makeAlert({ id: 'a2' }),
    ];

    expect(mergeAlertsWithLocalState(incoming, existing)).toEqual([
      makeAlert({
        id: 'a1',
        assigned_to: 'user-2',
        snoozed_until: '2026-02-27T12:00:00Z',
        metadata: { escalation: 'manual' },
      }),
      makeAlert({ id: 'a2' }),
    ]);
  });

  it('marks an alert acknowledged with timestamp', () => {
    const updated = markAlertAcknowledged([makeAlert({ id: 'a1' }), makeAlert({ id: 'a2' })], 'a2', '2026-02-27T10:05:00Z');

    expect(updated).toEqual([
      makeAlert({ id: 'a1' }),
      makeAlert({ id: 'a2', acknowledged: true, acknowledged_at: '2026-02-27T10:05:00Z' }),
    ]);
  });

  it('removes an alert by id', () => {
    const updated = removeAlertById([makeAlert({ id: 'a1' }), makeAlert({ id: 'a2' })], 'a1');

    expect(updated).toEqual([makeAlert({ id: 'a2' })]);
  });

  it('updates alert assignment and supports unassign', () => {
    const assigned = setAlertAssignment([makeAlert({ id: 'a1' })], 'a1', 'user-9');
    expect(assigned).toEqual([makeAlert({ id: 'a1', assigned_to: 'user-9' })]);

    const unassigned = setAlertAssignment(assigned, 'a1', undefined);
    expect(unassigned).toEqual([makeAlert({ id: 'a1', assigned_to: undefined })]);
  });

  it('updates snoozed-until value', () => {
    const updated = setAlertSnoozeUntil([makeAlert({ id: 'a1' })], 'a1', '2026-02-27T14:00:00Z');

    expect(updated).toEqual([makeAlert({ id: 'a1', snoozed_until: '2026-02-27T14:00:00Z' })]);
  });

  it('escalates non-critical alerts to critical and leaves critical unchanged', () => {
    const escalated = escalateAlertSeverity([
      makeAlert({ id: 'a1', severity: 'warning' }),
      makeAlert({ id: 'a2', severity: 'critical' }),
    ], 'a1');

    expect(escalated).toEqual([
      makeAlert({ id: 'a1', severity: 'critical' }),
      makeAlert({ id: 'a2', severity: 'critical' }),
    ]);
  });
});
