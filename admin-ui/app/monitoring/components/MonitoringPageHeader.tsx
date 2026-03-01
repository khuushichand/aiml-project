import { Button } from '@/components/ui/button';
import { RefreshCw } from 'lucide-react';

type MonitoringPageHeaderProps = {
  lastUpdated: Date | null;
  loading: boolean;
  onRefresh: () => Promise<void> | void;
};

export default function MonitoringPageHeader({
  lastUpdated,
  loading,
  onRefresh,
}: MonitoringPageHeaderProps) {
  return (
    <div className="mb-8 flex items-center justify-between">
      <div>
        <h1 className="text-3xl font-bold">Monitoring</h1>
        <p className="text-muted-foreground">System health, metrics, and alerts</p>
      </div>
      <div className="flex items-center gap-4">
        {lastUpdated ? (
          <span className="text-sm text-muted-foreground" aria-live="polite">
            Last updated: {lastUpdated.toLocaleTimeString()}
          </span>
        ) : null}
        <Button variant="outline" onClick={onRefresh} disabled={loading}>
          <RefreshCw
            className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`}
            aria-hidden="true"
          />
          Refresh
        </Button>
      </div>
    </div>
  );
}
