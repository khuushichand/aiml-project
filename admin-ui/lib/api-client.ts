'use client';

import { ApiError, requestJson, requestText } from './http';
import { normalizeListResponse, normalizePagedResponse } from './normalize';
import type {
  ApiKey,
  ApiKeyMutationResponse,
  AuditLog,
  BackupScheduleListResponse,
  BackupScheduleMutationResponse,
  BackupsResponse,
  EffectivePermissionsResponse,
  FeatureRegistryEntry,
  IncidentsResponse,
  Invoice,
  OrgMember,
  Organization,
  OrgMembership,
  OrgUsageSummary,
  Plan,
  ProviderSecret,
  RegistrationCode,
  RetentionPoliciesResponse,
  SecurityAlertStatus,
  SecurityHealthData,
  Subscription,
  Team,
  TeamMembership,
  User,
  UserWithKeyCount,
  VoiceAnalyticsSummary,
  VoiceCommand,
  VoiceCommandListResponse,
  VoiceCommandUsage,
  VoiceSession,
  VoiceSessionListResponse,
  WatchlistSettings,
} from '@/types';
export { ApiError };

type QueryParamPrimitive = string | number | boolean;
type QueryParamValue = QueryParamPrimitive | QueryParamPrimitive[] | null | undefined;

type CreatePlanInput = {
  name: string;
  tier: string;
  monthly_price_cents: number;
  included_token_credits: number;
  overage_rate_per_1k_tokens_cents: number;
  stripe_product_id?: string;
  stripe_price_id?: string;
  features?: string[];
  is_default?: boolean;
};

type UpdatePlanInput = Partial<CreatePlanInput>;

type AddTeamMemberInput =
  | { email: string; role?: string }
  | { userId: string | number; role?: string }
  | { user_id: number; role?: string };

function normalizeTeamMemberInput(member: AddTeamMemberInput): Record<string, unknown> {
  if ('email' in member) {
    return { email: member.email, role: member.role };
  }
  if ('user_id' in member) {
    return { user_id: member.user_id, role: member.role };
  }
  if ('userId' in member) {
    const userId = typeof member.userId === 'number'
      ? member.userId
      : Number(member.userId);
    if (!Number.isFinite(userId)) {
      throw new Error('Invalid userId');
    }
    return { user_id: userId, role: member.role };
  }
  throw new Error('Invalid team member payload');
}

function buildQueryString(params?: Record<string, QueryParamValue>): string {
  if (!params) return '';
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined) return;
    if (Array.isArray(value)) {
      value.forEach((entry) => {
        query.append(key, String(entry));
      });
      return;
    }
    query.append(key, String(value));
  });
  return query.toString();
}

function requestRouterAnalytics(path: string, params?: Record<string, string>) {
  const queryParams = params ? new URLSearchParams(params).toString() : '';
  return requestJson(`/admin/router-analytics/${path}${queryParams ? `?${queryParams}` : ''}`);
}

export async function getTeam(teamId: string) {
  return await requestJson(`/admin/teams/${encodeURIComponent(teamId)}`);
}

export async function getTeamMembers(teamId: string) {
  return await requestJson(`/admin/teams/${encodeURIComponent(teamId)}/members`);
}

