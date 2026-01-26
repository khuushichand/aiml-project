'use client';

import { ApiError, requestJson, requestText } from './http';
import { normalizeListResponse, normalizePagedResponse } from './normalize';
import type {
  AuditLog,
  BackupsResponse,
  IncidentsResponse,
  RegistrationCode,
  RetentionPoliciesResponse,
  User,
  UserWithKeyCount,
} from '@/types';
export { ApiError };

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
  getDashboardActivity: (days = 7) => requestJson(`/admin/activity?days=${days}`),

  // ============================================
  // User Management
  // ============================================
  getUsers: async (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    const response = await requestJson(`/admin/users${queryParams ? `?${queryParams}` : ''}`);
    return normalizeListResponse<UserWithKeyCount>(response, ['users', 'items']);
  },
  createUser: (data: Record<string, unknown>) => requestJson('/admin/users', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  getUser: (userId: string) => requestJson(`/admin/users/${userId}`),
  getUserOrgMemberships: (userId: string) => requestJson(`/admin/users/${userId}/org-memberships`),
  getUserEffectivePermissions: (userId: string) =>
    requestJson(`/admin/users/${userId}/effective-permissions`),
  getUserSessions: (userId: string) => requestJson(`/admin/users/${userId}/sessions`),
  revokeUserSession: (userId: string, sessionId: string) =>
    requestJson(`/admin/users/${userId}/sessions/${sessionId}`, {
      method: 'DELETE',
    }),
  revokeAllUserSessions: (userId: string) =>
    requestJson(`/admin/users/${userId}/sessions/revoke-all`, {
      method: 'POST',
    }),
  getUserMfaStatus: (userId: string) => requestJson(`/admin/users/${userId}/mfa`),
  disableUserMfa: (userId: string) =>
    requestJson(`/admin/users/${userId}/mfa/disable`, {
      method: 'POST',
    }),
  updateUser: (userId: string, data: Record<string, unknown>) => requestJson(`/admin/users/${userId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  deleteUser: (userId: string) => requestJson(`/admin/users/${userId}`, {
    method: 'DELETE',
  }),
  getCurrentUser: () => requestJson('/users/me'),

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
  getUserApiKeys: (userId: string) => requestJson(`/admin/users/${userId}/api-keys`),
  createApiKey: (userId: string, data: Record<string, unknown>) => requestJson(`/admin/users/${userId}/api-keys`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  rotateApiKey: (userId: string, keyId: string) => requestJson(`/admin/users/${userId}/api-keys/${keyId}/rotate`, {
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
  getOrganization: (orgId: string) => requestJson(`/orgs/${orgId}`),
  createOrganization: (data: Record<string, unknown>) => requestJson('/admin/orgs', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  getOrgMembers: (orgId: string) => requestJson(`/admin/orgs/${orgId}/members`),
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

  // ============================================
  // Teams
  // ============================================
  getTeam,
  getTeams: (orgId: string) => requestJson(`/admin/orgs/${orgId}/teams`),
  createTeam: (orgId: string, data: Record<string, unknown>) => requestJson(`/admin/orgs/${orgId}/teams`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  getTeamMembers,
  addTeamMember,
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
  createUserByokKey: (userId: string, data: Record<string, unknown>) => requestJson(`/admin/users/${userId}/byok-keys`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  deleteUserByokKey: (userId: string, provider: string) => requestJson(`/admin/users/${userId}/byok-keys/${provider}`, {
    method: 'DELETE',
  }),
  getOrgByokKeys: (orgId: string) => requestJson(`/admin/orgs/${orgId}/byok-keys`),
  createOrgByokKey: (orgId: string, data: Record<string, unknown>) => requestJson(`/admin/orgs/${orgId}/byok-keys`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  deleteOrgByokKey: (orgId: string, provider: string) => requestJson(`/admin/orgs/${orgId}/byok-keys/${provider}`, {
    method: 'DELETE',
  }),

  // ============================================
  // Budgets
  // ============================================
  getBudgets: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/admin/budgets${queryParams ? `?${queryParams}` : ''}`);
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
  getRetentionPolicies: () => requestJson<RetentionPoliciesResponse>('/admin/retention-policies'),
  updateRetentionPolicy: (policyKey: string, data: Record<string, unknown>) =>
    requestJson(`/admin/retention-policies/${encodeURIComponent(policyKey)}`, {
      method: 'PUT',
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
  getHealth: () => requestJson('/health'),
  getHealthMetrics: () => requestJson('/health/metrics'),
  getLlmHealth: () => requestJson('/llm/health'),
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
  getLlmUsageSummary: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/admin/llm-usage/summary${queryParams ? `?${queryParams}` : ''}`);
  },
  getLlmTopSpenders: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return requestJson(`/admin/llm-usage/top-spenders${queryParams ? `?${queryParams}` : ''}`);
  },

  // ============================================
  // Resource Governor
  // ============================================
  getResourceGovernorPolicy: (params?: { include_ids?: boolean }, signal?: AbortSignal) => {
    const queryParams = params ? new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)])
    ).toString() : '';
    return requestJson(`/resource-governor/policy${queryParams ? `?${queryParams}` : ''}`, { signal });
  },
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
  setRoleRateLimits: (roleId: string, data: { requests_per_minute?: number; requests_per_hour?: number; requests_per_day?: number }) =>
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
  setUserRateLimits: (userId: string, data: Record<string, unknown>) =>
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
  testNotification: () =>
    requestJson('/monitoring/notifications/test', {
      method: 'POST',
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
  getSecurityHealth: () => requestJson('/health/security'),
  getSecurityAlertStatus: () => requestJson('/admin/security/alert-status'),

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
  getJobAttachments: (jobId: string) =>
    requestJson(`/admin/jobs/${encodeURIComponent(jobId)}/attachments`),
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
    requestJson(`/admin/orgs/${encodeURIComponent(orgId)}/watchlists/settings`),
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
};

export default api;
