import type { ComponentProps } from 'react';
import AlertRulesPanel from './AlertRulesPanel';
import AlertsPanel from './AlertsPanel';
import NotificationsPanel from './NotificationsPanel';
import SystemStatusPanel from './SystemStatusPanel';
import WatchlistsPanel from './WatchlistsPanel';

type MonitoringManagementPanelsProps = {
  alertRulesPanelProps: ComponentProps<typeof AlertRulesPanel>;
  alertsPanelProps: ComponentProps<typeof AlertsPanel>;
  watchlistsPanelProps: ComponentProps<typeof WatchlistsPanel>;
  notificationsPanelProps: ComponentProps<typeof NotificationsPanel>;
  systemStatusPanelProps: ComponentProps<typeof SystemStatusPanel>;
};

export default function MonitoringManagementPanels({
  alertRulesPanelProps,
  alertsPanelProps,
  watchlistsPanelProps,
  notificationsPanelProps,
  systemStatusPanelProps,
}: MonitoringManagementPanelsProps) {
  return (
    <>
      <div className="mb-6">
        <AlertRulesPanel {...alertRulesPanelProps} />
        <p className="mt-2 text-xs text-muted-foreground">
          Alert rules are stored locally until a backend alert-rules endpoint is available.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <AlertsPanel {...alertsPanelProps} />
        <WatchlistsPanel {...watchlistsPanelProps} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2 mt-6">
        <NotificationsPanel {...notificationsPanelProps} />
        <SystemStatusPanel {...systemStatusPanelProps} />
      </div>
    </>
  );
}
