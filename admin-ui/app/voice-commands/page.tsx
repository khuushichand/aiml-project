'use client';

import { useCallback, useEffect, useState, Suspense } from 'react';
import { useForm, FormProvider } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { EmptyState } from '@/components/ui/empty-state';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Pagination } from '@/components/ui/pagination';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Form, FormInput, FormSelect, FormTextarea } from '@/components/ui/form';
import { Eye, Mic, MicOff, Search, Plus, Trash2, BarChart2 } from 'lucide-react';
import { AccessibleIconButton } from '@/components/ui/accessible-icon-button';
import { api } from '@/lib/api-client';
import { parseVoiceCommandInputs } from '@/lib/voice-commands';
import type { VoiceCommand, VoiceActionType, VoiceAnalyticsSummary } from '@/types';
import { Skeleton, TableSkeleton } from '@/components/ui/skeleton';
import { useUrlState, useUrlPagination } from '@/lib/use-url-state';
import { usePrivilegedActionDialog } from '@/components/ui/privileged-action-dialog';
import { useToast } from '@/components/ui/toast';
import Link from 'next/link';
import { UsageTrendsChart, TopCommandsChart, ActiveSessionsPanel } from './components';

const ACTION_TYPE_OPTIONS: { value: VoiceActionType; label: string }[] = [
  { value: 'mcp_tool', label: 'MCP Tool' },
  { value: 'workflow', label: 'Workflow' },
  { value: 'custom', label: 'Custom Handler' },
  { value: 'llm_chat', label: 'LLM Chat' },
];

const createCommandSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  phrases: z.string().min(1, 'At least one phrase is required'),
  action_type: z.enum(['mcp_tool', 'workflow', 'custom', 'llm_chat']),
  action_config: z.string().optional(),
  description: z.string().optional(),
  priority: z.coerce.number().int().min(0).default(0),
  requires_confirmation: z.boolean().default(false),
});

type CreateCommandFormInput = z.input<typeof createCommandSchema>;
type CreateCommandFormData = z.output<typeof createCommandSchema>;

