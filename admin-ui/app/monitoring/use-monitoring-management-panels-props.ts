import { useCallback, useMemo, type ComponentProps } from 'react';
import MonitoringManagementPanels from './components/MonitoringManagementPanels';
import type {
  AlertAssignableUser,
  AlertHistoryEntry,
  AlertRule,
  AlertRuleDraft,
  AlertRuleValidationErrors,
  NotificationSettings,
  RecentNotification,
  SnoozeDurationOption,
  SystemAlert,
  SystemStatusItem,
  Watchlist,
  WatchlistDraft,
} from './types';

type UseMonitoringManagementPanelsPropsArgs = {
  alertRules: AlertRule[];
  alertRuleDraft: AlertRuleDraft;
  alertRuleValidationErrors: AlertRuleValidationErrors;
  alertRulesSaving: boolean;
  handleAlertRuleDraftChange: (draft: AlertRuleDraft) => void;
  handleCreateAlertRule: () => void;
  handleDeleteAlertRule: (rule: AlertRule) => void;
  alerts: SystemAlert[];
  alertHistory: AlertHistoryEntry[];
  showSnoozedAlerts: boolean;
  setShowSnoozedAlerts: (updater: (prev: boolean) => boolean) => void;
  assignableUsers: AlertAssignableUser[];
  loading: boolean;
  handleAcknowledgeAlert: (alert: SystemAlert) => void;
  handleDismissAlert: (alert: SystemAlert) => void;
  handleAssignAlert: (alert: SystemAlert, userId: string) => void;
  handleSnoozeAlert: (alert: SystemAlert, duration: SnoozeDurationOption) => void;
  handleEscalateAlert: (alert: SystemAlert) => void;
  watchlists: Watchlist[];
  showCreateWatchlist: boolean;
  setShowCreateWatchlist: (open: boolean) => void;
  newWatchlist: WatchlistDraft;
  setNewWatchlist: (next: WatchlistDraft) => void;
  handleCreateWatchlist: () => void;
  handleDeleteWatchlist: (watchlist: Watchlist) => void;
  deletingWatchlistId: string | null;
  notificationSettings: NotificationSettings | null;
  recentNotifications: RecentNotification[];
  notificationsSaving: boolean;
  canSaveNotificationSettings: boolean;
  handleSaveNotificationSettings: (settings: NotificationSettings) => Promise<boolean> | boolean;
  handleTestNotification: (payload?: { message?: string; severity?: string }) => Promise<void> | void;
  systemStatus: SystemStatusItem[];
};

export const useMonitoringManagementPanelsProps = ({
  alertRules,
  alertRuleDraft,
  alertRuleValidationErrors,
  alertRulesSaving,
  handleAlertRuleDraftChange,
  handleCreateAlertRule,
  handleDeleteAlertRule,
  alerts,
  alertHistory,
  showSnoozedAlerts,
  setShowSnoozedAlerts,
  assignableUsers,
  loading,
  handleAcknowledgeAlert,
  handleDismissAlert,
  handleAssignAlert,
  handleSnoozeAlert,
  handleEscalateAlert,
  watchlists,
  showCreateWatchlist,
  setShowCreateWatchlist,
  newWatchlist,
  setNewWatchlist,
  handleCreateWatchlist,
  handleDeleteWatchlist,
  deletingWatchlistId,
  notificationSettings,
  recentNotifications,
  notificationsSaving,
  canSaveNotificationSettings,
  handleSaveNotificationSettings,
  handleTestNotification,
  systemStatus,
}: UseMonitoringManagementPanelsPropsArgs): ComponentProps<typeof MonitoringManagementPanels> => {
  const handleToggleShowSnoozed = useCallback(() => {
    setShowSnoozedAlerts((prev) => !prev);
  }, [setShowSnoozedAlerts]);

  return useMemo(
    () => ({
      alertRulesPanelProps: {
        rules: alertRules,
        draft: alertRuleDraft,
        errors: alertRuleValidationErrors,
        saving: alertRulesSaving,
        onDraftChange: handleAlertRuleDraftChange,
        onCreateRule: handleCreateAlertRule,
        onDeleteRule: handleDeleteAlertRule,
      },
      alertsPanelProps: {
        alerts,
        history: alertHistory,
        showSnoozed: showSnoozedAlerts,
        assignableUsers,
        loading,
        onToggleShowSnoozed: handleToggleShowSnoozed,
        onAcknowledge: handleAcknowledgeAlert,
        onDismiss: handleDismissAlert,
        onAssign: handleAssignAlert,
        onSnooze: handleSnoozeAlert,
        onEscalate: handleEscalateAlert,
      },
      watchlistsPanelProps: {
        watchlists,
        loading,
        showCreateWatchlist,
        setShowCreateWatchlist,
        newWatchlist,
        setNewWatchlist,
        onCreate: handleCreateWatchlist,
        onDelete: handleDeleteWatchlist,
        deletingWatchlistId,
      },
      notificationsPanelProps: {
        settings: notificationSettings,
        recentNotifications,
        loading,
        saving: notificationsSaving,
        canSave: canSaveNotificationSettings,
        onSave: handleSaveNotificationSettings,
        onTest: handleTestNotification,
      },
      systemStatusPanelProps: {
        systemStatus,
      },
    }),
    [
      alertHistory,
      alertRuleDraft,
      alertRuleValidationErrors,
      alertRules,
      alertRulesSaving,
      alerts,
      assignableUsers,
      canSaveNotificationSettings,
      deletingWatchlistId,
      handleAcknowledgeAlert,
      handleAlertRuleDraftChange,
      handleAssignAlert,
      handleCreateAlertRule,
      handleCreateWatchlist,
      handleDeleteAlertRule,
      handleDeleteWatchlist,
      handleDismissAlert,
      handleEscalateAlert,
      handleSaveNotificationSettings,
      handleSnoozeAlert,
      handleTestNotification,
      handleToggleShowSnoozed,
      loading,
      newWatchlist,
      notificationSettings,
      notificationsSaving,
      recentNotifications,
      setNewWatchlist,
      setShowCreateWatchlist,
      showCreateWatchlist,
      showSnoozedAlerts,
      systemStatus,
      watchlists,
    ]
  );
};
