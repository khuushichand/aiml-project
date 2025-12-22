import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Bell, Check, CheckCircle, X } from 'lucide-react';
import type { SystemAlert } from '../types';

type AlertsPanelProps = {
  alerts: SystemAlert[];
  loading: boolean;
  onAcknowledge: (alert: SystemAlert) => void;
  onDismiss: (alert: SystemAlert) => void;
};

const getSeverityBadge = (severity: string) => {
  switch (severity) {
    case 'critical':
      return <Badge variant="destructive">Critical</Badge>;
    case 'error':
      return <Badge variant="destructive">Error</Badge>;
    case 'warning':
      return <Badge className="bg-yellow-500">Warning</Badge>;
    default:
      return <Badge variant="secondary">Info</Badge>;
  }
};

const formatTimestamp = (timestamp?: string) => {
  if (!timestamp) return '-';
  return new Date(timestamp).toLocaleString();
};

export default function AlertsPanel({
  alerts,
  loading,
  onAcknowledge,
  onDismiss,
}: AlertsPanelProps) {
  const activeCount = alerts.filter((alert) => !alert.acknowledged).length;
  const acknowledgedCount = alerts.length - activeCount;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Alerts
          </CardTitle>
          <CardDescription>
            {activeCount} active, {acknowledgedCount} acknowledged
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="text-center text-muted-foreground py-8">Loading...</div>
        ) : alerts.length === 0 ? (
          <div className="text-center text-muted-foreground py-8">
            <CheckCircle className="h-12 w-12 mx-auto mb-2 text-green-500" />
            <p>No alerts - system is healthy</p>
          </div>
        ) : (
          <div className="space-y-3">
            {alerts.slice(0, 10).map((alert) => (
              <div
                key={alert.id}
                className={`flex items-start justify-between p-3 rounded-lg border ${
                  alert.acknowledged ? 'bg-muted/30 opacity-60' : 'bg-background'
                }`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    {getSeverityBadge(alert.severity)}
                    {alert.acknowledged && (
                      <Badge variant="outline" className="text-xs">
                        <Check className="mr-1 h-3 w-3" />
                        Acknowledged
                      </Badge>
                    )}
                  </div>
                  <p className="text-sm font-medium truncate">{alert.message}</p>
                  <p className="text-xs text-muted-foreground">
                    {alert.source && `${alert.source} • `}
                    {formatTimestamp(alert.timestamp)}
                  </p>
                </div>
                {!alert.acknowledged && (
                  <div className="flex gap-1 ml-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onAcknowledge(alert)}
                      title="Acknowledge"
                    >
                      <Check className="h-4 w-4 text-green-500" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onDismiss(alert)}
                      title="Dismiss"
                    >
                      <X className="h-4 w-4 text-red-500" />
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
