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
        <CardDescription>CPU and memory usage over time</CardDescription>
      </CardHeader>
      <CardContent>
        {metricsHistory.length === 0 ? (
          <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
            Collecting metrics data...
          </div>
        ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%" minHeight={1} minWidth={1}>
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
                stroke="hsl(var(--chart-1))"
                fill="hsl(var(--chart-1))"
                fillOpacity={0.2}
                name="CPU %"
              />
              <Area
                type="monotone"
                dataKey="memory"
                stroke="hsl(var(--chart-2))"
                fill="hsl(var(--chart-2))"
                fillOpacity={0.2}
                name="Memory %"
              />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
