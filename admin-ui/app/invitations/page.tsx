'use client';

import { useCallback, useEffect, useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { EmptyState } from '@/components/ui/empty-state';
import { CardSkeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { Mail, RefreshCw, Trash2, RotateCw } from 'lucide-react';
import { AccessibleIconButton } from '@/components/ui/accessible-icon-button';
import { api } from '@/lib/api-client';
import type { Organization } from '@/types';

interface Invite {
  id: string;
  code: string;
  org_id: number;
  team_id?: number | null;
  role_to_grant: string;
  max_uses: number;
  uses: number;
  status: string;
  description?: string | null;
  expires_at?: string | null;
  created_at: string;
}

export default function InvitationsPage() {
  const [invites, setInvites] = useState<Invite[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrgId, setSelectedOrgId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [orgNames, setOrgNames] = useState<Record<string, string>>({});
  const toast = useToast();
  const confirm = useConfirm();

  const loadOrgs = useCallback(async () => {
    try {
      const orgs = await api.getOrganizations();
      const list = Array.isArray(orgs) ? orgs : [];
      setOrganizations(list as Organization[]);
      const names: Record<string, string> = {};
      list.forEach((o: Organization) => { names[String(o.id)] = o.name; });
      setOrgNames(names);
      if (list.length > 0 && !selectedOrgId) {
        setSelectedOrgId(String(list[0].id));
      }
    } catch {
      toast.error('Failed to load organizations');
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- selectedOrgId read at call-time via guard, not reactive
  }, [toast]);

  const loadInvites = useCallback(async () => {
    if (!selectedOrgId) return;
    setLoading(true);
    try {
      const data = await api.getOrgInvites(selectedOrgId, { include_expired: 'true' });
      const items = (data as { items?: Invite[] })?.items ?? (Array.isArray(data) ? data : []);
      setInvites(items as Invite[]);
    } catch {
      toast.error('Failed to load invites');
    } finally {
      setLoading(false);
    }
  }, [selectedOrgId, toast]);

  useEffect(() => { loadOrgs(); }, [loadOrgs]);
  useEffect(() => { loadInvites(); }, [loadInvites]);

  const handleRevoke = async (invite: Invite) => {
    const ok = await confirm({
      title: 'Revoke Invite',
      message: `Revoke invite code ${invite.code.slice(0, 8)}...? It will no longer be usable.`,
      confirmText: 'Revoke',
      variant: 'danger',
      icon: 'delete',
    });
    if (!ok) return;
    try {
      await api.revokeOrgInvite(String(invite.org_id), invite.id);
      toast.success('Invite revoked');
      loadInvites();
    } catch {
      toast.error('Failed to revoke invite');
    }
  };

  const handleResend = async (invite: Invite) => {
    // Resend creates a new invite with same parameters
    try {
      await api.createOrgInvite(String(invite.org_id), {
        role_to_grant: invite.role_to_grant,
        team_id: invite.team_id,
        max_uses: invite.max_uses,
        description: invite.description ? `Resent: ${invite.description}` : 'Resent invite',
      });
      toast.success('New invite created (resent)');
      loadInvites();
    } catch {
      toast.error('Failed to resend invite');
    }
  };

  const getStatusBadge = (invite: Invite) => {
    if (invite.status === 'revoked') return <Badge variant="destructive">Revoked</Badge>;
    if (invite.expires_at && new Date(invite.expires_at) < new Date()) return <Badge variant="secondary">Expired</Badge>;
    if (invite.max_uses > 0 && invite.uses >= invite.max_uses) return <Badge variant="secondary">Exhausted</Badge>;
    return <Badge variant="default">Active</Badge>;
  };

  return (
    <PermissionGuard variant="route" requireAuth role={['admin', 'super_admin', 'owner']}>
      <ResponsiveLayout>
        <div className="p-4 lg:p-8 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold flex items-center gap-2">
                <Mail className="h-7 w-7" />
                Organization Invitations
              </h1>
              <p className="text-muted-foreground">Manage invite codes across organizations</p>
            </div>
            <AccessibleIconButton
              icon={RefreshCw}
              label="Refresh"
              variant="outline"
              onClick={() => loadInvites()}
              className={loading ? 'animate-spin' : ''}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Select Organization</CardTitle>
              <CardDescription>View and manage invites for a specific organization</CardDescription>
            </CardHeader>
            <CardContent>
              <Select
                value={selectedOrgId}
                onChange={(e) => setSelectedOrgId(e.target.value)}
                className="max-w-md"
              >
                {organizations.map((org) => (
                  <option key={org.id} value={String(org.id)}>
                    {org.name} ({org.slug})
                  </option>
                ))}
              </Select>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Invitations</CardTitle>
              <CardDescription>
                {invites.length} invite{invites.length !== 1 ? 's' : ''} for {orgNames[selectedOrgId] || 'selected organization'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <CardSkeleton />
              ) : invites.length === 0 ? (
                <EmptyState
                  icon={Mail}
                  title="No Invitations"
                  description="No invite codes found for this organization."
                />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Code</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Uses</TableHead>
                      <TableHead>Expires</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {invites.map((invite) => (
                      <TableRow key={invite.id}>
                        <TableCell className="font-mono text-sm">{invite.code.slice(0, 12)}...</TableCell>
                        <TableCell><Badge variant="outline">{invite.role_to_grant}</Badge></TableCell>
                        <TableCell>{getStatusBadge(invite)}</TableCell>
                        <TableCell>{invite.uses} / {invite.max_uses || '∞'}</TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                          {invite.expires_at ? new Date(invite.expires_at).toLocaleDateString() : 'Never'}
                        </TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                          {new Date(invite.created_at).toLocaleDateString()}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            <AccessibleIconButton
                              icon={RotateCw}
                              label="Resend invite"
                              variant="ghost"
                              size="sm"
                              onClick={() => handleResend(invite)}
                            />
                            <AccessibleIconButton
                              icon={Trash2}
                              label="Revoke invite"
                              variant="ghost"
                              size="sm"
                              onClick={() => handleRevoke(invite)}
                              className="text-destructive hover:text-destructive"
                            />
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
