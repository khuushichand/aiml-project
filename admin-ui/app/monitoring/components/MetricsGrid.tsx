import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import type { Metric } from '../types';

type MetricsGridProps = {
  metrics: Metric[];
  loading: boolean;
};

const getStatusIcon = (status?: string) => {
  switch (status) {
    case 'healthy':
    case 'active':
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    case 'warning':
      return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    case 'critical':
    case 'error':
      return <AlertTriangle className="h-4 w-4 text-red-500" />;
    default:
      return <Clock className="h-4 w-4 text-muted-foreground" />;
  }
};

export default function MetricsGrid({ metrics, loading }: MetricsGridProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-6">
      {loading ? (
        <Card className="col-span-full">
          <CardContent className="pt-6">
            <div className="text-center text-muted-foreground">Loading metrics...</div>
          </CardContent>
        </Card>
      ) : metrics.length === 0 ? (
        <Card className="col-span-full">
          <CardContent className="pt-6">
            <div className="text-center text-muted-foreground">
              No metrics available. The server may not expose metrics.
            </div>
          </CardContent>
        </Card>
      ) : (
        metrics.slice(0, 8).map((metric) => (
          <Card key={metric.name}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                {metric.name.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())}
              </CardTitle>
              {getStatusIcon(metric.status)}
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {typeof metric.value === 'number' ? metric.value.toLocaleString() : metric.value}
                {metric.unit && (
                  <span className="text-sm font-normal text-muted-foreground ml-1">{metric.unit}</span>
                )}
              </div>
            </CardContent>
          </Card>
        ))
      )}
    </div>
  );
}
