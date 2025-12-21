'use client';

import { useEffect, useState } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Plus, Users, Eye } from 'lucide-react';
import { Organization } from '@/types';
import { api } from '@/lib/api-client';
import { TableSkeleton } from '@/components/ui/skeleton';
import Link from 'next/link';

export default function OrganizationsPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [formData, setFormData] = useState({
    name: '',
    slug: '',
  });

  useEffect(() => {
    loadOrganizations();
  }, []);

  const loadOrganizations = async () => {
    try {
      setLoading(true);
      const data = await api.getOrganizations();
      setOrganizations(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Failed to load organizations:', error);
      setOrganizations([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createOrganization(formData);
      setShowCreateForm(false);
      setFormData({ name: '', slug: '' });
      loadOrganizations();
    } catch (error: any) {
      console.error('Failed to create organization:', error);
      alert(`Failed to create organization: ${error.message}`);
    }
  };

  // Auto-generate slug from name
  const handleNameChange = (name: string) => {
    const slug = name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '');
    setFormData({ name, slug });
  };

  return (
    <ProtectedRoute>
      <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="mb-8 flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold">Organizations</h1>
                <p className="text-muted-foreground">Manage organizations and their members</p>
              </div>
              <Button onClick={() => setShowCreateForm(!showCreateForm)}>
                <Plus className="mr-2 h-4 w-4" />
                New Organization
              </Button>
            </div>

            {showCreateForm && (
              <Card className="mb-6">
                <CardHeader>
                  <CardTitle>Create Organization</CardTitle>
                  <CardDescription>Add a new organization to the system</CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="name">Organization Name *</Label>
                        <Input
                          id="name"
                          placeholder="e.g., Acme Corporation"
                          value={formData.name}
                          onChange={(e) => handleNameChange(e.target.value)}
                          required
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="slug">Slug *</Label>
                        <Input
                          id="slug"
                          placeholder="e.g., acme-corp"
                          value={formData.slug}
                          onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
                          required
                        />
                        <p className="text-xs text-muted-foreground">
                          Unique URL-friendly identifier
                        </p>
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <Button type="submit">Create Organization</Button>
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
                <CardTitle>Organizations List</CardTitle>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="py-4">
                    <TableSkeleton rows={3} columns={5} />
                  </div>
                ) : organizations.length === 0 ? (
                  <div className="text-center text-muted-foreground py-8">
                    No organizations found. Create one to get started.
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>ID</TableHead>
                        <TableHead>Name</TableHead>
                        <TableHead>Slug</TableHead>
                        <TableHead>Created</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {organizations.map((org) => (
                        <TableRow key={org.id}>
                          <TableCell className="font-mono text-sm">{org.id}</TableCell>
                          <TableCell className="font-medium">{org.name}</TableCell>
                          <TableCell>
                            <Badge variant="secondary">{org.slug}</Badge>
                          </TableCell>
                          <TableCell>{new Date(org.created_at).toLocaleDateString()}</TableCell>
                          <TableCell className="text-right">
                            <Link href={`/organizations/${org.id}`}>
                              <Button variant="outline" size="sm">
                                <Eye className="mr-2 h-4 w-4" />
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
