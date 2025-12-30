'use client';

import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  Clock,
  TrendingUp,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

type ActivityChartPoint = {
  name: string;
  requests: number;
  users: number;
};

type HealthStatus = 'healthy' | 'degraded' | 'down';

type SystemHealth = {
  api: HealthStatus;
  database: HealthStatus;
  llm: HealthStatus;
};

type ActivitySectionProps = {
  activityChartData: ActivityChartPoint[];
  systemHealth: SystemHealth;
};

const getHealthIcon = (status: HealthStatus) => {
  switch (status) {
    case 'healthy':
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    case 'degraded':
      return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    case 'down':
      return <AlertTriangle className="h-4 w-4 text-red-500" />;
    default:
      return <Clock className="h-4 w-4 text-muted-foreground" />;
  }
};

const getHealthBadge = (status: HealthStatus) => {
  switch (status) {
    case 'healthy':
      return <Badge className="bg-green-500">Healthy</Badge>;
    case 'degraded':
      return <Badge className="bg-yellow-500">Degraded</Badge>;
    case 'down':
      return <Badge variant="destructive">Down</Badge>;
    default:
      return <Badge variant="secondary">Unknown</Badge>;
  }
};

export const ActivitySection = ({ activityChartData, systemHealth }: ActivitySectionProps) => (
  <div className="grid gap-6 lg:grid-cols-3 mb-8">
    <Card className="lg:col-span-2">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5" />
          Weekly Activity
        </CardTitle>
        <CardDescription>API requests and active users over the past week</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%" minHeight={1} minWidth={1}>
            <AreaChart data={activityChartData}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis dataKey="name" className="text-xs" />
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
                dataKey="requests"
                stackId="1"
                stroke="#3b82f6"
                fill="#3b82f6"
                fillOpacity={0.3}
                name="Requests"
              />
              <Area
                type="monotone"
                dataKey="users"
                stackId="2"
                stroke="#10b981"
                fill="#10b981"
                fillOpacity={0.3}
                name="Active Users"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>

    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-5 w-5" />
          System Health
        </CardTitle>
        <CardDescription className="text-xs text-muted-foreground">
          Heuristic based on loaded data/configuration; use monitoring for live health checks.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
          <div className="flex items-center gap-3">
            {getHealthIcon(systemHealth.api)}
            <span className="font-medium">API Server</span>
          </div>
          {getHealthBadge(systemHealth.api)}
        </div>
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
          <div className="flex items-center gap-3">
            {getHealthIcon(systemHealth.database)}
            <span className="font-medium">Database</span>
          </div>
          {getHealthBadge(systemHealth.database)}
        </div>
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
          <div className="flex items-center gap-3">
            {getHealthIcon(systemHealth.llm)}
            <span className="font-medium">LLM Services</span>
          </div>
          {getHealthBadge(systemHealth.llm)}
        </div>
        <Link href="/monitoring" className="block">
          <Button variant="outline" className="w-full mt-2">
            View Details
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </Link>
      </CardContent>
    </Card>
  </div>
);
