import { useState } from 'react';
import type { NotificationSettings, RecentNotification } from './types';

export type MonitoringNotificationSettingsStatus = 'pending' | 'fulfilled' | 'rejected';

export const useMonitoringNotificationState = () => {
  const [notificationSettings, setNotificationSettings] = useState<NotificationSettings | null>(null);
  const [recentNotifications, setRecentNotifications] = useState<RecentNotification[]>([]);
  const [notificationSettingsStatus, setNotificationSettingsStatus] =
    useState<MonitoringNotificationSettingsStatus>('pending');

  return {
    notificationSettings,
    setNotificationSettings,
    recentNotifications,
    setRecentNotifications,
    notificationSettingsStatus,
    setNotificationSettingsStatus,
    canSaveNotificationSettings: notificationSettingsStatus === 'fulfilled',
  };
};
