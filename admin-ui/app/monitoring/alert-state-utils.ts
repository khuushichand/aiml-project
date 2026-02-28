import type { SystemAlert } from './types';

export const mergeAlertsWithLocalState = (
  incoming: SystemAlert[],
  existing: SystemAlert[]
): SystemAlert[] => {
  const existingById = new Map(existing.map((alert) => [alert.id, alert]));
  return incoming.map((alert) => {
    const prev = existingById.get(alert.id);
    return {
      ...alert,
      assigned_to: prev?.assigned_to ?? alert.assigned_to,
      snoozed_until: prev?.snoozed_until ?? alert.snoozed_until,
      metadata: prev?.metadata ?? alert.metadata,
    };
  });
};

export const markAlertAcknowledged = (
  alerts: SystemAlert[],
  alertId: string,
  acknowledgedAt: string
): SystemAlert[] => (
  alerts.map((item) => (
    item.id === alertId
      ? {
        ...item,
        acknowledged: true,
        acknowledged_at: acknowledgedAt,
      }
      : item
  ))
);

export const removeAlertById = (alerts: SystemAlert[], alertId: string): SystemAlert[] => (
  alerts.filter((item) => item.id !== alertId)
);

export const setAlertAssignment = (
  alerts: SystemAlert[],
  alertId: string,
  assignedTo?: string
): SystemAlert[] => (
  alerts.map((item) => (
    item.id === alertId
      ? { ...item, assigned_to: assignedTo }
      : item
  ))
);

export const setAlertSnoozeUntil = (
  alerts: SystemAlert[],
  alertId: string,
  snoozedUntil: string
): SystemAlert[] => (
  alerts.map((item) => (
    item.id === alertId
      ? { ...item, snoozed_until: snoozedUntil }
      : item
  ))
);

export const escalateAlertSeverity = (
  alerts: SystemAlert[],
  alertId: string
): SystemAlert[] => (
  alerts.map((item) => (
    item.id === alertId && item.severity !== 'critical'
      ? { ...item, severity: 'critical' }
      : item
  ))
);
