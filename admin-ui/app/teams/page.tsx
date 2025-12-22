'use client';

import { useCallback, useEffect, useState } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useToast } from '@/components/ui/toast';
import { Plus, Users, Building2 } from 'lucide-react';
import { Team, Organization } from '@/types';
import { api } from '@/lib/api-client';
import Link from 'next/link';

export default function TeamsPage() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrgId, setSelectedOrgId] = useState<string>('');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const { warning, error: showError } = useToast();
  const [formData, setFormData] = useState({
    name: '',
    description: '',
  });

  const loadOrganizations = useCallback(async () => {
    try {
      const data = await api.getOrganizations();
      const orgs = Array.isArray(data) ? data : [];
      setOrganizations(orgs);
      if (orgs.length > 0) {
        setSelectedOrgId((current) => current || String(orgs[0].id));
      }
    } catch (error) {
      console.error('Failed to load organizations:', error);
      setOrganizations([]);
    }
  }, []);

  const loadTeams = useCallback(async (orgId: string) => {
    try {
      setLoading(true);
      const data = await api.getTeams(orgId);
      setTeams(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Failed to load teams:', error);
      setTeams([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadOrganizations();
  }, [loadOrganizations]);

  useEffect(() => {
    if (selectedOrgId) {
      loadTeams(selectedOrgId);
    } else {
      setTeams([]);
    }
  }, [loadTeams, selectedOrgId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOrgId) {
      warning('Select organization', 'Please select an organization first.');
      return;
    }
    try {
      await api.createTeam(selectedOrgId, formData);
      setShowCreateForm(false);
      setFormData({ name: '', description: '' });
      loadTeams(selectedOrgId);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Please try again.';
      console.error('Failed to create team:', error);
      showError('Failed to create team', message);
    }
  };

  return (
    <ProtectedRoute>
      <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="mb-8 flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold">Teams</h1>
                <p className="text-muted-foreground">Manage teams within organizations</p>
              </div>
              <Button
                onClick={() => setShowCreateForm(!showCreateForm)}
                disabled={!selectedOrgId}
              >
                <Plus className="mr-2 h-4 w-4" />
                New Team
              </Button>
            </div>

            {/* Organization Selector */}
            <Card className="mb-6">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Building2 className="h-5 w-5" />
                  Select Organization
                </CardTitle>
              </CardHeader>
              <CardContent>
                {organizations.length === 0 ? (
                  <p className="text-muted-foreground">
                    No organizations found.{' '}
                    <Link href="/organizations" className="text-primary underline">
                      Create one first
                    </Link>
                  </p>
                ) : (
                  <Select
                    value={selectedOrgId}
                    onChange={(e) => setSelectedOrgId(e.target.value)}
                    className="max-w-md"
                  >
                    {organizations.map((org) => (
                      <option key={org.id} value={org.id}>
                        {org.name} ({org.slug})
                      </option>
                    ))}
                  </Select>
                )}
              </CardContent>
            </Card>

            {showCreateForm && selectedOrgId && (
              <Card className="mb-6">
                <CardHeader>
                  <CardTitle>Create Team</CardTitle>
                  <CardDescription>Add a new team to the selected organization</CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="name">Team Name *</Label>
                        <Input
                          id="name"
                          placeholder="e.g., Engineering"
                          value={formData.name}
                          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                          required
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="description">Description</Label>
                        <Input
                          id="description"
                          placeholder="e.g., Core engineering team"
                          value={formData.description}
                          onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                        />
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <Button type="submit">Create Team</Button>
                      <Button type="button" variant="outline" onClick={() => setShowCreateForm(false)}>
                        Cancel
                      </Button>
                    </div>
                  </form>
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader>
                <CardTitle>Teams List</CardTitle>
                <CardDescription>
                  {selectedOrgId
                    ? `Teams in ${organizations.find(o => String(o.id) === selectedOrgId)?.name || 'selected organization'}`
                    : 'Select an organization to view teams'}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {!selectedOrgId ? (
                  <div className="text-center text-muted-foreground py-8">
                    Select an organization above to view its teams.
                  </div>
                ) : loading ? (
                  <div className="text-center text-muted-foreground py-8">Loading...</div>
                ) : teams.length === 0 ? (
                  <div className="text-center text-muted-foreground py-8">
                    No teams found in this organization. Create one to get started.
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>ID</TableHead>
                        <TableHead>Name</TableHead>
                        <TableHead>Description</TableHead>
                        <TableHead>Created</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {teams.map((team) => (
                        <TableRow key={team.id}>
                          <TableCell className="font-mono text-sm">{team.id}</TableCell>
                          <TableCell className="font-medium">{team.name}</TableCell>
                          <TableCell className="text-muted-foreground">
                            {team.description || '-'}
                          </TableCell>
                          <TableCell>{new Date(team.created_at).toLocaleDateString()}</TableCell>
                          <TableCell className="text-right">
                            <Link href={`/teams/${team.id}`}>
                              <Button variant="outline" size="sm">
                                <Users className="mr-2 h-4 w-4" />
                                Manage
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
          </div>
      </ResponsiveLayout>
    </ProtectedRoute>
  );
}
