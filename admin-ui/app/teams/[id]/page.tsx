'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { ArrowLeft, Users, UserPlus, Trash2, Shield, Building2 } from 'lucide-react';
import { api } from '@/lib/api-client';
import { Team, TeamMember, Organization } from '@/types';
import Link from 'next/link';

export default function TeamDetailPage() {
  const params = useParams();
  const router = useRouter();
  const confirm = useConfirm();
  const teamId = params.id as string;

  const [team, setTeam] = useState<Team | null>(null);
  const [org, setOrg] = useState<Organization | null>(null);
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Add member dialog
  const [showAddMember, setShowAddMember] = useState(false);
  const [newMemberUserId, setNewMemberUserId] = useState('');
  const [newMemberRole, setNewMemberRole] = useState('member');

  useEffect(() => {
    loadData();
  }, [teamId]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError('');

      // First load team members
      const membersData = await api.getTeamMembers(teamId);
      setMembers(Array.isArray(membersData) ? membersData : []);

      // Try to get team info from the members response or from a teams list
      // Since we don't have a direct getTeam endpoint, we'll construct basic info
      // In a real implementation, you'd have a dedicated endpoint
      if (membersData && membersData.team) {
        setTeam(membersData.team);
      }
    } catch (err: any) {
      console.error('Failed to load team data:', err);
      setError(err.message || 'Failed to load team data');
    } finally {
      setLoading(false);
    }
  };

  const handleAddMember = async () => {
    if (!newMemberUserId) {
      setError('User ID is required');
      return;
    }

    try {
      setError('');
      const userId = parseInt(newMemberUserId, 10);
      if (Number.isNaN(userId)) {
        setError('Please enter a valid numeric User ID');
        return;
      }
      await api.addTeamMember(teamId, {
        user_id: userId,
        role: newMemberRole,
      });
      setSuccess('Member added successfully');
      setShowAddMember(false);
      setNewMemberUserId('');
      setNewMemberRole('member');
      loadData();
    } catch (err: any) {
      console.error('Failed to add member:', err);
      setError(err.message || 'Failed to add member');
    }
  };

  const handleRemoveMember = async (userId: number, username?: string) => {
    const confirmed = await confirm({
      title: 'Remove Team Member',
      message: `Remove ${username || `user ${userId}`} from this team?`,
      confirmText: 'Remove',
      variant: 'danger',
      icon: 'remove-user',
    });
    if (!confirmed) return;

    try {
      setError('');
      await api.removeTeamMember(teamId, userId.toString());
      setSuccess('Member removed successfully');
      loadData();
    } catch (err: any) {
      console.error('Failed to remove member:', err);
      setError(err.message || 'Failed to remove member');
    }
  };

  if (loading) {
    return (
      <ProtectedRoute>
        <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="text-center text-muted-foreground py-8">Loading...</div>
          </div>
        </ResponsiveLayout>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            {/* Header */}
            <div className="mb-8 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <Button variant="ghost" onClick={() => router.push('/teams')}>
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <div>
                  <div className="flex items-center gap-3">
                    <Shield className="h-8 w-8 text-primary" />
                    <h1 className="text-3xl font-bold">{team?.name || `Team ${teamId}`}</h1>
                  </div>
                  {team?.description && (
                    <p className="text-muted-foreground mt-1">{team.description}</p>
                  )}
                  {team?.org_id && (
                    <Link href={`/organizations/${team.org_id}`} className="text-sm text-primary hover:underline mt-1 inline-flex items-center gap-1">
                      <Building2 className="h-3 w-3" />
                      View Organization
                    </Link>
                  )}
                </div>
              </div>
              <Dialog open={showAddMember} onOpenChange={setShowAddMember}>
                <DialogTrigger asChild>
                  <Button>
                    <UserPlus className="mr-2 h-4 w-4" />
                    Add Member
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Add Team Member</DialogTitle>
                    <DialogDescription>
                      Add an existing user to this team
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    <div className="space-y-2">
                      <Label htmlFor="userId">User ID</Label>
                      <Input
                        id="userId"
                        type="number"
                        placeholder="Enter user ID"
                        value={newMemberUserId}
                        onChange={(e) => setNewMemberUserId(e.target.value)}
                      />
                      <p className="text-xs text-muted-foreground">
                        The user must be a member of the parent organization
                      </p>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="memberRole">Role</Label>
                      <select
                        id="memberRole"
                        value={newMemberRole}
                        onChange={(e) => setNewMemberRole(e.target.value)}
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      >
                        <option value="member">Member</option>
                        <option value="lead">Lead</option>
                        <option value="admin">Admin</option>
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

            {/* Team Info */}
            <Card className="mb-6">
              <CardContent className="pt-6">
                <div className="flex items-start gap-4">
                  <Users className="h-8 w-8 text-primary mt-1" />
                  <div>
                    <h3 className="font-semibold">Team Management</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Teams are groups within an organization that can have their own members and permissions.
                      Add users from the parent organization to this team to collaborate on projects.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Members Section */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-5 w-5" />
                  Team Members
                </CardTitle>
                <CardDescription>
                  {members.length} member{members.length !== 1 ? 's' : ''} in this team
                </CardDescription>
              </CardHeader>
              <CardContent>
                {members.length === 0 ? (
                  <div className="text-center text-muted-foreground py-8">
                    No members in this team yet. Add members to get started.
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
                              <div className="font-medium">
                                {member.user?.username || `User ${member.user_id}`}
                              </div>
                              {member.user?.email && (
                                <div className="text-xs text-muted-foreground">{member.user.email}</div>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge variant={
                              member.role === 'admin' ? 'default' :
                              member.role === 'lead' ? 'secondary' : 'outline'
                            }>
                              {member.role}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {new Date(member.joined_at).toLocaleDateString()}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex justify-end gap-1">
                              <Link href={`/users/${member.user_id}`}>
                                <Button variant="ghost" size="sm" title="View user">
                                  <Users className="h-4 w-4" />
                                </Button>
                              </Link>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleRemoveMember(member.user_id, member.user?.username)}
                                title="Remove from team"
                              >
                                <Trash2 className="h-4 w-4 text-red-500" />
                              </Button>
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
    </ProtectedRoute>
  );
}
