'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { usePrivilegedActionDialog } from '@/components/ui/privileged-action-dialog';
import { useToast } from '@/components/ui/toast';
import { ArrowLeft, Key, Save, Building2, Users, Shield, Monitor, RefreshCw, Trash2, Clock, ShieldCheck, Plus, X } from 'lucide-react';
import { AccessibleIconButton } from '@/components/ui/accessible-icon-button';
import { api, ApiError } from '@/lib/api-client';
import { formatDateTime } from '@/lib/format';
import { parseOptionalInt } from '@/lib/number';
import {
  deriveLimitPerMinute,
  getDerivedLimitPerMin,
  normalizeRateLimitValue,
  validateRateLimitInputs,
} from '@/lib/rate-limits';
import { canEditFromMemberships } from '@/lib/permissions';
import { User, Permission, AuditLog } from '@/types';
import Link from 'next/link';

type UserRateLimits = {
  requests_per_minute?: number | null;
  requests_per_hour?: number | null;
  requests_per_day?: number | null;
};

type RateLimitUpsertPayload = {
  resource: string;
  limit_per_min: number | null;
  burst: number | null;
};

const DEFAULT_RATE_LIMIT_RESOURCE = 'api.default';

type PermissionOverride = {
  id: number;
  permission_id: number;
  permission_name: string;
  grant: boolean;
};

type EffectivePermissionSource = 'role' | 'override' | 'inherited';

type EffectivePermission = {
  id: number;
  name: string;
  source: EffectivePermissionSource;
  sourceLabel?: string;
};

const roleOptions = [
  { value: 'user', label: 'User' },
  { value: 'admin', label: 'Admin' },
  { value: 'service', label: 'Service' },
] as const;

type UserRole = (typeof roleOptions)[number]['value'];

type UserFormData = {
  username: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  storage_quota_mb: number;
};

const isValidRole = (role: string): role is UserRole => roleOptions.some((option) => option.value === role);
type MfaStatus = {
  enabled: boolean;
  has_secret: boolean;
  has_backup_codes: boolean;
  method?: string | null;
};

type UserSession = {
  id: number;
  ip_address?: string | null;
  user_agent?: string | null;
  created_at: string;
  last_activity?: string | null;
  expires_at?: string | null;
};

type PasswordResetResponse = {
  force_password_change?: boolean;
  message?: string;
};

type LoginHistoryStatus = 'success' | 'failure';

type LoginHistoryEntry = {
  id: string;
  timestamp: string;
  ipAddress?: string;
  userAgent?: string;
  status: LoginHistoryStatus;
};

type OrgMembership = {
  org_id: number;
  role: string;
  org_name?: string;
};

type TeamMembership = {
  team_id: number;
  org_id: number;
  role: string;
  team_name?: string;
  org_name?: string;
};

type RateLimitRecord = {
  resource?: string;
  limit_per_min?: number | null;
  burst?: number | null;
  requests_per_minute?: number | null;
  requests_per_hour?: number | null;
  requests_per_day?: number | null;
};

const toOptionalNumber = (input: unknown): number | null => {
  if (typeof input !== 'number' || !Number.isFinite(input)) return null;
  return input > 0 ? input : null;
};

const selectRateLimitRecord = (items: RateLimitRecord[]): RateLimitRecord | null => {
  if (!items.length) return null;
  return items.find((item) => item.resource === DEFAULT_RATE_LIMIT_RESOURCE) ?? items[0];
};

const normalizeRateLimits = (value: unknown): UserRateLimits | null => {
  if (!value) return null;
  if (Array.isArray(value)) {
    const record = selectRateLimitRecord(value as RateLimitRecord[]);
    return record ? normalizeRateLimits(record) : null;
  }
  if (typeof value !== 'object') return null;

  const container = value as RateLimitRecord & { rate_limits?: unknown; items?: unknown };
  if (container.rate_limits) {
    return normalizeRateLimits(container.rate_limits);
  }
  if (container.items) {
    return normalizeRateLimits(container.items);
  }

  const rpm = toOptionalNumber(container.requests_per_minute ?? container.limit_per_min);
  const rph = toOptionalNumber(container.requests_per_hour);
  const rpd = toOptionalNumber(container.requests_per_day);

  if (rpm === null && rph === null && rpd === null) return null;
  return {
    requests_per_minute: rpm,
    requests_per_hour: rph,
    requests_per_day: rpd,
  };
};

const isForbiddenError = (err: unknown): boolean => {
  if (err instanceof ApiError) {
    return err.status === 403;
  }
  if (typeof err === 'object' && err !== null && 'status' in err) {
    return (err as { status?: number }).status === 403;
  }
  if (err instanceof Error) {
    return /not authorized|forbidden|permission/i.test(err.message);
  }
  return false;
};

const formatDate = (dateStr?: string) => formatDateTime(dateStr, { fallback: 'Never' });

const getLoginAttemptStatus = (entry: AuditLog): LoginHistoryStatus => {
  const details = entry.details ?? {};
  const raw = entry.raw ?? {};
  const successValue = details.success ?? raw.success;
  if (typeof successValue === 'boolean') {
    return successValue ? 'success' : 'failure';
  }

  const statusText = String(details.status ?? details.result ?? raw.status ?? '').toLowerCase();
  if (statusText.includes('fail') || statusText.includes('error') || statusText.includes('denied')) {
    return 'failure';
  }
  if (statusText.includes('success') || statusText.includes('ok')) {
    return 'success';
  }

  const actionText = String(entry.action ?? raw.action ?? '').toLowerCase();
  if (actionText.includes('fail') || actionText.includes('denied')) {
    return 'failure';
  }
  return 'success';
};

const toLoginHistoryEntry = (entry: AuditLog, index: number): LoginHistoryEntry => {
  const details = entry.details ?? {};
  const raw = entry.raw ?? {};
  const ipValue = entry.ip_address
    ?? (typeof details.ip_address === 'string' ? details.ip_address : undefined)
    ?? (typeof details.ip === 'string' ? details.ip : undefined)
    ?? (typeof raw.ip_address === 'string' ? raw.ip_address : undefined)
    ?? (typeof raw.ip === 'string' ? raw.ip : undefined);
  const detailsUserAgent = details['user_agent'];
  const detailsUserAgentAlt = details['userAgent'];
  const rawUserAgent = raw['user_agent'];
  const rawUserAgentAlt = raw['userAgent'];
  const userAgentValue = (typeof detailsUserAgent === 'string' ? detailsUserAgent : undefined)
    ?? (typeof detailsUserAgentAlt === 'string' ? detailsUserAgentAlt : undefined)
    ?? (typeof rawUserAgent === 'string' ? rawUserAgent : undefined)
    ?? (typeof rawUserAgentAlt === 'string' ? rawUserAgentAlt : undefined);

  return {
    id: entry.id || `${entry.timestamp}-${index}`,
    timestamp: entry.timestamp,
    ipAddress: ipValue,
    userAgent: userAgentValue,
    status: getLoginAttemptStatus(entry),
  };
};

