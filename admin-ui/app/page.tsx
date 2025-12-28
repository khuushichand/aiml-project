'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Checkbox } from '@/components/ui/checkbox';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { useToast } from '@/components/ui/toast';
import { useOrgContext } from '@/components/OrgContextSwitcher';
import {
  Building2, Users, Key, Cpu, HardDrive, Activity, Shield, FileText,
  CheckCircle, AlertTriangle, Clock, TrendingUp, RefreshCw, ArrowRight,
  Clipboard, Plus, Settings, Trash2, UserPlus
} from 'lucide-react';
import { api } from '@/lib/api-client';
import { AuditLog, LLMProvider, Organization, RegistrationCode, RegistrationSettings, User } from '@/types';
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

type ServerStatusState = 'online' | 'degraded' | 'offline' | 'unknown';

interface DashboardAlert {
  id: string | number;
  message?: string;
  severity?: 'info' | 'warning' | 'error' | 'critical';
  acknowledged: boolean;
  created_at?: string;
}

type ProviderMap = Record<string, Partial<Omit<LLMProvider, 'name'>>>;

type ActivityPoint = {
  date: string;
  requests: number;
  users: number;
};

const ACTIVITY_DAYS = 7;

const buildEmptyActivityPoints = (days: number): ActivityPoint[] => {
  const today = new Date();
  const points: ActivityPoint[] = [];
  for (let offset = days - 1; offset >= 0; offset -= 1) {
    const date = new Date(Date.UTC(
      today.getUTCFullYear(),
      today.getUTCMonth(),
      today.getUTCDate() - offset,
    ));
    points.push({
      date: date.toISOString().slice(0, 10),
      requests: 0,
      users: 0,
    });
  }
  return points;
};

const formatActivityLabel = (dateStr: string) => {
  const date = new Date(`${dateStr}T00:00:00Z`);
  return date.toLocaleDateString(undefined, { weekday: 'short' });
};

const processUsers = (result: PromiseSettledResult<unknown>): User[] => {
  if (result.status !== 'fulfilled') {
    return [];
  }
  if (Array.isArray(result.value)) {
    return result.value;
  }
  if (result.value && typeof result.value === 'object') {
    const users = (result.value as { users?: User[] }).users;
    return Array.isArray(users) ? users : [];
  }
  return [];
};

const processOrganizations = (result: PromiseSettledResult<unknown>): Organization[] => {
  if (result.status !== 'fulfilled') {
    return [];
  }
  return Array.isArray(result.value) ? result.value : [];
};

const processProviders = (result: PromiseSettledResult<unknown>) => {
  const rawProviders: ProviderMap | LLMProvider[] =
    result.status === 'fulfilled' && result.value ? result.value as ProviderMap | LLMProvider[] : {};
  const providerList: LLMProvider[] = Array.isArray(rawProviders)
    ? rawProviders.map((provider) => ({
        name: provider.name,
        enabled: provider.enabled ?? true,
        models: provider.models,
      }))
    : Object.entries(rawProviders).map(([name, value]) => ({
        name,
        enabled: value.enabled ?? true,
        models: value.models,
      }));
  const enabledProviders = providerList.filter((provider) => provider.enabled !== false);
  return { providerList, enabledProviders };
};

const processAuditLogs = (result: PromiseSettledResult<unknown>): AuditLog[] => {
  if (result.status !== 'fulfilled') {
    return [];
  }
  if (Array.isArray(result.value)) {
    return result.value;
  }
  const entries = (result.value as { entries?: AuditLog[] } | null)?.entries;
  if (Array.isArray(entries)) {
    return entries;
  }
  const items = (result.value as { items?: AuditLog[] } | null)?.items;
  return Array.isArray(items) ? items : [];
};

const processAlerts = (result: PromiseSettledResult<unknown>): DashboardAlert[] => {
  if (result.status !== 'fulfilled') {
    return [];
  }
  return Array.isArray(result.value) ? result.value : [];
};

