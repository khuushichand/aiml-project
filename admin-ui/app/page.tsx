'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Checkbox } from '@/components/ui/checkbox';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { useToast } from '@/components/ui/toast';
import { useOrgContext } from '@/components/OrgContextSwitcher';
import { AlertsBanner } from '@/components/dashboard/AlertsBanner';
import { CreateOrganizationDialog } from '@/components/dashboard/CreateOrganizationDialog';
import { CreateRegistrationCodeDialog } from '@/components/dashboard/CreateRegistrationCodeDialog';
import { CreateUserDialog } from '@/components/dashboard/CreateUserDialog';
import { DashboardHeader } from '@/components/dashboard/DashboardHeader';
import { StatsGrid } from '@/components/dashboard/StatsGrid';
import { ActivitySection } from '@/components/dashboard/ActivitySection';
import { RecentActivityCard } from '@/components/dashboard/RecentActivityCard';
import { QuickActionsCard } from '@/components/dashboard/QuickActionsCard';
import {
  Building2, Clipboard, RefreshCw, Settings, Trash2, UserPlus, ShieldAlert
} from 'lucide-react';
import { AccessibleIconButton } from '@/components/ui/accessible-icon-button';
import { api } from '@/lib/api-client';
import { AuditLog, LLMProvider, Organization, RegistrationCode, RegistrationSettings, type SecurityHealthData, User } from '@/types';
import { buildDashboardUIStats, type DashboardUIStats } from '@/lib/dashboard';
import { isSecurityHealthData } from '@/lib/type-guards';
import Link from 'next/link';

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
  return Array.isArray(result.value) ? result.value : [];
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
  const router = useRouter();
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
  const [deletingRegistrationId, setDeletingRegistrationId] = useState<string | null>(null);
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
  const [securityHealth, setSecurityHealth] = useState<SecurityHealthData | null>(null);

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
        securityHealthResult,
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
        api.getSecurityHealth(),
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

      // Process security health
      if (securityHealthResult.status === 'fulfilled' && isSecurityHealthData(securityHealthResult.value)) {
        setSecurityHealth(securityHealthResult.value);
      } else {
        // Set default values if endpoint not available
        setSecurityHealth({
          risk_score: 0,
          recent_security_events: 0,
          failed_logins_24h: 0,
          suspicious_activity: 0,
          mfa_adoption_rate: 0,
        });
      }

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

      const failures = [
        { key: 'stats', label: 'stats', result: statsResult },
        { key: 'users', label: 'users', result: usersResult },
        { key: 'organizations', label: 'organizations', result: orgsResult },
        { key: 'providers', label: 'providers', result: providersResult },
        { key: 'audit', label: 'audit logs', result: auditResult },
        { key: 'alerts', label: 'alerts', result: alertsResult },
        { key: 'activity', label: 'activity', result: activityResult },
        { key: 'registration_settings', label: 'registration settings', result: registrationSettingsResult },
        { key: 'registration_codes', label: 'registration codes', result: registrationCodesResult },
        { key: 'health', label: 'health', result: healthResult },
        { key: 'security_health', label: 'security health', result: securityHealthResult },
      ].filter((entry): entry is {
        key: string;
        label: string;
        result: PromiseRejectedResult;
      } => entry.result.status === 'rejected');

      if (failures.length > 0) {
        const failedLabels = failures.map((entry) => entry.label);
        console.warn(
          'Dashboard data fetch failures:',
          failures.map((entry) => ({ key: entry.key, reason: entry.result.reason }))
        );
        setError(`Some dashboard data failed to load: ${failedLabels.join(', ')}`);
      }
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
    if (!code.expires_at) {
      return code.times_used < code.max_uses;
    }
    const expiresAt = new Date(code.expires_at);
    if (Number.isNaN(expiresAt.getTime())) {
      return code.times_used < code.max_uses;
    }
    return expiresAt >= new Date() && code.times_used < code.max_uses;
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
    const codeId = String(code.id);
    if (deletingRegistrationId === codeId) return;
    const confirmed = await confirm({
      title: 'Delete registration code',
      message: `Delete code ${code.code.slice(0, 6)}…? Users will no longer be able to register with it.`,
      confirmText: 'Delete',
      variant: 'danger',
      icon: 'key',
    });
    if (!confirmed) return;

    try {
      setDeletingRegistrationId(codeId);
      await api.deleteRegistrationCode(code.id);
      success('Registration code deleted', `Code ${code.code.slice(0, 6)}… removed.`);
      await loadDashboardData();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to delete registration code';
      showError('Delete failed', message);
    } finally {
      setDeletingRegistrationId((prev) => (prev === codeId ? null : prev));
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

  const handleOrgSlugChange = (slug: string) => {
    setOrgForm((prev) => ({ ...prev, slug }));
  };

  const handleRegistrationDialogOpenChange = (open: boolean) => {
    setShowRegistrationDialog(open);
    if (!open) setRegistrationError('');
  };

  const handleCreateUserDialogOpenChange = (open: boolean) => {
    setShowCreateUserDialog(open);
    if (!open) setCreateUserError('');
  };

  const handleOrgDialogOpenChange = (open: boolean) => {
    setShowOrgDialog(open);
    if (!open) setOrgError('');
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
  const serverStatusLabel = getServerStatusLabel(serverStatus.state);
  const serverStatusDotClass = getServerStatusDot(serverStatus.state);
  const checkedAtLabel = serverStatus.checkedAt ? formatTimeAgo(serverStatus.checkedAt) : null;

  const activeRegistrationCount = registrationCodes.filter(isRegistrationCodeActive).length;
  const recentRegistrationCodes = registrationCodes.slice(0, 3);
  const recentOrganizations = organizations.slice(0, 3);
  const registrationEnabled = registrationSettings?.enable_registration ?? false;
  const registrationRequiresCode = registrationSettings?.require_registration_code ?? false;
  const registrationBlocked = registrationSettings?.self_registration_allowed === false && registrationEnabled;

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
        <div className="p-4 lg:p-8">
          <DashboardHeader
            serverStatusLabel={serverStatusLabel}
            serverStatusDotClass={serverStatusDotClass}
            checkedAtLabel={checkedAtLabel}
            loading={loading}
            onRefresh={loadDashboardData}
          />

          {error && (
            <Alert variant="destructive" className="mb-6">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <AlertsBanner count={alerts.length} />

          <StatsGrid
            loading={loading}
            stats={stats}
            storagePercentage={storagePercentage}
          />

          <ActivitySection
            activityChartData={activityChartData}
            systemHealth={systemHealth}
          />

          <div className="grid gap-6 lg:grid-cols-2">
            <RecentActivityCard
              loading={loading}
              recentActivity={recentActivity}
              formatTimeAgo={formatTimeAgo}
            />
            <QuickActionsCard />
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
                      <CreateRegistrationCodeDialog
                        open={showRegistrationDialog}
                        onOpenChange={handleRegistrationDialogOpenChange}
                        error={registrationError}
                        form={registrationForm}
                        setForm={setRegistrationForm}
                        creating={creatingRegistration}
                        onSubmit={handleRegistrationSubmit}
                      />

                      <CreateUserDialog
                        open={showCreateUserDialog}
                        onOpenChange={handleCreateUserDialogOpenChange}
                        error={createUserError}
                        form={createUserForm}
                        setForm={setCreateUserForm}
                        creating={creatingUser}
                        onSubmit={handleCreateUserSubmit}
                      />
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
                        onCheckedChange={(checked) => {
                          const enabled = Boolean(checked);
                          handleRegistrationSettingsUpdate(
                            { enable_registration: enabled },
                            enabled ? 'Self-registration enabled.' : 'Self-registration disabled.'
                          );
                        }}
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
                        onCheckedChange={(checked) => {
                          const required = Boolean(checked);
                          handleRegistrationSettingsUpdate(
                            { require_registration_code: required },
                            required ? 'Registration codes required.' : 'Registration codes optional.'
                          );
                        }}
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
                        <AccessibleIconButton
                          icon={Clipboard}
                          label="Copy registration code"
                          variant="ghost"
                          onClick={() => copyToClipboard(latestRegistrationCode.code, 'Registration code')}
                        />
                      </div>
                    </div>
                  )}

                  <div className="mt-4 space-y-3">
                    {recentRegistrationCodes.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No active registration codes yet.</p>
                    ) : (
                      recentRegistrationCodes.map((code) => {
                        const active = isRegistrationCodeActive(code);
                        const isDeleting = deletingRegistrationId === String(code.id);
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
                              <AccessibleIconButton
                                icon={Clipboard}
                                label="Copy registration code"
                                variant="ghost"
                                onClick={() => copyToClipboard(code.code, 'Registration code')}
                              />
                              <AccessibleIconButton
                                icon={isDeleting ? RefreshCw : Trash2}
                                label={isDeleting ? 'Deleting registration code' : 'Delete registration code'}
                                variant="ghost"
                                onClick={() => handleRegistrationDelete(code)}
                                disabled={isDeleting}
                                iconClassName={isDeleting ? 'animate-spin text-destructive' : 'text-destructive'}
                              />
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
                    <CreateOrganizationDialog
                      open={showOrgDialog}
                      onOpenChange={handleOrgDialogOpenChange}
                      error={orgError}
                      form={orgForm}
                      onNameChange={handleOrgNameChange}
                      onSlugChange={handleOrgSlugChange}
                      creating={creatingOrg}
                      onSubmit={handleOrgSubmit}
                    />
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

            {/* Security Health Card */}
            <div className="mt-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <ShieldAlert className="h-5 w-5" />
                    Security Overview
                  </CardTitle>
                  <CardDescription>Security posture and recent activity</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">Risk Score</p>
                      <div className="flex items-center gap-2">
                        <span className={`text-2xl font-bold ${
                          (securityHealth?.risk_score ?? 0) >= 70 ? 'text-red-500' :
                          (securityHealth?.risk_score ?? 0) >= 40 ? 'text-yellow-500' :
                          'text-green-500'
                        }`}>
                          {securityHealth?.risk_score ?? 0}
                        </span>
                        <span className="text-xs text-muted-foreground">/ 100</span>
                      </div>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">Security Events (24h)</p>
                      <p className="text-2xl font-bold">{securityHealth?.recent_security_events ?? 0}</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">Failed Logins (24h)</p>
                      <p className={`text-2xl font-bold ${
                        (securityHealth?.failed_logins_24h ?? 0) > 10 ? 'text-red-500' : ''
                      }`}>
                        {securityHealth?.failed_logins_24h ?? 0}
                      </p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">Suspicious Activity</p>
                      <p className={`text-2xl font-bold ${
                        (securityHealth?.suspicious_activity ?? 0) > 0 ? 'text-yellow-500' : ''
                      }`}>
                        {securityHealth?.suspicious_activity ?? 0}
                      </p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">MFA Adoption</p>
                      <p className="text-2xl font-bold">{securityHealth?.mfa_adoption_rate ?? 0}%</p>
                    </div>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button variant="outline" size="sm" onClick={() => router.push('/security')}>
                      Security Dashboard
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => router.push('/audit?filter=security')}>
                      Security Audit Logs
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
        </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
