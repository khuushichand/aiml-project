'use client';

import { Button } from '@/components/ui/button';
import { RefreshCw } from 'lucide-react';

type DashboardHeaderProps = {
  serverStatusLabel: string;
  serverStatusDotClass: string;
  checkedAtLabel?: string | null;
  uptimePercent: number | null;
  lastIncidentAt: string | null;
  uptimeWindowDays?: number;
  loading: boolean;
  onRefresh: () => Promise<void> | void;
  autoRefreshEnabled?: boolean;
  onToggleAutoRefresh?: () => void;
  lastRefreshedAt?: Date | null;
};

const formatRelativeTime = (date: Date): string => {
  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (seconds < 10) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.round(minutes / 60)}h ago`;
};

const formatUptimeValue = (value: number | null) => {
  if (value === null || !Number.isFinite(value)) {
    return 'N/A';
  }
  return `${value.toFixed(2)}%`;
};

const formatIncidentTimestamp = (timestamp: string | null) => {
  if (!timestamp) return 'No incidents recorded';
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) return 'Unavailable';
  return parsed.toLocaleString([], {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export const DashboardHeader = ({
  serverStatusLabel,
  serverStatusDotClass,
  checkedAtLabel,
  uptimePercent,
  lastIncidentAt,
  uptimeWindowDays = 30,
  loading,
  onRefresh,
  autoRefreshEnabled,
  onToggleAutoRefresh,
  lastRefreshedAt,
}: DashboardHeaderProps) => (
  <div className="mb-8 flex items-center justify-between">
    <div>
      <h1 className="text-3xl font-bold">Dashboard</h1>
      <p className="text-muted-foreground">Overview of your tldw_server instance</p>
    </div>
    <div className="flex items-center gap-3">
      <div className="flex flex-wrap items-center gap-2 rounded-full border px-3 py-1 text-sm">
        <span className={`h-2 w-2 rounded-full ${serverStatusDotClass}`} />
        <span className="font-medium">{serverStatusLabel}</span>
        {checkedAtLabel && (
          <span className="text-xs text-muted-foreground">
            Checked {checkedAtLabel}
          </span>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2 rounded-full border px-3 py-1 text-sm">
        <span className="font-medium">Uptime {loading ? '...' : formatUptimeValue(uptimePercent)}</span>
        <span className="text-xs text-muted-foreground">{uptimeWindowDays}d window</span>
        <span className="text-xs text-muted-foreground">
          Last incident {loading ? 'loading...' : formatIncidentTimestamp(lastIncidentAt)}
        </span>
      </div>
      <Button
        variant="outline"
        onClick={() => {
          void onRefresh();
        }}
        disabled={loading}
      >
        <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
        Refresh
      </Button>
      {onToggleAutoRefresh && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {lastRefreshedAt && (
            <span>Updated {formatRelativeTime(lastRefreshedAt)}</span>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleAutoRefresh}
            className="text-xs h-7 px-2"
          >
            Auto: {autoRefreshEnabled ? 'ON' : 'OFF'}
          </Button>
        </div>
      )}
    </div>
  </div>
);
