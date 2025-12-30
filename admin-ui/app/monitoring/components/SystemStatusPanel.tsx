import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertTriangle, CheckCircle, Clock, Server } from 'lucide-react';
import type { SystemHealthStatus, SystemStatusItem } from '../types';

type SystemStatusPanelProps = {
  systemStatus: SystemStatusItem[];
};

const getSystemStatusIcon = (status: SystemHealthStatus) => {
  switch (status) {
    case 'healthy':
      return <CheckCircle className="h-8 w-8 text-green-500" />;
    case 'warning':
      return <AlertTriangle className="h-8 w-8 text-yellow-500" />;
    case 'critical':
      return <AlertTriangle className="h-8 w-8 text-red-500" />;
    default:
      return <Clock className="h-8 w-8 text-muted-foreground" />;
  }
};

export default function SystemStatusPanel({ systemStatus }: SystemStatusPanelProps) {
  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Server className="h-5 w-5" />
          System Status
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 md:grid-cols-4">
          {systemStatus.map((item) => (
            <div key={item.key} className="flex items-center gap-3 p-4 rounded-lg bg-muted/50">
              {getSystemStatusIcon(item.status)}
              <div>
                <div className="font-semibold">{item.label}</div>
                <div className="text-sm text-muted-foreground">{item.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
