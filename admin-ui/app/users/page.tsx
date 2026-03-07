'use client';

import { useCallback, useEffect, useMemo, useState, Suspense } from 'react';
import { useRouter } from 'next/navigation';
import { useForm, FormProvider } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { PermissionGuard, usePermissions } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { EmptyState } from '@/components/ui/empty-state';
import { Pagination } from '@/components/ui/pagination';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { Form, FormCheckbox, FormInput, FormSelect } from '@/components/ui/form';
import {
  Eye,
  Key,
  Search,
  Plus,
  Trash2,
  UserCheck,
  UserX,
  BookmarkPlus,
  BookmarkX,
  ShieldCheck,
  ShieldOff,
} from 'lucide-react';
import { AccessibleIconButton } from '@/components/ui/accessible-icon-button';
import { api } from '@/lib/api-client';
import { Organization, User } from '@/types';
import { ExportMenu } from '@/components/ui/export-menu';
import { exportUsers, ExportFormat } from '@/lib/export';
import { Skeleton, TableSkeleton } from '@/components/ui/skeleton';
import { useUrlState, useUrlPagination } from '@/lib/use-url-state';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { usePrivilegedActionDialog } from '@/components/ui/privileged-action-dialog';
import { useToast } from '@/components/ui/toast';
import { useOrgContext } from '@/components/OrgContextSwitcher';
import { useResourceState } from '@/lib/use-resource-state';

type SavedUserView = {
  id: string;
  name: string;
  query: string;
};

type UserStatusFilter = 'all' | 'active' | 'inactive';
type UserVerifiedFilter = 'all' | 'verified' | 'unverified';
type UserMfaFilter = 'all' | 'enabled' | 'disabled';
type BulkActionType =
  | 'activate'
  | 'deactivate'
  | 'delete'
  | 'assign-role'
  | 'reset-password'
  | 'mfa-require'
  | 'mfa-clear'
  | null;

const SAVED_VIEWS_STORAGE_KEY = 'admin_users_saved_views';

const createUserSchema = z.object({
  username: z.string().min(1, 'Username is required'),
  email: z.string().email('Enter a valid email address'),
  password: z.string().min(10, 'Password must be at least 10 characters'),
  role: z.enum(['user', 'admin', 'service']),
  is_active: z.boolean(),
  is_verified: z.boolean(),
});

type CreateUserFormData = z.infer<typeof createUserSchema>;

type InvitationStatus = 'sent' | 'accepted' | 'expired';

type OrgInviteRecord = Record<string, unknown>;

type InvitationRow = {
  id: string;
  status: InvitationStatus;
  email: string;
  invitedBy: string;
  role: string;
  org: string;
  sentAt: string | null;
  expiresAt: string | null;
};

const toRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === 'object'
    ? (value as Record<string, unknown>)
    : null;

const pickString = (...values: unknown[]): string | null => {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return null;
};

const pickNumber = (...values: unknown[]): number | null => {
  for (const value of values) {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === 'string' && value.trim()) {
      const parsed = Number.parseInt(value.trim(), 10);
      if (Number.isFinite(parsed)) return parsed;
    }
  }
  return null;
};

const parseOrganizationsResponse = (value: unknown): Organization[] => {
  if (Array.isArray(value)) {
    return value as Organization[];
  }
  const payload = toRecord(value);
  if (payload && Array.isArray(payload.items)) {
    return payload.items as Organization[];
  }
  return [];
};

const parseOrgInvitesResponse = (value: unknown): OrgInviteRecord[] => {
  if (Array.isArray(value)) {
    return value.filter((item) => toRecord(item) !== null) as OrgInviteRecord[];
  }
  const payload = toRecord(value);
  if (payload && Array.isArray(payload.items)) {
    return payload.items.filter((item) => toRecord(item) !== null) as OrgInviteRecord[];
  }
  return [];
};

const resolveInvitationStatus = (invite: OrgInviteRecord, nowMs: number = Date.now()): InvitationStatus => {
  const expiresAtRaw = pickString(invite.expires_at);
  const expiresAtMs = expiresAtRaw ? Date.parse(expiresAtRaw) : Number.NaN;
  if (Number.isFinite(expiresAtMs) && expiresAtMs < nowMs) {
    return 'expired';
  }
  const usesCount = pickNumber(invite.uses_count) ?? 0;
  if (usesCount > 0) {
    return 'accepted';
  }
  return 'sent';
};

const invitationStatusBadgeVariant = (status: InvitationStatus): 'default' | 'secondary' | 'destructive' => {
  if (status === 'accepted') return 'default';
  if (status === 'expired') return 'destructive';
  return 'secondary';
};

