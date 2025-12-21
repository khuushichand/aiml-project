'use client';

import { useCallback, useEffect, useState } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Building2, Users, Key, Cpu, HardDrive, Activity, Shield, FileText,
  CheckCircle, AlertTriangle, Clock, TrendingUp, RefreshCw, ArrowRight
} from 'lucide-react';
import { api } from '@/lib/api-client';
import { AuditLog, LLMProvider, Organization, User } from '@/types';
import { buildDashboardUIStats, type DashboardUIStats } from '@/lib/dashboard';
import Link from 'next/link';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { Skeleton, StatsCardSkeleton } from '@/components/ui/skeleton';

interface SystemHealth {
  api: 'healthy' | 'degraded' | 'down';
  database: 'healthy' | 'degraded' | 'down';
  llm: 'healthy' | 'degraded' | 'down';
}

interface DashboardAlert {
  id: string | number;
  message?: string;
  severity?: 'info' | 'warning' | 'error' | 'critical';
  acknowledged: boolean;
  created_at?: string;
}

type ProviderMap = Record<string, Partial<Omit<LLMProvider, 'name'>>>;

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardUIStats>({
    users: 0,
    activeUsers: 0,
    organizations: 0,
    teams: 0,
    apiKeys: 0,
    activeApiKeys: 0,
    providers: 0,
    enabledProviders: 0,
    storageUsedMb: 0,
    storageQuotaMb: 1000,
  });
  const [recentActivity, setRecentActivity] = useState<AuditLog[]>([]);
  const [alerts, setAlerts] = useState<DashboardAlert[]>([]);
  const [systemHealth, setSystemHealth] = useState<SystemHealth>({
    api: 'healthy',
    database: 'healthy',
    llm: 'healthy',
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // TODO(#metrics-endpoint): Replace placeholder activity data once metrics endpoint is available.
  const [activityData] = useState([
    { name: 'Mon', requests: 120, users: 45 },
    { name: 'Tue', requests: 150, users: 52 },
    { name: 'Wed', requests: 180, users: 61 },
    { name: 'Thu', requests: 140, users: 48 },
    { name: 'Fri', requests: 200, users: 70 },
    { name: 'Sat', requests: 80, users: 30 },
    { name: 'Sun', requests: 60, users: 25 },
  ]);

  const loadDashboardData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch all dashboard data in parallel
      const [
        statsResult,
        usersResult,
        orgsResult,
        providersResult,
        auditResult,
        alertsResult,
      ] = await Promise.allSettled([
        api.getDashboardStats(),
        api.getUsers(),
        api.getOrganizations(),
        api.getLLMProviders(),
        api.getAuditLogs({ limit: '5' }),
        api.getAlerts(),
      ]);

      // Process users
      let users: User[] = [];
      if (usersResult.status === 'fulfilled') {
        users = Array.isArray(usersResult.value) ? usersResult.value : [];
      }

      // Process organizations
      let orgs: Organization[] = [];
      if (orgsResult.status === 'fulfilled') {
        orgs = Array.isArray(orgsResult.value) ? orgsResult.value : [];
      }

      // Process providers
      let providers: ProviderMap | LLMProvider[] = {};
      if (providersResult.status === 'fulfilled') {
        providers = providersResult.value || {};
      }
      const providerList: LLMProvider[] = Array.isArray(providers)
        ? providers.map((provider) => ({
            name: provider.name,
            enabled: provider.enabled ?? true,
            models: provider.models,
          }))
        : Object.entries(providers).map(([name, value]) => ({
            name,
            enabled: value.enabled ?? true,
            models: value.models,
          }));
      const enabledProviders = providerList.filter((p) => p.enabled !== false);

      // Process audit logs
      if (auditResult.status === 'fulfilled') {
        const logs = Array.isArray(auditResult.value) ? auditResult.value : (auditResult.value?.items || []);
        setRecentActivity(logs.slice(0, 5));
      }

      // Process alerts
      if (alertsResult.status === 'fulfilled') {
        const alertsList: DashboardAlert[] = Array.isArray(alertsResult.value)
          ? alertsResult.value
          : [];
        setAlerts(alertsList.filter((a) => !a.acknowledged).slice(0, 3));
      }

      // Calculate stats
      const activeUsers = users.filter((u) => u.is_active).length;
      const totalStorage = users.reduce((acc, u) => acc + (u.storage_used_mb || 0), 0);
      const totalQuota = users.reduce((acc, u) => acc + (u.storage_quota_mb || 0), 0);

      const computedStats: DashboardUIStats = {
        users: users.length,
        activeUsers,
        organizations: orgs.length,
        teams: 0,
        apiKeys: 0,
        activeApiKeys: 0,
        providers: providerList.length,
        enabledProviders: enabledProviders.length,
        storageUsedMb: totalStorage,
        storageQuotaMb: totalQuota || 1000,
      };
      const nextStats = buildDashboardUIStats({
        computedStats,
        statsResponse: statsResult.status === 'fulfilled' ? statsResult.value : null,
      });
      setStats(nextStats);

      // Check system health
      setSystemHealth({
        api: 'healthy',
        database: nextStats.users > 0 ? 'healthy' : 'degraded',
        llm: nextStats.enabledProviders > 0 ? 'healthy' : 'degraded',
      });

    } catch (err: unknown) {
      console.error('Failed to load dashboard data:', err);
      setError('Failed to load dashboard statistics');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  const getHealthIcon = (status: string) => {
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

  const getHealthBadge = (status: string) => {
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

  const formatTimeAgo = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'Just now';
  };

  const storagePercentage = stats.storageQuotaMb > 0
    ? Math.min((stats.storageUsedMb / stats.storageQuotaMb) * 100, 100)
    : 0;

  return (
    <ProtectedRoute>
      <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            {/* Header */}
            <div className="mb-8 flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold">Dashboard</h1>
                <p className="text-muted-foreground">Overview of your tldw_server instance</p>
              </div>
              <Button variant="outline" onClick={loadDashboardData} disabled={loading}>
                <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </div>

            {error && (
              <Alert variant="destructive" className="mb-6">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {/* Active Alerts */}
            {alerts.length > 0 && (
              <Alert className="mb-6 bg-yellow-50 border-yellow-200">
                <AlertTriangle className="h-4 w-4 text-yellow-600" />
                <AlertDescription className="text-yellow-800">
                  {alerts.length} active alert{alerts.length !== 1 ? 's' : ''} require attention.{' '}
                  <Link href="/monitoring" className="underline font-medium">View all</Link>
                </AlertDescription>
              </Alert>
            )}

            {/* Stats Grid */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8">
              {loading ? (
                <>
                  <StatsCardSkeleton />
                  <StatsCardSkeleton />
                  <StatsCardSkeleton />
                  <StatsCardSkeleton />
                </>
              ) : (
                <>
                  <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium">Total Users</CardTitle>
                      <Users className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">{stats.users}</div>
                      <p className="text-xs text-muted-foreground">
                        {stats.activeUsers} active
                      </p>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium">Organizations</CardTitle>
                      <Building2 className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">{stats.organizations}</div>
                      <p className="text-xs text-muted-foreground">
                        {stats.teams} teams
                      </p>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium">LLM Providers</CardTitle>
                      <Cpu className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">{stats.enabledProviders}</div>
                      <p className="text-xs text-muted-foreground">
                        of {stats.providers} configured
                      </p>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium">Storage</CardTitle>
                      <HardDrive className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">
                        {`${(stats.storageUsedMb / 1024).toFixed(1)} GB`}
                      </div>
                      <div className="mt-2">
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full ${
                              storagePercentage > 90 ? 'bg-red-500' :
                              storagePercentage > 70 ? 'bg-yellow-500' : 'bg-green-500'
                            }`}
                            style={{ width: `${storagePercentage}%` }}
                          />
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          {storagePercentage.toFixed(0)}% used
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                </>
              )}
            </div>

            <div className="grid gap-6 lg:grid-cols-3 mb-8">
              {/* Activity Chart */}
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
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={activityData}>
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

              {/* System Health */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Activity className="h-5 w-5" />
                    System Health
                  </CardTitle>
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

            <div className="grid gap-6 lg:grid-cols-2">
              {/* Recent Activity */}
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <FileText className="h-5 w-5" />
                      Recent Activity
                    </CardTitle>
                    <CardDescription>Latest system events</CardDescription>
                  </div>
                  <Link href="/audit">
                    <Button variant="ghost" size="sm">
                      View All
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Button>
                  </Link>
                </CardHeader>
                <CardContent>
                  {loading ? (
                    <div className="space-y-4">
                      {Array.from({ length: 5 }).map((_, i) => (
                        <div key={i} className="flex items-start gap-3">
                          <Skeleton className="h-8 w-8 rounded-full" />
                          <div className="flex-1 space-y-2">
                            <Skeleton className="h-4 w-3/4" />
                            <Skeleton className="h-3 w-1/2" />
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : recentActivity.length === 0 ? (
                    <p className="text-center text-muted-foreground py-8">No recent activity</p>
                  ) : (
                    <div className="space-y-4">
                      {recentActivity.map((log) => (
                        <div key={log.id} className="flex items-start gap-3">
                          <div className="p-2 rounded-full bg-muted">
                            <Activity className="h-3 w-3" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">
                              {log.action} on {log.resource}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              User {log.user_id} • {formatTimeAgo(log.timestamp)}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Quick Actions */}
              <Card>
                <CardHeader>
                  <CardTitle>Quick Actions</CardTitle>
                  <CardDescription>Common administrative tasks</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Link
                      href="/users"
                      className="flex items-center gap-3 p-4 rounded-lg border hover:bg-muted transition-colors"
                    >
                      <Users className="h-5 w-5 text-primary" />
                      <div>
                        <p className="font-medium">Manage Users</p>
                        <p className="text-xs text-muted-foreground">Add or edit users</p>
                      </div>
                    </Link>
                    <Link
                      href="/api-keys"
                      className="flex items-center gap-3 p-4 rounded-lg border hover:bg-muted transition-colors"
                    >
                      <Key className="h-5 w-5 text-primary" />
                      <div>
                        <p className="font-medium">API Keys</p>
                        <p className="text-xs text-muted-foreground">Create or revoke</p>
                      </div>
                    </Link>
                    <Link
                      href="/roles"
                      className="flex items-center gap-3 p-4 rounded-lg border hover:bg-muted transition-colors"
                    >
                      <Shield className="h-5 w-5 text-primary" />
                      <div>
                        <p className="font-medium">Roles & Permissions</p>
                        <p className="text-xs text-muted-foreground">Manage access</p>
                      </div>
                    </Link>
                    <Link
                      href="/config"
                      className="flex items-center gap-3 p-4 rounded-lg border hover:bg-muted transition-colors"
                    >
                      <Cpu className="h-5 w-5 text-primary" />
                      <div>
                        <p className="font-medium">Configuration</p>
                        <p className="text-xs text-muted-foreground">System settings</p>
                      </div>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
      </ResponsiveLayout>
    </ProtectedRoute>
  );
}