function VoiceCommandsPageContent() {
  const promptPrivilegedAction = usePrivilegedActionDialog();
  const { success, error: showError } = useToast();
  const [commands, setCommands] = useState<VoiceCommand[]>([]);
  const [analytics, setAnalytics] = useState<VoiceAnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [createError, setCreateError] = useState('');
  const [creating, setCreating] = useState(false);
  const [deletingCommandId, setDeletingCommandId] = useState<string | null>(null);
  const [showDetailedAnalytics, setShowDetailedAnalytics] = useState(false);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);

  const createForm = useForm<CreateCommandFormInput, unknown, CreateCommandFormData>({
    resolver: zodResolver(createCommandSchema),
    defaultValues: {
      name: '',
      phrases: '',
      action_type: 'llm_chat',
      action_config: '{}',
      description: '',
      priority: 0,
      requires_confirmation: false,
    },
  });

  // URL state for search
  const [searchQuery, setSearchQuery] = useUrlState<string>('q', { defaultValue: '' });
  const [actionTypeFilter, setActionTypeFilter] = useUrlState<string>('type', { defaultValue: '' });

  // URL state for pagination
  const { page: currentPage, pageSize, setPage: setCurrentPage, setPageSize, resetPagination } = useUrlPagination();

  useEffect(() => {
    if (!showCreateDialog) {
      createForm.reset();
      setCreateError('');
    }
  }, [createForm, showCreateDialog]);

  const loadCommands = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const params: Record<string, string> = { limit: '200', include_disabled: 'true' };
      if (actionTypeFilter) params.action_type = actionTypeFilter;
      const data = await api.getVoiceCommands(params);
      const items = Array.isArray(data) ? data : (data?.commands || data?.items || []);
      setCommands(items);
    } catch (err: unknown) {
      console.error('Failed to load voice commands:', err);
      setError(err instanceof Error ? err.message : 'Failed to load voice commands');
      setCommands([]);
    } finally {
      setLoading(false);
    }
  }, [actionTypeFilter]);

  const loadAnalytics = useCallback(async () => {
    try {
      setAnalyticsLoading(true);
      const data = await api.getVoiceAnalytics({ days: 7 });
      setAnalytics(data);
    } catch (err: unknown) {
      console.warn('Failed to load voice analytics:', err);
    } finally {
      setAnalyticsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCommands();
    loadAnalytics();
  }, [loadCommands, loadAnalytics]);

  const filteredCommands = commands.filter((cmd) => {
    if (!searchQuery) return true;
    const query = (searchQuery || '').toLowerCase();
    return (
      cmd.name?.toLowerCase().includes(query) ||
      cmd.description?.toLowerCase().includes(query) ||
      cmd.phrases?.some((p) => p.toLowerCase().includes(query))
    );
  });

  // Pagination calculations
  const totalItems = filteredCommands.length;
  const totalPages = Math.ceil(totalItems / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const paginatedCommands = filteredCommands.slice(startIndex, startIndex + pageSize);

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

  const handleActionTypeChange = (value: string) => {
    setActionTypeFilter(value || undefined);
    resetPagination();
  };

  const handleCreateSubmit = createForm.handleSubmit(async (data) => {
    setCreateError('');
    try {
      setCreating(true);

      const parsedInputs = parseVoiceCommandInputs(data.phrases, data.action_config);
      if (!parsedInputs.ok) {
        setCreateError(parsedInputs.error);
        return;
      }

      await api.createVoiceCommand({
        name: data.name,
        phrases: parsedInputs.phrases,
        action_type: data.action_type,
        action_config: parsedInputs.actionConfig,
        description: data.description || undefined,
        priority: data.priority,
        requires_confirmation: data.requires_confirmation,
        enabled: true,
      });

      success('Voice command created', `"${data.name}" has been added.`);
      setShowCreateDialog(false);
      createForm.reset();
      void loadCommands();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create voice command';
      setCreateError(message);
      showError('Create failed', message);
    } finally {
      setCreating(false);
    }
  });

  const handleToggleEnabled = async (command: VoiceCommand) => {
    try {
      await api.toggleVoiceCommand(command.id, !command.enabled);
      success(
        command.enabled ? 'Command disabled' : 'Command enabled',
        `"${command.name}" has been ${command.enabled ? 'disabled' : 'enabled'}.`
      );
      void loadCommands();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to toggle command';
      showError('Toggle failed', message);
    }
  };

  const handleDeleteCommand = async (command: VoiceCommand) => {
    if (deletingCommandId === command.id) return;
    const result = await promptPrivilegedAction({
      title: 'Delete Voice Command',
      message: `Delete "${command.name}"? This cannot be undone.`,
      confirmText: 'Delete',
      requirePassword: false,
    });
    if (!result) return;

    try {
      setDeletingCommandId(command.id);
      await api.deleteVoiceCommand(command.id);
      success('Command deleted', `"${command.name}" has been removed.`);
      void loadCommands();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to delete command';
      showError('Delete failed', message);
    } finally {
      setDeletingCommandId((prev) => (prev === command.id ? null : prev));
    }
  };

  const getActionTypeBadgeVariant = (type: VoiceActionType) => {
    switch (type) {
      case 'mcp_tool':
        return 'default';
      case 'workflow':
        return 'secondary';
      case 'custom':
        return 'outline';
      case 'llm_chat':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
        <div className="p-4 lg:p-8">
          <div className="mb-8 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold">Voice Commands</h1>
              <p className="text-muted-foreground">Manage voice assistant commands and triggers</p>
            </div>
            <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="mr-2 h-4 w-4" />
                  Create Command
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-lg">
                <DialogHeader>
                  <DialogTitle>Create Voice Command</DialogTitle>
                  <DialogDescription>Define a new voice command with trigger phrases and actions.</DialogDescription>
                </DialogHeader>
                {createError && (
                  <Alert variant="destructive">
                    <AlertDescription>{createError}</AlertDescription>
                  </Alert>
                )}
                <FormProvider {...createForm}>
                  <Form onSubmit={handleCreateSubmit}>
                    <FormInput<CreateCommandFormData>
                      name="name"
                      label="Name"
                      placeholder="search_media"
                      required
                    />
                    <FormTextarea<CreateCommandFormData>
                      name="phrases"
                      label="Trigger Phrases"
                      placeholder="search for, find, look up"
                      description="Comma or newline separated phrases that trigger this command"
                      required
                    />
                    <FormSelect<CreateCommandFormData>
                      name="action_type"
                      label="Action Type"
                      options={ACTION_TYPE_OPTIONS}
                    />
                    <FormTextarea<CreateCommandFormData>
                      name="action_config"
                      label="Action Config (JSON)"
                      placeholder='{"tool_name": "media.search"}'
                      description="JSON configuration for the action"
                    />
                    <FormInput<CreateCommandFormData>
                      name="description"
                      label="Description"
                      placeholder="Searches media library"
                    />
                    <div className="grid grid-cols-2 gap-4">
                      <FormInput<CreateCommandFormData>
                        name="priority"
                        label="Priority"
                        type="number"
                        description="Higher priority commands match first"
                      />
                      <div className="flex items-center space-x-2 pt-6">
                        <input
                          type="checkbox"
                          id="requires_confirmation"
                          {...createForm.register('requires_confirmation')}
                          className="h-4 w-4"
                        />
                        <Label htmlFor="requires_confirmation">Requires Confirmation</Label>
                      </div>
                    </div>
                    <DialogFooter className="gap-2 sm:gap-0">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => setShowCreateDialog(false)}
                        disabled={creating}
                      >
                        Cancel
                      </Button>
                      <Button type="submit" loading={creating} loadingText="Creating...">
                        Create Command
                      </Button>
                    </DialogFooter>
                  </Form>
                </FormProvider>
              </DialogContent>
            </Dialog>
          </div>

          {/* Analytics Summary */}
          {analytics && (
            <div className="space-y-6 mb-6">
              {/* Summary Cards */}
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Analytics Overview</h2>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowDetailedAnalytics(!showDetailedAnalytics)}
                >
                  <BarChart2 className="h-4 w-4 mr-2" />
                  {showDetailedAnalytics ? 'Hide Details' : 'Show Details'}
                </Button>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-2xl font-bold">{analytics.total_voice_commands ?? 0}</div>
                    <p className="text-xs text-muted-foreground">Total Commands</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-2xl font-bold">{analytics.enabled_commands ?? 0}</div>
                    <p className="text-xs text-muted-foreground">Enabled</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-2xl font-bold">{analytics.total_commands_processed ?? 0}</div>
                    <p className="text-xs text-muted-foreground">Commands Processed (7d)</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-2xl font-bold">
                      {analytics.success_rate != null ? `${(analytics.success_rate * 100).toFixed(1)}%` : 'N/A'}
                    </div>
                    <p className="text-xs text-muted-foreground">Success Rate</p>
                  </CardContent>
                </Card>
              </div>

              {/* Detailed Analytics (collapsible) */}
              {showDetailedAnalytics && (
                <div className="space-y-6 animate-in slide-in-from-top-2 duration-200">
                  {/* Usage Trends & Top Commands Charts */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <UsageTrendsChart
                      data={analytics.usage_by_day || []}
                      isLoading={analyticsLoading}
                    />
                    <TopCommandsChart
                      data={analytics.top_commands || []}
                      isLoading={analyticsLoading}
                    />
                  </div>

                  {/* Active Sessions Panel */}
                  <ActiveSessionsPanel onSessionEnded={loadAnalytics} />
                </div>
              )}
            </div>
          )}

          {error && (
            <Alert variant="destructive" className="mb-6">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Search & Filters */}
          <Card className="mb-6">
            <CardContent className="pt-6">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
                <div className="relative flex-1 max-w-md">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" aria-hidden="true" />
                  <label htmlFor="voice-search" className="sr-only">
                    Search voice commands
                  </label>
                  <Input
                    id="voice-search"
                    placeholder="Search by name, description, or phrase..."
                    value={searchQuery || ''}
                    onChange={(e) => handleSearchChange(e.target.value)}
                    className="pl-10"
                  />
                </div>
                <Select
                  value={actionTypeFilter || ''}
                  onChange={(e) => handleActionTypeChange(e.target.value)}
                  className="w-full sm:w-48"
                >
                  <option value="">All Action Types</option>
                  {ACTION_TYPE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </Select>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Voice Commands</CardTitle>
              <CardDescription>
                {totalItems} command{totalItems !== 1 ? 's' : ''} found
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="py-4">
                  <TableSkeleton rows={5} columns={7} />
                </div>
              ) : filteredCommands.length === 0 ? (
                <EmptyState
                  icon={Mic}
                  title={searchQuery || actionTypeFilter ? 'No commands match your filters' : 'No voice commands configured'}
                  description={
                    searchQuery || actionTypeFilter
                      ? 'Adjust filters to find commands.'
                      : 'Create a voice command to enable quick actions.'
                  }
                  actions={[
                    searchQuery || actionTypeFilter
                      ? {
                          label: 'Clear filters',
                          onClick: () => {
                            handleSearchChange('');
                            handleActionTypeChange('');
                          },
                        }
                      : {
                          label: 'Create command',
                          onClick: () => setShowCreateDialog(true),
                        },
                  ]}
                />
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Phrases</TableHead>
                        <TableHead>Action Type</TableHead>
                        <TableHead>Priority</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Confirmation</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {paginatedCommands.map((cmd) => {
                        const isDeleting = deletingCommandId === cmd.id;
                        return (
                        <TableRow key={cmd.id}>
                          <TableCell>
                            <div className="font-medium">{cmd.name}</div>
                            {cmd.description && (
                              <div className="text-xs text-muted-foreground truncate max-w-xs">
                                {cmd.description}
                              </div>
                            )}
                          </TableCell>
                          <TableCell>
                            <div className="flex flex-wrap gap-1 max-w-xs">
                              {cmd.phrases.slice(0, 3).map((phrase, idx) => (
                                <Badge key={idx} variant="outline" className="text-xs">
                                  {phrase}
                                </Badge>
                              ))}
                              {cmd.phrases.length > 3 && (
                                <Badge variant="secondary" className="text-xs">
                                  +{cmd.phrases.length - 3}
                                </Badge>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge variant={getActionTypeBadgeVariant(cmd.action_type)}>
                              {cmd.action_type}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-center">{cmd.priority}</TableCell>
                          <TableCell>
                            <Badge variant={cmd.enabled ? 'default' : 'secondary'}>
                              {cmd.enabled ? 'Enabled' : 'Disabled'}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            {cmd.requires_confirmation ? (
                              <Badge variant="outline">Required</Badge>
                            ) : (
                              <span className="text-muted-foreground text-sm">No</span>
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex justify-end gap-1">
                              <Link href={`/voice-commands/${cmd.id}`}>
                                <AccessibleIconButton
                                  icon={Eye}
                                  label="View command details"
                                  variant="ghost"
                                  size="sm"
                                />
                              </Link>
                              <AccessibleIconButton
                                icon={cmd.enabled ? MicOff : Mic}
                                label={cmd.enabled ? 'Disable command' : 'Enable command'}
                                variant="ghost"
                                size="sm"
                                onClick={() => handleToggleEnabled(cmd)}
                              />
                              <AccessibleIconButton
                                icon={Trash2}
                                label={isDeleting ? 'Deleting command' : 'Delete command'}
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDeleteCommand(cmd)}
                                disabled={isDeleting}
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
export default function VoiceCommandsPage() {
  return (
    <Suspense fallback={
      <PermissionGuard variant="route" requireAuth role="admin">
        <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="mb-8">
              <Skeleton className="h-8 w-48 mb-2" />
              <Skeleton className="h-4 w-64" />
            </div>
            <TableSkeleton rows={5} columns={7} />
          </div>
        </ResponsiveLayout>
      </PermissionGuard>
    }>
      <VoiceCommandsPageContent />
    </Suspense>
  );
}