const processActivity = (
  result: PromiseSettledResult<unknown>,
  days: number
): ActivityPoint[] => {
  if (result.status !== 'fulfilled' || !result.value) {
    return buildEmptyActivityPoints(days);
  }
  const points = (result.value as { points?: ActivityPoint[] } | null)?.points;
  if (Array.isArray(points) && points.length > 0) {
    return points;
  }
  return buildEmptyActivityPoints(days);
};

const processRegistrationCodes = (result: PromiseSettledResult<unknown>): RegistrationCode[] => {
  if (result.status !== 'fulfilled') {
    return [];
  }
  return Array.isArray(result.value) ? result.value : [];
};

const processRegistrationSettings = (
  result: PromiseSettledResult<unknown>
): RegistrationSettings | null => {
  if (result.status !== 'fulfilled' || !result.value) {
    return null;
  }
  return result.value as RegistrationSettings;
};

const computeUserStats = (users: User[]) => ({
  activeUsers: users.filter((user) => user.is_active).length,
  totalStorage: users.reduce((acc, user) => acc + (user.storage_used_mb || 0), 0),
  totalQuota: users.reduce((acc, user) => acc + (user.storage_quota_mb || 0), 0),
});

const deriveSystemHealth = (
  usersResult: PromiseSettledResult<unknown>,
  orgsResult: PromiseSettledResult<unknown>,
  providersResult: PromiseSettledResult<unknown>,
  enabledProviders: number
): SystemHealth => {
  const databaseStatus =
    usersResult.status === 'fulfilled' && orgsResult.status === 'fulfilled'
      ? 'healthy'
      : 'degraded';
  const llmStatus =
    providersResult.status === 'fulfilled' && enabledProviders > 0
      ? 'healthy'
      : 'degraded';
  return {
    api: 'healthy',
    database: databaseStatus,
    llm: llmStatus,
  };
};

