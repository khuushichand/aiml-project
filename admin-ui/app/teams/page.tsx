'use client';

import { useCallback, useEffect, useState } from 'react';
import { useForm, FormProvider } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useToast } from '@/components/ui/toast';
import { Pagination } from '@/components/ui/pagination';
import { TableSkeleton } from '@/components/ui/skeleton';
import { Form, FormInput } from '@/components/ui/form';
import { Plus, Users, Building2, Search } from 'lucide-react';
import { Team, Organization } from '@/types';
import { api } from '@/lib/api-client';
import Link from 'next/link';
import { useUrlPagination, useUrlState } from '@/lib/use-url-state';

const teamSchema = z.object({
  name: z.string().min(1, 'Team name is required'),
  description: z.string().optional(),
});

type TeamFormData = z.infer<typeof teamSchema>;

export default function TeamsPage() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrgId, setSelectedOrgId] = useUrlState<string>('org');
  const [searchQuery, setSearchQuery] = useUrlState<string>('q', { defaultValue: '' });
  const {
    page: currentPage,
    pageSize,
    setPage: setCurrentPage,
    setPageSize,
    resetPagination,
  } = useUrlPagination();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const { warning, error: showError } = useToast();
  const teamForm = useForm<TeamFormData>({
    resolver: zodResolver(teamSchema),
    defaultValues: {
      name: '',
      description: '',
    },
  });

  const loadOrganizations = useCallback(async () => {
    try {
      const data = await api.getOrganizations();
      const orgs = Array.isArray(data) ? data : [];
      setOrganizations(orgs);
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
    if (!selectedOrgId && organizations.length > 0) {
      setSelectedOrgId(String(organizations[0].id));
    }
  }, [organizations, selectedOrgId, setSelectedOrgId]);

  useEffect(() => {
    if (!showCreateForm) {
      teamForm.reset();
    }
  }, [showCreateForm, teamForm]);

  useEffect(() => {
    if (selectedOrgId) {
      loadTeams(selectedOrgId);
    } else {
      setTeams([]);
    }
  }, [loadTeams, selectedOrgId]);

  const handleSubmit = teamForm.handleSubmit(async (data) => {
    if (!selectedOrgId) {
      warning('Select organization', 'Please select an organization first.');
      return;
    }
    try {
      await api.createTeam(selectedOrgId, {
        name: data.name,
        description: data.description?.trim() || undefined,
      });
      setShowCreateForm(false);
      teamForm.reset();
      loadTeams(selectedOrgId);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Please try again.';
      console.error('Failed to create team:', error);
      showError('Failed to create team', message);
    }
  });

  const handleSearchChange = (value: string) => {
    setSearchQuery(value || undefined);
    resetPagination();
  };

  const handleOrgChange = (value: string) => {
    setSelectedOrgId(value || undefined);
    resetPagination();
  };

  const filteredTeams = teams.filter((team) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      team.name?.toLowerCase().includes(query) ||
      team.description?.toLowerCase().includes(query)
    );
  });

  const totalItems = filteredTeams.length;
  const totalPages = Math.ceil(totalItems / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const paginatedTeams = filteredTeams.slice(startIndex, startIndex + pageSize);

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
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
                    value={selectedOrgId || ''}
                    onChange={(e) => handleOrgChange(e.target.value)}
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
                  <FormProvider {...teamForm}>
                    <Form onSubmit={handleSubmit}>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <FormInput<TeamFormData>
                          name="name"
                          label="Team Name"
                          placeholder="e.g., Engineering"
                          required
                        />
                        <FormInput<TeamFormData>
                          name="description"
                          label="Description"
                          placeholder="e.g., Core engineering team"
                        />
                      </div>

                      <div className="flex gap-2">
                        <Button type="submit">Create Team</Button>
                        <Button type="button" variant="outline" onClick={() => setShowCreateForm(false)}>
                          Cancel
                        </Button>
                      </div>
                    </Form>
                  </FormProvider>
                </CardContent>
              </Card>
            )}

            {/* Search */}
            <Card className="mb-6">
              <CardContent className="pt-6">
                <div className="relative max-w-md">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search teams by name or description..."
                    value={searchQuery || ''}
                    onChange={(e) => handleSearchChange(e.target.value)}
                    className="pl-10"
                    disabled={!selectedOrgId}
                  />
                </div>
              </CardContent>
            </Card>

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
                  <div className="py-4">
                    <TableSkeleton rows={4} columns={5} />
                  </div>
                ) : filteredTeams.length === 0 ? (
                  <div className="text-center text-muted-foreground py-8">
                    {searchQuery ? 'No teams match your search.' : 'No teams found in this organization. Create one to get started.'}
                  </div>
                ) : (
                  <>
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
                        {paginatedTeams.map((team) => (
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

                    <Pagination
                      currentPage={currentPage}
                      totalPages={totalPages}
                      totalItems={totalItems}
                      pageSize={pageSize}
                      onPageChange={setCurrentPage}
                      onPageSizeChange={(size) => {
                        setPageSize(size);
                        resetPagination();
                      }}
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
