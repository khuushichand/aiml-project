'use client';

import { getJWTToken, getApiKey, logout } from './auth';

// API configuration
const API_HOST = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_VERSION = process.env.NEXT_PUBLIC_API_VERSION || 'v1';
const API_URL = `${API_HOST.replace(/\/$/, '')}/api/${API_VERSION}`;

export class ApiError extends Error {
  status: number;
  detail?: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

type AddTeamMemberInput =
  | { email: string; role?: string }
  | { userId: string | number; role?: string }
  | { user_id: number; role?: string };

/**
 * Get CSRF token from cookie
 */
function getCsrfToken(): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(
    new RegExp('(?:^|; )csrf_token=([^;]*)')
  );
  return match ? decodeURIComponent(match[1]) : null;
}

/**
 * Build auth headers including JWT, API key, and CSRF token
 */
function getAuthHeaders(method: string = 'GET'): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  // JWT Bearer token
  const token = getJWTToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // X-API-KEY for single-user mode
  const apiKey = getApiKey();
  if (apiKey) {
    headers['X-API-KEY'] = apiKey;
  }

  // CSRF token for mutating requests (when not using API key auth)
  const methodUpper = method.toUpperCase();
  const needsCsrf = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(methodUpper) && !apiKey;
  if (needsCsrf) {
    const csrf = getCsrfToken();
    if (csrf) {
      headers['X-CSRF-Token'] = csrf;
    }
  }

  return headers;
}

/**
 * Generic request function with error handling
 */
async function request<T = unknown>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const method = options.method || 'GET';
  const headers = {
    ...getAuthHeaders(method),
    ...options.headers,
  };

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
    credentials: 'include', // Include cookies for CSRF
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));

    // Handle unauthorized - clear credentials and redirect
    if (response.status === 401 && typeof window !== 'undefined') {
      await logout();
      window.location.href = '/login';
    }

    // Handle CSRF errors
    if (response.status === 403) {
      const detail = error.detail || '';
      if (typeof detail === 'string' && detail.toLowerCase().includes('csrf')) {
        throw new ApiError(
          response.status,
          'CSRF validation failed. Please refresh the page and try again.',
          error
        );
      }
    }

    const message = String(error.detail || error.message || 'Request failed');
    throw new ApiError(response.status, message, error);
  }

  // Handle empty responses
  const text = await response.text();
  if (!text) return {} as T;

  return JSON.parse(text);
}

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
  return await request(`/admin/teams/${encodeURIComponent(teamId)}`);
}

export async function getTeamMembers(teamId: string) {
  return await request(`/admin/teams/${encodeURIComponent(teamId)}/members`);
}