export default function DashboardPage() {
  const { selectedOrg } = useOrgContext();
  const confirm = useConfirm();
  const { success, error: showError } = useToast();
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
  const [serverStatus, setServerStatus] = useState<{
    state: ServerStatusState;
    checkedAt?: string;
  }>({ state: 'unknown' });
  const [activityData, setActivityData] = useState<ActivityPoint[]>(
    buildEmptyActivityPoints(ACTIVITY_DAYS)
  );
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [registrationCodes, setRegistrationCodes] = useState<RegistrationCode[]>([]);
  const [registrationSettings, setRegistrationSettings] = useState<RegistrationSettings | null>(null);
  const [registrationSettingsError, setRegistrationSettingsError] = useState('');
  const [savingRegistrationSettings, setSavingRegistrationSettings] = useState(false);
  const [showRegistrationDialog, setShowRegistrationDialog] = useState(false);
  const [registrationForm, setRegistrationForm] = useState({
    max_uses: 1,
    expiry_days: 7,
    role_to_grant: 'user',
  });
  const [registrationError, setRegistrationError] = useState('');
  const [creatingRegistration, setCreatingRegistration] = useState(false);
  const [latestRegistrationCode, setLatestRegistrationCode] = useState<RegistrationCode | null>(null);
  const [showCreateUserDialog, setShowCreateUserDialog] = useState(false);
  const [createUserForm, setCreateUserForm] = useState({
    username: '',
    email: '',
    password: '',
    role: 'user',
    is_active: true,
    is_verified: true,
  });
  const [createUserError, setCreateUserError] = useState('');
  const [creatingUser, setCreatingUser] = useState(false);
  const [showOrgDialog, setShowOrgDialog] = useState(false);
  const [orgForm, setOrgForm] = useState({ name: '', slug: '' });
  const [orgError, setOrgError] = useState('');
  const [creatingOrg, setCreatingOrg] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboardData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const orgParams = selectedOrg ? { org_id: String(selectedOrg.id) } : undefined;
      const auditParams = selectedOrg ? { limit: '5', org_id: String(selectedOrg.id) } : { limit: '5' };

      // Fetch all dashboard data in parallel
      const [
        statsResult,
        usersResult,
        orgsResult,
        providersResult,
        auditResult,
        alertsResult,
        activityResult,
        registrationSettingsResult,
        registrationCodesResult,
        healthResult,
      ] = await Promise.allSettled([
        api.getDashboardStats(),
        api.getUsers(orgParams),
        api.getOrganizations(),
        api.getLLMProviders(),
        api.getAuditLogs(auditParams),
        api.getAlerts(),
        api.getDashboardActivity(ACTIVITY_DAYS),
        api.getRegistrationSettings(),
        api.getRegistrationCodes(),
        api.getHealth(),
      ]);

      const users = processUsers(usersResult);
      const orgs = processOrganizations(orgsResult);
      setOrganizations(orgs);

      const { providerList, enabledProviders } = processProviders(providersResult);

      const logs = processAuditLogs(auditResult);
      setRecentActivity(logs.slice(0, 5));

      const alertsList = processAlerts(alertsResult);
      setAlerts(alertsList.filter((alert) => !alert.acknowledged).slice(0, 3));

      setActivityData(processActivity(activityResult, ACTIVITY_DAYS));
      setRegistrationSettings(processRegistrationSettings(registrationSettingsResult));
      setRegistrationSettingsError(
        registrationSettingsResult.status === 'rejected'
          ? 'Failed to load registration settings'
          : ''
      );
      setRegistrationCodes(processRegistrationCodes(registrationCodesResult));

      const healthState: ServerStatusState = (() => {
        if (healthResult.status !== 'fulfilled') {
          return 'offline';
        }
        const status = (healthResult.value as { status?: string } | null)?.status;
        if (status === 'ok') return 'online';
        if (status === 'degraded') return 'degraded';
        if (status === 'unhealthy') return 'offline';
        return 'unknown';
      })();
      setServerStatus({ state: healthState, checkedAt: new Date().toISOString() });

      const { activeUsers, totalStorage, totalQuota } = computeUserStats(users);

      const computedStats: DashboardUIStats = {
        users: users.length,
        activeUsers,
        organizations: orgs.length,
        // Teams and API key counts provided by stats endpoint.
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

      // Check system health (heuristic; not a live health endpoint)
      setSystemHealth(deriveSystemHealth(usersResult, orgsResult, providersResult, nextStats.enabledProviders));

    } catch (err: unknown) {
      console.error('Failed to load dashboard data:', err);
      setError('Failed to load dashboard statistics');
    } finally {
      setLoading(false);
    }
  }, [selectedOrg]);

  useEffect(() => {
    void loadDashboardData();
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

  const getServerStatusLabel = (state: ServerStatusState) => {
    switch (state) {
      case 'online':
        return 'Online';
      case 'degraded':
        return 'Degraded';
      case 'offline':
        return 'Offline';
      default:
        return 'Unknown';
    }
  };

  const getServerStatusDot = (state: ServerStatusState) => {
    switch (state) {
      case 'online':
        return 'bg-green-500';
      case 'degraded':
        return 'bg-yellow-500';
      case 'offline':
        return 'bg-red-500';
      default:
        return 'bg-gray-400';
    }
  };

  const formatShortDate = (dateStr: string) => {
    const date = new Date(dateStr);
    if (Number.isNaN(date.getTime())) return '—';
    return date.toLocaleDateString();
  };

  const copyToClipboard = async (value: string, label: string) => {
    try {
      await navigator.clipboard.writeText(value);
      success('Copied to clipboard', `${label} copied.`);
    } catch (err: unknown) {
      console.error('Failed to copy to clipboard:', err);
      showError('Copy failed', 'Please copy manually or check browser permissions.');
    }
  };

  const isRegistrationCodeActive = (code: RegistrationCode) => {
    const expiresAt = new Date(code.expires_at);
    const expired = Number.isNaN(expiresAt.getTime()) ? false : expiresAt < new Date();
    return !expired && code.times_used < code.max_uses;
  };

  const handleRegistrationSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setRegistrationError('');
    setCreatingRegistration(true);
    try {
      const created = await api.createRegistrationCode(registrationForm);
      setLatestRegistrationCode(created as RegistrationCode);
      success('Registration code created', `Role: ${registrationForm.role_to_grant}`);
      setShowRegistrationDialog(false);
      setRegistrationForm({ max_uses: 1, expiry_days: 7, role_to_grant: 'user' });
      await loadDashboardData();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create registration code';
      setRegistrationError(message);
      showError('Registration code failed', message);
    } finally {
      setCreatingRegistration(false);
    }
  };

  const handleRegistrationDelete = async (code: RegistrationCode) => {
    const confirmed = await confirm({
      title: 'Delete registration code',
      message: `Delete code ${code.code.slice(0, 6)}…? Users will no longer be able to register with it.`,
      confirmText: 'Delete',
      variant: 'danger',
      icon: 'key',
    });
    if (!confirmed) return;

    try {
      await api.deleteRegistrationCode(code.id);
      success('Registration code deleted', `Code ${code.code.slice(0, 6)}… removed.`);
      await loadDashboardData();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to delete registration code';
      showError('Delete failed', message);
    }
  };

  const handleRegistrationSettingsUpdate = async (
    updates: Partial<RegistrationSettings>,
    toastMessage: string
  ) => {
    if (!registrationSettings || savingRegistrationSettings) return;
    const previous = registrationSettings;
    setRegistrationSettings({ ...registrationSettings, ...updates });
    setRegistrationSettingsError('');
    setSavingRegistrationSettings(true);
    try {
      const updated = await api.updateRegistrationSettings(updates as Record<string, unknown>);
      setRegistrationSettings(updated as RegistrationSettings);
      success('Registration settings updated', toastMessage);
    } catch (err: unknown) {
      setRegistrationSettings(previous);
      const message = err instanceof Error ? err.message : 'Failed to update registration settings';
      setRegistrationSettingsError(message);
      showError('Registration settings failed', message);
    } finally {
      setSavingRegistrationSettings(false);
    }
  };

  const handleCreateUserSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setCreateUserError('');
    setCreatingUser(true);
    try {
      await api.createUser({
        username: createUserForm.username,
        email: createUserForm.email,
        password: createUserForm.password,
        role: createUserForm.role,
        is_active: createUserForm.is_active,
        is_verified: createUserForm.is_verified,
      });
      success('User created', `${createUserForm.username} added.`);
      setShowCreateUserDialog(false);
      setCreateUserForm({
        username: '',
        email: '',
        password: '',
        role: 'user',
        is_active: true,
        is_verified: true,
      });
      await loadDashboardData();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create user';
      setCreateUserError(message);
      showError('Create user failed', message);
    } finally {
      setCreatingUser(false);
    }
  };

  const handleOrgNameChange = (name: string) => {
    const slug = name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '');
    setOrgForm({ name, slug });
  };

  const handleOrgSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setOrgError('');
    setCreatingOrg(true);
    try {
      await api.createOrganization(orgForm);
      success('Organization created', `${orgForm.name} added.`);
      setShowOrgDialog(false);
      setOrgForm({ name: '', slug: '' });
      await loadDashboardData();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create organization';
      setOrgError(message);
      showError('Organization failed', message);
    } finally {
      setCreatingOrg(false);
    }
  };

  const activityChartData = useMemo(
    () => activityData.map((point) => ({
      name: formatActivityLabel(point.date),
      requests: point.requests,
      users: point.users,
    })),
    [activityData]
  );

  const storagePercentage = stats.storageQuotaMb > 0
    ? Math.min((stats.storageUsedMb / stats.storageQuotaMb) * 100, 100)
    : 0;

  const activeRegistrationCount = registrationCodes.filter(isRegistrationCodeActive).length;
  const recentRegistrationCodes = registrationCodes.slice(0, 3);
  const recentOrganizations = organizations.slice(0, 3);
  const registrationEnabled = registrationSettings?.enable_registration ?? false;
  const registrationRequiresCode = registrationSettings?.require_registration_code ?? false;
  const registrationBlocked = registrationSettings?.self_registration_allowed === false && registrationEnabled;

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
              <div className="flex items-center gap-3">
                <div className="flex flex-wrap items-center gap-2 rounded-full border px-3 py-1 text-sm">
                  <span className={`h-2 w-2 rounded-full ${getServerStatusDot(serverStatus.state)}`} />
                  <span className="font-medium">{getServerStatusLabel(serverStatus.state)}</span>
                  {serverStatus.checkedAt && (
                    <span className="text-xs text-muted-foreground">
                      Checked {formatTimeAgo(serverStatus.checkedAt)}
                    </span>
                  )}
                </div>
                <Button variant="outline" onClick={loadDashboardData} disabled={loading}>
                  <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                  Refresh
                </Button>
              </div>
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

              {/* System Health */}
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
                      href="/organizations"
                      className="flex items-center gap-3 p-4 rounded-lg border hover:bg-muted transition-colors"
                    >
                      <Building2 className="h-5 w-5 text-primary" />
                      <div>
                        <p className="font-medium">Organizations</p>
                        <p className="text-xs text-muted-foreground">Create or manage orgs</p>
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
                      href="/audit"
                      className="flex items-center gap-3 p-4 rounded-lg border hover:bg-muted transition-colors"
                    >
                      <FileText className="h-5 w-5 text-primary" />
                      <div>
                        <p className="font-medium">Audit Logs</p>
                        <p className="text-xs text-muted-foreground">Review system activity</p>
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

            <div className="mt-8 grid gap-6 lg:grid-cols-3">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <UserPlus className="h-5 w-5" />
                    User Registration
                  </CardTitle>
                  <CardDescription>Issue codes and onboard new users</CardDescription>
                </CardHeader>
                <CardContent>
                  {registrationSettingsError && (
                    <Alert variant="destructive" className="mb-4">
                      <AlertDescription>{registrationSettingsError}</AlertDescription>
                    </Alert>
                  )}
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm text-muted-foreground">Active codes</p>
                      <p className="text-2xl font-bold">{activeRegistrationCount}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Dialog
                        open={showRegistrationDialog}
                        onOpenChange={(open) => {
                          setShowRegistrationDialog(open);
                          if (!open) setRegistrationError('');
                        }}
                      >
                        <DialogTrigger asChild>
                          <Button size="sm">
                            <Plus className="mr-2 h-4 w-4" />
                            New Code
                          </Button>
                        </DialogTrigger>
                        <DialogContent>
                          <DialogHeader>
                            <DialogTitle>Create registration code</DialogTitle>
                            <DialogDescription>
                              Share a code to allow new users to register with a predefined role.
                            </DialogDescription>
                          </DialogHeader>
                          {registrationError && (
                            <Alert variant="destructive">
                              <AlertDescription>{registrationError}</AlertDescription>
                            </Alert>
                          )}
                          <form onSubmit={handleRegistrationSubmit} className="space-y-4">
                            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                              <div className="space-y-2">
                                <Label htmlFor="reg-max-uses">Max uses</Label>
                                <Input
                                  id="reg-max-uses"
                                  type="number"
                                  min={1}
                                  max={100}
                                  value={registrationForm.max_uses}
                                  onChange={(event) => setRegistrationForm((prev) => ({
                                    ...prev,
                                    max_uses: Number(event.target.value || 1),
                                  }))}
                                />
                              </div>
                              <div className="space-y-2">
                                <Label htmlFor="reg-expiry-days">Expiry (days)</Label>
                                <Input
                                  id="reg-expiry-days"
                                  type="number"
                                  min={1}
                                  max={365}
                                  value={registrationForm.expiry_days}
                                  onChange={(event) => setRegistrationForm((prev) => ({
                                    ...prev,
                                    expiry_days: Number(event.target.value || 1),
                                  }))}
                                />
                              </div>
                            </div>
                            <div className="space-y-2">
                              <Label htmlFor="reg-role">Role</Label>
                              <Select
                                id="reg-role"
                                value={registrationForm.role_to_grant}
                                onChange={(event) => setRegistrationForm((prev) => ({
                                  ...prev,
                                  role_to_grant: event.target.value,
                                }))}
                              >
                                <option value="user">User</option>
                                <option value="admin">Admin</option>
                                <option value="service">Service</option>
                              </Select>
                            </div>
                            <DialogFooter className="gap-2 sm:gap-0">
                              <Button
                                type="button"
                                variant="outline"
                                onClick={() => setShowRegistrationDialog(false)}
                                disabled={creatingRegistration}
                              >
                                Cancel
                              </Button>
                              <Button type="submit" disabled={creatingRegistration}>
                                {creatingRegistration ? 'Creating…' : 'Create code'}
                              </Button>
                            </DialogFooter>
                          </form>
                        </DialogContent>
                      </Dialog>

                      <Dialog
                        open={showCreateUserDialog}
                        onOpenChange={(open) => {
                          setShowCreateUserDialog(open);
                          if (!open) setCreateUserError('');
                        }}
                      >
                        <DialogTrigger asChild>
                          <Button size="sm" variant="outline">
                            <UserPlus className="mr-2 h-4 w-4" />
                            Create user
                          </Button>
                        </DialogTrigger>
                        <DialogContent>
                          <DialogHeader>
                            <DialogTitle>Create user</DialogTitle>
                            <DialogDescription>
                              Create a user directly as an admin. Provide a temporary password.
                            </DialogDescription>
                          </DialogHeader>
                          {createUserError && (
                            <Alert variant="destructive">
                              <AlertDescription>{createUserError}</AlertDescription>
                            </Alert>
                          )}
                          <form onSubmit={handleCreateUserSubmit} className="space-y-4">
                            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                              <div className="space-y-2">
                                <Label htmlFor="create-user-username">Username</Label>
                                <Input
                                  id="create-user-username"
                                  value={createUserForm.username}
                                  onChange={(event) => setCreateUserForm((prev) => ({
                                    ...prev,
                                    username: event.target.value,
                                  }))}
                                  required
                                />
                              </div>
                              <div className="space-y-2">
                                <Label htmlFor="create-user-email">Email</Label>
                                <Input
                                  id="create-user-email"
                                  type="email"
                                  value={createUserForm.email}
                                  onChange={(event) => setCreateUserForm((prev) => ({
                                    ...prev,
                                    email: event.target.value,
                                  }))}
                                  required
                                />
                              </div>
                            </div>
                            <div className="space-y-2">
                              <Label htmlFor="create-user-password">Password</Label>
                              <Input
                                id="create-user-password"
                                type="password"
                                value={createUserForm.password}
                                onChange={(event) => setCreateUserForm((prev) => ({
                                  ...prev,
                                  password: event.target.value,
                                }))}
                                required
                              />
                              <p className="text-xs text-muted-foreground">Minimum 10 characters.</p>
                            </div>
                            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                              <div className="space-y-2">
                                <Label htmlFor="create-user-role">Role</Label>
                                <Select
                                  id="create-user-role"
                                  value={createUserForm.role}
                                  onChange={(event) => setCreateUserForm((prev) => ({
                                    ...prev,
                                    role: event.target.value,
                                  }))}
                                >
                                  <option value="user">User</option>
                                  <option value="admin">Admin</option>
                                  <option value="service">Service</option>
                                </Select>
                              </div>
                              <div className="space-y-2">
                                <Label className="block">Status</Label>
                                <div className="space-y-2">
                                  <label className="flex items-center gap-2 text-sm">
                                    <Checkbox
                                      id="create-user-active"
                                      checked={createUserForm.is_active}
                                      onCheckedChange={(checked) => setCreateUserForm((prev) => ({
                                        ...prev,
                                        is_active: checked,
                                      }))}
                                    />
                                    Active
                                  </label>
                                  <label className="flex items-center gap-2 text-sm">
                                    <Checkbox
                                      id="create-user-verified"
                                      checked={createUserForm.is_verified}
                                      onCheckedChange={(checked) => setCreateUserForm((prev) => ({
                                        ...prev,
                                        is_verified: checked,
                                      }))}
                                    />
                                    Verified
                                  </label>
                                </div>
                              </div>
                            </div>
                            <DialogFooter className="gap-2 sm:gap-0">
                              <Button
                                type="button"
                                variant="outline"
                                onClick={() => setShowCreateUserDialog(false)}
                                disabled={creatingUser}
                              >
                                Cancel
                              </Button>
                              <Button type="submit" disabled={creatingUser}>
                                {creatingUser ? 'Creating…' : 'Create user'}
                              </Button>
                            </DialogFooter>
                          </form>
                        </DialogContent>
                      </Dialog>
                    </div>
                  </div>

                  <div className="mt-4 space-y-3 rounded-lg border p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium">Self-registration</p>
                        <p className="text-xs text-muted-foreground">Allow new users to sign up.</p>
                      </div>
                      <Checkbox
                        id="registration-enabled"
                        checked={registrationEnabled}
                        disabled={!registrationSettings || savingRegistrationSettings}
                        onCheckedChange={(checked) => handleRegistrationSettingsUpdate(
                          { enable_registration: checked },
                          checked ? 'Self-registration enabled.' : 'Self-registration disabled.'
                        )}
                      />
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium">Require registration code</p>
                        <p className="text-xs text-muted-foreground">Limit signups to issued codes.</p>
                      </div>
                      <Checkbox
                        id="registration-requires-code"
                        checked={registrationRequiresCode}
                        disabled={!registrationSettings || savingRegistrationSettings}
                        onCheckedChange={(checked) => handleRegistrationSettingsUpdate(
                          { require_registration_code: checked },
                          checked ? 'Registration codes required.' : 'Registration codes optional.'
                        )}
                      />
                    </div>
                    {registrationBlocked && (
                      <p className="text-xs text-muted-foreground">
                        Self-registration is blocked by profile {registrationSettings?.profile ?? 'local-single-user'}.
                      </p>
                    )}
                    {registrationSettings && (
                      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                        <Badge className={registrationEnabled ? 'bg-green-500' : 'bg-muted text-muted-foreground'}>
                          {registrationEnabled ? 'Registration enabled' : 'Registration disabled'}
                        </Badge>
                        <Badge variant="secondary">
                          {registrationRequiresCode ? 'Codes required' : 'Codes optional'}
                        </Badge>
                      </div>
                    )}
                  </div>

                  {latestRegistrationCode && (
                    <div className="mt-4 rounded-lg border bg-muted/40 p-3">
                      <p className="text-xs text-muted-foreground">Latest code</p>
                      <div className="mt-2 flex items-center justify-between gap-2">
                        <span className="font-mono text-xs break-all">{latestRegistrationCode.code}</span>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => copyToClipboard(latestRegistrationCode.code, 'Registration code')}
                        >
                          <Clipboard className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  )}

                  <div className="mt-4 space-y-3">
                    {recentRegistrationCodes.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No active registration codes yet.</p>
                    ) : (
                      recentRegistrationCodes.map((code) => {
                        const active = isRegistrationCodeActive(code);
                        return (
                          <div key={code.id} className="flex items-start justify-between gap-2 rounded-lg border p-3">
                            <div className="min-w-0 space-y-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="font-mono text-xs break-all">{code.code}</span>
                                <Badge className={active ? 'bg-green-500' : 'bg-muted text-muted-foreground'}>
                                  {active ? 'Active' : 'Expired'}
                                </Badge>
                              </div>
                              <p className="text-xs text-muted-foreground">
                                Role {code.role_to_grant} • {code.times_used}/{code.max_uses} used •
                                Expires {formatShortDate(String(code.expires_at))}
                              </p>
                            </div>
                            <div className="flex items-center gap-1">
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => copyToClipboard(code.code, 'Registration code')}
                              >
                                <Clipboard className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleRegistrationDelete(code)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2">
                    <Link href="/users">
                      <Button variant="outline" size="sm">Manage users</Button>
                    </Link>
                    <Link href="/roles">
                      <Button variant="ghost" size="sm">Roles & access</Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Building2 className="h-5 w-5" />
                    Organization Management
                  </CardTitle>
                  <CardDescription>Create, invite, and manage orgs</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground">Organizations</p>
                      <p className="text-2xl font-bold">{stats.organizations}</p>
                    </div>
                    <Dialog
                      open={showOrgDialog}
                      onOpenChange={(open) => {
                        setShowOrgDialog(open);
                        if (!open) setOrgError('');
                      }}
                    >
                      <DialogTrigger asChild>
                        <Button size="sm">
                          <Plus className="mr-2 h-4 w-4" />
                          New Org
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>Create organization</DialogTitle>
                          <DialogDescription>Add a new organization to the system.</DialogDescription>
                        </DialogHeader>
                        {orgError && (
                          <Alert variant="destructive">
                            <AlertDescription>{orgError}</AlertDescription>
                          </Alert>
                        )}
                        <form onSubmit={handleOrgSubmit} className="space-y-4">
                          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                            <div className="space-y-2">
                              <Label htmlFor="org-name">Organization name</Label>
                              <Input
                                id="org-name"
                                value={orgForm.name}
                                onChange={(event) => handleOrgNameChange(event.target.value)}
                                required
                              />
                            </div>
                            <div className="space-y-2">
                              <Label htmlFor="org-slug">Slug</Label>
                              <Input
                                id="org-slug"
                                value={orgForm.slug}
                                onChange={(event) => setOrgForm((prev) => ({
                                  ...prev,
                                  slug: event.target.value,
                                }))}
                                required
                              />
                              <p className="text-xs text-muted-foreground">URL-friendly identifier</p>
                            </div>
                          </div>
                          <DialogFooter className="gap-2 sm:gap-0">
                            <Button
                              type="button"
                              variant="outline"
                              onClick={() => setShowOrgDialog(false)}
                              disabled={creatingOrg}
                            >
                              Cancel
                            </Button>
                            <Button type="submit" disabled={creatingOrg}>
                              {creatingOrg ? 'Creating…' : 'Create organization'}
                            </Button>
                          </DialogFooter>
                        </form>
                      </DialogContent>
                    </Dialog>
                  </div>

                  <div className="mt-4 space-y-3">
                    {recentOrganizations.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No organizations created yet.</p>
                    ) : (
                      recentOrganizations.map((org) => (
                        <div key={org.id} className="flex items-center justify-between rounded-lg border p-3">
                          <div>
                            <p className="text-sm font-medium">{org.name}</p>
                            <p className="text-xs text-muted-foreground">{org.slug}</p>
                          </div>
                          <Link href={`/organizations/${org.id}`}>
                            <Button variant="ghost" size="sm">
                              Manage
                            </Button>
                          </Link>
                        </div>
                      ))
                    )}
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2">
                    <Link href="/organizations">
                      <Button variant="outline" size="sm">Manage orgs</Button>
                    </Link>
                    <Link href="/teams">
                      <Button variant="ghost" size="sm">Teams & invites</Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Settings className="h-5 w-5" />
                    Server & Governance
                  </CardTitle>
                  <CardDescription>Configuration, providers, and monitoring controls</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">LLM providers</span>
                      <Badge variant="secondary">
                        {stats.enabledProviders}/{stats.providers} enabled
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Active users</span>
                      <Badge variant="secondary">{stats.activeUsers}</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Open alerts</span>
                      <Badge variant={alerts.length > 0 ? 'destructive' : 'secondary'}>
                        {alerts.length}
                      </Badge>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-2 sm:grid-cols-2">
                    <Link href="/config">
                      <Button variant="outline" size="sm" className="w-full">
                        Server settings
                      </Button>
                    </Link>
                    <Link href="/providers">
                      <Button variant="outline" size="sm" className="w-full">
                        Provider keys
                      </Button>
                    </Link>
                    <Link href="/monitoring">
                      <Button variant="ghost" size="sm" className="w-full">
                        Monitoring
                      </Button>
                    </Link>
                    <Link href="/audit">
                      <Button variant="ghost" size="sm" className="w-full">
                        Audit logs
                      </Button>
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
