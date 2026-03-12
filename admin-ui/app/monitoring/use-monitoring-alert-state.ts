import { useEffect, useRef, useState } from 'react';
import type {
  AlertAssignableUser,
  AlertHistoryEntry,
  SystemAlert,
} from './types';

export const useMonitoringAlertState = () => {
  const [alerts, setAlerts] = useState<SystemAlert[]>([]);
  const [assignableUsers, setAssignableUsers] = useState<AlertAssignableUser[]>([]);
  const [showSnoozedAlerts, setShowSnoozedAlerts] = useState(false);
  const [alertHistory, setAlertHistory] = useState<AlertHistoryEntry[]>([]);
  const alertsRef = useRef<SystemAlert[]>([]);
  const alertHistoryRef = useRef<AlertHistoryEntry[]>([]);

  useEffect(() => {
    alertsRef.current = alerts;
  }, [alerts]);

  useEffect(() => {
    alertHistoryRef.current = alertHistory;
  }, [alertHistory]);

  return {
    alerts,
    setAlerts,
    alertsRef,
    assignableUsers,
    setAssignableUsers,
    showSnoozedAlerts,
    setShowSnoozedAlerts,
    alertHistory,
    setAlertHistory,
    alertHistoryRef,
  };
};
