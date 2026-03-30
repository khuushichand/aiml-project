'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingUp } from 'lucide-react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
} from 'recharts';
import type { VoiceAnalytics } from '@/types';

interface UsageTrendsChartProps {
  data: VoiceAnalytics[];
  isLoading?: boolean;
}

export function UsageTrendsChart({ data, isLoading }: UsageTrendsChartProps) {
  // Format data for chart
  const chartData = data.map((d) => ({
    date: new Date(d.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    commands: d.total_commands,
    users: d.unique_users,
    successRate: Math.round(d.success_rate * 100),
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5" />
          Usage Trends
        </CardTitle>
        <CardDescription>Command usage and success rate over time</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading || data.length === 0 ? (
          <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
            {isLoading ? 'Loading usage data...' : 'No usage data available yet'}
          </div>
        ) : (
          <div className="h-64" role="img" aria-label={`Voice command usage trends chart showing ${chartData.length} data points for commands, users, and success rate`}>
            <ResponsiveContainer width="100%" height="100%" minHeight={1} minWidth={1}>
              <AreaChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis dataKey="date" className="text-xs" />
                <YAxis yAxisId="left" className="text-xs" />
                <YAxis yAxisId="right" orientation="right" className="text-xs" domain={[0, 100]} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--background))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                  }}
                />
                <Legend />
                <Area
                  yAxisId="left"
                  type="monotone"
                  dataKey="commands"
                  stroke="hsl(var(--chart-1))"
                  fill="hsl(var(--chart-1))"
                  fillOpacity={0.2}
                  name="Commands"
                />
                <Area
                  yAxisId="left"
                  type="monotone"
                  dataKey="users"
                  stroke="hsl(var(--chart-2))"
                  fill="hsl(var(--chart-2))"
                  fillOpacity={0.2}
                  name="Unique Users"
                />
                <Area
                  yAxisId="right"
                  type="monotone"
                  dataKey="successRate"
                  stroke="hsl(var(--chart-3))"
                  fill="hsl(var(--chart-3))"
                  fillOpacity={0.1}
                  name="Success Rate %"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