export async function addTeamMember(teamId: string, member: AddTeamMemberInput) {
  const payload = normalizeTeamMemberInput(member);
  return await request(`/admin/teams/${encodeURIComponent(teamId)}/members`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function removeTeamMember(teamId: string, memberId: string | number) {
  const memberValue = String(memberId).trim();
  if (!memberValue) {
    throw new Error('memberId is required');
  }
  return await request(`/admin/teams/${encodeURIComponent(teamId)}/members/${encodeURIComponent(memberValue)}`, {
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
  getDashboardStats: () => request('/admin/stats'),
  getDashboardActivity: (days = 7) => request(`/admin/activity?days=${days}`),

  // ============================================
  // User Management
  // ============================================
  getUsers: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return request(`/admin/users${queryParams ? `?${queryParams}` : ''}`);
  },
  createUser: (data: Record<string, unknown>) => request('/admin/users', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  getUser: (userId: string) => request(`/admin/users/${userId}`),
  getUserOrgMemberships: (userId: string) => request(`/admin/users/${userId}/org-memberships`),
  getUserEffectivePermissions: (userId: string) =>
    request(`/admin/users/${userId}/effective-permissions`),
  getUserSessions: (userId: string) => request(`/admin/users/${userId}/sessions`),
  revokeUserSession: (userId: string, sessionId: string) =>
    request(`/admin/users/${userId}/sessions/${sessionId}`, {
      method: 'DELETE',
    }),
  revokeAllUserSessions: (userId: string) =>
    request(`/admin/users/${userId}/sessions/revoke-all`, {
      method: 'POST',
    }),
  getUserMfaStatus: (userId: string) => request(`/admin/users/${userId}/mfa`),
  disableUserMfa: (userId: string) =>
    request(`/admin/users/${userId}/mfa/disable`, {
      method: 'POST',
    }),
  updateUser: (userId: string, data: Record<string, unknown>) => request(`/admin/users/${userId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  deleteUser: (userId: string) => request(`/admin/users/${userId}`, {
    method: 'DELETE',
  }),
  getCurrentUser: () => request('/users/me'),

  // ============================================
  // Registration Codes
  // ============================================
  getRegistrationSettings: () => request('/admin/registration-settings'),
  updateRegistrationSettings: (data: Record<string, unknown>) => request('/admin/registration-settings', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  getRegistrationCodes: async (includeExpired: boolean = false) => {
    const response = await request(`/admin/registration-codes?include_expired=${includeExpired}`);
    if (Array.isArray(response)) {
      return response;
    }
    if (response && Array.isArray((response as { codes?: unknown }).codes)) {
      return (response as { codes: unknown[] }).codes;
    }
    return [];
  },
  createRegistrationCode: (data: Record<string, unknown>) => request('/admin/registration-codes', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  deleteRegistrationCode: (codeId: number | string) => request(`/admin/registration-codes/${codeId}`, {
    method: 'DELETE',
  }),

  // ============================================
  // API Key Management
  // ============================================
  getUserApiKeys: (userId: string) => request(`/admin/users/${userId}/api-keys`),
  createApiKey: (userId: string, data: Record<string, unknown>) => request(`/admin/users/${userId}/api-keys`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  rotateApiKey: (userId: string, keyId: string) => request(`/admin/users/${userId}/api-keys/${keyId}/rotate`, {
    method: 'POST',
  }),
  revokeApiKey: (userId: string, keyId: string) => request(`/admin/users/${userId}/api-keys/${keyId}`, {
    method: 'DELETE',
  }),
  getApiKeyAuditLog: (keyId: string) => request(`/admin/api-keys/${keyId}/audit-log`),

  // ============================================
  // Organizations
  // ============================================
  getOrganizations: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return request(`/admin/orgs${queryParams ? `?${queryParams}` : ''}`);
  },
  getOrganization: (orgId: string) => request(`/orgs/${orgId}`),
  createOrganization: (data: Record<string, unknown>) => request('/admin/orgs', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  getOrgMembers: (orgId: string) => request(`/admin/orgs/${orgId}/members`),
  addOrgMember: (orgId: string, data: Record<string, unknown>) => request(`/admin/orgs/${orgId}/members`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  removeOrgMember: (orgId: string, userId: string) => request(`/admin/orgs/${orgId}/members/${userId}`, {
    method: 'DELETE',
  }),
  updateOrgMemberRole: (orgId: string, userId: string, data: Record<string, unknown>) => request(`/admin/orgs/${orgId}/members/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  }),
  createOrgInvite: (orgId: string, data: Record<string, unknown>) => request(`/orgs/${orgId}/invite`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // ============================================
  // Teams
  // ============================================
  getTeam,
  getTeams: (orgId: string) => request(`/admin/orgs/${orgId}/teams`),
  createTeam: (orgId: string, data: Record<string, unknown>) => request(`/admin/orgs/${orgId}/teams`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  getTeamMembers,
  addTeamMember,
  removeTeamMember,

  // ============================================
  // Roles & Permissions (RBAC)
  // ============================================
  getRoles: () => request('/admin/roles'),
  getRole: (roleId: string) => request(`/admin/roles/${roleId}`),
  createRole: (data: Record<string, unknown>) => request('/admin/roles', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  updateRole: (roleId: string, data: Record<string, unknown>) => request(`/admin/roles/${roleId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  deleteRole: (roleId: string) => request(`/admin/roles/${roleId}`, {
    method: 'DELETE',
  }),
  getRolePermissions: (roleId: string) => request(`/admin/roles/${roleId}/permissions`),
  assignPermissionToRole: (roleId: string, permissionId: string) => request(`/admin/roles/${roleId}/permissions/${permissionId}`, {
    method: 'POST',
  }),
  removePermissionFromRole: (roleId: string, permissionId: string) => request(`/admin/roles/${roleId}/permissions/${permissionId}`, {
    method: 'DELETE',
  }),
  getRoleUsers: (roleId: string) => request(`/admin/roles/${roleId}/users`),
  getPermissions: () => request('/admin/permissions'),
  getPermission: (permId: string) => request(`/admin/permissions/${permId}`),
  createPermission: (data: Record<string, unknown>) => request('/admin/permissions', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  updatePermission: (permId: string, data: Record<string, unknown>) => request(`/admin/permissions/${permId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  deletePermission: (permId: string) => request(`/admin/permissions/${permId}`, {
    method: 'DELETE',
  }),
  // Tool permissions
  getToolPermissions: () => request('/admin/tool-permissions'),
  assignToolPermission: (data: Record<string, unknown>) => request('/admin/tool-permissions', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // ============================================
  // Provider Secrets (BYOK)
  // ============================================
  getUserByokKeys: (userId: string) => request(`/admin/users/${userId}/byok-keys`),
  createUserByokKey: (userId: string, data: Record<string, unknown>) => request(`/admin/users/${userId}/byok-keys`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  deleteUserByokKey: (userId: string, provider: string) => request(`/admin/users/${userId}/byok-keys/${provider}`, {
    method: 'DELETE',
  }),
  getOrgByokKeys: (orgId: string) => request(`/admin/orgs/${orgId}/byok-keys`),
  createOrgByokKey: (orgId: string, data: Record<string, unknown>) => request(`/admin/orgs/${orgId}/byok-keys`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  deleteOrgByokKey: (orgId: string, provider: string) => request(`/admin/orgs/${orgId}/byok-keys/${provider}`, {
    method: 'DELETE',
  }),

  // ============================================
  // Budgets
  // ============================================
  getBudgets: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return request(`/admin/budgets${queryParams ? `?${queryParams}` : ''}`);
  },

  // ============================================
  // Data Ops
  // ============================================
  getBackups: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return request(`/admin/backups${queryParams ? `?${queryParams}` : ''}`);
  },
  createBackup: (data: Record<string, unknown>) => request('/admin/backups', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  restoreBackup: (backupId: string, data: Record<string, unknown>) =>
    request(`/admin/backups/${encodeURIComponent(backupId)}/restore`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getRetentionPolicies: () => request('/admin/retention-policies'),
  updateRetentionPolicy: (policyKey: string, data: Record<string, unknown>) =>
    request(`/admin/retention-policies/${encodeURIComponent(policyKey)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  // ============================================
  // System Ops
  // ============================================
  getSystemLogs: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return request(`/admin/system/logs${queryParams ? `?${queryParams}` : ''}`);
  },
  getMaintenanceMode: () => request('/admin/maintenance'),
  updateMaintenanceMode: (data: Record<string, unknown>) => request('/admin/maintenance', {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  getFeatureFlags: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return request(`/admin/feature-flags${queryParams ? `?${queryParams}` : ''}`);
  },
  upsertFeatureFlag: (flagKey: string, data: Record<string, unknown>) =>
    request(`/admin/feature-flags/${encodeURIComponent(flagKey)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  deleteFeatureFlag: (flagKey: string, params: Record<string, string>) => {
    const queryParams = new URLSearchParams(params).toString();
    return request(`/admin/feature-flags/${encodeURIComponent(flagKey)}?${queryParams}`, {
      method: 'DELETE',
    });
  },
  getIncidents: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return request(`/admin/incidents${queryParams ? `?${queryParams}` : ''}`);
  },
  createIncident: (data: Record<string, unknown>) => request('/admin/incidents', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  updateIncident: (incidentId: string, data: Record<string, unknown>) =>
    request(`/admin/incidents/${encodeURIComponent(incidentId)}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  addIncidentEvent: (incidentId: string, data: Record<string, unknown>) =>
    request(`/admin/incidents/${encodeURIComponent(incidentId)}/events`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  deleteIncident: (incidentId: string) =>
    request(`/admin/incidents/${encodeURIComponent(incidentId)}`, {
      method: 'DELETE',
    }),

  // ============================================
  // Audit Logs
  // ============================================
  getAuditLogs: async (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    const response = await request(`/admin/audit-log${queryParams ? `?${queryParams}` : ''}`);
    const items = Array.isArray(response)
      ? response
      : (response && Array.isArray((response as { entries?: unknown }).entries))
        ? (response as { entries: unknown[] }).entries
        : (response && Array.isArray((response as { items?: unknown }).items))
          ? (response as { items: unknown[] }).items
          : [];
    const mapped = items.map((entry) => {
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
    const total = typeof (response as { total?: unknown })?.total === 'number'
      ? Number((response as { total?: unknown }).total)
      : mapped.length;
    const limit = typeof (response as { limit?: unknown })?.limit === 'number'
      ? Number((response as { limit?: unknown }).limit)
      : undefined;
    const offset = typeof (response as { offset?: unknown })?.offset === 'number'
      ? Number((response as { offset?: unknown }).offset)
      : undefined;
    return { entries: mapped, total, limit, offset };
  },

  // ============================================
  // Configuration
  // ============================================
  getSetupStatus: () => request('/setup/status'),
  getConfig: () => request('/setup/config'),
  updateConfig: (data: Record<string, unknown>) => request('/setup/config', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // ============================================
  // LLM Providers
  // ============================================
  getLLMProviders: () => request('/llm/providers'),
  getLLMProviderOverrides: () => request('/admin/llm/providers/overrides'),
  getLLMProviderOverride: (provider: string) => request(`/admin/llm/providers/overrides/${encodeURIComponent(provider)}`),
  updateLLMProviderOverride: (provider: string, data: Record<string, unknown>) => request(`/admin/llm/providers/overrides/${encodeURIComponent(provider)}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  deleteLLMProviderOverride: (provider: string) => request(`/admin/llm/providers/overrides/${encodeURIComponent(provider)}`, {
    method: 'DELETE',
  }),
  testLLMProvider: (data: Record<string, unknown>) => request('/admin/llm/providers/test', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // ============================================
  // Monitoring
  // ============================================
  getWatchlists: () => request('/monitoring/watchlists'),
  createWatchlist: (data: Record<string, unknown>) => request('/monitoring/watchlists', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  updateWatchlist: (watchlistId: string, data: Record<string, unknown>) => request(`/monitoring/watchlists/${watchlistId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  deleteWatchlist: (watchlistId: string) => request(`/monitoring/watchlists/${watchlistId}`, {
    method: 'DELETE',
  }),
  getAlerts: () => request('/monitoring/alerts'),
  acknowledgeAlert: (alertId: string) => request(`/monitoring/alerts/${alertId}/acknowledge`, {
    method: 'POST',
  }),
  dismissAlert: (alertId: string) => request(`/monitoring/alerts/${alertId}`, {
    method: 'DELETE',
  }),
  getHealth: () => request('/health'),
  getHealthMetrics: () => request('/health/metrics'),
  getLlmHealth: () => request('/llm/health'),
  getMetrics: () => request('/metrics'),
  getRagHealth: () => request('/rag/health'),

  // ============================================
  // Jobs
  // ============================================
  getJobs: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return request(`/jobs/list${queryParams ? `?${queryParams}` : ''}`);
  },
  getJobDetail: (jobId: string | number, params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return request(`/jobs/${encodeURIComponent(String(jobId))}${queryParams ? `?${queryParams}` : ''}`);
  },
  getJobsStats: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return request(`/jobs/stats${queryParams ? `?${queryParams}` : ''}`);
  },
  getJobsStale: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return request(`/jobs/stale${queryParams ? `?${queryParams}` : ''}`);
  },
  cancelJobs: (data: Record<string, unknown>) => request('/jobs/batch/cancel', {
    method: 'POST',
    headers: { 'X-Confirm': 'true' },
    body: JSON.stringify(data),
  }),
  retryJobsNow: (data: Record<string, unknown>) => request('/jobs/retry-now', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  requeueQuarantinedJobs: (data: Record<string, unknown>) => request('/jobs/batch/requeue_quarantined', {
    method: 'POST',
    headers: { 'X-Confirm': 'true' },
    body: JSON.stringify(data),
  }),

  // ============================================
  // Usage Analytics
  // ============================================
  getUsageDaily: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return request(`/admin/usage/daily${queryParams ? `?${queryParams}` : ''}`);
  },
  getUsageTop: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return request(`/admin/usage/top${queryParams ? `?${queryParams}` : ''}`);
  },
  getLlmUsageSummary: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return request(`/admin/llm-usage/summary${queryParams ? `?${queryParams}` : ''}`);
  },
  getLlmTopSpenders: (params?: Record<string, string>) => {
    const queryParams = params ? new URLSearchParams(params).toString() : '';
    return request(`/admin/llm-usage/top-spenders${queryParams ? `?${queryParams}` : ''}`);
  },
};

export default api;
