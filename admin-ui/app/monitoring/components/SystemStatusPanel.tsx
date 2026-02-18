import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { AlertTriangle, CheckCircle, Clock, Server } from 'lucide-react';
import type { SystemHealthStatus, SystemStatusItem } from '../types';

type SystemStatusPanelProps = {
  systemStatus: SystemStatusItem[];
};

const getSystemStatusIcon = (status: SystemHealthStatus) => {
  switch (status) {
    case 'healthy':
      return <CheckCircle className="h-8 w-8 text-green-500" aria-hidden="true" />;
    case 'warning':
      return <AlertTriangle className="h-8 w-8 text-yellow-500" aria-hidden="true" />;
    case 'critical':
      return <AlertTriangle className="h-8 w-8 text-red-500" aria-hidden="true" />;
    default:
      return <Clock className="h-8 w-8 text-muted-foreground" aria-hidden="true" />;
  }
};

const getStatusLabel = (status: SystemHealthStatus) => {
  switch (status) {
    case 'healthy':
      return 'Healthy';
    case 'warning':
      return 'Warning';
    case 'critical':
      return 'Critical';
    default:
      return 'Unknown';
  }
};

const getStatusBadge = (status: SystemHealthStatus) => {
  switch (status) {
    case 'healthy':
      return <Badge className="bg-green-500">Healthy</Badge>;
    case 'warning':
      return <Badge className="bg-yellow-500">Warning</Badge>;
    case 'critical':
      return <Badge variant="destructive">Critical</Badge>;
    default:
      return <Badge variant="secondary">Unknown</Badge>;
  }
};

const formatLastChecked = (value?: string): string => {
  if (!value) return 'Last checked: unavailable';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) return 'Last checked: unavailable';
  return `Last checked: ${parsed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
};

const formatResponseTime = (value?: number | null): string => {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) {
    return 'Response: unavailable';
  }
  return `Response: ${Math.round(value)} ms`;
};

export default function SystemStatusPanel({ systemStatus }: SystemStatusPanelProps) {
  const liveMode = useMemo<'polite' | 'assertive'>(() => {
    const hasDegradedStatus = systemStatus.some((item) => item.status === 'warning' || item.status === 'critical');
    return hasDegradedStatus ? 'assertive' : 'polite';
  }, [systemStatus]);

  const liveSummary = useMemo(() => {
    if (systemStatus.length === 0) {
      return 'System status unavailable.';
    }
    const criticalCount = systemStatus.filter((item) => item.status === 'critical').length;
    const warningCount = systemStatus.filter((item) => item.status === 'warning').length;
    const healthyCount = systemStatus.filter((item) => item.status === 'healthy').length;
    return `System health updated. ${criticalCount} critical, ${warningCount} warning, ${healthyCount} healthy services.`;
  }, [systemStatus]);

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Server className="h-5 w-5" />
          System Status
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div
          className="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
          role="status"
          aria-live={liveMode}
          aria-atomic="true"
          data-testid="system-status-live-region"
        >
          <p className="sr-only">{liveSummary}</p>
          {systemStatus.map((item) => (
            <div
              key={item.key}
              className="rounded-lg bg-muted/50 p-4"
              role="status"
              aria-label={`${item.label}: ${getStatusLabel(item.status)} - ${item.detail}. ${formatLastChecked(item.lastCheckedAt)}. ${formatResponseTime(item.responseTimeMs)}`}
              data-testid={`system-status-card-${item.key}`}
            >
              <div className="mb-2 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  {getSystemStatusIcon(item.status)}
                  <div className="font-semibold">{item.label}</div>
                </div>
                {getStatusBadge(item.status)}
              </div>
              <div className="space-y-1 text-sm text-muted-foreground">
                <p>{item.detail}</p>
                <p data-testid={`system-status-checked-${item.key}`}>{formatLastChecked(item.lastCheckedAt)}</p>
                <p data-testid={`system-status-response-${item.key}`}>{formatResponseTime(item.responseTimeMs)}</p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