export async function addTeamMember(teamId: string, member: AddTeamMemberInput) {
  const payload = normalizeTeamMemberInput(member);
  return await requestJson(`/admin/teams/${encodeURIComponent(teamId)}/members`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function removeTeamMember(teamId: string, memberId: string | number) {
  const memberValue = String(memberId).trim();
  if (!memberValue) {
    throw new Error('memberId is required');
  }
  return await requestJson(`/admin/teams/${encodeURIComponent(teamId)}/members/${encodeURIComponent(memberValue)}`, {
    method: 'DELETE',
  });
}

/**
 * API client for tldw_server admin operations
 */
export const api = {
  // ============================================
  // Dashboard & Stats
  // ============================================
  getDashboardStats: () => requestJson('/admin/stats'),
  getDashboardActivity: (days = 7, params?: { granularity?: 'hour' | 'day' }) => {
    const query = new URLSearchParams({ days: String(days) });
    if (params?.granularity) {
      query.set('granularity', params.granularity);
    }
    return requestJson(`/admin/activity?${query.toString()}`);
  },

  // ============================================
  // User Management
  // ============================================
  getUsersPage: async (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    const response = await requestJson(`/admin/users${queryParams ? `?${queryParams}` : ''}`);
    const { items, total, limit } = normalizePagedResponse<UserWithKeyCount>(response, ['users', 'items']);
    const record = response && typeof response === 'object'
      ? (response as Record<string, unknown>)
      : {};
    const page = typeof record.page === 'number' ? record.page : 1;
    const pages = typeof record.pages === 'number'
      ? record.pages
      : (typeof limit === 'number' && limit > 0 ? Math.ceil(total / limit) : 1);
    return {
      items,
      total,
      page,
      limit: limit ?? items.length,
      pages,
    };
  },
  getUsers: async (params?: Record<string, string>) => {
    const response = await api.getUsersPage(params);
    return response.items;
  },
  createUser: (data: Record<string, unknown>) => requestJson('/admin/users', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  getUser: (userId: string) => requestJson<User>(`/admin/users/${userId}`),
  getUserOrgMemberships: (userId: string) => requestJson<OrgMembership[]>(`/admin/users/${userId}/org-memberships`),
  getUserTeamMemberships: (userId: string) => requestJson<TeamMembership[]>(`/admin/users/${userId}/team-memberships`),
  getUserEffectivePermissions: (userId: string) =>
    requestJson<EffectivePermissionsResponse>(`/admin/users/${userId}/effective-permissions`),
  getUserSessions: (userId: string) => requestJson(`/admin/users/${userId}/sessions`),
  revokeUserSession: (userId: string, sessionId: string, data: { reason: string; admin_password?: string | null }) =>
    requestJson(`/admin/users/${userId}/sessions/${sessionId}`, {
      method: 'DELETE',
      body: JSON.stringify(data),
    }),
  revokeAllUserSessions: (userId: string, data: { reason: string; admin_password?: string | null }) =>
    requestJson(`/admin/users/${userId}/sessions/revoke-all`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getUserMfaStatus: (userId: string) => requestJson(`/admin/users/${userId}/mfa`),
  disableUserMfa: (userId: string, data: { reason: string; admin_password?: string | null }) =>
    requestJson(`/admin/users/${userId}/mfa/disable`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  setUserMfaRequirement: (userId: string, data: { require_mfa: boolean; reason: string; admin_password?: string | null }) =>
    requestJson(`/admin/users/${userId}/mfa/require`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateUser: (userId: string, data: Record<string, unknown>) => requestJson(`/admin/users/${userId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  resetUserPassword: (
    userId: string,
    data: { temporary_password: string; force_password_change?: boolean; reason: string; admin_password?: string | null }
  ) => requestJson(`/admin/users/${userId}/reset-password`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  deleteUser: (userId: string, data: { reason: string; admin_password?: string | null }) => requestJson(`/admin/users/${userId}`, {
    method: 'DELETE',
    body: JSON.stringify(data),
  }),
  getCurrentUser: () => requestJson<User>('/users/me'),

  // ============================================
  // Registration Codes
  // ============================================
  getRegistrationSettings: () => requestJson('/admin/registration-settings'),
  updateRegistrationSettings: (data: Record<string, unknown>) => requestJson('/admin/registration-settings', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  getRegistrationCodes: async (includeExpired: boolean = false) => {
    const response = await requestJson(`/admin/registration-codes?include_expired=${includeExpired}`);
    return normalizeListResponse<RegistrationCode>(response, ['codes', 'items']);
  },
  createRegistrationCode: (data: Record<string, unknown>) => requestJson('/admin/registration-codes', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  deleteRegistrationCode: (codeId: number | string) => requestJson(`/admin/registration-codes/${codeId}`, {
    method: 'DELETE',
  }),

  // ============================================
  // API Key Management
  // ============================================
  getUserApiKeys: (
    userId: string,
    params?: {
      include_revoked?: boolean;
    }
  ) => {
    const query = new URLSearchParams();
    if (params?.include_revoked !== undefined) {
      query.set('include_revoked', String(params.include_revoked));
    }
    const suffix = query.toString() ? `?${query.toString()}` : '';
    return requestJson<ApiKey[]>(`/admin/users/${userId}/api-keys${suffix}`);
  },
  createApiKey: (userId: string, data: Record<string, unknown>) => requestJson<ApiKeyMutationResponse>(`/admin/users/${userId}/api-keys`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  rotateApiKey: (userId: string, keyId: string) => requestJson<ApiKeyMutationResponse>(`/admin/users/${userId}/api-keys/${keyId}/rotate`, {
    method: 'POST',
  }),
  revokeApiKey: (userId: string, keyId: string) => requestJson(`/admin/users/${userId}/api-keys/${keyId}`, {
    method: 'DELETE',
  }),
  getApiKeyAuditLog: (keyId: string) => requestJson(`/admin/api-keys/${keyId}/audit-log`),

  // ============================================
  // Organizations
  // ============================================
  getOrganizations: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/admin/orgs${queryParams ? `?${queryParams}` : ''}`);
  },
  getOrganization: (orgId: string) => requestJson<Organization>(`/orgs/${orgId}`),
  createOrganization: (data: Record<string, unknown>) => requestJson('/admin/orgs', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  updateOrganization: (orgId: string, data: Record<string, unknown>) => requestJson(`/orgs/${orgId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  }),
  deleteOrganization: (orgId: string) => requestJson(`/orgs/${orgId}`, {
    method: 'DELETE',
  }),
  getOrgMembers: (orgId: string) => requestJson<OrgMember[]>(`/admin/orgs/${orgId}/members`),
  addOrgMember: (orgId: string, data: Record<string, unknown>) => requestJson(`/admin/orgs/${orgId}/members`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  removeOrgMember: (orgId: string, userId: string) => requestJson(`/admin/orgs/${orgId}/members/${userId}`, {
    method: 'DELETE',
  }),
  updateOrgMemberRole: (orgId: string, userId: string, data: Record<string, unknown>) => requestJson(`/admin/orgs/${orgId}/members/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  }),
  createOrgInvite: (orgId: string, data: Record<string, unknown>) => requestJson(`/orgs/${orgId}/invite`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  getOrgInvites: (orgId: string, params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/orgs/${encodeURIComponent(orgId)}/invites${queryParams ? `?${queryParams}` : ''}`);
  },

  // ============================================
  // Teams
  // ============================================
  getTeam,
  getTeams: (orgId: string) => requestJson<Team[]>(`/admin/orgs/${orgId}/teams`),
  createTeam: (orgId: string, data: Record<string, unknown>) => requestJson(`/admin/orgs/${orgId}/teams`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  updateTeam: (orgId: string, teamId: string, data: Record<string, unknown>) =>
    requestJson(`/orgs/${orgId}/teams/${teamId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  deleteTeam: (orgId: string, teamId: string) =>
    requestJson(`/orgs/${orgId}/teams/${teamId}`, {
      method: 'DELETE',
    }),
  getTeamMembers,
  addTeamMember,
  updateTeamMemberRole: (teamId: string, memberId: string | number, data: Record<string, unknown>) =>
    requestJson(`/admin/teams/${encodeURIComponent(teamId)}/members/${encodeURIComponent(String(memberId))}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  removeTeamMember,

  // ============================================
  // Roles & Permissions (RBAC)
  // ============================================
  getRoles: () => requestJson('/admin/roles'),
  getRole: (roleId: string) => requestJson(`/admin/roles/${roleId}`),
  createRole: (data: Record<string, unknown>) => requestJson('/admin/roles', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  updateRole: (roleId: string, data: Record<string, unknown>) => requestJson(`/admin/roles/${roleId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  deleteRole: (roleId: string) => requestJson(`/admin/roles/${roleId}`, {
    method: 'DELETE',
  }),
  getRolePermissions: (roleId: string) => requestJson(`/admin/roles/${roleId}/permissions`),
  assignPermissionToRole: (roleId: string, permissionId: string) => requestJson(`/admin/roles/${roleId}/permissions/${permissionId}`, {
    method: 'POST',
  }),
  removePermissionFromRole: (roleId: string, permissionId: string) => requestJson(`/admin/roles/${roleId}/permissions/${permissionId}`, {
    method: 'DELETE',
  }),
  getRoleUsers: (roleId: string) => requestJson(`/admin/roles/${roleId}/users`),
  getPermissions: () => requestJson('/admin/permissions'),
  getPermission: (permId: string) => requestJson(`/admin/permissions/${permId}`),
  createPermission: (data: Record<string, unknown>) => requestJson('/admin/permissions', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  updatePermission: (permId: string, data: Record<string, unknown>) => requestJson(`/admin/permissions/${permId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  deletePermission: (permId: string) => requestJson(`/admin/permissions/${permId}`, {
    method: 'DELETE',
  }),
  // Tool permissions
  getToolPermissions: () => requestJson('/admin/tool-permissions'),
  assignToolPermission: (data: Record<string, unknown>) => requestJson('/admin/tool-permissions', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // ============================================
  // Provider Secrets (BYOK)
  // ============================================
  getUserByokKeys: (userId: string) => requestJson(`/admin/users/${userId}/byok-keys`),
  getAdminUserByokKeys: (userId: string) => requestJson(`/admin/keys/users/${userId}`),
  createUserByokKey: (userId: string, data: Record<string, unknown>) => requestJson(`/admin/users/${userId}/byok-keys`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  deleteUserByokKey: (userId: string, provider: string) => requestJson(`/admin/users/${userId}/byok-keys/${provider}`, {
    method: 'DELETE',
  }),
  getOrgByokKeys: (orgId: string) => requestJson<ProviderSecret[]>(`/admin/orgs/${orgId}/byok-keys`),
  createOrgByokKey: (orgId: string, data: Record<string, unknown>) => requestJson(`/admin/orgs/${orgId}/byok-keys`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  deleteOrgByokKey: (orgId: string, provider: string) => requestJson(`/admin/orgs/${orgId}/byok-keys/${provider}`, {
    method: 'DELETE',
  }),
  getOpenAIOAuthStatus: () => requestJson('/users/keys/openai/oauth/status'),
  startOpenAIOAuth: (data?: { credential_fields?: Record<string, unknown>; return_path?: string }) =>
    requestJson('/users/keys/openai/oauth/authorize', {
      method: 'POST',
      body: JSON.stringify(data ?? {}),
    }),
  refreshOpenAIOAuth: () => requestJson('/users/keys/openai/oauth/refresh', {
    method: 'POST',
  }),
  disconnectOpenAIOAuth: () => requestJson('/users/keys/openai/oauth', {
    method: 'DELETE',
  }),
  switchOpenAICredentialSource: (authSource: 'api_key' | 'oauth') =>
    requestJson('/users/keys/openai/source', {
      method: 'POST',
      body: JSON.stringify({ auth_source: authSource }),
    }),

  // ============================================
  // Budgets
  // ============================================
  getBudgets: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/admin/budgets${queryParams ? `?${queryParams}` : ''}`);
  },
  updateBudget: async (orgId: string, data: Record<string, unknown>) => {
    const normalizedOrgId = Number(orgId);
    if (!Number.isInteger(normalizedOrgId) || normalizedOrgId <= 0) {
      throw new Error('Invalid organization ID');
    }
    try {
      return await requestJson(`/admin/budgets/${encodeURIComponent(String(normalizedOrgId))}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      });
    } catch (error: unknown) {
      if (error instanceof ApiError && [404, 405].includes(error.status)) {
        return requestJson('/admin/budgets', {
          method: 'POST',
          body: JSON.stringify({
            org_id: normalizedOrgId,
            ...data,
          }),
        });
      }
      throw error;
    }
  },

  // ============================================
  // Data Ops
  // ============================================
  getBackups: (params?: Record<string, string>, options?: RequestInit) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson<BackupsResponse>(`/admin/backups${queryParams ? `?${queryParams}` : ''}`, options);
  },
  createBackup: (data: Record<string, unknown>) => requestJson('/admin/backups', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  restoreBackup: (backupId: string, data: Record<string, unknown>) =>
    requestJson(`/admin/backups/${encodeURIComponent(backupId)}/restore`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  listBackupSchedules: (params?: Record<string, string>, options?: RequestInit) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson<BackupScheduleListResponse>(
      `/admin/backup-schedules${queryParams ? `?${queryParams}` : ''}`,
      options
    );
  },
  createBackupSchedule: (data: Record<string, unknown>) =>
    requestJson<BackupScheduleMutationResponse>('/admin/backup-schedules', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateBackupSchedule: (scheduleId: string, data: Record<string, unknown>) =>
    requestJson<BackupScheduleMutationResponse>(`/admin/backup-schedules/${encodeURIComponent(scheduleId)}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  pauseBackupSchedule: (scheduleId: string) =>
    requestJson<BackupScheduleMutationResponse>(`/admin/backup-schedules/${encodeURIComponent(scheduleId)}/pause`, {
      method: 'POST',
    }),
  resumeBackupSchedule: (scheduleId: string) =>
    requestJson<BackupScheduleMutationResponse>(`/admin/backup-schedules/${encodeURIComponent(scheduleId)}/resume`, {
      method: 'POST',
    }),
  deleteBackupSchedule: (scheduleId: string) =>
    requestJson<BackupScheduleMutationResponse>(`/admin/backup-schedules/${encodeURIComponent(scheduleId)}`, {
      method: 'DELETE',
    }),
  getRetentionPolicies: () => requestJson<RetentionPoliciesResponse>('/admin/retention-policies'),
  previewRetentionPolicyImpact: (policyKey: string, data: Record<string, unknown>) =>
    requestJson(`/admin/retention-policies/${encodeURIComponent(policyKey)}/preview`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateRetentionPolicy: (policyKey: string, data: Record<string, unknown>) =>
    requestJson(`/admin/retention-policies/${encodeURIComponent(policyKey)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  previewDataSubjectRequest: (data: Record<string, unknown>) =>
    requestJson('/admin/data-subject-requests/preview', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  listDataSubjectRequests: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/admin/data-subject-requests${queryParams ? `?${queryParams}` : ''}`);
  },
  createDataSubjectRequest: (data: Record<string, unknown>) =>
    requestJson('/admin/data-subject-requests', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // ============================================
  // System Ops
  // ============================================
  getSystemLogs: (params?: Record<string, string>, options?: RequestInit) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/admin/system/logs${queryParams ? `?${queryParams}` : ''}`, options);
  },
  getMaintenanceMode: (options?: RequestInit) => requestJson('/admin/maintenance', options),
  updateMaintenanceMode: (data: Record<string, unknown>) => requestJson('/admin/maintenance', {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  getFeatureFlags: (params?: Record<string, string>, options?: RequestInit) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/admin/feature-flags${queryParams ? `?${queryParams}` : ''}`, options);
  },
  upsertFeatureFlag: (flagKey: string, data: Record<string, unknown>) =>
    requestJson(`/admin/feature-flags/${encodeURIComponent(flagKey)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  deleteFeatureFlag: (flagKey: string, params: Record<string, string>) => {
    const queryParams = new URLSearchParams(params).toString();
    return requestJson(`/admin/feature-flags/${encodeURIComponent(flagKey)}?${queryParams}`, {
      method: 'DELETE',
    });
  },
  getIncidents: (params?: Record<string, string>, options?: RequestInit) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson<IncidentsResponse>(
      `/admin/incidents${queryParams ? `?${queryParams}` : ''}`,
      options
    );
  },
  createIncident: (data: Record<string, unknown>) => requestJson('/admin/incidents', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  updateIncident: (incidentId: string, data: Record<string, unknown>) =>
    requestJson(`/admin/incidents/${encodeURIComponent(incidentId)}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  addIncidentEvent: (incidentId: string, data: Record<string, unknown>) =>
    requestJson(`/admin/incidents/${encodeURIComponent(incidentId)}/events`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  deleteIncident: (incidentId: string) =>
    requestJson(`/admin/incidents/${encodeURIComponent(incidentId)}`, {
      method: 'DELETE',
    }),

  // ============================================
  // Audit Logs
  // ============================================
  getAuditLogs: async (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    const response = await requestJson(`/admin/audit-log${queryParams ? `?${queryParams}` : ''}`);
    const { items, total, limit, offset } = normalizePagedResponse(
      response,
      ['entries', 'items']
    );
    const mapped: AuditLog[] = items.map((entry) => {
      const record = entry as Record<string, unknown>;
      const rawDetails = record.details;
      let details: Record<string, unknown> | undefined;
      if (rawDetails && typeof rawDetails === 'string') {
        try {
          const parsed = JSON.parse(rawDetails);
          details = (parsed && typeof parsed === 'object')
            ? (parsed as Record<string, unknown>)
            : { value: parsed };
        } catch {
          details = { value: rawDetails };
        }
      } else if (rawDetails && typeof rawDetails === 'object') {
        details = rawDetails as Record<string, unknown>;
      }
      return {
        id: String(record.id ?? ''),
        timestamp: (record.timestamp ?? record.created_at ?? '') as string,
        user_id: Number(record.user_id ?? 0),
        action: String(record.action ?? ''),
        resource: String(record.resource ?? record.resource_type ?? ''),
        details,
        ip_address: record.ip_address ? String(record.ip_address) : undefined,
        username: record.username ? String(record.username) : undefined,
        raw: record,
      };
    });
    return { entries: mapped, total, limit, offset };
  },

  // ============================================
  // Configuration
  // ============================================
  getSetupStatus: () => requestJson('/setup/status'),
  getConfig: () => requestJson('/setup/config'),
  updateConfig: (data: Record<string, unknown>) => requestJson('/setup/config', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // ============================================
  // Config Profiles & Editing
  // ============================================
  getEffectiveConfig: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/admin/config/effective${queryParams ? `?${queryParams}` : ''}`);
  },
  getConfigProfiles: () => requestJson('/admin/config/profiles'),
  snapshotConfigProfile: (data: { name: string; description?: string }) =>
    requestJson('/admin/config/profiles/snapshot', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getConfigProfile: (name: string) =>
    requestJson(`/admin/config/profiles/${encodeURIComponent(name)}`),
  restoreConfigProfile: (name: string) =>
    requestJson(`/admin/config/profiles/${encodeURIComponent(name)}/restore`, {
      method: 'POST',
    }),
  deleteConfigProfile: (name: string) =>
    requestJson(`/admin/config/profiles/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    }),
  updateConfigSection: (section: string, values: Record<string, string>) =>
    requestJson(`/admin/config/sections/${encodeURIComponent(section)}`, {
      method: 'PUT',
      body: JSON.stringify({ values }),
    }),
  exportConfig: () => requestJson('/admin/config/export'),
  importConfig: (sections: Record<string, Record<string, string>>) =>
    requestJson('/admin/config/import', {
      method: 'POST',
      body: JSON.stringify({ sections }),
    }),

  // ============================================
  // LLM Providers
  // ============================================
  getLLMProviders: () => requestJson('/llm/providers'),
  getLLMProviderOverrides: () => requestJson('/admin/llm/providers/overrides'),
  getLLMProviderOverride: (provider: string) => requestJson(`/admin/llm/providers/overrides/${encodeURIComponent(provider)}`),
  updateLLMProviderOverride: (provider: string, data: Record<string, unknown>) => requestJson(`/admin/llm/providers/overrides/${encodeURIComponent(provider)}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  deleteLLMProviderOverride: (provider: string) => requestJson(`/admin/llm/providers/overrides/${encodeURIComponent(provider)}`, {
    method: 'DELETE',
  }),
  testLLMProvider: (data: Record<string, unknown>) => requestJson('/admin/llm/providers/test', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  getLLMProvidersHealth: () => requestJson('/admin/llm/providers/health'),

  // ============================================
  // Monitoring
  // ============================================
  getWatchlists: () => requestJson('/monitoring/watchlists'),
  createWatchlist: <T extends object>(data: T) => requestJson('/monitoring/watchlists', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  updateWatchlist: <T extends object>(watchlistId: string, data: T) => requestJson(`/monitoring/watchlists/${watchlistId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  deleteWatchlist: (watchlistId: string) => requestJson(`/monitoring/watchlists/${watchlistId}`, {
    method: 'DELETE',
  }),
  getAlerts: () => requestJson('/monitoring/alerts'),
  acknowledgeAlert: (alertId: string) => requestJson(`/monitoring/alerts/${alertId}/acknowledge`, {
    method: 'POST',
  }),
  dismissAlert: (alertId: string) => requestJson(`/monitoring/alerts/${alertId}`, {
    method: 'DELETE',
  }),
  getMonitoringMetrics: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/monitoring/metrics${queryParams ? `?${queryParams}` : ''}`);
  },
  getHealth: () => requestJson('/health'),
  getHealthMetrics: () => requestJson('/health/metrics'),
  getLlmHealth: () => requestJson('/llm/health'),
  getTtsHealth: () => requestJson('/audio/health'),
  getSttHealth: () => requestJson('/audio/transcriptions/health'),
  getEmbeddingsHealth: () => requestJson('/embeddings/health'),
  getMetrics: () => requestJson('/metrics'),
  getMetricsText: () => requestText('/metrics/text'),
  getRagHealth: () => requestJson('/rag/health'),

  // ============================================
  // Jobs
  // ============================================
  getJobs: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/jobs/list${queryParams ? `?${queryParams}` : ''}`);
  },
  getJobDetail: (jobId: string | number, params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/jobs/${encodeURIComponent(String(jobId))}${queryParams ? `?${queryParams}` : ''}`);
  },
  getJobsStats: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/jobs/stats${queryParams ? `?${queryParams}` : ''}`);
  },
  getJobsStale: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/jobs/stale${queryParams ? `?${queryParams}` : ''}`);
  },
  cancelJobs: (data: Record<string, unknown>) => requestJson('/jobs/batch/cancel', {
    method: 'POST',
    headers: { 'X-Confirm': 'true' },
    body: JSON.stringify(data),
  }),
  retryJobsNow: (data: Record<string, unknown>) => requestJson('/jobs/retry-now', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  requeueQuarantinedJobs: (data: Record<string, unknown>) => requestJson('/jobs/batch/requeue_quarantined', {
    method: 'POST',
    headers: { 'X-Confirm': 'true' },
    body: JSON.stringify(data),
  }),

  // ============================================
  // Usage Analytics
  // ============================================
  getUsageDaily: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/admin/usage/daily${queryParams ? `?${queryParams}` : ''}`);
  },
  getUsageTop: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/admin/usage/top${queryParams ? `?${queryParams}` : ''}`);
  },
  getLlmUsageSummary: (params?: Record<string, QueryParamValue>) => {
    const queryParams = buildQueryString(params);
    return requestJson(`/admin/llm-usage/summary${queryParams ? `?${queryParams}` : ''}`);
  },
  getLlmUsage: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/admin/llm-usage${queryParams ? `?${queryParams}` : ''}`);
  },
  getLlmTopSpenders: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/admin/llm-usage/top-spenders${queryParams ? `?${queryParams}` : ''}`);
  },
  getRouterAnalyticsStatus: (params?: Record<string, string>) => requestRouterAnalytics('status', params),
  getRouterAnalyticsStatusBreakdowns: (params?: Record<string, string>) =>
    requestRouterAnalytics('status/breakdowns', params),
  getRouterAnalyticsQuota: (params?: Record<string, string>) => requestRouterAnalytics('quota', params),
  getRouterAnalyticsProviders: (params?: Record<string, string>) => requestRouterAnalytics('providers', params),
  getRouterAnalyticsAccess: (params?: Record<string, string>) => requestRouterAnalytics('access', params),
  getRouterAnalyticsNetwork: (params?: Record<string, string>) => requestRouterAnalytics('network', params),
  getRouterAnalyticsModels: (params?: Record<string, string>) => requestRouterAnalytics('models', params),
  getRouterAnalyticsConversations: (params?: Record<string, string>) => requestRouterAnalytics('conversations', params),
  getRouterAnalyticsLog: (params?: Record<string, string>) => requestRouterAnalytics('log', params),
  getRouterAnalyticsMeta: (params?: Record<string, string>) => requestRouterAnalytics('meta', params),

  // ============================================
  // Resource Governor
  // ============================================
  getRateLimitEvents: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/admin/rate-limit-events${queryParams ? `?${queryParams}` : ''}`);
  },
  getResourceGovernorPolicy: (params?: { include_ids?: boolean }, signal?: AbortSignal) => {
    const queryParams = params ? new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)])
    ).toString() : '';
    return requestJson(`/resource-governor/policy${queryParams ? `?${queryParams}` : ''}`, { signal });
  },
  simulateResourceGovernorPolicy: (data: Record<string, unknown>) =>
    requestJson('/resource-governor/policy/simulate', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateResourceGovernorPolicy: (data: Record<string, unknown>) =>
    requestJson('/resource-governor/policy', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  deleteResourceGovernorPolicy: (policyId: string) =>
    requestJson(`/resource-governor/policy/${encodeURIComponent(policyId)}`, {
      method: 'DELETE',
    }),

  // ============================================
  // Rate Limiting
  // ============================================
  setRoleRateLimits: (roleId: string, data: { resource: string; limit_per_min?: number | null; burst?: number | null }) =>
    requestJson(`/admin/roles/${encodeURIComponent(roleId)}/rate-limits`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  clearRoleRateLimits: (roleId: string) =>
    requestJson(`/admin/roles/${encodeURIComponent(roleId)}/rate-limits`, {
      method: 'DELETE',
    }),
  getUserRateLimits: (userId: string) =>
    requestJson(`/admin/users/${encodeURIComponent(userId)}/rate-limits`),
  setUserRateLimits: (userId: string, data: { resource: string; limit_per_min?: number | null; burst?: number | null }) =>
    requestJson(`/admin/users/${encodeURIComponent(userId)}/rate-limits`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // ============================================
  // Notification Settings
  // ============================================
  getNotificationSettings: () => requestJson('/monitoring/notifications/settings'),
  updateNotificationSettings: (data: Record<string, unknown>) =>
    requestJson('/monitoring/notifications/settings', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  testNotification: (data?: Record<string, unknown>) =>
    requestJson('/monitoring/notifications/test', {
      method: 'POST',
      body: JSON.stringify(data ?? {}),
    }),
  getRecentNotifications: () => requestJson('/monitoring/notifications/recent'),

  // ============================================
  // User Permission Overrides
  // ============================================
  getUserPermissionOverrides: (userId: string) =>
    requestJson(`/admin/users/${encodeURIComponent(userId)}/overrides`),
  addUserPermissionOverride: (userId: string, data: { permission_id: number; grant: boolean }) =>
    requestJson(`/admin/users/${encodeURIComponent(userId)}/overrides`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  removeUserPermissionOverride: (userId: string, permissionId: string) =>
    requestJson(`/admin/users/${encodeURIComponent(userId)}/overrides/${encodeURIComponent(permissionId)}`, {
      method: 'DELETE',
    }),

  // ============================================
  // Shared Provider Keys (Org/Team BYOK)
  // ============================================
  getSharedProviderKeys: (params?: { scope_type?: string; scope_id?: number; provider?: string }) => {
    const queryParams = params ? new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined)
        .map(([k, v]) => [k, String(v)])
    ).toString() : '';
    return requestJson(`/admin/keys/shared${queryParams ? `?${queryParams}` : ''}`);
  },
  createSharedProviderKey: (data: { scope_type: string; scope_id: number; provider: string; api_key: string }) =>
    requestJson('/admin/keys/shared', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  deleteSharedProviderKey: (scopeType: string, scopeId: number, provider: string) =>
    requestJson(`/admin/keys/shared/${encodeURIComponent(scopeType)}/${encodeURIComponent(String(scopeId))}/${encodeURIComponent(provider)}`, {
      method: 'DELETE',
    }),
  testSharedProviderKey: (data: { scope_type: string; scope_id: number; provider: string; model?: string }) =>
    requestJson('/admin/keys/shared/test', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // ============================================
  // Security Health
  // ============================================
  getSecurityHealth: () => requestJson<SecurityHealthData>('/health/security'),
  getSecurityAlertStatus: () => requestJson<SecurityAlertStatus>('/admin/security/alert-status'),

  // ============================================
  // Virtual API Keys
  // ============================================
  getUserVirtualKeys: (userId: string) =>
    requestJson(`/admin/users/${encodeURIComponent(userId)}/virtual-keys`),
  createUserVirtualKey: (userId: string, data: { name: string; scopes: string[] }) =>
    requestJson(`/admin/users/${encodeURIComponent(userId)}/virtual-keys`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // ============================================
  // Tool Permissions (Role-specific)
  // ============================================
  getRoleToolPermissions: (roleId: string) =>
    requestJson(`/admin/roles/${encodeURIComponent(roleId)}/permissions/tools`),
  batchGrantToolPermissions: (roleId: string, data: { tools: string[] }) =>
    requestJson(`/admin/roles/${encodeURIComponent(roleId)}/permissions/tools/batch`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  batchRevokeToolPermissions: (roleId: string, data: { tools: string[] }) =>
    requestJson(`/admin/roles/${encodeURIComponent(roleId)}/permissions/tools/batch/revoke`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  grantToolPermissionsByPrefix: (roleId: string, prefix: string) =>
    requestJson(`/admin/roles/${encodeURIComponent(roleId)}/permissions/tools/prefix/grant`, {
      method: 'POST',
      body: JSON.stringify({ prefix }),
    }),
  revokeToolPermissionsByPrefix: (roleId: string, prefix: string) =>
    requestJson(`/admin/roles/${encodeURIComponent(roleId)}/permissions/tools/prefix/revoke`, {
      method: 'POST',
      body: JSON.stringify({ prefix }),
    }),

  // ============================================
  // Cleanup Settings
  // ============================================
  getCleanupSettings: () => requestJson('/admin/cleanup-settings'),
  updateCleanupSettings: (data: Record<string, unknown>) =>
    requestJson('/admin/cleanup-settings', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // ============================================
  // Notes Title Settings
  // ============================================
  getNotesTitleSettings: () => requestJson('/admin/notes/title-settings'),
  updateNotesTitleSettings: (data: Record<string, unknown>) =>
    requestJson('/admin/notes/title-settings', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // ============================================
  // Kanban FTS Maintenance
  // ============================================
  runKanbanFtsMaintenance: () =>
    requestJson('/admin/kanban/fts-maintenance', {
      method: 'POST',
    }),

  // ============================================
  // Job SLA & Attachments
  // ============================================
  getJobSlaPolicies: () => requestJson('/admin/jobs/sla/policies'),
  createJobSlaPolicy: (data: Record<string, unknown>) =>
    requestJson('/admin/jobs/sla/policy', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getJobAttachments: (jobId: string | number, params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/admin/jobs/${encodeURIComponent(String(jobId))}/attachments${queryParams ? `?${queryParams}` : ''}`);
  },
  addJobAttachment: (jobId: string, data: FormData) =>
    requestJson(`/admin/jobs/${encodeURIComponent(jobId)}/attachments`, {
      method: 'POST',
      body: data,
    }),
  rotateJobCrypto: () =>
    requestJson('/admin/jobs/crypto/rotate', {
      method: 'POST',
    }),

  // ============================================
  // Organization Watchlist Settings
  // ============================================
  getOrgWatchlistSettings: (orgId: string) =>
    requestJson<WatchlistSettings>(`/admin/orgs/${encodeURIComponent(orgId)}/watchlists/settings`),
  updateOrgWatchlistSettings: (orgId: string, data: Record<string, unknown>) =>
    requestJson(`/admin/orgs/${encodeURIComponent(orgId)}/watchlists/settings`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  // ============================================
  // Debug Tools
  // ============================================
  debugResolveApiKey: (apiKey: string) =>
    requestJson('/authnz/debug/api-key-id', {
      headers: { 'X-API-KEY': apiKey },
    }),
  debugGetBudgetSummary: (apiKey: string) =>
    requestJson('/authnz/debug/budget-summary', {
      headers: { 'X-API-KEY': apiKey },
    }),

  // ============================================
  // ACP Sessions (Admin)
  // ============================================
  getACPSessions: (params?: Record<string, QueryParamValue>) => {
    const queryParams = buildQueryString(params);
    return requestJson(`/admin/acp/sessions${queryParams ? `?${queryParams}` : ''}`);
  },
  getACPSessionUsage: (sessionId: string) =>
    requestJson(`/admin/acp/sessions/${encodeURIComponent(sessionId)}/usage`),
  closeACPSession: (sessionId: string) =>
    requestJson(`/admin/acp/sessions/${encodeURIComponent(sessionId)}/close`, {
      method: 'POST',
    }),

  // ============================================
  // ACP Agent Configs (Admin)
  // ============================================
  getACPAgentConfigs: (params?: Record<string, QueryParamValue>) => {
    const queryParams = buildQueryString(params);
    return requestJson(`/admin/acp/agents${queryParams ? `?${queryParams}` : ''}`);
  },
  getACPAgentConfig: (configId: number) =>
    requestJson(`/admin/acp/agents/${configId}`),
  createACPAgentConfig: (data: Record<string, unknown>) =>
    requestJson('/admin/acp/agents', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateACPAgentConfig: (configId: number, data: Record<string, unknown>) =>
    requestJson(`/admin/acp/agents/${configId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  deleteACPAgentConfig: (configId: number) =>
    requestJson(`/admin/acp/agents/${configId}`, {
      method: 'DELETE',
    }),

  // ============================================
  // ACP Permission Policies (Admin)
  // ============================================
  getACPPermissionPolicies: (params?: Record<string, QueryParamValue>) => {
    const queryParams = buildQueryString(params);
    return requestJson(`/admin/acp/permission-policies${queryParams ? `?${queryParams}` : ''}`);
  },
  createACPPermissionPolicy: (data: Record<string, unknown>) =>
    requestJson('/admin/acp/permission-policies', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateACPPermissionPolicy: (policyId: number, data: Record<string, unknown>) =>
    requestJson(`/admin/acp/permission-policies/${policyId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  deleteACPPermissionPolicy: (policyId: number) =>
    requestJson(`/admin/acp/permission-policies/${policyId}`, {
      method: 'DELETE',
    }),

  // ============================================
  // MCP Servers (Admin)
  // ============================================
  getMCPStatus: () => requestJson('/mcp/status'),
  getMCPMetrics: () => requestJson('/mcp/metrics'),
  getMCPTools: () => requestJson('/mcp/tools'),
  getMCPModules: () => requestJson('/mcp/modules'),
  getMCPModulesHealth: () => requestJson('/mcp/modules/health'),
  getMCPHealth: () => requestJson('/mcp/health'),

  // ============================================
  // Voice Commands & Assistant
  // ============================================
  getVoiceCommands: async (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson<VoiceCommandListResponse | VoiceCommand[]>(`/voice/commands${queryParams ? `?${queryParams}` : ''}`);
  },
  getVoiceCommand: (commandId: string, signal?: AbortSignal) =>
    requestJson<VoiceCommand>(`/voice/commands/${encodeURIComponent(commandId)}`, { signal }),
  createVoiceCommand: (data: Record<string, unknown>) =>
    requestJson<VoiceCommand>('/voice/commands', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateVoiceCommand: (commandId: string, data: Record<string, unknown>) =>
    requestJson<VoiceCommand>(`/voice/commands/${encodeURIComponent(commandId)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  deleteVoiceCommand: (commandId: string) =>
    requestJson(`/voice/commands/${encodeURIComponent(commandId)}`, {
      method: 'DELETE',
    }),
  toggleVoiceCommand: (commandId: string, enabled: boolean) =>
    requestJson<VoiceCommand>(`/voice/commands/${encodeURIComponent(commandId)}/toggle`, {
      method: 'POST',
      body: JSON.stringify({ enabled }),
    }),

  // Voice Sessions
  getVoiceSessions: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson<VoiceSessionListResponse | VoiceSession[]>(`/voice/sessions${queryParams ? `?${queryParams}` : ''}`);
  },
  getVoiceSession: (sessionId: string) =>
    requestJson<VoiceSession>(`/voice/sessions/${encodeURIComponent(sessionId)}`),
  deleteVoiceSession: (sessionId: string) =>
    requestJson(`/voice/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE',
    }),

  // Voice Analytics
  getVoiceAnalytics: (params?: { days?: number; user_id?: number }) => {
    const queryParams = params ? new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined)
        .map(([k, v]) => [k, String(v)])
    ).toString() : '';
    return requestJson<VoiceAnalyticsSummary>(`/voice/analytics${queryParams ? `?${queryParams}` : ''}`);
  },
  getVoiceCommandUsage: (commandId: string, params?: { days?: number }, signal?: AbortSignal) => {
    const queryParams = params ? new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined)
        .map(([k, v]) => [k, String(v)])
    ).toString() : '';
    return requestJson<VoiceCommandUsage>(`/voice/commands/${encodeURIComponent(commandId)}/usage${queryParams ? `?${queryParams}` : ''}`, { signal });
  },

  // Voice Workflow Templates
  getVoiceWorkflowTemplates: () =>
    requestJson('/voice/workflows/templates'),

  // ============================================
  // Plans & Billing
  // ============================================
  getPlans: (params?: Record<string, QueryParamValue>) => {
    const qs = buildQueryString(params);
    return requestJson<Plan[]>(`/billing/plans${qs ? `?${qs}` : ''}`);
  },
  getPlan: (planId: string) =>
    requestJson<Plan>(`/billing/plans/${encodeURIComponent(planId)}`),
  createPlan: (data: CreatePlanInput) =>
    requestJson<Plan>('/billing/plans', { method: 'POST', body: JSON.stringify(data) }),
  updatePlan: (planId: string, data: UpdatePlanInput) =>
    requestJson<Plan>(`/billing/plans/${encodeURIComponent(planId)}`, { method: 'PUT', body: JSON.stringify(data) }),
  deletePlan: (planId: string) =>
    requestJson(`/billing/plans/${encodeURIComponent(planId)}`, { method: 'DELETE' }),

  // Subscriptions
  getSubscriptions: (params?: Record<string, QueryParamValue>) => {
    const qs = buildQueryString(params);
    return requestJson<Subscription[]>(`/billing/subscriptions${qs ? `?${qs}` : ''}`);
  },
  getOrgSubscription: (orgId: number) =>
    requestJson<Subscription>(`/billing/orgs/${orgId}/subscription`),
  createSubscription: (orgId: number, data: { plan_id: string; trial_days?: number }) =>
    requestJson<{ checkout_url?: string; subscription?: Subscription }>(
      `/billing/orgs/${orgId}/subscription`, { method: 'POST', body: JSON.stringify(data) }),
  updateSubscription: (orgId: number, data: { plan_id: string }) =>
    requestJson<Subscription>(`/billing/orgs/${orgId}/subscription`, { method: 'PUT', body: JSON.stringify(data) }),
  cancelSubscription: (orgId: number) =>
    requestJson(`/billing/orgs/${orgId}/subscription`, { method: 'DELETE' }),

  // Usage & Invoices
  getOrgUsageSummary: (orgId: number, params?: { period?: string }) => {
    const qs = buildQueryString(params);
    return requestJson<OrgUsageSummary>(`/billing/orgs/${orgId}/usage${qs ? `?${qs}` : ''}`);
  },
  getOrgInvoices: (orgId: number, params?: Record<string, QueryParamValue>) => {
    const qs = buildQueryString(params);
    return requestJson<Invoice[]>(`/billing/orgs/${orgId}/invoices${qs ? `?${qs}` : ''}`);
  },

  // Feature Registry
  getFeatureRegistry: () =>
    requestJson<FeatureRegistryEntry[]>('/billing/feature-registry'),
  updateFeatureRegistry: (data: FeatureRegistryEntry[]) =>
    requestJson<FeatureRegistryEntry[]>('/billing/feature-registry', { method: 'PUT', body: JSON.stringify(data) }),

  // Onboarding
  createOnboardingSession: (data: { org_name: string; org_slug: string; plan_id: string; owner_email?: string }) =>
    requestJson<{ checkout_url?: string; org_id?: number }>(
      '/billing/onboarding', { method: 'POST', body: JSON.stringify(data) }),
};

export default api;