function UsersPageContent() {
  const router = useRouter();
  const confirm = useConfirm();
  const promptPrivilegedAction = usePrivilegedActionDialog();
  const { success, error: showError } = useToast();
  const { selectedOrg } = useOrgContext();
  const { user: currentUser } = usePermissions();
  const currentUserId = currentUser?.id;
  const [bulkAction, setBulkAction] = useState<BulkActionType>(null);
  const [selectedUserIds, setSelectedUserIds] = useState<Set<number>>(new Set());
  const [bulkRole, setBulkRole] = useState('user');
  const [showCreateUserDialog, setShowCreateUserDialog] = useState(false);
  const [createUserError, setCreateUserError] = useState('');
  const [creatingUser, setCreatingUser] = useState(false);
  const [deletingUserIds, setDeletingUserIds] = useState<Set<number>>(new Set());
  const [savedViews, setSavedViews] = useState<SavedUserView[]>([]);
  const [showSaveViewDialog, setShowSaveViewDialog] = useState(false);
  const [saveViewName, setSaveViewName] = useState('');
  const [saveViewError, setSaveViewError] = useState('');
  const [mfaByUserId, setMfaByUserId] = useState<Record<number, boolean>>({});
  const [mfaLoading, setMfaLoading] = useState(false);
  const [orgInvites, setOrgInvites] = useState<OrgInviteRecord[]>([]);
  const [invitesLoading, setInvitesLoading] = useState(true);
  const [invitesError, setInvitesError] = useState('');
  const createUserForm = useForm<CreateUserFormData>({
    resolver: zodResolver(createUserSchema),
    defaultValues: {
      username: '',
      email: '',
      password: '',
      role: 'user',
      is_active: true,
      is_verified: true,
    },
  });

  // URL state for search + filters
  const [searchQuery, setSearchQuery] = useUrlState<string>('q', { defaultValue: '' });
  const [statusFilter, setStatusFilter] = useUrlState<UserStatusFilter>('status', { defaultValue: 'all' });
  const [verifiedFilter, setVerifiedFilter] = useUrlState<UserVerifiedFilter>('verified', { defaultValue: 'all' });
  const [mfaFilter, setMfaFilter] = useUrlState<UserMfaFilter>('mfa', { defaultValue: 'all' });
  const activeViewId = useMemo(() => {
    const match = savedViews.find((view) => view.query === (searchQuery || ''));
    return match ? match.id : '';
  }, [savedViews, searchQuery]);

  // URL state for pagination
  const { page: currentPage, pageSize, setPage: setCurrentPage, setPageSize, resetPagination } = useUrlPagination();

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const stored = window.localStorage.getItem(SAVED_VIEWS_STORAGE_KEY);
      if (!stored) return;
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed)) {
        setSavedViews(parsed as SavedUserView[]);
      }
    } catch (err) {
      console.warn('Failed to load saved user views:', err);
    }
  }, []);

  useEffect(() => {
    if (!showCreateUserDialog) {
      createUserForm.reset();
      setCreateUserError('');
    }
  }, [createUserForm, showCreateUserDialog]);

  const persistSavedViews = useCallback((views: SavedUserView[]) => {
    setSavedViews(views);
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(SAVED_VIEWS_STORAGE_KEY, JSON.stringify(views));
    } catch (err) {
      console.warn('Failed to persist saved user views:', err);
    }
  }, []);

  const loadUsersResource = useCallback(async () => {
    const params: Record<string, string> = { limit: '200' };
    if (selectedOrg) params.org_id = String(selectedOrg.id);
    if (searchQuery) params.search = searchQuery;
    if (statusFilter === 'active') params.is_active = 'true';
    if (statusFilter === 'inactive') params.is_active = 'false';
    if (verifiedFilter === 'verified') params.is_verified = 'true';
    if (verifiedFilter === 'unverified') params.is_verified = 'false';
    if (mfaFilter === 'enabled') params.mfa_enabled = 'true';
    if (mfaFilter === 'disabled') params.mfa_enabled = 'false';
    try {
      return await api.getUsers(params);
    } catch (err: unknown) {
      console.error('Failed to load users:', err);
      throw err instanceof Error
        ? err
        : new Error('Failed to load users');
    }
  }, [mfaFilter, searchQuery, selectedOrg, statusFilter, verifiedFilter]);

  const {
    value: users,
    loading,
    error,
    reload: loadUsers,
  } = useResourceState<User[]>({
    load: loadUsersResource,
    deps: [selectedOrg?.id, searchQuery, statusFilter, verifiedFilter, mfaFilter],
    initialValue: [],
    defaultError: 'Failed to load users',
    resetOnError: true,
  });

  const loadInvitations = useCallback(async () => {
    try {
      setInvitesLoading(true);
      setInvitesError('');

      const organizations = selectedOrg
        ? [{ id: selectedOrg.id, name: selectedOrg.name || `Org #${selectedOrg.id}` }] as Array<Pick<Organization, 'id' | 'name'>>
        : parseOrganizationsResponse(await api.getOrganizations({ limit: '200' }));

      if (organizations.length === 0) {
        setOrgInvites([]);
        return;
      }

      const inviteResults = await Promise.allSettled(
        organizations.map((org) =>
          api.getOrgInvites(String(org.id), {
            include_expired: 'true',
            include_inactive: 'true',
            limit: '100',
          }),
        ),
      );

      const invites: OrgInviteRecord[] = [];
      let successCount = 0;
      inviteResults.forEach((result, index) => {
        if (result.status !== 'fulfilled') return;
        successCount += 1;
        const org = organizations[index];
        parseOrgInvitesResponse(result.value).forEach((invite) => {
          invites.push({
            ...invite,
            org_id: pickNumber(invite.org_id) ?? org.id,
            org_name: pickString(invite.org_name) ?? org.name,
          });
        });
      });

      if (successCount === 0) {
        const firstError = inviteResults.find((result) => result.status === 'rejected');
        throw (firstError && firstError.status === 'rejected') ? firstError.reason : new Error('Failed to load invites');
      }
      if (successCount < inviteResults.length) {
        setInvitesError('Some organization invitations could not be loaded.');
      }

      setOrgInvites(invites);
    } catch (err: unknown) {
      console.error('Failed to load invitations:', err);
      setInvitesError(err instanceof Error && err.message ? err.message : 'Failed to load invitations');
      setOrgInvites([]);
    } finally {
      setInvitesLoading(false);
    }
  }, [selectedOrg]);

  useEffect(() => {
    void loadInvitations();
  }, [loadInvitations]);

  useEffect(() => {
    setSelectedUserIds((prev) => {
      if (prev.size === 0) return prev;
      const available = new Set(users.map((user) => user.id));
      const next = new Set<number>();
      prev.forEach((id) => {
        if (available.has(id) && id !== currentUserId) {
          next.add(id);
        }
      });
      return next;
    });
  }, [currentUserId, users]);

  useEffect(() => {
    if (mfaFilter === 'all') return;
    const missingIds = users
      .map((user) => user.id)
      .filter((id) => mfaByUserId[id] === undefined);
    if (missingIds.length === 0) return;

    let cancelled = false;
    const loadMfaStatus = async () => {
      try {
        setMfaLoading(true);
        const results = await Promise.allSettled(
          missingIds.map(async (id) => {
            const status = await api.getUserMfaStatus(String(id)) as { enabled?: boolean };
            return { id, enabled: Boolean(status?.enabled) };
          })
        );
        if (cancelled) return;
        setMfaByUserId((prev) => {
          const next = { ...prev };
          results.forEach((result) => {
            if (result.status === 'fulfilled') {
              next[result.value.id] = result.value.enabled;
            }
          });
          return next;
        });
      } catch (err) {
        console.error('Failed to load MFA status for users:', err);
      } finally {
        if (!cancelled) {
          setMfaLoading(false);
        }
      }
    };
    void loadMfaStatus();

    return () => {
      cancelled = true;
    };
  }, [mfaByUserId, mfaFilter, users]);

  const filteredUsers = users.filter((user) => {
    const query = (searchQuery || '').toLowerCase();
    if (
      query
      && !(
        user.username?.toLowerCase().includes(query)
        || user.email?.toLowerCase().includes(query)
        || user.role?.toLowerCase().includes(query)
      )
    ) {
      return false;
    }

    if (statusFilter === 'active' && !user.is_active) return false;
    if (statusFilter === 'inactive' && user.is_active) return false;

    if (verifiedFilter === 'verified' && !user.is_verified) return false;
    if (verifiedFilter === 'unverified' && user.is_verified) return false;

    if (mfaFilter !== 'all') {
      const hasMfa = mfaByUserId[user.id];
      if (hasMfa === undefined) return false;
      if (mfaFilter === 'enabled' && !hasMfa) return false;
      if (mfaFilter === 'disabled' && hasMfa) return false;
    }

    return true;
  });

  const userDisplayById = useMemo(() => {
    const mapping = new Map<number, string>();
    users.forEach((user) => {
      mapping.set(user.id, user.username || user.email || `User #${user.id}`);
    });
    return mapping;
  }, [users]);

  const invitationRows = useMemo<InvitationRow[]>(() => {
    const nowMs = Date.now();
    return orgInvites
      .map((invite, index) => {
        const status = resolveInvitationStatus(invite, nowMs);
        const createdBy = pickNumber(invite.created_by);
        const orgId = pickNumber(invite.org_id);
        const allowedEmailDomain = pickString(invite.allowed_email_domain);
        const email = pickString(invite.email, invite.invited_email, invite.invitee_email)
          ?? (allowedEmailDomain
            ? `Any ${allowedEmailDomain.startsWith('@') ? allowedEmailDomain : `@${allowedEmailDomain}`}`
            : '—');

        return {
          id: `${orgId ?? 'org'}-${pickNumber(invite.id) ?? index}`,
          status,
          email,
          invitedBy: pickString(invite.invited_by, invite.created_by_name)
            ?? (createdBy !== null ? userDisplayById.get(createdBy) ?? `User #${createdBy}` : '—'),
          role: pickString(invite.role_to_grant, invite.role) ?? 'member',
          org: pickString(invite.org_name) ?? (orgId !== null ? `Org #${orgId}` : '—'),
          sentAt: pickString(invite.created_at, invite.sent_at),
          expiresAt: pickString(invite.expires_at),
        };
      })
      .sort((a, b) => {
        const aMs = a.sentAt ? Date.parse(a.sentAt) : 0;
        const bMs = b.sentAt ? Date.parse(b.sentAt) : 0;
        return bMs - aMs;
      });
  }, [orgInvites, userDisplayById]);

  const invitationFunnel = useMemo(() => {
    const totalSent = invitationRows.length;
    const totalAccepted = invitationRows.filter((row) => row.status === 'accepted').length;
    const totalPending = invitationRows.filter((row) => row.status === 'sent').length;
    const totalExpired = invitationRows.filter((row) => row.status === 'expired').length;
    const conversionRate = totalSent > 0 ? (totalAccepted / totalSent) * 100 : 0;
    return {
      totalSent,
      totalAccepted,
      totalPending,
      totalExpired,
      conversionRate,
    };
  }, [invitationRows]);

  // Pagination calculations
  const totalItems = filteredUsers.length;
  const totalPages = Math.ceil(totalItems / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const paginatedUsers = filteredUsers.slice(startIndex, startIndex + pageSize);
  const selectableUsers = currentUserId
    ? paginatedUsers.filter((user) => user.id !== currentUserId)
    : paginatedUsers;
  const allVisibleSelected = selectableUsers.length > 0
    && selectableUsers.every((user) => selectedUserIds.has(user.id));
  const selectedCount = selectedUserIds.size;
  const bulkBusy = bulkAction !== null;
  const hasActiveFilters = (statusFilter || 'all') !== 'all'
    || (verifiedFilter || 'all') !== 'all'
    || (mfaFilter || 'all') !== 'all';
  const bulkRoleOptions = useMemo(() => {
    const roleSet = new Set<string>(['user', 'admin', 'service']);
    users.forEach((user) => {
      if (typeof user.role === 'string' && user.role.trim()) {
        roleSet.add(user.role);
      }
    });
    return Array.from(roleSet);
  }, [users]);

  useEffect(() => {
    if (bulkRoleOptions.length === 0) return;
    if (!bulkRoleOptions.includes(bulkRole)) {
      setBulkRole(bulkRoleOptions[0]);
    }
  }, [bulkRole, bulkRoleOptions]);

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

  const handlePageSizeChange = (size: number) => {
    setPageSize(size);
    resetPagination();
  };

  const handleSearchChange = (value: string) => {
    setSearchQuery(value || undefined);
    resetPagination();
  };

  const handleStatusFilterChange = (value: UserStatusFilter) => {
    setStatusFilter(value === 'all' ? undefined : value);
    resetPagination();
  };

  const handleVerifiedFilterChange = (value: UserVerifiedFilter) => {
    setVerifiedFilter(value === 'all' ? undefined : value);
    resetPagination();
  };

  const handleMfaFilterChange = (value: UserMfaFilter) => {
    setMfaFilter(value === 'all' ? undefined : value);
    resetPagination();
  };

  const handleClearFilters = () => {
    setStatusFilter(undefined);
    setVerifiedFilter(undefined);
    setMfaFilter(undefined);
    resetPagination();
  };

  const handleToggleSelectUser = (userId: number, checked: boolean) => {
    if (currentUserId && userId === currentUserId) return;
    setSelectedUserIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        next.add(userId);
      } else {
        next.delete(userId);
      }
      return next;
    });
  };

  const handleToggleSelectAllVisible = (checked: boolean) => {
    setSelectedUserIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        paginatedUsers.forEach((user) => {
          if (currentUserId && user.id === currentUserId) return;
          next.add(user.id);
        });
      } else {
        paginatedUsers.forEach((user) => {
          if (currentUserId && user.id === currentUserId) return;
          next.delete(user.id);
        });
      }
      return next;
    });
  };

  const handleClearSelection = () => {
    setSelectedUserIds(new Set());
  };

  const handleBulkToggleActive = async (nextState: boolean) => {
    const ids = Array.from(selectedUserIds);
    if (ids.length === 0) return;
    const approval = await promptPrivilegedAction({
      title: nextState ? 'Activate selected users' : 'Deactivate selected users',
      message: `${nextState ? 'Activate' : 'Deactivate'} ${ids.length} selected user${ids.length !== 1 ? 's' : ''}? Reauthentication is required.`,
      confirmText: nextState ? 'Activate' : 'Deactivate',
    });
    if (!approval) return;

    try {
      setBulkAction(nextState ? 'activate' : 'deactivate');
      const results = await Promise.allSettled(
        ids.map((id) => api.updateUser(id.toString(), {
          is_active: nextState,
          reason: approval.reason,
          admin_password: approval.adminPassword,
        }))
      );
      const failures = results.filter((result) => result.status === 'rejected').length;
      if (failures > 0) {
        showError(
          'Bulk update incomplete',
          `${ids.length - failures} updated, ${failures} failed.`
        );
      } else {
        success(
          'Users updated',
          `${ids.length} user${ids.length !== 1 ? 's' : ''} ${nextState ? 'activated' : 'deactivated'}.`
        );
      }
      handleClearSelection();
      void loadUsers();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update users';
      showError('Bulk update failed', message);
    } finally {
      setBulkAction(null);
    }
  };

  const handleBulkDelete = async () => {
    const ids = Array.from(selectedUserIds);
    if (ids.length === 0) return;
    if (currentUser && ids.includes(currentUser.id)) {
      showError('Cannot delete yourself', 'Remove your account from the selection to continue.');
      return;
    }
    const approval = await promptPrivilegedAction({
      title: 'Delete selected users',
      message: `Delete ${ids.length} selected user${ids.length !== 1 ? 's' : ''}? This cannot be undone.`,
      confirmText: 'Delete',
    });
    if (!approval) return;

    try {
      setBulkAction('delete');
      const results = await Promise.allSettled(
        ids.map((id) => api.deleteUser(id.toString(), {
          reason: approval.reason,
          admin_password: approval.adminPassword,
        }))
      );
      const failures = results.filter((result) => result.status === 'rejected').length;
      if (failures > 0) {
        showError(
          'Bulk delete incomplete',
          `${ids.length - failures} deleted, ${failures} failed.`
        );
      } else {
        success(
          'Users deleted',
          `${ids.length} user${ids.length !== 1 ? 's' : ''} removed.`
        );
      }
      handleClearSelection();
      void loadUsers();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to delete users';
      showError('Bulk delete failed', message);
    } finally {
      setBulkAction(null);
    }
  };

  const handleBulkAssignRole = async () => {
    const ids = Array.from(selectedUserIds);
    if (ids.length === 0 || !bulkRole) return;
    const approval = await promptPrivilegedAction({
      title: 'Assign role to selected users',
      message: `Assign "${bulkRole}" role to ${ids.length} selected user${ids.length !== 1 ? 's' : ''}? Reauthentication is required.`,
      confirmText: 'Assign role',
    });
    if (!approval) return;

    try {
      setBulkAction('assign-role');
      const results = await Promise.allSettled(
        ids.map((id) => api.updateUser(id.toString(), {
          role: bulkRole,
          reason: approval.reason,
          admin_password: approval.adminPassword,
        }))
      );
      const failures = results.filter((result) => result.status === 'rejected').length;
      if (failures > 0) {
        showError(
          'Role assignment incomplete',
          `${ids.length - failures} updated, ${failures} failed.`
        );
      } else {
        success(
          'Roles assigned',
          `${ids.length} user${ids.length !== 1 ? 's' : ''} updated to ${bulkRole}.`
        );
      }
      handleClearSelection();
      void loadUsers();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to assign role';
      showError('Role assignment failed', message);
    } finally {
      setBulkAction(null);
    }
  };

  const handleBulkResetPasswords = async () => {
    const ids = Array.from(selectedUserIds);
    if (ids.length === 0) return;
    const approval = await promptPrivilegedAction({
      title: 'Reset selected user passwords',
      message: `Reset passwords for ${ids.length} selected user${ids.length !== 1 ? 's' : ''}?`,
      confirmText: 'Reset passwords',
    });
    if (!approval) return;

    try {
      setBulkAction('reset-password');
      const results = await Promise.allSettled(
        ids.map((id) => api.resetUserPassword(id.toString(), {
          force_password_change: true,
          reason: approval.reason,
          admin_password: approval.adminPassword,
        }))
      );
      const failures = results.filter((result) => result.status === 'rejected').length;
      if (failures > 0) {
        showError(
          'Bulk password reset incomplete',
          `${ids.length - failures} reset, ${failures} failed.`
        );
      } else {
        success(
          'Passwords reset',
          `${ids.length} user${ids.length !== 1 ? 's' : ''} now require a password change on next login.`
        );
      }
      handleClearSelection();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to reset passwords';
      showError('Bulk password reset failed', message);
    } finally {
      setBulkAction(null);
    }
  };

  const handleBulkSetMfaRequirement = async (requireMfa: boolean) => {
    const ids = Array.from(selectedUserIds);
    if (ids.length === 0) return;
    const approval = await promptPrivilegedAction({
      title: requireMfa ? 'Require MFA for selected users' : 'Clear MFA requirement for selected users',
      message: `${requireMfa ? 'Require MFA for' : 'Clear MFA requirement for'} ${ids.length} selected user${ids.length !== 1 ? 's' : ''}?`,
      confirmText: requireMfa ? 'Require MFA' : 'Clear requirement',
    });
    if (!approval) return;

    try {
      setBulkAction(requireMfa ? 'mfa-require' : 'mfa-clear');
      const results = await Promise.allSettled(
        ids.map((id) => api.setUserMfaRequirement(id.toString(), {
          require_mfa: requireMfa,
          reason: approval.reason,
          admin_password: approval.adminPassword,
        }))
      );
      const failures = results.filter((result) => result.status === 'rejected').length;
      const successIds: number[] = [];
      results.forEach((result, index) => {
        if (result.status === 'fulfilled') {
          successIds.push(ids[index]);
        }
      });
      if (successIds.length > 0) {
        setMfaByUserId((prev) => {
          const next = { ...prev };
          successIds.forEach((id) => {
            next[id] = requireMfa;
          });
          return next;
        });
      }

      if (failures > 0) {
        showError(
          'Bulk MFA update incomplete',
          `${ids.length - failures} updated, ${failures} failed.`
        );
      } else {
        success(
          'MFA requirements updated',
          `${ids.length} user${ids.length !== 1 ? 's' : ''} ${requireMfa ? 'now require' : 'no longer require'} MFA.`
        );
      }
      handleClearSelection();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update MFA requirement';
      showError('Bulk MFA update failed', message);
    } finally {
      setBulkAction(null);
    }
  };

  const getRoleBadgeVariant = (role: string) => {
    switch (role) {
      case 'admin':
      case 'super_admin':
      case 'owner':
        return 'default';
      default:
        return 'secondary';
    }
  };

  const formatStorageUsage = (usedMb: number, quotaMb: number) => {
    const percentage = quotaMb > 0 ? (usedMb / quotaMb) * 100 : 0;
    return {
      text: `${usedMb.toFixed(1)} / ${quotaMb} MB`,
      percentage: Math.min(percentage, 100),
    };
  };

  const handleExport = (format: ExportFormat) => {
    exportUsers(filteredUsers, format);
  };

  const handleApplySavedView = (viewId: string) => {
    if (!viewId) {
      setSearchQuery(undefined);
      resetPagination();
      return;
    }
    const view = savedViews.find((item) => item.id === viewId);
    if (!view) return;
    setSearchQuery(view.query || undefined);
    resetPagination();
  };

  const handleSaveView = () => {
    const name = saveViewName.trim();
    if (!name) {
      setSaveViewError('Provide a name for this view.');
      return;
    }
    const query = searchQuery || '';
    const newView: SavedUserView = {
      id: `${Date.now()}`,
      name,
      query,
    };
    persistSavedViews([newView, ...savedViews]);
    setSaveViewName('');
    setSaveViewError('');
    setShowSaveViewDialog(false);
    success('Saved view', `${name} has been added.`);
  };

  const handleDeleteView = async () => {
    if (!activeViewId) return;
    const view = savedViews.find((item) => item.id === activeViewId);
    if (!view) return;
    const confirmed = await confirm({
      title: 'Delete saved view',
      message: `Delete "${view.name}"?`,
      confirmText: 'Delete',
      variant: 'danger',
      icon: 'delete',
    });
    if (!confirmed) return;
    const next = savedViews.filter((item) => item.id !== activeViewId);
    persistSavedViews(next);
    success('Saved view removed', `"${view.name}" deleted.`);
  };

  const handleCreateUserSubmit = createUserForm.handleSubmit(async (data) => {
    setCreateUserError('');
    try {
      setCreatingUser(true);
      await api.createUser({
        username: data.username,
        email: data.email,
        password: data.password,
        role: data.role,
        is_active: data.is_active,
        is_verified: data.is_verified,
      });
      success('User created', `${data.username} added.`);
      setShowCreateUserDialog(false);
      createUserForm.reset();
      void loadUsers();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create user';
      setCreateUserError(message);
      showError('Create user failed', message);
    } finally {
      setCreatingUser(false);
    }
  });

  const handleToggleActive = async (user: User) => {
    const nextState = !user.is_active;
    const approval = await promptPrivilegedAction({
      title: nextState ? 'Activate User' : 'Deactivate User',
      message: `${nextState ? 'Activate' : 'Deactivate'} ${user.username || user.email}? Reauthentication is required.`,
      confirmText: nextState ? 'Activate' : 'Deactivate',
    });
    if (!approval) return;

    try {
      await api.updateUser(user.id.toString(), {
        is_active: nextState,
        reason: approval.reason,
        admin_password: approval.adminPassword,
      });
      success('User updated', `${user.username || user.email} ${nextState ? 'activated' : 'deactivated'}.`);
      void loadUsers();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update user';
      showError('Update failed', message);
    }
  };

  const handleDeleteUser = async (user: User) => {
    if (currentUser && user.id === currentUser.id) {
      showError('Cannot delete yourself', 'You cannot delete your own account.');
      return;
    }
    const userId = user.id;
    if (deletingUserIds.has(userId)) return;
    const approval = await promptPrivilegedAction({
      title: 'Delete User',
      message: `Delete ${user.username || user.email}? This cannot be undone.`,
      confirmText: 'Delete',
    });
    if (!approval) return;

    try {
      setDeletingUserIds((prev) => {
        const next = new Set(prev);
        next.add(userId);
        return next;
      });
      await api.deleteUser(String(userId), {
        reason: approval.reason,
        admin_password: approval.adminPassword,
      });
      success('User deleted', `${user.username || user.email} removed.`);
      void loadUsers();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to delete user';
      showError('Delete failed', message);
    } finally {
      setDeletingUserIds((prev) => {
        const next = new Set(prev);
        next.delete(userId);
        return next;
      });
    }
  };

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="mb-8 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h1 className="text-3xl font-bold">Users</h1>
                <p className="text-muted-foreground">Manage system users and their access</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <ExportMenu
                  onExport={handleExport}
                  disabled={filteredUsers.length === 0}
                />
                <Dialog open={showCreateUserDialog} onOpenChange={setShowCreateUserDialog}>
                  <DialogTrigger asChild>
                    <Button>
                      <Plus className="mr-2 h-4 w-4" />
                      Create User
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Create user</DialogTitle>
                      <DialogDescription>Create a user with a temporary password.</DialogDescription>
                    </DialogHeader>
                    {createUserError && (
                      <Alert variant="destructive">
                        <AlertDescription>{createUserError}</AlertDescription>
                      </Alert>
                    )}
                    <FormProvider {...createUserForm}>
                      <Form onSubmit={handleCreateUserSubmit}>
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                          <FormInput<CreateUserFormData>
                            name="username"
                            label="Username"
                            required
                          />
                          <FormInput<CreateUserFormData>
                            name="email"
                            label="Email"
                            type="email"
                            required
                          />
                        </div>
                        <FormInput<CreateUserFormData>
                          name="password"
                          label="Password"
                          type="password"
                          description="Minimum 10 characters."
                          required
                        />
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                          <FormSelect<CreateUserFormData>
                            name="role"
                            label="Role"
                            options={[
                              { value: 'user', label: 'User' },
                              { value: 'admin', label: 'Admin' },
                              { value: 'service', label: 'Service' },
                            ]}
                          />
                          <div className="space-y-2">
                            <Label className="block">Status</Label>
                            <div className="space-y-2">
                              <FormCheckbox<CreateUserFormData>
                                name="is_active"
                                label="Active"
                              />
                              <FormCheckbox<CreateUserFormData>
                                name="is_verified"
                                label="Verified"
                              />
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
                          <Button type="submit" loading={creatingUser} loadingText="Creating...">
                            Create user
                          </Button>
                        </DialogFooter>
                      </Form>
                    </FormProvider>
                  </DialogContent>
                </Dialog>
              </div>
            </div>

            {error && (
              <Alert variant="destructive" className="mb-6">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {/* Search */}
            <Card className="mb-6">
              <CardContent className="pt-6">
                <div className="space-y-4">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="relative max-w-md w-full">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" aria-hidden="true" />
                      <label htmlFor="users-search" className="sr-only">
                        Search users by username, email, or role
                      </label>
                      <Input
                        id="users-search"
                        placeholder="Search by username, email, or role..."
                        value={searchQuery || ''}
                        onChange={(e) => handleSearchChange(e.target.value)}
                        className="pl-10"
                      />
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Select
                        id="users-saved-view-filter"
                        value={activeViewId}
                        onChange={(event) => handleApplySavedView(event.target.value)}
                        className="min-w-[200px]"
                        aria-label="Saved views"
                        disabled={savedViews.length === 0}
                      >
                        <option value="">Saved views</option>
                        {savedViews.map((view) => (
                          <option key={view.id} value={view.id}>
                            {view.name}
                          </option>
                        ))}
                      </Select>
                      <Dialog open={showSaveViewDialog} onOpenChange={(open) => {
                        setShowSaveViewDialog(open);
                        if (!open) {
                          setSaveViewError('');
                          setSaveViewName('');
                        }
                      }}>
                        <DialogTrigger asChild>
                          <Button variant="outline">
                            <BookmarkPlus className="mr-2 h-4 w-4" />
                            Save view
                          </Button>
                        </DialogTrigger>
                        <DialogContent>
                          <DialogHeader>
                            <DialogTitle>Save view</DialogTitle>
                            <DialogDescription>Store the current search for quick reuse.</DialogDescription>
                          </DialogHeader>
                          {saveViewError && (
                            <Alert variant="destructive">
                              <AlertDescription>{saveViewError}</AlertDescription>
                            </Alert>
                          )}
                          <div className="space-y-2">
                            <Label htmlFor="saved-view-name">View name</Label>
                            <Input
                              id="saved-view-name"
                              value={saveViewName}
                              onChange={(event) => setSaveViewName(event.target.value)}
                              placeholder="e.g., Inactive admins"
                            />
                            <p className="text-xs text-muted-foreground">
                              Current search: {searchQuery || 'All users'}
                            </p>
                          </div>
                          <DialogFooter>
                            <Button variant="outline" onClick={() => setShowSaveViewDialog(false)}>
                              Cancel
                            </Button>
                            <Button onClick={handleSaveView}>
                              Save view
                            </Button>
                          </DialogFooter>
                        </DialogContent>
                      </Dialog>
                      <Button
                        variant="outline"
                        onClick={handleDeleteView}
                        disabled={!activeViewId}
                      >
                        <BookmarkX className="mr-2 h-4 w-4" />
                        Delete view
                      </Button>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Label htmlFor="users-status-filter" className="sr-only">Filter by user status</Label>
                    <Select
                      id="users-status-filter"
                      className="min-w-[160px]"
                      value={statusFilter || 'all'}
                      onChange={(event) => handleStatusFilterChange(event.target.value as UserStatusFilter)}
                    >
                      <option value="all">Status: All</option>
                      <option value="active">Status: Active</option>
                      <option value="inactive">Status: Inactive</option>
                    </Select>
                    <Label htmlFor="users-verified-filter" className="sr-only">Filter by verification state</Label>
                    <Select
                      id="users-verified-filter"
                      className="min-w-[160px]"
                      value={verifiedFilter || 'all'}
                      onChange={(event) => handleVerifiedFilterChange(event.target.value as UserVerifiedFilter)}
                    >
                      <option value="all">Verified: All</option>
                      <option value="verified">Verified: Yes</option>
                      <option value="unverified">Verified: No</option>
                    </Select>
                    <Label htmlFor="users-mfa-filter" className="sr-only">Filter by MFA status</Label>
                    <Select
                      id="users-mfa-filter"
                      className="min-w-[160px]"
                      value={mfaFilter || 'all'}
                      onChange={(event) => handleMfaFilterChange(event.target.value as UserMfaFilter)}
                    >
                      <option value="all">MFA: All</option>
                      <option value="enabled">MFA: Enabled</option>
                      <option value="disabled">MFA: Disabled</option>
                    </Select>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleClearFilters}
                      disabled={!hasActiveFilters}
                    >
                      Clear filters
                    </Button>
                    {mfaFilter !== 'all' && mfaLoading && (
                      <span className="text-xs text-muted-foreground">Loading MFA status...</span>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Invitations</CardTitle>
                <CardDescription>
                  Onboarding invitation visibility across organizations.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {invitesError && (
                  <Alert variant="destructive">
                    <AlertDescription>{invitesError}</AlertDescription>
                  </Alert>
                )}
                <div className="grid gap-3 sm:grid-cols-4">
                  <div className="rounded-lg border p-3">
                    <p className="text-xs uppercase text-muted-foreground">Total Sent</p>
                    <p className="text-2xl font-semibold" data-testid="invitation-total-sent">
                      {invitationFunnel.totalSent}
                    </p>
                  </div>
                  <div className="rounded-lg border p-3">
                    <p className="text-xs uppercase text-muted-foreground">Accepted</p>
                    <p className="text-2xl font-semibold" data-testid="invitation-total-accepted">
                      {invitationFunnel.totalAccepted}
                    </p>
                  </div>
                  <div className="rounded-lg border p-3">
                    <p className="text-xs uppercase text-muted-foreground">Pending</p>
                    <p className="text-2xl font-semibold">{invitationFunnel.totalPending}</p>
                  </div>
                  <div className="rounded-lg border p-3">
                    <p className="text-xs uppercase text-muted-foreground">Conversion Rate</p>
                    <p className="text-2xl font-semibold" data-testid="invitation-conversion-rate">
                      {invitationFunnel.conversionRate.toFixed(1)}%
                    </p>
                  </div>
                </div>

                {invitesLoading ? (
                  <div className="text-sm text-muted-foreground">Loading invitations…</div>
                ) : invitationRows.length === 0 ? (
                  <div className="text-sm text-muted-foreground">No invitations found.</div>
                ) : (
                  <div className="rounded-md border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Status</TableHead>
                          <TableHead>Email</TableHead>
                          <TableHead>Invited by</TableHead>
                          <TableHead>Role</TableHead>
                          <TableHead>Org</TableHead>
                          <TableHead>Sent</TableHead>
                          <TableHead>Expires</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {invitationRows.map((invite) => (
                          <TableRow key={invite.id} data-testid={`invitation-row-${invite.id}`}>
                            <TableCell>
                              <Badge variant={invitationStatusBadgeVariant(invite.status)}>
                                {invite.status}
                              </Badge>
                            </TableCell>
                            <TableCell>{invite.email}</TableCell>
                            <TableCell>{invite.invitedBy}</TableCell>
                            <TableCell>{invite.role}</TableCell>
                            <TableCell>{invite.org}</TableCell>
                            <TableCell>
                              {invite.sentAt ? new Date(invite.sentAt).toLocaleDateString() : '—'}
                            </TableCell>
                            <TableCell>
                              {invite.expiresAt ? new Date(invite.expiresAt).toLocaleDateString() : '—'}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Users List</CardTitle>
                <CardDescription>
                  {totalItems} user{totalItems !== 1 ? 's' : ''} found
                </CardDescription>
              </CardHeader>
              <CardContent>
                {selectedCount > 0 && (
                  <div className="mb-4 flex flex-col gap-3 rounded-md border bg-muted/20 p-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">{selectedCount} selected</Badge>
                      <span className="text-sm text-muted-foreground">
                        Bulk actions apply to selected users.
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Select
                        value={bulkRole}
                        onChange={(event) => setBulkRole(event.target.value)}
                        className="min-w-[160px]"
                        aria-label="Bulk role selection"
                        disabled={bulkBusy}
                      >
                        {bulkRoleOptions.map((role) => (
                          <option key={role} value={role}>
                            {role}
                          </option>
                        ))}
                      </Select>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleBulkAssignRole}
                        loading={bulkAction === 'assign-role'}
                        loadingText="Assigning..."
                        disabled={bulkBusy && bulkAction !== 'assign-role'}
                      >
                        Assign Role
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleBulkToggleActive(true)}
                        loading={bulkAction === 'activate'}
                        loadingText="Activating..."
                        disabled={bulkBusy && bulkAction !== 'activate'}
                      >
                        <UserCheck className="mr-2 h-4 w-4" />
                        Activate
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleBulkToggleActive(false)}
                        loading={bulkAction === 'deactivate'}
                        loadingText="Deactivating..."
                        disabled={bulkBusy && bulkAction !== 'deactivate'}
                      >
                        <UserX className="mr-2 h-4 w-4" />
                        Deactivate
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleBulkResetPasswords}
                        loading={bulkAction === 'reset-password'}
                        loadingText="Resetting..."
                        disabled={bulkBusy && bulkAction !== 'reset-password'}
                      >
                        <Key className="mr-2 h-4 w-4" />
                        Reset Passwords
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleBulkSetMfaRequirement(true)}
                        loading={bulkAction === 'mfa-require'}
                        loadingText="Applying..."
                        disabled={bulkBusy && bulkAction !== 'mfa-require'}
                      >
                        <ShieldCheck className="mr-2 h-4 w-4" />
                        Require MFA
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleBulkSetMfaRequirement(false)}
                        loading={bulkAction === 'mfa-clear'}
                        loadingText="Clearing..."
                        disabled={bulkBusy && bulkAction !== 'mfa-clear'}
                      >
                        <ShieldOff className="mr-2 h-4 w-4" />
                        Clear MFA
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleBulkDelete}
                        loading={bulkAction === 'delete'}
                        loadingText="Deleting..."
                        disabled={bulkBusy && bulkAction !== 'delete'}
                      >
                        <Trash2 className="mr-2 h-4 w-4 text-destructive" />
                        Delete
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleClearSelection}
                        disabled={bulkBusy}
                      >
                        Clear selection
                      </Button>
                    </div>
                  </div>
                )}
                {loading ? (
                  <div className="py-4">
                    <TableSkeleton rows={5} columns={9} />
                  </div>
                ) : filteredUsers.length === 0 ? (
                  <EmptyState
                    icon={UserCheck}
                    title={searchQuery || hasActiveFilters ? 'No users match your filters' : 'No users found'}
                    description={
                      searchQuery || hasActiveFilters
                        ? 'Try adjusting search terms or clearing filters.'
                        : 'Create your first user to start onboarding.'
                    }
                    actions={[
                      searchQuery || hasActiveFilters
                        ? {
                            label: 'Clear filters',
                            onClick: () => {
                              setSearchQuery(undefined);
                              handleClearFilters();
                            },
                          }
                        : {
                            label: 'Create user',
                            onClick: () => setShowCreateUserDialog(true),
                          },
                    ]}
                  />
                ) : (
                  <>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-10">
                            <Checkbox
                              checked={allVisibleSelected}
                              onCheckedChange={handleToggleSelectAllVisible}
                              aria-label="Select all visible users"
                            />
                          </TableHead>
                          <TableHead>ID</TableHead>
                          <TableHead>Username</TableHead>
                          <TableHead>Email</TableHead>
                          <TableHead>Role</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Storage</TableHead>
                          <TableHead>Last Login</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {paginatedUsers.map((user) => {
                          const storage = formatStorageUsage(
                            user.storage_used_mb || 0,
                            user.storage_quota_mb || 0
                          );
                          const isCurrentUser = currentUserId === user.id;
                          const isDeleting = deletingUserIds.has(user.id);
                          return (
                            <TableRow key={user.id}>
                              <TableCell>
                                <Checkbox
                                  checked={selectedUserIds.has(user.id)}
                                  onCheckedChange={(checked) => handleToggleSelectUser(user.id, checked)}
                                  aria-label={`Select user ${user.username || user.email || user.id}`}
                                  disabled={isCurrentUser}
                                />
                              </TableCell>
                              <TableCell className="font-mono text-sm">{user.id}</TableCell>
                              <TableCell className="font-medium">{user.username}</TableCell>
                              <TableCell>{user.email}</TableCell>
                              <TableCell>
                                <Badge variant={getRoleBadgeVariant(user.role)}>
                                  {user.role}
                                </Badge>
                              </TableCell>
                              <TableCell>
                                <Badge variant={user.is_active ? 'default' : 'destructive'}>
                                  {user.is_active ? 'Active' : 'Inactive'}
                                </Badge>
                                {user.is_verified && (
                                  <Badge variant="outline" className="ml-1">
                                    Verified
                                  </Badge>
                                )}
                              </TableCell>
                              <TableCell>
                                <div className="space-y-1">
                                  <div className="text-xs">{storage.text}</div>
                                  <div
                                    className="w-20 bg-gray-200 rounded-full h-1.5"
                                    role="progressbar"
                                    aria-valuenow={Math.round(storage.percentage)}
                                    aria-valuemin={0}
                                    aria-valuemax={100}
                                    aria-label={`Storage usage: ${Math.round(storage.percentage)}%${
                                      storage.percentage > 90 ? ', critical' :
                                      storage.percentage > 70 ? ', warning' : ''
                                    }`}
                                  >
                                    <div
                                      className={`h-1.5 rounded-full ${
                                        storage.percentage > 90 ? 'bg-red-500' :
                                        storage.percentage > 70 ? 'bg-yellow-500' :
                                        'bg-green-500'
                                      }`}
                                      style={{ width: `${storage.percentage}%` }}
                                    />
                                  </div>
                                </div>
                              </TableCell>
                              <TableCell className="text-muted-foreground text-sm">
                                {user.last_login
                                  ? new Date(user.last_login).toLocaleDateString()
                                  : 'Never'}
                              </TableCell>
                              <TableCell className="text-right">
                                <div className="flex justify-end gap-1">
                                  <AccessibleIconButton
                                    icon={Eye}
                                    label="View user details"
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => router.push(`/users/${user.id}`)}
                                  />
                                  <AccessibleIconButton
                                    icon={Key}
                                    label="Manage API keys"
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => router.push(`/users/${user.id}/api-keys`)}
                                  />
                                  <AccessibleIconButton
                                    icon={user.is_active ? UserX : UserCheck}
                                    label={user.is_active ? 'Deactivate user' : 'Activate user'}
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleToggleActive(user)}
                                  />
                                  <AccessibleIconButton
                                    icon={Trash2}
                                    label={isDeleting ? 'Deleting user' : isCurrentUser ? 'Cannot delete yourself' : 'Delete user'}
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleDeleteUser(user)}
                                    disabled={isCurrentUser || isDeleting}
                                    loading={isDeleting}
                                    className="text-destructive hover:text-destructive"
                                  />
                                </div>
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>

                    <Pagination
                      currentPage={currentPage}
                      totalPages={totalPages}
                      totalItems={totalItems}
                      pageSize={pageSize}
                      onPageChange={handlePageChange}
                      onPageSizeChange={handlePageSizeChange}
                    />
                  </>
                )}
              </CardContent>
            </Card>
          </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}

// Wrap with Suspense for useSearchParams
export default function UsersPage() {
  return (
    <Suspense fallback={
      <PermissionGuard variant="route" requireAuth role="admin">
        <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="mb-8">
              <Skeleton className="h-8 w-32 mb-2" />
              <Skeleton className="h-4 w-64" />
            </div>
            <TableSkeleton rows={5} columns={9} />
          </div>
        </ResponsiveLayout>
      </PermissionGuard>
    }>
      <UsersPageContent />
    </Suspense>
  );
}