const normalizePermissionOverrideList = (value: unknown): PermissionOverride[] => {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => {
      const record = item as Record<string, unknown>;
      const id = Number(record.id);
      const permissionId = Number(record.permission_id ?? record.permissionId ?? record.id);
      const permissionName = String(record.permission_name ?? record.permissionName ?? '').trim();
      const grantValue = record.grant;
      const grant = typeof grantValue === 'boolean' ? grantValue : true;
      if (!permissionName || !Number.isFinite(permissionId)) return null;
      return {
        id: Number.isFinite(id) ? id : permissionId,
        permission_id: permissionId,
        permission_name: permissionName,
        grant,
      };
    })
    .filter((entry): entry is PermissionOverride => entry !== null);
};

const normalizeEffectivePermissionList = (
  value: unknown,
  overrideEntries: PermissionOverride[],
  roleName?: string
): EffectivePermission[] => {
  if (!Array.isArray(value)) return [];
  const overrideGrantNames = new Set(
    overrideEntries
      .filter((entry) => entry.grant)
      .map((entry) => entry.permission_name)
  );
  return value
    .map((item, index) => {
      const roleLabel = roleName || '';
      if (typeof item === 'string') {
        const permissionName = item.trim();
        if (!permissionName) return null;
        if (overrideGrantNames.has(permissionName)) {
          return {
            id: index,
            name: permissionName,
            source: 'override' as const,
            sourceLabel: 'Direct override',
          };
        }
        return {
          id: index,
          name: permissionName,
          source: 'role' as const,
          sourceLabel: roleLabel || 'role',
        };
      }

      if (!item || typeof item !== 'object') return null;
      const record = item as Record<string, unknown>;
      const permissionName = String(
        record.name ?? record.permission_name ?? record.permission ?? ''
      ).trim();
      if (!permissionName) return null;
      const sourceText = String(record.source ?? '').toLowerCase();
      const explicitRoleName = String(record.role_name ?? record.source_role ?? '').trim();
      const idValue = Number(record.id ?? index);

      let source: EffectivePermissionSource = 'inherited';
      let sourceLabel = 'Inherited';
      if (sourceText.includes('override') || overrideGrantNames.has(permissionName)) {
        source = 'override';
        sourceLabel = 'Direct override';
      } else if (sourceText.includes('inherit')) {
        source = 'inherited';
        sourceLabel = 'Inherited';
      } else if (sourceText.includes('role') || explicitRoleName) {
        source = 'role';
        sourceLabel = explicitRoleName || roleLabel || 'role';
      } else if (roleLabel) {
        source = 'role';
        sourceLabel = roleLabel;
      }

      return {
        id: Number.isFinite(idValue) ? idValue : index,
        name: permissionName,
        source,
        sourceLabel,
      };
    })
    .filter((entry): entry is EffectivePermission => entry !== null);
};

