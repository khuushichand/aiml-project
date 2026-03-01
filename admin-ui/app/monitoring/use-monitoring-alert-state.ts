import { useEffect, useRef, useState } from 'react';
import {
  readStoredAlertHistory,
  writeStoredAlertHistory,
} from '@/lib/monitoring-alerts';
import type {
  AlertAssignableUser,
  AlertHistoryEntry,
  SystemAlert,
} from './types';

export const useMonitoringAlertState = () => {
  const [alerts, setAlerts] = useState<SystemAlert[]>([]);
  const [assignableUsers, setAssignableUsers] = useState<AlertAssignableUser[]>([]);
  const [showSnoozedAlerts, setShowSnoozedAlerts] = useState(false);
  const [alertHistory, setAlertHistory] = useState<AlertHistoryEntry[]>(() => readStoredAlertHistory());

  const alertHistoryPersistReadyRef = useRef(false);
  const alertsRef = useRef<SystemAlert[]>([]);
  const alertHistoryRef = useRef<AlertHistoryEntry[]>([]);

  useEffect(() => {
    if (!alertHistoryPersistReadyRef.current) {
      alertHistoryPersistReadyRef.current = true;
      return;
    }
    writeStoredAlertHistory(alertHistory);
  }, [alertHistory]);

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
