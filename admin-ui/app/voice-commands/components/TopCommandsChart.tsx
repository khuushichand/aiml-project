'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { BarChart3 } from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { VoiceCommandUsage } from '@/types';

interface TopCommandsChartProps {
  data: VoiceCommandUsage[];
  isLoading?: boolean;
}

// Colors for bar chart
const COLORS = [
  'hsl(var(--chart-1))',
  'hsl(var(--chart-2))',
  'hsl(var(--chart-3))',
  'hsl(var(--chart-4))',
  'hsl(var(--chart-5))',
];

export function TopCommandsChart({ data, isLoading }: TopCommandsChartProps) {
  // Take top 10 and format
  const chartData = data.slice(0, 10).map((d) => ({
    name: d.command_name.length > 15 ? d.command_name.slice(0, 15) + '...' : d.command_name,
    fullName: d.command_name,
    invocations: d.total_invocations,
    successRate: d.total_invocations > 0
      ? Math.round((d.success_count / d.total_invocations) * 100)
      : 0,
    avgResponseMs: Math.round(d.avg_response_time_ms),
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BarChart3 className="h-5 w-5" />
          Top Commands
        </CardTitle>
        <CardDescription>Most frequently used voice commands</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading || data.length === 0 ? (
          <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
            {isLoading ? 'Loading command data...' : 'No command usage data available yet'}
          </div>
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%" minHeight={1} minWidth={1}>
              <BarChart data={chartData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" horizontal={false} />
                <XAxis type="number" className="text-xs" />
                <YAxis
                  type="category"
                  dataKey="name"
                  className="text-xs"
                  width={100}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--background))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                  }}
                  formatter={(value: number, name: string) => {
                    if (name === 'invocations') return [value, 'Invocations'];
                    return [value, name];
                  }}
                  labelFormatter={(label: string, payload: unknown[]) => {
                    const item = payload?.[0] as { payload?: { fullName: string } } | undefined;
                    return item?.payload?.fullName || label;
                  }}
                />
                <Bar dataKey="invocations" name="Invocations" radius={[0, 4, 4, 0]}>
                  {chartData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