export default function UserDetailPage() {
  const params = useParams();
  const router = useRouter();
  const userId = Array.isArray(params.id) ? params.id[0] : params.id;
  const confirm = useConfirm();
  const promptPrivilegedAction = usePrivilegedActionDialog();
  const { success: toastSuccess, error: showError } = useToast();

  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isAuthorized, setIsAuthorized] = useState(true);
  const [securityLoading, setSecurityLoading] = useState(false);
  const [securityError, setSecurityError] = useState('');
  const [mfaStatus, setMfaStatus] = useState<MfaStatus | null>(null);
  const [sessions, setSessions] = useState<UserSession[]>([]);
  const [loginHistory, setLoginHistory] = useState<LoginHistoryEntry[]>([]);
  const [loginHistoryLoading, setLoginHistoryLoading] = useState(false);
  const [loginHistoryError, setLoginHistoryError] = useState('');
  const [showOrgMembershipsDialog, setShowOrgMembershipsDialog] = useState(false);
  const [showTeamMembershipsDialog, setShowTeamMembershipsDialog] = useState(false);
  const [orgMemberships, setOrgMemberships] = useState<OrgMembership[]>([]);
  const [teamMemberships, setTeamMemberships] = useState<TeamMembership[]>([]);
  const [orgMembershipsLoading, setOrgMembershipsLoading] = useState(false);
  const [teamMembershipsLoading, setTeamMembershipsLoading] = useState(false);
  const [orgMembershipsError, setOrgMembershipsError] = useState('');
  const [teamMembershipsError, setTeamMembershipsError] = useState('');
  const [forcePasswordChangeOnNextLogin, setForcePasswordChangeOnNextLogin] = useState(true);
  const [passwordResetLoading, setPasswordResetLoading] = useState(false);
  const [resetPasswordValue, setResetPasswordValue] = useState('');

  const [formData, setFormData] = useState<UserFormData>({
    username: '',
    email: '',
    role: 'user',
    is_active: true,
    storage_quota_mb: 0,
  });

  // Rate Limits
  const [rateLimits, setRateLimits] = useState<UserRateLimits>({});
  const [editRpm, setEditRpm] = useState('');
  const [editRph, setEditRph] = useState('');
  const [editRpd, setEditRpd] = useState('');
  const [rateLimitsSaving, setRateLimitsSaving] = useState(false);

  // Permission Overrides
  const [permissionOverrides, setPermissionOverrides] = useState<PermissionOverride[]>([]);
  const [effectivePermissions, setEffectivePermissions] = useState<EffectivePermission[]>([]);
  const [allPermissions, setAllPermissions] = useState<Permission[]>([]);
  const [permissionsLoading, setPermissionsLoading] = useState(false);
  const [showAddOverride, setShowAddOverride] = useState(false);
  const [newOverridePermissionId, setNewOverridePermissionId] = useState('');
  const [newOverrideGrant, setNewOverrideGrant] = useState(true);

  const applyRateLimits = useCallback((limits?: UserRateLimits | null) => {
    if (!limits) {
      setRateLimits({});
      setEditRpm('');
      setEditRph('');
      setEditRpd('');
      return;
    }
    setRateLimits(limits);
    setEditRpm(limits.requests_per_minute?.toString() || '');
    setEditRph(limits.requests_per_hour?.toString() || '');
    setEditRpd(limits.requests_per_day?.toString() || '');
  }, []);

  const loadUser = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      setIsAuthorized(true);
      const data = await api.getUser(userId);
      const userValue = data as User & { rate_limits?: UserRateLimits; metadata?: Record<string, unknown> };
      const roleValue = userValue.role && isValidRole(userValue.role) ? userValue.role : 'user';
      setUser(userValue);
      setFormData({
        username: userValue.username || '',
        email: userValue.email || '',
        role: roleValue,
        is_active: userValue.is_active ?? true,
        storage_quota_mb: userValue.storage_quota_mb || 0,
      });
      const normalizedRateLimits = normalizeRateLimits(userValue.rate_limits);
      applyRateLimits(normalizedRateLimits);
      const forceChange =
        typeof userValue.metadata?.force_password_change === 'boolean'
          ? userValue.metadata.force_password_change
          : true;
      setForcePasswordChangeOnNextLogin(forceChange);

      try {
        const currentUser = await api.getCurrentUser();
        const [adminMemberships, targetMemberships] = await Promise.all([
          api.getUserOrgMemberships(currentUser.id.toString()),
          api.getUserOrgMemberships(userId),
        ]);

        const adminList = Array.isArray(adminMemberships) ? adminMemberships : [];
        const targetList = Array.isArray(targetMemberships) ? targetMemberships : [];

        if (!canEditFromMemberships(adminList, targetList)) {
          setIsAuthorized(false);
          setError('You are not authorized to edit this user.');
        }
      } catch (scopeErr: unknown) {
        if (isForbiddenError(scopeErr)) {
          setIsAuthorized(false);
          setError('You are not authorized to edit this user.');
        } else {
          console.error('Failed to verify user scope:', scopeErr);
        }
      }
    } catch (err: unknown) {
      if (isForbiddenError(err)) {
        setIsAuthorized(false);
        setError('You are not authorized to view or edit this user.');
        setUser(null);
        return;
      }
      const message =
        err instanceof Error ? err.message : typeof err === 'string' ? err : 'Failed to load user';
      console.error('Failed to load user:', message);
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [applyRateLimits, userId]);

  const loadSecurity = useCallback(async () => {
    if (!userId) return;
    try {
      setSecurityLoading(true);
      setSecurityError('');
      const [mfaResult, sessionsResult] = await Promise.allSettled([
        api.getUserMfaStatus(userId),
        api.getUserSessions(userId),
      ]);

      if (mfaResult.status === 'fulfilled') {
        setMfaStatus(mfaResult.value as MfaStatus);
      } else {
        setMfaStatus(null);
      }

      if (sessionsResult.status === 'fulfilled') {
        setSessions(Array.isArray(sessionsResult.value) ? (sessionsResult.value as UserSession[]) : []);
      } else {
        setSessions([]);
      }

      if (mfaResult.status === 'rejected' || sessionsResult.status === 'rejected') {
        setSecurityError('Failed to load security controls.');
      }
    } catch (err: unknown) {
      console.error('Failed to load security controls:', err);
      setSecurityError('Failed to load security controls.');
      setMfaStatus(null);
      setSessions([]);
    } finally {
      setSecurityLoading(false);
    }
  }, [userId]);

  const loadLoginHistory = useCallback(async () => {
    if (!userId) return;
    try {
      setLoginHistoryLoading(true);
      setLoginHistoryError('');
      const response = await api.getAuditLogs({
        user_id: String(userId),
        action: 'login',
        limit: '20',
        offset: '0',
      });
      const entries = Array.isArray(response?.entries)
        ? (response.entries as AuditLog[])
        : [];
      const mapped = entries.map((entry, index) => toLoginHistoryEntry(entry, index));
      mapped.sort((a, b) => {
        const aTime = Date.parse(a.timestamp || '');
        const bTime = Date.parse(b.timestamp || '');
        return (Number.isFinite(bTime) ? bTime : 0) - (Number.isFinite(aTime) ? aTime : 0);
      });
      setLoginHistory(mapped.slice(0, 20));
    } catch (err: unknown) {
      console.error('Failed to load login history:', err);
      setLoginHistory([]);
      setLoginHistoryError('Failed to load login history.');
    } finally {
      setLoginHistoryLoading(false);
    }
  }, [userId]);

  const loadOrgMemberships = useCallback(async () => {
    if (!userId) return;
    try {
      setOrgMembershipsLoading(true);
      setOrgMembershipsError('');
      const response = await api.getUserOrgMemberships(userId);
      const items = Array.isArray(response) ? response : [];
      const normalized = items
        .map((item) => {
          if (!item || typeof item !== 'object') return null;
          const record = item as Record<string, unknown>;
          const orgId = Number(record.org_id);
          const role = String(record.role ?? '').trim();
          const orgName = record.org_name;
          if (!Number.isFinite(orgId) || !role) return null;
          return {
            org_id: orgId,
            role,
            org_name: typeof orgName === 'string' ? orgName : undefined,
          };
        })
        .filter((entry): entry is OrgMembership => entry !== null);
      setOrgMemberships(normalized);
    } catch (err: unknown) {
      console.error('Failed to load user organizations:', err);
      setOrgMemberships([]);
      setOrgMembershipsError('Failed to load user organizations.');
    } finally {
      setOrgMembershipsLoading(false);
    }
  }, [userId]);

  const loadTeamMemberships = useCallback(async () => {
    if (!userId) return;
    try {
      setTeamMembershipsLoading(true);
      setTeamMembershipsError('');
      const response = await api.getUserTeamMemberships(userId);
      const items = Array.isArray(response) ? response : [];
      const normalized = items
        .map((item) => {
          if (!item || typeof item !== 'object') return null;
          const record = item as Record<string, unknown>;
          const teamId = Number(record.team_id);
          const orgId = Number(record.org_id);
          const role = String(record.role ?? '').trim();
          const teamName = record.team_name;
          const orgName = record.org_name;
          if (!Number.isFinite(teamId) || !Number.isFinite(orgId) || !role) return null;
          return {
            team_id: teamId,
            org_id: orgId,
            role,
            team_name: typeof teamName === 'string' ? teamName : undefined,
            org_name: typeof orgName === 'string' ? orgName : undefined,
          };
        })
        .filter((entry): entry is TeamMembership => entry !== null);
      setTeamMemberships(normalized);
    } catch (err: unknown) {
      console.error('Failed to load user teams:', err);
      setTeamMemberships([]);
      setTeamMembershipsError('Failed to load user teams.');
    } finally {
      setTeamMembershipsLoading(false);
    }
  }, [userId]);

  const loadPermissions = useCallback(async () => {
    if (!userId) return;
    try {
      setPermissionsLoading(true);
      const results = await Promise.allSettled([
        api.getUserEffectivePermissions(userId),
        api.getUserPermissionOverrides(userId),
        api.getPermissions(),
        api.getUserRateLimits(userId),
      ]);
      const [effectiveResult, overridesResult, allPermsResult, rateLimitsResult] = results;
      const hasRejected = results.some((result) => result.status === 'rejected');
      if (hasRejected) {
        setEffectivePermissions([]);
        setPermissionOverrides([]);
        setAllPermissions([]);
        applyRateLimits(normalizeRateLimits({}));
        return;
      }

      let normalizedOverrides: PermissionOverride[] = [];
      if (overridesResult.status === 'fulfilled') {
        const data = overridesResult.value as { overrides?: unknown; items?: unknown };
        const rawOverrides = Array.isArray(data.overrides) ? data.overrides :
          Array.isArray(data.items) ? data.items :
          Array.isArray(data) ? data : [];
        normalizedOverrides = normalizePermissionOverrideList(rawOverrides);
      }
      setPermissionOverrides(normalizedOverrides);

      if (effectiveResult.status === 'fulfilled') {
        const data = effectiveResult.value as { permissions?: unknown; items?: unknown };
        const rawPermissions = Array.isArray(data.permissions) ? data.permissions :
          Array.isArray(data.items) ? data.items :
          Array.isArray(data) ? data : [];
        setEffectivePermissions(
          normalizeEffectivePermissionList(rawPermissions, normalizedOverrides, user?.role)
        );
      } else {
        setEffectivePermissions([]);
      }

      if (allPermsResult.status === 'fulfilled') {
        setAllPermissions(Array.isArray(allPermsResult.value) ? allPermsResult.value : []);
      }

      if (rateLimitsResult.status === 'fulfilled') {
        const normalizedRateLimits = normalizeRateLimits(rateLimitsResult.value);
        applyRateLimits(normalizedRateLimits);
      }
    } catch (err: unknown) {
      console.error('Failed to load permissions:', err);
    } finally {
      setPermissionsLoading(false);
    }
  }, [applyRateLimits, user?.role, userId]);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  useEffect(() => {
    if (user && isAuthorized) {
      void loadSecurity();
      void loadPermissions();
      void loadLoginHistory();
    }
  }, [user, isAuthorized, loadLoginHistory, loadSecurity, loadPermissions]);

  const handleSave = async () => {
    if (!isAuthorized) {
      setError('You are not authorized to update this user.');
      return;
    }
    const requiresPrivilegedApproval = Boolean(
      user && (
        formData.role !== user.role
        || formData.is_active !== user.is_active
      )
    );
    try {
      setSaving(true);
      setError('');
      setSuccess('');
      let payload: Record<string, unknown> = { ...formData };
      if (requiresPrivilegedApproval) {
        const approval = await promptPrivilegedAction({
          title: 'Apply privileged user changes',
          message: 'Changing role or activation state requires a reason and reauthentication.',
          confirmText: 'Apply changes',
        });
        if (!approval) {
          setSaving(false);
          return;
        }
        payload = {
          ...payload,
          reason: approval.reason,
          admin_password: approval.adminPassword,
        };
      }
      await api.updateUser(userId, payload);
      setSuccess('User updated successfully');
      void loadUser();
    } catch (err: unknown) {
      if (isForbiddenError(err)) {
        setIsAuthorized(false);
        setError('You are not authorized to update this user.');
        return;
      }
      if (err instanceof Error) {
        console.error('Failed to update user:', err);
        setError(err.message);
      } else {
        console.error('Failed to update user:', err);
        setError(String(err));
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDisableMfa = async () => {
    if (!mfaStatus?.enabled) return;
    const approval = await promptPrivilegedAction({
      title: 'Disable MFA',
      message: `Disable MFA for ${user?.username || user?.email || 'this user'}?`,
      confirmText: 'Disable MFA',
    });
    if (!approval) return;

    try {
      await api.disableUserMfa(userId, {
        reason: approval.reason,
        admin_password: approval.adminPassword,
      });
      toastSuccess('MFA disabled', 'Multi-factor authentication has been turned off.');
      void loadSecurity();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to disable MFA';
      showError('Disable MFA failed', message);
    }
  };

  const handleRevokeSession = async (session: UserSession) => {
    const approval = await promptPrivilegedAction({
      title: 'Revoke Session',
      message: 'Revoke this session? The user will be signed out on that device.',
      confirmText: 'Revoke',
    });
    if (!approval) return;

    try {
      await api.revokeUserSession(userId, session.id.toString(), {
        reason: approval.reason,
        admin_password: approval.adminPassword,
      });
      toastSuccess('Session revoked', 'The session has been revoked.');
      void loadSecurity();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to revoke session';
      showError('Revoke failed', message);
    }
  };

  const handleRevokeAllSessions = async () => {
    const approval = await promptPrivilegedAction({
      title: 'Revoke All Sessions',
      message: 'Revoke all active sessions for this user? They will be signed out everywhere.',
      confirmText: 'Revoke all',
    });
    if (!approval) return;

    try {
      await api.revokeAllUserSessions(userId, {
        reason: approval.reason,
        admin_password: approval.adminPassword,
      });
      toastSuccess('Sessions revoked', 'All sessions have been revoked.');
      void loadSecurity();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to revoke sessions';
      showError('Revoke failed', message);
    }
  };

  const handleResetPassword = async () => {
    const normalizedTemporaryPassword = resetPasswordValue.trim();
    if (normalizedTemporaryPassword.length < 10) {
      showError('Password reset failed', 'Enter a temporary password with at least 10 characters.');
      return;
    }

    const approval = await promptPrivilegedAction({
      title: 'Reset Password',
      message: `Reset password for ${user?.username || user?.email || 'this user'}?`,
      confirmText: 'Reset password',
    });
    if (!approval) return;

    try {
      setPasswordResetLoading(true);
      await api.resetUserPassword(userId, {
        temporary_password: normalizedTemporaryPassword,
        force_password_change: forcePasswordChangeOnNextLogin,
        reason: approval.reason,
        admin_password: approval.adminPassword,
      }) as PasswordResetResponse;
      setResetPasswordValue('');
      toastSuccess(
        'Password reset',
        'Temporary password updated. Share it with the user through an approved secure channel.'
      );
      void loadUser();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to reset password';
      showError('Password reset failed', message);
    } finally {
      setPasswordResetLoading(false);
    }
  };

  const handleViewOrganizations = () => {
    setShowOrgMembershipsDialog(true);
    void loadOrgMemberships();
  };

  const handleViewTeams = () => {
    setShowTeamMembershipsDialog(true);
    void loadTeamMemberships();
  };

  const buildRateLimitPayload = (
    rpm: number | null,
    rph: number | null,
    rpd: number | null
  ): RateLimitUpsertPayload => {
    const limitPerMin = getDerivedLimitPerMin(rpm, rph, rpd);
    const burstPerMinute = rph != null
      ? deriveLimitPerMinute(rph, 60)
      : rpd != null
        ? deriveLimitPerMinute(rpd, 1440)
        : null;
    const burstMultiplier = burstPerMinute != null && limitPerMin
      ? Math.max(1, burstPerMinute / limitPerMin)
      : 1;

    return {
      resource: DEFAULT_RATE_LIMIT_RESOURCE,
      limit_per_min: normalizeRateLimitValue(limitPerMin),
      burst: normalizeRateLimitValue(burstMultiplier),
    };
  };

  const handleSaveRateLimits = async () => {
    try {
      setRateLimitsSaving(true);
      setError('');
      const data: UserRateLimits = {};
      const rpm = parseOptionalInt(editRpm);
      const rph = parseOptionalInt(editRph);
      const rpd = parseOptionalInt(editRpd);
      const normalizedRpm = normalizeRateLimitValue(rpm);
      const normalizedRph = normalizeRateLimitValue(rph);
      const normalizedRpd = normalizeRateLimitValue(rpd);
      if (normalizedRpm !== null) data.requests_per_minute = normalizedRpm;
      if (normalizedRph !== null) data.requests_per_hour = normalizedRph;
      if (normalizedRpd !== null) data.requests_per_day = normalizedRpd;

      const { error: rateLimitError } = validateRateLimitInputs(
        normalizedRpm,
        normalizedRph,
        normalizedRpd
      );
      if (rateLimitError) {
        setRateLimitsSaving(false);
        setError(rateLimitError);
        return;
      }

      const payload = buildRateLimitPayload(normalizedRpm, normalizedRph, normalizedRpd);
      await api.setUserRateLimits(userId, payload);
      let normalizedRateLimits: UserRateLimits | null = null;
      try {
        const updated = await api.getUserRateLimits(userId);
        normalizedRateLimits = normalizeRateLimits(updated);
      } catch (err: unknown) {
        console.error('Failed to reload rate limits after update:', err);
        normalizedRateLimits = data;
      }
      applyRateLimits(normalizedRateLimits);
      toastSuccess('Rate limits updated', 'User rate limits have been saved.');
    } catch (err: unknown) {
      console.error('Failed to update rate limits:', err);
      const message = err instanceof Error ? err.message : 'Failed to update rate limits';
      showError('Save failed', message);
    } finally {
      setRateLimitsSaving(false);
    }
  };

  const handleClearRateLimits = async () => {
    const confirmed = await confirm({
      title: 'Clear Rate Limits',
      message: 'Remove all custom rate limits for this user? They will inherit role or default limits.',
      confirmText: 'Clear',
      variant: 'danger',
    });
    if (!confirmed) return;

    try {
      setRateLimitsSaving(true);
      await api.setUserRateLimits(userId, {
        resource: DEFAULT_RATE_LIMIT_RESOURCE,
        limit_per_min: null,
        burst: null,
      });
      setRateLimits({});
      setEditRpm('');
      setEditRph('');
      setEditRpd('');
      toastSuccess('Rate limits cleared', 'Custom rate limits have been removed.');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to clear rate limits';
      showError('Clear failed', message);
    } finally {
      setRateLimitsSaving(false);
    }
  };

  const handleAddPermissionOverride = async () => {
    if (!newOverridePermissionId) {
      showError('Select permission', 'Please select a permission to override.');
      return;
    }

    try {
      setPermissionsLoading(true);
      await api.addUserPermissionOverride(userId, {
        permission_id: parseInt(newOverridePermissionId, 10),
        grant: newOverrideGrant,
      });
      toastSuccess('Override added', 'Permission override has been added.');
      setShowAddOverride(false);
      setNewOverridePermissionId('');
      setNewOverrideGrant(true);
      void loadPermissions();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to add override';
      showError('Add failed', message);
    } finally {
      setPermissionsLoading(false);
    }
  };

  const handleRemovePermissionOverride = async (override: PermissionOverride) => {
    const confirmed = await confirm({
      title: 'Remove Override',
      message: `Remove the override for "${override.permission_name}"? The user will inherit this permission from their role.`,
      confirmText: 'Remove',
      variant: 'warning',
    });
    if (!confirmed) return;

    try {
      setPermissionsLoading(true);
      await api.removeUserPermissionOverride(userId, override.id.toString());
      toastSuccess('Override removed', 'Permission override has been removed.');
      void loadPermissions();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to remove override';
      showError('Remove failed', message);
    } finally {
      setPermissionsLoading(false);
    }
  };

  const formatStorage = (usedMb: number, quotaMb: number) => {
    const percentage = quotaMb > 0 ? (usedMb / quotaMb) * 100 : 0;
    return {
      used: usedMb.toFixed(1),
      quota: quotaMb,
      percentage: Math.min(percentage, 100).toFixed(1),
    };
  };

  let content: JSX.Element = <></>;

  if (loading) {
    content = (
      <div className="p-4 lg:p-8">
        <div className="text-center text-muted-foreground py-8">Loading user...</div>
      </div>
    );
  } else if (!user) {
    if (!isAuthorized) {
      content = (
        <div className="p-4 lg:p-8">
          <Alert variant="destructive">
            <AlertDescription>You are not authorized to view this user.</AlertDescription>
          </Alert>
          <Button onClick={() => router.push('/users')} className="mt-4">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Users
          </Button>
        </div>
      );
    } else {
      content = (
        <div className="p-4 lg:p-8">
          <Alert variant="destructive">
            <AlertDescription>User not found</AlertDescription>
          </Alert>
          <Button onClick={() => router.push('/users')} className="mt-4">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Users
          </Button>
        </div>
      );
    }
  } else {
    const storage = formatStorage(user.storage_used_mb || 0, user.storage_quota_mb || 0);
    content = (
      <div className="p-4 lg:p-8">
            {/* Header */}
            <div className="mb-8 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <AccessibleIconButton
                  icon={ArrowLeft}
                  label="Go back to users list"
                  variant="ghost"
                  onClick={() => router.push('/users')}
                />
                <div>
                  <h1 className="text-3xl font-bold">{user.username}</h1>
                  <p className="text-muted-foreground">{user.email}</p>
                </div>
                <Badge variant={user.is_active ? 'default' : 'destructive'}>
                  {user.is_active ? 'Active' : 'Inactive'}
                </Badge>
                <Badge variant="outline">{user.role}</Badge>
              </div>
              <div className="flex gap-2">
                <Link href={`/users/${userId}/api-keys`}>
                  <Button variant="outline">
                    <Key className="mr-2 h-4 w-4" />
                    API Keys
                  </Button>
                </Link>
              </div>
            </div>

            {error && (
              <Alert variant="destructive" className="mb-6">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {success && (
              <Alert className="mb-6 bg-green-50 border-green-200">
                <AlertDescription className="text-green-800">{success}</AlertDescription>
              </Alert>
            )}

            <div className="grid gap-6 lg:grid-cols-2">
              {/* User Info Card */}
              <Card>
                <CardHeader>
                  <CardTitle>User Information</CardTitle>
                  <CardDescription>View and edit user details</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>User ID</Label>
                      <Input value={user.id} disabled />
                    </div>
                    <div className="space-y-2">
                      <Label>UUID</Label>
                      <Input value={user.uuid} disabled className="font-mono text-xs" />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="username">Username</Label>
                    <Input
                      id="username"
                      value={formData.username}
                      disabled={!isAuthorized}
                      onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <Input
                      id="email"
                      type="email"
                      value={formData.email}
                      disabled={!isAuthorized}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="role">Role</Label>
                    <Select
                      id="role"
                      value={formData.role}
                      disabled={!isAuthorized}
                      onChange={(e) => {
                        const nextRole = e.target.value;
                        if (isValidRole(nextRole)) {
                          setFormData({ ...formData, role: nextRole });
                        }
                      }}
                    >
                      {roleOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="is_active"
                      checked={formData.is_active}
                      disabled={!isAuthorized}
                      onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                      className="h-4 w-4 rounded border-primary"
                    />
                    <Label htmlFor="is_active">Active</Label>
                  </div>

                  <Button onClick={handleSave} disabled={saving || !isAuthorized} loading={saving} loadingText="Saving...">
                    <Save className="mr-2 h-4 w-4" />
                    Save Changes
                  </Button>
                </CardContent>
              </Card>

              {/* Storage & Activity Card */}
              <Card>
                <CardHeader>
                  <CardTitle>Storage & Activity</CardTitle>
                  <CardDescription>Usage statistics and timestamps</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Storage Usage */}
                  <div className="space-y-2">
                    <Label>Storage Usage</Label>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>{storage.used} MB used</span>
                        <span>{storage.quota} MB quota</span>
                      </div>
                      <div
                        className="w-full bg-gray-200 rounded-full h-3"
                        role="progressbar"
                        aria-valuenow={parseFloat(storage.percentage)}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-label={`Storage usage: ${storage.percentage}%${
                          parseFloat(storage.percentage) > 90 ? ', critical' :
                          parseFloat(storage.percentage) > 70 ? ', warning' : ''
                        }`}
                      >
                        <div
                          className={`h-3 rounded-full transition-all ${
                            parseFloat(storage.percentage) > 90 ? 'bg-red-500' :
                            parseFloat(storage.percentage) > 70 ? 'bg-yellow-500' :
                            'bg-green-500'
                          }`}
                          style={{ width: `${storage.percentage}%` }}
                        />
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {storage.percentage}% of quota used
                      </p>
                    </div>

                    <div className="pt-2">
                      <Label htmlFor="storage_quota">Storage Quota (MB)</Label>
                      <Input
                        id="storage_quota"
                        type="number"
                        min="0"
                        value={formData.storage_quota_mb}
                        disabled={!isAuthorized}
                        onChange={(e) => {
                          const val = parseInt(e.target.value, 10);
                          setFormData({
                            ...formData,
                            storage_quota_mb: Number.isNaN(val) ? formData.storage_quota_mb : val,
                          });
                        }}
                        className="mt-1"
                      />
                    </div>
                  </div>

                  {/* Timestamps */}
                  <div className="space-y-3 pt-4 border-t">
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Created</span>
                      <span className="text-sm">{formatDate(user.created_at)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Updated</span>
                      <span className="text-sm">{formatDate(user.updated_at)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Last Login</span>
                      <span className="text-sm">{formatDate(user.last_login)}</span>
                    </div>
                  </div>

                  {/* Verification Status */}
                  <div className="pt-4 border-t">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Email Verified</span>
                      <Badge variant={user.is_verified ? 'default' : 'secondary'}>
                        {user.is_verified ? 'Verified' : 'Not Verified'}
                      </Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Security Controls */}
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle>Security Controls</CardTitle>
                  <CardDescription>MFA status and active sessions</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {securityError && (
                    <Alert variant="destructive">
                      <AlertDescription>{securityError}</AlertDescription>
                    </Alert>
                  )}

                  <div className="rounded-lg border p-4 space-y-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="font-medium">Password reset</div>
                        <p className="text-sm text-muted-foreground">
                          Generate a temporary password for this user.
                        </p>
                      </div>
                      <Button
                        onClick={handleResetPassword}
                        disabled={!isAuthorized || passwordResetLoading}
                        loading={passwordResetLoading}
                        loadingText="Resetting..."
                      >
                        Reset Password
                      </Button>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="temporary-password">Temporary Password to Set</Label>
                      <Input
                        id="temporary-password"
                        type="password"
                        autoComplete="new-password"
                        value={resetPasswordValue}
                        onChange={(event) => setResetPasswordValue(event.target.value)}
                        disabled={!isAuthorized || passwordResetLoading}
                        minLength={10}
                        placeholder="Enter a temporary password to share securely"
                      />
                      <p className="text-xs text-muted-foreground">
                        Set the temporary password yourself so it never needs to be returned to the browser.
                      </p>
                    </div>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={forcePasswordChangeOnNextLogin}
                        onChange={(event) => setForcePasswordChangeOnNextLogin(event.target.checked)}
                        disabled={!isAuthorized || passwordResetLoading}
                        className="h-4 w-4 rounded border-primary"
                      />
                      Force Password Change on Next Login
                    </label>
                  </div>

                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Shield className="h-4 w-4 text-muted-foreground" />
                        <span className="font-medium">Multi-factor authentication</span>
                      </div>
                      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                        <Badge variant={mfaStatus?.enabled ? 'default' : 'secondary'}>
                          {mfaStatus?.enabled ? 'Enabled' : 'Disabled'}
                        </Badge>
                        {mfaStatus?.method && <span className="text-xs">Method: {mfaStatus.method}</span>}
                        <span className="text-xs">
                          Backup codes: {mfaStatus?.has_backup_codes ? 'Set' : 'Not set'}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        MFA enrollment is managed by the user from their profile.
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      onClick={handleDisableMfa}
                      disabled={!mfaStatus?.enabled || !isAuthorized}
                    >
                      Disable MFA
                    </Button>
                  </div>

                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <Monitor className="h-4 w-4 text-muted-foreground" />
                        <span className="font-medium">Active sessions</span>
                        <Badge variant="outline">{sessions.length}</Badge>
                      </div>
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={loadSecurity} disabled={securityLoading}>
                          <RefreshCw className={`mr-2 h-4 w-4 ${securityLoading ? 'animate-spin' : ''}`} />
                          Refresh
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleRevokeAllSessions}
                          disabled={!sessions.length || !isAuthorized}
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Revoke all
                        </Button>
                      </div>
                    </div>

                    {securityLoading ? (
                      <div className="text-sm text-muted-foreground">Loading sessions...</div>
                    ) : sessions.length === 0 ? (
                      <div className="text-sm text-muted-foreground">No active sessions found.</div>
                    ) : (
                      <div className="overflow-x-auto">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Session</TableHead>
                              <TableHead>IP Address</TableHead>
                              <TableHead>Last Activity</TableHead>
                              <TableHead>Expires</TableHead>
                              <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {sessions.map((session) => (
                              <TableRow key={session.id}>
                                <TableCell>
                                  <div className="text-sm font-mono">{session.id}</div>
                                  <div className="text-xs text-muted-foreground truncate max-w-[240px]">
                                    {session.user_agent || 'Unknown device'}
                                  </div>
                                </TableCell>
                                <TableCell className="text-sm font-mono">
                                  {session.ip_address || '—'}
                                </TableCell>
                                <TableCell className="text-sm">{formatDate(session.last_activity || session.created_at)}</TableCell>
                                <TableCell className="text-sm">{formatDate(session.expires_at || '')}</TableCell>
                                <TableCell className="text-right">
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handleRevokeSession(session)}
                                    disabled={!isAuthorized}
                                  >
                                    Revoke
                                  </Button>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                  </div>

                  <div className="space-y-3 border-t pt-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <Clock className="h-4 w-4 text-muted-foreground" />
                        <span className="font-medium">Login History</span>
                        <Badge variant="outline">{loginHistory.length}</Badge>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={loadLoginHistory}
                        disabled={loginHistoryLoading}
                      >
                        <RefreshCw className={`mr-2 h-4 w-4 ${loginHistoryLoading ? 'animate-spin' : ''}`} />
                        Refresh
                      </Button>
                    </div>

                    {loginHistoryError && (
                      <Alert variant="destructive">
                        <AlertDescription>{loginHistoryError}</AlertDescription>
                      </Alert>
                    )}

                    {loginHistoryLoading ? (
                      <div className="text-sm text-muted-foreground">Loading login history...</div>
                    ) : loginHistory.length === 0 ? (
                      <div className="text-sm text-muted-foreground">No recent login attempts found.</div>
                    ) : (
                      <div className="overflow-x-auto">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Timestamp</TableHead>
                              <TableHead>Status</TableHead>
                              <TableHead>IP Address</TableHead>
                              <TableHead>User Agent</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {loginHistory.map((entry) => (
                              <TableRow key={entry.id}>
                                <TableCell className="text-sm">{formatDate(entry.timestamp)}</TableCell>
                                <TableCell>
                                  <Badge variant={entry.status === 'success' ? 'default' : 'destructive'}>
                                    {entry.status === 'success' ? 'Success' : 'Failure'}
                                  </Badge>
                                </TableCell>
                                <TableCell className="text-sm font-mono">{entry.ipAddress || '—'}</TableCell>
                                <TableCell className="text-xs text-muted-foreground">
                                  {entry.userAgent || 'Unknown client'}
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Rate Limits */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Clock className="h-5 w-5" />
                    Rate Limits
                  </CardTitle>
                  <CardDescription>
                    Set custom rate limits for this user (overrides role defaults)
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-3">
                    <div className="space-y-1">
                      <Label htmlFor="user-rate-rpm">Requests/Min</Label>
                      <Input
                        id="user-rate-rpm"
                        type="number"
                        min="0"
                        placeholder="e.g., 60"
                        value={editRpm}
                        onChange={(e) => setEditRpm(e.target.value)}
                        disabled={!isAuthorized}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="user-rate-rph">Requests/Hour</Label>
                      <Input
                        id="user-rate-rph"
                        type="number"
                        min="0"
                        placeholder="e.g., 1000"
                        value={editRph}
                        onChange={(e) => setEditRph(e.target.value)}
                        disabled={!isAuthorized}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="user-rate-rpd">Requests/Day</Label>
                      <Input
                        id="user-rate-rpd"
                        type="number"
                        min="0"
                        placeholder="e.g., 10000"
                        value={editRpd}
                        onChange={(e) => setEditRpd(e.target.value)}
                        disabled={!isAuthorized}
                      />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      onClick={handleSaveRateLimits}
                      disabled={rateLimitsSaving || !isAuthorized}
                      loading={rateLimitsSaving}
                      loadingText="Saving..."
                    >
                      Save Limits
                    </Button>
                    {(rateLimits.requests_per_minute || rateLimits.requests_per_hour || rateLimits.requests_per_day) && (
                      <Button
                        variant="outline"
                        onClick={handleClearRateLimits}
                        disabled={rateLimitsSaving || !isAuthorized}
                      >
                        Clear
                      </Button>
                    )}
                  </div>
                  {(rateLimits.requests_per_minute || rateLimits.requests_per_hour || rateLimits.requests_per_day) && (
                    <p className="text-sm text-muted-foreground">
                      Current limits:{' '}
                      {rateLimits.requests_per_minute && `${rateLimits.requests_per_minute}/min`}
                      {rateLimits.requests_per_minute && rateLimits.requests_per_hour && ', '}
                      {rateLimits.requests_per_hour && `${rateLimits.requests_per_hour}/hr`}
                      {(rateLimits.requests_per_minute || rateLimits.requests_per_hour) && rateLimits.requests_per_day && ', '}
                      {rateLimits.requests_per_day && `${rateLimits.requests_per_day}/day`}
                    </p>
                  )}
                </CardContent>
              </Card>

              {/* Permission Overrides */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <ShieldCheck className="h-5 w-5" />
                    Permission Overrides
                  </CardTitle>
                  <CardDescription>
                    Grant or deny specific permissions beyond role defaults
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Add Override Form */}
                  {showAddOverride ? (
                    <div className="p-4 border rounded-lg space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">Add Permission Override</span>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setShowAddOverride(false)}
                          aria-label="Close add permission override"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div className="space-y-1">
                          <Label htmlFor="override-permission">Permission</Label>
                          <Select
                            id="override-permission"
                            value={newOverridePermissionId}
                            onChange={(e) => setNewOverridePermissionId(e.target.value)}
                          >
                            <option value="">Select permission...</option>
                            {allPermissions.map((perm) => (
                              <option key={perm.id} value={perm.id}>
                                {perm.name}
                              </option>
                            ))}
                          </Select>
                        </div>
                        <div className="space-y-1">
                          <Label htmlFor="override-grant">Action</Label>
                          <Select
                            id="override-grant"
                            value={newOverrideGrant ? 'grant' : 'deny'}
                            onChange={(e) => setNewOverrideGrant(e.target.value === 'grant')}
                          >
                            <option value="grant">Grant</option>
                            <option value="deny">Deny</option>
                          </Select>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          onClick={handleAddPermissionOverride}
                          disabled={permissionsLoading || !newOverridePermissionId}
                        >
                          Add Override
                        </Button>
                        <Button variant="outline" onClick={() => setShowAddOverride(false)}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <Button
                      variant="outline"
                      onClick={() => setShowAddOverride(true)}
                      disabled={!isAuthorized}
                    >
                      <Plus className="mr-2 h-4 w-4" />
                      Add Override
                    </Button>
                  )}

                  {/* Current Overrides */}
                  {permissionOverrides.length > 0 && (
                    <div className="space-y-2">
                      <span className="text-sm font-medium">Active Overrides</span>
                      <div className="space-y-1">
                        {permissionOverrides.map((override) => (
                          <div
                            key={override.id}
                            className={`flex items-center justify-between p-2 rounded text-sm ${
                              override.grant ? 'bg-green-50 dark:bg-green-900/20' : 'bg-red-50 dark:bg-red-900/20'
                            }`}
                          >
                            <div className="flex items-center gap-2">
                              <Badge variant={override.grant ? 'default' : 'destructive'}>
                                {override.grant ? 'Grant' : 'Deny'}
                              </Badge>
                              <code className="font-mono text-xs">{override.permission_name}</code>
                            </div>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleRemovePermissionOverride(override)}
                              disabled={!isAuthorized || permissionsLoading}
                              aria-label={`Remove override for ${override.permission_name}`}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Effective Permissions */}
                  {effectivePermissions.length > 0 && (
                    <details className="text-sm">
                      <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                        View effective permissions ({effectivePermissions.length})
                      </summary>
                      <div className="mt-2 max-h-48 overflow-y-auto space-y-1">
                        {effectivePermissions.map((perm, index) => (
                          <div
                            key={perm.id || `perm-${index}`}
                            className="flex items-center justify-between p-2 rounded bg-muted/30"
                          >
                            <code className="font-mono text-xs">{perm.name}</code>
                            {perm.source === 'override' ? (
                              <Badge variant="secondary" className="text-xs">
                                Direct override
                              </Badge>
                            ) : perm.source === 'role' ? (
                              <Badge variant="outline" className="text-xs">
                                Role: {perm.sourceLabel || user.role || 'role'}
                              </Badge>
                            ) : (
                              <Badge variant="outline" className="text-xs">
                                Inherited
                              </Badge>
                            )}
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </CardContent>
              </Card>

              {/* Quick Actions */}
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle>Quick Actions</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-4">
                    <Link href={`/users/${userId}/api-keys`}>
                      <Button variant="outline">
                        <Key className="mr-2 h-4 w-4" />
                        Manage API Keys
                      </Button>
                    </Link>
                    <Button variant="outline" onClick={handleViewOrganizations}>
                      <Building2 className="mr-2 h-4 w-4" />
                      View Organizations
                    </Button>
                    <Button variant="outline" onClick={handleViewTeams}>
                      <Users className="mr-2 h-4 w-4" />
                      View Teams
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Dialog open={showOrgMembershipsDialog} onOpenChange={setShowOrgMembershipsDialog}>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>User Organizations</DialogTitle>
                    <DialogDescription>
                      Organizations this user belongs to and their role in each organization.
                    </DialogDescription>
                  </DialogHeader>
                  {orgMembershipsError && (
                    <Alert variant="destructive">
                      <AlertDescription>{orgMembershipsError}</AlertDescription>
                    </Alert>
                  )}
                  {orgMembershipsLoading ? (
                    <div className="text-sm text-muted-foreground">Loading organizations...</div>
                  ) : orgMemberships.length === 0 ? (
                    <div className="text-sm text-muted-foreground">No organization memberships found.</div>
                  ) : (
                    <div className="max-h-80 overflow-y-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Organization</TableHead>
                            <TableHead>Role</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {orgMemberships.map((membership) => (
                            <TableRow key={membership.org_id}>
                              <TableCell className="text-sm">
                                {membership.org_name || `Organization ${membership.org_id}`}
                              </TableCell>
                              <TableCell>
                                <Badge variant="outline">{membership.role}</Badge>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  )}
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setShowOrgMembershipsDialog(false)}>
                      Close
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>

              <Dialog open={showTeamMembershipsDialog} onOpenChange={setShowTeamMembershipsDialog}>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>User Teams</DialogTitle>
                    <DialogDescription>
                      Team memberships with organization context and assigned role.
                    </DialogDescription>
                  </DialogHeader>
                  {teamMembershipsError && (
                    <Alert variant="destructive">
                      <AlertDescription>{teamMembershipsError}</AlertDescription>
                    </Alert>
                  )}
                  {teamMembershipsLoading ? (
                    <div className="text-sm text-muted-foreground">Loading teams...</div>
                  ) : teamMemberships.length === 0 ? (
                    <div className="text-sm text-muted-foreground">No team memberships found.</div>
                  ) : (
                    <div className="max-h-80 overflow-y-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Team</TableHead>
                            <TableHead>Organization</TableHead>
                            <TableHead>Role</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {teamMemberships.map((membership) => (
                            <TableRow key={`${membership.org_id}-${membership.team_id}`}>
                              <TableCell className="text-sm">
                                {membership.team_name || `Team ${membership.team_id}`}
                              </TableCell>
                              <TableCell className="text-sm text-muted-foreground">
                                {membership.org_name || `Organization ${membership.org_id}`}
                              </TableCell>
                              <TableCell>
                                <Badge variant="outline">{membership.role}</Badge>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  )}
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setShowTeamMembershipsDialog(false)}>
                      Close
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          </div>
    );
  }

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
        {content}
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
