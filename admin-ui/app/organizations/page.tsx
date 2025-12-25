'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useForm, FormProvider } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Pagination } from '@/components/ui/pagination';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Select } from '@/components/ui/select';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { useToast } from '@/components/ui/toast';
import { Form, FormField } from '@/components/ui/form';
import { Plus, Eye, Search, BookmarkPlus, BookmarkX } from 'lucide-react';
import { Organization } from '@/types';
import { api } from '@/lib/api-client';
import { TableSkeleton } from '@/components/ui/skeleton';
import Link from 'next/link';
import { useUrlPagination, useUrlState } from '@/lib/use-url-state';

type SavedOrgView = {
  id: string;
  name: string;
  query: string;
};

const SAVED_VIEWS_STORAGE_KEY = 'admin_org_saved_views';

const organizationSchema = z.object({
  name: z.string().min(1, 'Organization name is required'),
  slug: z.string()
    .min(1, 'Slug is required')
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, 'Slug must be lowercase letters, numbers, and hyphens'),
});

type OrganizationFormData = z.infer<typeof organizationSchema>;

export default function OrganizationsPage() {
  const confirm = useConfirm();
  const { success, error: showError } = useToast();
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [createError, setCreateError] = useState('');
  const [totalItems, setTotalItems] = useState(0);
  const [slugTouched, setSlugTouched] = useState(false);
  const [searchQuery, setSearchQuery] = useUrlState<string>('q', { defaultValue: '' });
  const [savedViews, setSavedViews] = useState<SavedOrgView[]>([]);
  const activeViewId = useMemo(() => {
    const match = savedViews.find((view) => view.query === (searchQuery || ''));
    return match ? match.id : '';
  }, [savedViews, searchQuery]);
  const [showSaveViewDialog, setShowSaveViewDialog] = useState(false);
  const [saveViewName, setSaveViewName] = useState('');
  const [saveViewError, setSaveViewError] = useState('');
  const organizationForm = useForm<OrganizationFormData>({
    resolver: zodResolver(organizationSchema),
    defaultValues: {
      name: '',
      slug: '',
    },
  });
  const {
    page: currentPage,
    pageSize,
    setPage: setCurrentPage,
    setPageSize,
    resetPagination,
  } = useUrlPagination();

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const stored = window.localStorage.getItem(SAVED_VIEWS_STORAGE_KEY);
      if (!stored) return;
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed)) {
        setSavedViews(parsed as SavedOrgView[]);
      }
    } catch (err) {
      console.warn('Failed to load saved organization views:', err);
    }
  }, []);

  const persistSavedViews = useCallback((views: SavedOrgView[]) => {
    setSavedViews(views);
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(SAVED_VIEWS_STORAGE_KEY, JSON.stringify(views));
    } catch (err) {
      console.warn('Failed to persist saved organization views:', err);
    }
  }, []);

  const loadOrganizations = useCallback(async () => {
    try {
      setLoading(true);
      setLoadError('');
      const params: Record<string, string> = {
        limit: String(pageSize),
        offset: String((currentPage - 1) * pageSize),
      };
      if (searchQuery) {
        params.q = searchQuery;
      }
      const data = await api.getOrganizations(params);
      if (data && typeof data === 'object' && 'items' in data) {
        const items = Array.isArray((data as { items?: Organization[] }).items)
          ? (data as { items: Organization[] }).items
          : [];
        const total = (data as { total?: number }).total;
        setOrganizations(items);
        setTotalItems(typeof total === 'number' ? total : items.length);
        return;
      }
      if (Array.isArray(data)) {
        setOrganizations(data);
        setTotalItems(data.length);
        return;
      }
      setOrganizations([]);
      setTotalItems(0);
    } catch (error: unknown) {
      setOrganizations([]);
      setTotalItems(0);
      setLoadError(
        error instanceof Error && error.message
          ? error.message
          : 'Failed to load organizations'
      );
    } finally {
      setLoading(false);
    }
  }, [currentPage, pageSize, searchQuery]);

  useEffect(() => {
    loadOrganizations();
  }, [loadOrganizations]);

  useEffect(() => {
    if (!showCreateForm) {
      organizationForm.reset();
      setCreateError('');
      setSlugTouched(false);
    }
  }, [organizationForm, showCreateForm]);

  const handleSubmit = organizationForm.handleSubmit(async (data) => {
    setCreateError('');
    try {
      await api.createOrganization(data);
      setShowCreateForm(false);
      organizationForm.reset();
      setSlugTouched(false);
      loadOrganizations();
    } catch (error: unknown) {
      console.error('Failed to create organization:', error);
      const message =
        error instanceof Error && error.message
          ? error.message
          : 'Failed to create organization';
      setCreateError(message);
      showError('Create organization failed', message);
    }
  });

  const handleNameChange = (value: string) => {
    if (slugTouched) return;
    const slug = value
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '');
    organizationForm.setValue('slug', slug, { shouldDirty: true, shouldValidate: true });
  };

  const nameField = organizationForm.register('name');
  const slugField = organizationForm.register('slug');

  const handleSearchChange = (value: string) => {
    setSearchQuery(value || undefined);
    resetPagination();
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
    const newView: SavedOrgView = {
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

  const totalPages = Math.ceil(totalItems / pageSize);
  const paginatedOrganizations = organizations;

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
                  <FormProvider {...organizationForm}>
                    <Form onSubmit={handleSubmit}>
                      {createError && (
                        <Alert variant="destructive">
                          <AlertDescription>{createError}</AlertDescription>
                        </Alert>
                      )}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <FormField<OrganizationFormData> name="name" label="Organization Name" required>
                          <Input
                            id="name"
                            placeholder="e.g., Acme Corporation"
                            {...nameField}
                            onChange={(e) => {
                              nameField.onChange(e);
                              handleNameChange(e.target.value);
                            }}
                          />
                        </FormField>

                        <FormField<OrganizationFormData> name="slug" label="Slug" required>
                          <Input
                            id="slug"
                            placeholder="e.g., acme-corp"
                            {...slugField}
                            onChange={(e) => {
                              slugField.onChange(e);
                              setSlugTouched(true);
                            }}
                          />
                          <p className="text-xs text-muted-foreground">
                            Unique URL-friendly identifier
                          </p>
                        </FormField>
                      </div>

                      <div className="flex gap-2">
                        <Button type="submit">Create Organization</Button>
                        <Button type="button" variant="outline" onClick={() => setShowCreateForm(false)}>
                          Cancel
                        </Button>
                      </div>
                    </Form>
                  </FormProvider>
                </CardContent>
              </Card>
            )}

            {loadError && (
              <Alert variant="destructive" className="mb-6">
                <AlertDescription>{loadError}</AlertDescription>
              </Alert>
            )}

            {/* Search */}
            <Card className="mb-6">
              <CardContent className="pt-6">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="relative max-w-md w-full">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search organizations by name or slug..."
                      value={searchQuery || ''}
                      onChange={(e) => handleSearchChange(e.target.value)}
                      className="pl-10"
                    />
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Select
                      value={activeViewId}
                      onChange={(event) => handleApplySavedView(event.target.value)}
                      className="min-w-[200px]"
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
                          <Label htmlFor="saved-org-view-name">View name</Label>
                          <Input
                            id="saved-org-view-name"
                            value={saveViewName}
                            onChange={(event) => setSaveViewName(event.target.value)}
                            placeholder="e.g., Active orgs"
                          />
                          <p className="text-xs text-muted-foreground">
                            Current search: {searchQuery || 'All organizations'}
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
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Organizations List</CardTitle>
                <CardDescription>
                  {totalItems} organization{totalItems !== 1 ? 's' : ''} found
                </CardDescription>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="py-4">
                    <TableSkeleton rows={3} columns={5} />
                  </div>
                ) : organizations.length === 0 ? (
                  <div className="text-center text-muted-foreground py-8">
                    {searchQuery ? 'No organizations match your search' : 'No organizations found. Create one to get started.'}
                  </div>
                ) : (
                  <>
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
                        {paginatedOrganizations.map((org) => (
                          <TableRow key={org.id}>
                            <TableCell className="font-mono text-sm">{org.id}</TableCell>
                            <TableCell className="font-medium">{org.name}</TableCell>
                            <TableCell>
                              <Badge variant="secondary">{org.slug}</Badge>
                            </TableCell>
                            <TableCell>{new Date(org.created_at).toLocaleDateString()}</TableCell>
                            <TableCell className="text-right">
                              <Link href={`/organizations/${org.id}/analytics`}>
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
    </ProtectedRoute>
  );
}
