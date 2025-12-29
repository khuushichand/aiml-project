'use client';

import { Button } from '@/components/ui/button';
import { RefreshCw } from 'lucide-react';

type DashboardHeaderProps = {
  serverStatusLabel: string;
  serverStatusDotClass: string;
  checkedAtLabel?: string | null;
  loading: boolean;
  onRefresh: () => Promise<void> | void;
};

export const DashboardHeader = ({
  serverStatusLabel,
  serverStatusDotClass,
  checkedAtLabel,
  loading,
  onRefresh,
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
    </div>
  </div>
);
