import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Activity } from 'lucide-react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { MetricsHistoryPoint } from '../types';

type MetricsChartProps = {
  metricsHistory: MetricsHistoryPoint[];
};

export default function MetricsChart({ metricsHistory }: MetricsChartProps) {
  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-5 w-5" />
          System Metrics (24h)
        </CardTitle>
        <CardDescription>CPU, memory usage, and request volume over time</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={metricsHistory}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis dataKey="time" className="text-xs" />
              <YAxis className="text-xs" />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--background))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                }}
              />
              <Area
                type="monotone"
                dataKey="cpu"
                stroke="#3b82f6"
                fill="#3b82f6"
                fillOpacity={0.2}
                name="CPU %"
              />
              <Area
                type="monotone"
                dataKey="memory"
                stroke="#10b981"
                fill="#10b981"
                fillOpacity={0.2}
                name="Memory %"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
