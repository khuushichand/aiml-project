'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { useConfirm } from '@/components/ui/confirm-dialog';
import {
  ArrowLeft, Building2, Users, UserPlus, Mail, Trash2, Key, Shield, Copy, Plus, Eye, EyeOff, ListChecks
} from 'lucide-react';
import { api } from '@/lib/api-client';
import { Organization, OrgMember, Team, ProviderSecret, User, WatchlistSettings } from '@/types';
import Link from 'next/link';
import { UserPicker } from '@/components/users/UserPicker';

export default function OrganizationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const confirm = useConfirm();
  const orgId = params.id as string;

  const [org, setOrg] = useState<Organization | null>(null);
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [memberRoleSelections, setMemberRoleSelections] = useState<Record<number, string>>({});
  const [teams, setTeams] = useState<Team[]>([]);
  const [byokKeys, setByokKeys] = useState<ProviderSecret[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const successTimerRef = useRef<number | null>(null);

  // Add member dialog
  const [showAddMember, setShowAddMember] = useState(false);
  const [newMemberUserId, setNewMemberUserId] = useState('');
  const [newMemberRole, setNewMemberRole] = useState('member');
  const [selectedMember, setSelectedMember] = useState<User | null>(null);

  // Invite dialog
  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('member');
  const [inviteLink, setInviteLink] = useState('');

  // BYOK dialog
  const [showAddByok, setShowAddByok] = useState(false);
  const [byokProvider, setByokProvider] = useState('');
  const [byokApiKey, setByokApiKey] = useState('');
  const [showByokApiKey, setShowByokApiKey] = useState(false);
  const [deletingByokProvider, setDeletingByokProvider] = useState<string | null>(null);

  // Watchlist Settings
  const [watchlistSettings, setWatchlistSettings] = useState<WatchlistSettings | null>(null);
  const [watchlistLoading, setWatchlistLoading] = useState(false);
  const [watchlistSaving, setWatchlistSaving] = useState(false);
  const [editWatchlistEnabled, setEditWatchlistEnabled] = useState(false);
  const [editWatchlistThreshold, setEditWatchlistThreshold] = useState('');
  const [editWatchlistAlertOnBreach, setEditWatchlistAlertOnBreach] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');

    const [orgData, membersData, teamsData, byokData] = await Promise.allSettled([
      api.getOrganization(orgId),
      api.getOrgMembers(orgId),
      api.getTeams(orgId),
      api.getOrgByokKeys(orgId),
    ]);

    if (orgData.status === 'fulfilled') {
      setOrg(orgData.value);
    } else {
      setError('Failed to load organization');
    }

    if (membersData.status === 'fulfilled') {
      const nextMembers = Array.isArray(membersData.value) ? membersData.value : [];
      setMembers(nextMembers);
      setMemberRoleSelections(() => {
        const nextSelections: Record<number, string> = {};
        nextMembers.forEach((member) => {
          nextSelections[member.user_id] = member.role;
        });
        return nextSelections;
      });
    }

    if (teamsData.status === 'fulfilled') {
      setTeams(Array.isArray(teamsData.value) ? teamsData.value : []);
    }

    if (byokData.status === 'fulfilled') {
      setByokKeys(Array.isArray(byokData.value) ? byokData.value : []);
    }

    // Load watchlist settings separately (may not be available)
    try {
      setWatchlistLoading(true);
      const watchData = await api.getOrgWatchlistSettings(orgId);
      const settings = watchData as WatchlistSettings;
      setWatchlistSettings(settings);
      setEditWatchlistEnabled(settings?.watchlists_enabled ?? false);
      setEditWatchlistThreshold(settings?.default_threshold?.toString() || '100');
      setEditWatchlistAlertOnBreach(settings?.alert_on_breach ?? true);
    } catch {
      // Set defaults if endpoint unavailable
      setWatchlistSettings({
        watchlists_enabled: false,
        default_threshold: 100,
        alert_on_breach: true,
      });
      setEditWatchlistEnabled(false);
      setEditWatchlistThreshold('100');
      setEditWatchlistAlertOnBreach(true);
    } finally {
      setWatchlistLoading(false);
    }

    setLoading(false);
  }, [orgId]);

  useEffect(() => {
    let isActive = true;
    void Promise.resolve().then(() => {
      if (isActive) {
        void loadData();
      }
    });
    return () => {
      isActive = false;
    };
  }, [loadData]);

  useEffect(() => {
    return () => {
      if (successTimerRef.current !== null) {
        window.clearTimeout(successTimerRef.current);
        successTimerRef.current = null;
      }
    };
  }, []);

  const handleAddMember = async () => {
    if (!newMemberUserId) {
      setError('Select a user to add');
      return;
    }
    const userId = parseInt(newMemberUserId, 10);
    if (Number.isNaN(userId) || userId <= 0) {
      setError('User ID must be a valid positive number');
      return;
    }

    try {
      setError('');
      await api.addOrgMember(orgId, {
        user_id: userId,
        role: newMemberRole,
      });
      setSuccess('Member added successfully');
      setShowAddMember(false);
      setNewMemberUserId('');
      setNewMemberRole('member');
      setSelectedMember(null);
      void loadData();
    } catch (err: unknown) {
      console.error('Failed to add member:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to add member');
    }
  };

  const handleRemoveMember = async (userId: number, username?: string) => {
    const confirmed = await confirm({
      title: 'Remove Member',
      message: `Remove ${username || `user ${userId}`} from this organization?`,
      confirmText: 'Remove',
      variant: 'danger',
      icon: 'remove-user',
    });
    if (!confirmed) return;

    try {
      setError('');
      await api.removeOrgMember(orgId, userId.toString());
      setSuccess('Member removed successfully');
      void loadData();
    } catch (err: unknown) {
      console.error('Failed to remove member:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to remove member');
    }
  };

  const handleUpdateMemberRole = async (userId: number, newRole: string) => {
    try {
      setError('');
      await api.updateOrgMemberRole(orgId, userId.toString(), { role: newRole });
      setSuccess('Member role updated');
      void loadData();
      return true;
    } catch (err: unknown) {
      console.error('Failed to update member role:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to update member role');
      return false;
    }
  };

  const handleCreateInvite = async () => {
    if (!inviteEmail) {
      setError('Email is required');
      return;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(inviteEmail)) {
      setError('Please enter a valid email address');
      return;
    }

    try {
      setError('');
      const result = await api.createOrgInvite(orgId, {
        email: inviteEmail,
        role: inviteRole,
      });
      setInviteLink(result.invite_url || result.link || 'Invite created - check email');
      setSuccess('Invite created successfully');
      setInviteEmail('');
      setInviteRole('member');
    } catch (err: unknown) {
      console.error('Failed to create invite:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to create invite');
    }
  };

  const handleAddByokKey = async () => {
    if (!byokProvider || !byokApiKey) {
      setError('Provider and API key are required');
      return;
    }

    try {
      setError('');
      await api.createOrgByokKey(orgId, {
        provider: byokProvider,
        api_key: byokApiKey,
      });
      setSuccess('Provider key added successfully');
      setShowAddByok(false);
      setByokProvider('');
      setByokApiKey('');
      setShowByokApiKey(false);
      void loadData();
    } catch (err: unknown) {
      console.error('Failed to add BYOK key:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to add provider key');
    }
  };

  const handleDeleteByokKey = async (provider: string) => {
    if (deletingByokProvider === provider) return;
    const confirmed = await confirm({
      title: 'Remove API Key',
      message: `Remove the API key for ${provider}?`,
      confirmText: 'Remove',
      variant: 'danger',
      icon: 'key',
    });
    if (!confirmed) return;

    try {
      setError('');
      setDeletingByokProvider(provider);
      await api.deleteOrgByokKey(orgId, provider);
      setSuccess('Provider key removed');
      void loadData();
    } catch (err: unknown) {
      console.error('Failed to delete BYOK key:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to delete provider key');
    } finally {
      setDeletingByokProvider((prev) => (prev === provider ? null : prev));
    }
  };

  const handleSaveWatchlistSettings = async () => {
    const threshold = parseInt(editWatchlistThreshold, 10);
    if (Number.isNaN(threshold) || threshold < 1) {
      setError('Threshold must be at least 1');
      setWatchlistSaving(false);
      return;
    }
    try {
      setWatchlistSaving(true);
      setError('');
      await api.updateOrgWatchlistSettings(orgId, {
        watchlists_enabled: editWatchlistEnabled,
        default_threshold: threshold,
        alert_on_breach: editWatchlistAlertOnBreach,
      });
      setWatchlistSettings({
        ...watchlistSettings,
        watchlists_enabled: editWatchlistEnabled,
        default_threshold: threshold,
        alert_on_breach: editWatchlistAlertOnBreach,
      });
      setSuccess('Watchlist settings saved');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to save watchlist settings';
      setError(message);
    } finally {
      setWatchlistSaving(false);
    }
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setSuccess('Copied to clipboard!');
      if (successTimerRef.current !== null) {
        window.clearTimeout(successTimerRef.current);
      }
      successTimerRef.current = window.setTimeout(() => {
        setSuccess('');
        successTimerRef.current = null;
      }, 2000);
    } catch (err: unknown) {
      console.error('Failed to copy to clipboard:', err);
      setError('Failed to copy to clipboard');
    }
  };

  if (loading) {
    return (
      <PermissionGuard variant="route" requireAuth role="admin">
        <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="text-center text-muted-foreground py-8">Loading...</div>
          </div>
        </ResponsiveLayout>
      </PermissionGuard>
    );
  }

  if (!org) {
    return (
      <PermissionGuard variant="route" requireAuth role="admin">
        <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <Alert variant="destructive">
              <AlertDescription>Organization not found</AlertDescription>
            </Alert>
            <Button onClick={() => router.push('/organizations')} className="mt-4">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Organizations
            </Button>
          </div>
        </ResponsiveLayout>
      </PermissionGuard>
    );
  }

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            {/* Header */}
            <div className="mb-8 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <Button variant="ghost" onClick={() => router.push('/organizations')}>
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <div>
                  <div className="flex items-center gap-3">
                    <Building2 className="h-8 w-8 text-primary" />
                    <h1 className="text-3xl font-bold">{org.name}</h1>
                  </div>
                  <p className="text-muted-foreground mt-1">
                    <Badge variant="secondary">{org.slug}</Badge>
                    <span className="ml-3">Created {new Date(org.created_at).toLocaleDateString()}</span>
                  </p>
                </div>
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
              {/* Members Section */}
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Users className="h-5 w-5" />
                      Members
                    </CardTitle>
                    <CardDescription>
                      {members.length} member{members.length !== 1 ? 's' : ''}
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Dialog
                      open={showInvite}
                      onOpenChange={(nextOpen) => {
                        setShowInvite(nextOpen);
                        if (!nextOpen) {
                          setInviteEmail('');
                          setInviteRole('member');
                          setInviteLink('');
                        }
                      }}
                    >
                      <DialogTrigger asChild>
                        <Button variant="outline" size="sm">
                          <Mail className="mr-2 h-4 w-4" />
                          Invite
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>Invite Member</DialogTitle>
                          <DialogDescription>
                            Send an email invitation to join this organization
                          </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                          <div className="space-y-2">
                            <Label htmlFor="inviteEmail">Email Address</Label>
                            <Input
                              id="inviteEmail"
                              type="email"
                              placeholder="user@example.com"
                              value={inviteEmail}
                              onChange={(e) => setInviteEmail(e.target.value)}
                            />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="inviteRole">Role</Label>
                            <select
                              id="inviteRole"
                              value={inviteRole}
                              onChange={(e) => setInviteRole(e.target.value)}
                              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                            >
                              <option value="member">Member</option>
                              <option value="admin">Admin</option>
                            </select>
                          </div>
                          {inviteLink && (
                            <div className="space-y-2">
                              <Label>Invite Link</Label>
                              <div className="flex gap-2">
                                <Input value={inviteLink} readOnly className="font-mono text-sm" />
                                <Button variant="outline" size="icon" onClick={() => copyToClipboard(inviteLink)}>
                                  <Copy className="h-4 w-4" />
                                </Button>
                              </div>
                            </div>
                          )}
                        </div>
                        <DialogFooter>
                          <Button variant="outline" onClick={() => setShowInvite(false)}>
                            Close
                          </Button>
                          <Button onClick={handleCreateInvite}>Send Invite</Button>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>

                    <Dialog open={showAddMember} onOpenChange={setShowAddMember}>
                      <DialogTrigger asChild>
                        <Button size="sm">
                          <UserPlus className="mr-2 h-4 w-4" />
                          Add
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>Add Member</DialogTitle>
                          <DialogDescription>
                            Add an existing user to this organization
                          </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                          <UserPicker
                            label="User"
                            value={selectedMember}
                            helperText="Search by username or email to add a member."
                            onSelect={(user) => {
                              setSelectedMember(user);
                              setNewMemberUserId(String(user.id));
                              setError('');
                            }}
                            onClear={() => {
                              setSelectedMember(null);
                              setNewMemberUserId('');
                            }}
                          />
                          <div className="space-y-2">
                            <Label htmlFor="memberRole">Role</Label>
                            <select
                              id="memberRole"
                              value={newMemberRole}
                              onChange={(e) => setNewMemberRole(e.target.value)}
                              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                            >
                              <option value="member">Member</option>
                              <option value="admin">Admin</option>
                              <option value="owner">Owner</option>
                            </select>
                          </div>
                        </div>
                        <DialogFooter>
                          <Button variant="outline" onClick={() => setShowAddMember(false)}>Cancel</Button>
                          <Button onClick={handleAddMember}>Add Member</Button>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                  </div>
                </CardHeader>
                <CardContent>
                  {members.length === 0 ? (
                    <div className="text-center text-muted-foreground py-8">
                      No members yet. Add or invite members to get started.
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>User</TableHead>
                          <TableHead>Role</TableHead>
                          <TableHead>Joined</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {members.map((member) => (
                          <TableRow key={member.user_id}>
                            <TableCell>
                              <div>
                                <div className="font-medium">{member.user?.username || `User ${member.user_id}`}</div>
                                {member.user?.email && (
                                  <div className="text-xs text-muted-foreground">{member.user.email}</div>
                                )}
                              </div>
                            </TableCell>
                            <TableCell>
                              <select
                                value={memberRoleSelections[member.user_id] ?? member.role}
                                onChange={async (event) => {
                                  const newRole = event.target.value;
                                  const previousRole = memberRoleSelections[member.user_id] ?? member.role;
                                  setMemberRoleSelections((prev) => ({
                                    ...prev,
                                    [member.user_id]: newRole,
                                  }));
                                  const displayName = member.user?.username || `User ${member.user_id}`;
                                  const confirmed = await confirm({
                                    title: 'Change Role',
                                    message: `Change role for ${displayName} to ${newRole}?`,
                                    confirmText: 'Change Role',
                                    variant: 'default',
                                  });
                                  if (confirmed) {
                                    const updated = await handleUpdateMemberRole(member.user_id, newRole);
                                    if (!updated) {
                                      setMemberRoleSelections((prev) => ({
                                        ...prev,
                                        [member.user_id]: previousRole,
                                      }));
                                    }
                                  } else {
                                    setMemberRoleSelections((prev) => ({
                                      ...prev,
                                      [member.user_id]: previousRole,
                                    }));
                                  }
                                }}
                                className="h-8 rounded-md border border-input bg-background px-2 text-sm"
                              >
                                <option value="member">Member</option>
                                <option value="admin">Admin</option>
                                <option value="owner">Owner</option>
                              </select>
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {new Date(member.joined_at).toLocaleDateString()}
                            </TableCell>
                            <TableCell className="text-right">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleRemoveMember(member.user_id, member.user?.username)}
                              >
                                <Trash2 className="h-4 w-4 text-red-500" />
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>

              {/* Teams Section */}
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Shield className="h-5 w-5" />
                      Teams
                    </CardTitle>
                    <CardDescription>
                      {teams.length} team{teams.length !== 1 ? 's' : ''}
                    </CardDescription>
                  </div>
                  <Link href={`/teams?org=${orgId}`}>
                    <Button size="sm">
                      <Plus className="mr-2 h-4 w-4" />
                      New Team
                    </Button>
                  </Link>
                </CardHeader>
                <CardContent>
                  {teams.length === 0 ? (
                    <div className="text-center text-muted-foreground py-8">
                      No teams in this organization yet.
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Name</TableHead>
                          <TableHead>Description</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {teams.map((team) => (
                          <TableRow key={team.id}>
                            <TableCell className="font-medium">{team.name}</TableCell>
                            <TableCell className="text-muted-foreground text-sm">
                              {team.description || '-'}
                            </TableCell>
                            <TableCell className="text-right">
                              <Link href={`/teams/${team.id}`}>
                                <Button variant="ghost" size="sm">
                                  <Eye className="h-4 w-4" />
                                </Button>
                              </Link>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>

              {/* BYOK Provider Keys Section */}
              <Card className="lg:col-span-2">
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Key className="h-5 w-5" />
                      Provider API Keys (BYOK)
                    </CardTitle>
                    <CardDescription>
                      Organization-level API keys for LLM providers. These keys are shared by all members.
                    </CardDescription>
                  </div>
                    <Dialog
                      open={showAddByok}
                      onOpenChange={(nextOpen) => {
                        setShowAddByok(nextOpen);
                        if (!nextOpen) {
                          setShowByokApiKey(false);
                          setByokProvider('');
                          setByokApiKey('');
                        }
                      }}
                    >
                    <DialogTrigger asChild>
                      <Button size="sm">
                        <Plus className="mr-2 h-4 w-4" />
                        Add Key
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Add Provider API Key</DialogTitle>
                        <DialogDescription>
                          Add an API key for an LLM provider. This key will be used for all organization members.
                        </DialogDescription>
                      </DialogHeader>
                      <div className="space-y-4 py-4">
                        <div className="space-y-2">
                          <Label htmlFor="byokProvider">Provider</Label>
                          <select
                            id="byokProvider"
                            value={byokProvider}
                            onChange={(e) => setByokProvider(e.target.value)}
                            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                          >
                            <option value="">Select provider...</option>
                            <option value="openai">OpenAI</option>
                            <option value="anthropic">Anthropic</option>
                            <option value="google">Google AI</option>
                            <option value="cohere">Cohere</option>
                            <option value="groq">Groq</option>
                            <option value="mistral">Mistral AI</option>
                            <option value="deepseek">DeepSeek</option>
                            <option value="openrouter">OpenRouter</option>
                          </select>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="byokApiKey">API Key</Label>
                          <div className="relative">
                            <Input
                              id="byokApiKey"
                              type={showByokApiKey ? 'text' : 'password'}
                              placeholder="sk-..."
                              value={byokApiKey}
                              onChange={(e) => setByokApiKey(e.target.value)}
                              className="pr-10"
                            />
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              onClick={() => setShowByokApiKey((prev) => !prev)}
                              className="absolute right-1 top-1/2 h-8 w-8 -translate-y-1/2"
                              title={showByokApiKey ? 'Hide API key' : 'Show API key'}
                              aria-label={showByokApiKey ? 'Hide API key' : 'Show API key'}
                            >
                              {showByokApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                            </Button>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            This key will be encrypted and stored securely.
                          </p>
                        </div>
                      </div>
                      <DialogFooter>
                        <Button variant="outline" onClick={() => setShowAddByok(false)}>Cancel</Button>
                        <Button onClick={handleAddByokKey}>Add Key</Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                </CardHeader>
                <CardContent>
                  {byokKeys.length === 0 ? (
                    <div className="text-center text-muted-foreground py-8">
                      No provider keys configured. Add keys to allow members to use their own API accounts.
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Provider</TableHead>
                          <TableHead>Added</TableHead>
                          <TableHead>Last Updated</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {byokKeys.map((key) => {
                          const isDeleting = deletingByokProvider === key.provider;
                          return (
                          <TableRow key={key.provider}>
                            <TableCell>
                              <Badge variant="outline" className="capitalize">
                                {key.provider}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {new Date(key.created_at).toLocaleDateString()}
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {new Date(key.updated_at).toLocaleDateString()}
                            </TableCell>
                            <TableCell className="text-right">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDeleteByokKey(key.provider)}
                                disabled={isDeleting}
                              >
                                <Trash2 className="h-4 w-4 text-red-500" />
                              </Button>
                            </TableCell>
                          </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>

              {/* Watchlist Settings */}
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <ListChecks className="h-5 w-5" />
                    Watchlist Settings
                  </CardTitle>
                  <CardDescription>
                    Configure usage watchlists and alerts for this organization
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {watchlistLoading ? (
                    <div className="text-center text-muted-foreground py-4">Loading...</div>
                  ) : (
                    <div className="space-y-4">
                      <div className="grid gap-4 sm:grid-cols-3">
                        <div className="flex items-center justify-between p-3 border rounded-lg">
                          <div>
                            <Label>Enable Watchlists</Label>
                            <p className="text-xs text-muted-foreground">Track usage and spending</p>
                          </div>
                          <Checkbox
                            checked={editWatchlistEnabled}
                            onCheckedChange={setEditWatchlistEnabled}
                          />
                        </div>
                        <div className="space-y-1 p-3 border rounded-lg">
                          <Label htmlFor="watchlist-threshold">Default Threshold</Label>
                          <Input
                            id="watchlist-threshold"
                            type="number"
                            min="1"
                            value={editWatchlistThreshold}
                            onChange={(e) => setEditWatchlistThreshold(e.target.value)}
                            disabled={!editWatchlistEnabled}
                          />
                          <p className="text-xs text-muted-foreground">Usage limit before alerts</p>
                        </div>
                        <div className="flex items-center justify-between p-3 border rounded-lg">
                          <div>
                            <Label>Alert on Breach</Label>
                            <p className="text-xs text-muted-foreground">Send notifications when exceeded</p>
                          </div>
                          <Checkbox
                            checked={editWatchlistAlertOnBreach}
                            onCheckedChange={setEditWatchlistAlertOnBreach}
                            disabled={!editWatchlistEnabled}
                          />
                        </div>
                      </div>
                      <Button onClick={handleSaveWatchlistSettings} disabled={watchlistSaving}>
                        {watchlistSaving ? 'Saving...' : 'Save Settings'}
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
