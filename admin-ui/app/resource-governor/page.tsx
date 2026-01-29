'use client';

import { useCallback, useEffect, useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api-client';
import { formatDateTime } from '@/lib/format';
import { parseOptionalInt } from '@/lib/number';
import { RefreshCw, Trash2, Edit2, Plus, Gauge, X } from 'lucide-react';

type ResourcePolicy = {
  id?: string | number;
  name: string;
  scope: 'global' | 'org' | 'user' | 'role';
  scope_id?: string | number | null;
  resource_type: string;
  max_requests_per_minute?: number | null;
  max_requests_per_hour?: number | null;
  max_requests_per_day?: number | null;
  max_tokens_per_request?: number | null;
  max_concurrent_requests?: number | null;
  priority?: number;
  enabled: boolean;
  description?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

type PoliciesResponse = {
  policies?: ResourcePolicy[];
  items?: ResourcePolicy[];
};

const RESOURCE_TYPES = [
  'llm',
  'embedding',
  'transcription',
  'tts',
  'rag',
  'media_processing',
  'all',
] as const;

const POLICY_SCOPES = ['global', 'org', 'user', 'role'] as const;

const formatPolicyDate = (value?: string | null) =>
  formatDateTime(value, { fallback: '—' });

export default function ResourceGovernorPage() {
  const confirm = useConfirm();
  const { success, error: showError } = useToast();

  // Policies state
  const [policies, setPolicies] = useState<ResourcePolicy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Filter state
  const [scopeFilter, setScopeFilter] = useState('');
  const [resourceTypeFilter, setResourceTypeFilter] = useState('');

  // Form state for create/edit
  const [showForm, setShowForm] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<ResourcePolicy | null>(null);
  const [formSaving, setFormSaving] = useState(false);
  const [deletingPolicyId, setDeletingPolicyId] = useState<string | null>(null);

  // Form fields
  const [formName, setFormName] = useState('');
  const [formScope, setFormScope] = useState<ResourcePolicy['scope']>('global');
  const [formScopeId, setFormScopeId] = useState('');
  const [formResourceType, setFormResourceType] = useState('llm');
  const [formMaxRpm, setFormMaxRpm] = useState('');
  const [formMaxRph, setFormMaxRph] = useState('');
  const [formMaxRpd, setFormMaxRpd] = useState('');
  const [formMaxTokens, setFormMaxTokens] = useState('');
  const [formMaxConcurrent, setFormMaxConcurrent] = useState('');
  const [formPriority, setFormPriority] = useState('0');
  const [formEnabled, setFormEnabled] = useState(true);
  const [formDescription, setFormDescription] = useState('');

  const loadPolicies = useCallback(async (signal?: AbortSignal) => {
    try {
      setLoading(true);
      setError('');
      const data = (await api.getResourceGovernorPolicy({ include_ids: true }, signal)) as PoliciesResponse;
      const items = data.policies || data.items || [];
      let filtered = Array.isArray(items) ? items : [];
      if (scopeFilter) {
        filtered = filtered.filter((p) => p.scope === scopeFilter);
      }
      if (resourceTypeFilter) {
        filtered = filtered.filter((p) => p.resource_type === resourceTypeFilter);
      }
      setPolicies(filtered);
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return;
      const message = err instanceof Error && err.message ? err.message : 'Failed to load policies';
      setError(message);
      setPolicies([]);
    } finally {
      setLoading(false);
    }
  }, [scopeFilter, resourceTypeFilter]);

  useEffect(() => {
    const controller = new AbortController();
    void loadPolicies(controller.signal);
    return () => controller.abort();
  }, [loadPolicies]);

  const handleRefresh = useCallback(() => {
    void loadPolicies();
  }, [loadPolicies]);

  const resetForm = () => {
    setFormName('');
    setFormScope('global');
    setFormScopeId('');
    setFormResourceType('llm');
    setFormMaxRpm('');
    setFormMaxRph('');
    setFormMaxRpd('');
    setFormMaxTokens('');
    setFormMaxConcurrent('');
    setFormPriority('0');
    setFormEnabled(true);
    setFormDescription('');
    setEditingPolicy(null);
  };

  const handleNewPolicy = () => {
    resetForm();
    setShowForm(true);
  };

  const handleEditPolicy = (policy: ResourcePolicy) => {
    setEditingPolicy(policy);
    setFormName(policy.name || '');
    setFormScope(policy.scope || 'global');
    setFormScopeId(policy.scope_id?.toString() || '');
    setFormResourceType(policy.resource_type || 'llm');
    setFormMaxRpm(policy.max_requests_per_minute?.toString() || '');
    setFormMaxRph(policy.max_requests_per_hour?.toString() || '');
    setFormMaxRpd(policy.max_requests_per_day?.toString() || '');
    setFormMaxTokens(policy.max_tokens_per_request?.toString() || '');
    setFormMaxConcurrent(policy.max_concurrent_requests?.toString() || '');
    setFormPriority(policy.priority?.toString() || '0');
    setFormEnabled(policy.enabled ?? true);
    setFormDescription(policy.description || '');
    setShowForm(true);
  };

  const handleCancelForm = () => {
    setShowForm(false);
    resetForm();
  };

  const handleSavePolicy = async () => {
    const name = formName.trim();
    if (!name) {
      showError('Policy name is required');
      return;
    }

    if ((formScope === 'org' || formScope === 'user' || formScope === 'role') && !formScopeId.trim()) {
      showError(`${formScope.charAt(0).toUpperCase() + formScope.slice(1)} ID is required for ${formScope} scope`);
      return;
    }

    try {
      setFormSaving(true);
      const payload: Record<string, unknown> = {
        name,
        scope: formScope,
        resource_type: formResourceType,
        enabled: formEnabled,
      };

      if (formScope !== 'global') {
        payload.scope_id = formScopeId.trim();
      }

      const maxRpm = parseOptionalInt(formMaxRpm);
      const maxRph = parseOptionalInt(formMaxRph);
      const maxRpd = parseOptionalInt(formMaxRpd);
      const maxTokens = parseOptionalInt(formMaxTokens);
      const maxConcurrent = parseOptionalInt(formMaxConcurrent);
      const priority = parseOptionalInt(formPriority);
      const isEditMode = Boolean(editingPolicy?.id);

      if (maxRpm !== null) payload.max_requests_per_minute = maxRpm;
      else if (isEditMode) payload.max_requests_per_minute = null;

      if (maxRph !== null) payload.max_requests_per_hour = maxRph;
      else if (isEditMode) payload.max_requests_per_hour = null;

      if (maxRpd !== null) payload.max_requests_per_day = maxRpd;
      else if (isEditMode) payload.max_requests_per_day = null;

      if (maxTokens !== null) payload.max_tokens_per_request = maxTokens;
      else if (isEditMode) payload.max_tokens_per_request = null;

      if (maxConcurrent !== null) payload.max_concurrent_requests = maxConcurrent;
      else if (isEditMode) payload.max_concurrent_requests = null;

      if (priority !== null) payload.priority = priority;
      else if (isEditMode) payload.priority = null;

      if (isEditMode) {
        payload.description = formDescription.trim() || null;
      } else if (formDescription.trim()) {
        payload.description = formDescription.trim();
      }

      if (editingPolicy?.id) {
        payload.id = editingPolicy.id;
      }

      await api.updateResourceGovernorPolicy(payload);
      success(editingPolicy ? 'Policy updated' : 'Policy created');
      setShowForm(false);
      resetForm();
      await loadPolicies();
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to save policy';
      showError(message);
    } finally {
      setFormSaving(false);
    }
  };

  const handleDeletePolicy = async (policy: ResourcePolicy) => {
    if (!policy.id) {
      showError('Cannot delete policy without ID');
      return;
    }
    const policyId = String(policy.id);
    if (deletingPolicyId === policyId) return;

    const confirmed = await confirm({
      title: `Delete policy "${policy.name}"?`,
      message: 'This will remove the resource governance policy. This action cannot be undone.',
      confirmText: 'Delete',
      variant: 'danger',
    });

    if (!confirmed) return;

    try {
      setDeletingPolicyId(policyId);
      await api.deleteResourceGovernorPolicy(policyId);
      success('Policy deleted');
      await loadPolicies();
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to delete policy';
      showError(message);
    } finally {
      setDeletingPolicyId((prev) => (prev === policyId ? null : prev));
    }
  };

  const getScopeDisplay = (policy: ResourcePolicy) => {
    if (policy.scope === 'global') return 'Global';
    if (policy.scope === 'org') return `Org ${policy.scope_id}`;
    if (policy.scope === 'user') return `User ${policy.scope_id}`;
    if (policy.scope === 'role') return `Role ${policy.scope_id}`;
    return policy.scope;
  };

  const getLimitsDisplay = (policy: ResourcePolicy) => {
    const parts: string[] = [];
    if (policy.max_requests_per_minute != null) parts.push(`${policy.max_requests_per_minute}/min`);
    if (policy.max_requests_per_hour != null) parts.push(`${policy.max_requests_per_hour}/hr`);
    if (policy.max_requests_per_day != null) parts.push(`${policy.max_requests_per_day}/day`);
    if (policy.max_concurrent_requests != null) parts.push(`${policy.max_concurrent_requests} concurrent`);
    if (policy.max_tokens_per_request != null) parts.push(`${policy.max_tokens_per_request} tokens/req`);
    return parts.length > 0 ? parts.join(', ') : 'No limits set';
  };

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
        <div className="flex flex-col gap-6 p-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-2">
                <Gauge className="h-6 w-6" />
                Resource Governor
              </h1>
              <p className="text-muted-foreground">
                Manage rate limits and resource quotas for API operations.
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={handleRefresh} disabled={loading}>
                <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
              <Button onClick={handleNewPolicy}>
                <Plus className="mr-2 h-4 w-4" />
                New Policy
              </Button>
            </div>
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Create/Edit Form */}
          {showForm && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>{editingPolicy ? 'Edit Policy' : 'New Policy'}</CardTitle>
                    <CardDescription>
                      {editingPolicy ? 'Update the resource governance policy.' : 'Create a new resource governance policy.'}
                    </CardDescription>
                  </div>
                  <Button variant="ghost" size="icon" onClick={handleCancelForm}>
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="grid gap-4">
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="space-y-1">
                    <Label htmlFor="policy-name">Policy Name *</Label>
                    <Input
                      id="policy-name"
                      placeholder="e.g., Default LLM Rate Limit"
                      value={formName}
                      onChange={(e) => setFormName(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="policy-scope">Scope *</Label>
                    <Select
                      id="policy-scope"
                      value={formScope}
                      onChange={(e) => setFormScope(e.target.value as ResourcePolicy['scope'])}
                    >
                      {POLICY_SCOPES.map((scope) => (
                        <option key={scope} value={scope}>
                          {scope.charAt(0).toUpperCase() + scope.slice(1)}
                        </option>
                      ))}
                    </Select>
                  </div>
                  {formScope !== 'global' && (
                    <div className="space-y-1">
                      <Label htmlFor="policy-scope-id">
                        {formScope === 'org' ? 'Organization' : formScope === 'user' ? 'User' : 'Role'} ID *
                      </Label>
                      <Input
                        id="policy-scope-id"
                        placeholder={`Enter ${formScope} ID`}
                        value={formScopeId}
                        onChange={(e) => setFormScopeId(e.target.value)}
                      />
                    </div>
                  )}
                  <div className="space-y-1">
                    <Label htmlFor="policy-resource">Resource Type *</Label>
                    <Select
                      id="policy-resource"
                      value={formResourceType}
                      onChange={(e) => setFormResourceType(e.target.value)}
                    >
                      {RESOURCE_TYPES.map((type) => (
                        <option key={type} value={type}>
                          {type.replaceAll('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                        </option>
                      ))}
                    </Select>
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-5">
                  <div className="space-y-1">
                    <Label htmlFor="policy-rpm">Max Requests/Min</Label>
                    <Input
                      id="policy-rpm"
                      type="number"
                      min="0"
                      placeholder="e.g., 60"
                      value={formMaxRpm}
                      onChange={(e) => setFormMaxRpm(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="policy-rph">Max Requests/Hour</Label>
                    <Input
                      id="policy-rph"
                      type="number"
                      min="0"
                      placeholder="e.g., 1000"
                      value={formMaxRph}
                      onChange={(e) => setFormMaxRph(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="policy-rpd">Max Requests/Day</Label>
                    <Input
                      id="policy-rpd"
                      type="number"
                      min="0"
                      placeholder="e.g., 10000"
                      value={formMaxRpd}
                      onChange={(e) => setFormMaxRpd(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="policy-tokens">Max Tokens/Request</Label>
                    <Input
                      id="policy-tokens"
                      type="number"
                      min="0"
                      placeholder="e.g., 4096"
                      value={formMaxTokens}
                      onChange={(e) => setFormMaxTokens(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="policy-concurrent">Max Concurrent</Label>
                    <Input
                      id="policy-concurrent"
                      type="number"
                      min="0"
                      placeholder="e.g., 10"
                      value={formMaxConcurrent}
                      onChange={(e) => setFormMaxConcurrent(e.target.value)}
                    />
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-3">
                  <div className="space-y-1">
                    <Label htmlFor="policy-priority">Priority (higher = more important)</Label>
                    <Input
                      id="policy-priority"
                      type="number"
                      min="0"
                      placeholder="0"
                      value={formPriority}
                      onChange={(e) => setFormPriority(e.target.value)}
                    />
                  </div>
                  <div className="flex items-center gap-2 pt-6">
                    <Checkbox
                      id="policy-enabled"
                      checked={formEnabled}
                      onCheckedChange={(checked) => setFormEnabled(checked === true)}
                    />
                    <Label htmlFor="policy-enabled">Enabled</Label>
                  </div>
                </div>

                <div className="space-y-1">
                  <Label htmlFor="policy-description">Description</Label>
                  <Input
                    id="policy-description"
                    placeholder="Optional description for this policy"
                    value={formDescription}
                    onChange={(e) => setFormDescription(e.target.value)}
                  />
                </div>

                <div className="flex gap-2">
                  <Button onClick={handleSavePolicy} disabled={formSaving}>
                    {formSaving ? 'Saving...' : editingPolicy ? 'Update Policy' : 'Create Policy'}
                  </Button>
                  <Button variant="outline" onClick={handleCancelForm}>
                    Cancel
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Policies List */}
          <Card>
            <CardHeader>
              <CardTitle>Policies</CardTitle>
              <CardDescription>Resource governance policies in order of priority.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-1">
                  <Label htmlFor="scope-filter">Filter by Scope</Label>
                  <Select
                    id="scope-filter"
                    value={scopeFilter}
                    onChange={(e) => setScopeFilter(e.target.value)}
                  >
                    <option value="">All Scopes</option>
                    {POLICY_SCOPES.map((scope) => (
                      <option key={scope} value={scope}>
                        {scope.charAt(0).toUpperCase() + scope.slice(1)}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="resource-filter">Filter by Resource Type</Label>
                  <Select
                    id="resource-filter"
                    value={resourceTypeFilter}
                    onChange={(e) => setResourceTypeFilter(e.target.value)}
                  >
                    <option value="">All Resources</option>
                    {RESOURCE_TYPES.map((type) => (
                      <option key={type} value={type}>
                        {type.replaceAll('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                      </option>
                    ))}
                  </Select>
                </div>
              </div>

              {loading ? (
                <div className="py-8 text-center text-muted-foreground">Loading policies...</div>
              ) : policies.length === 0 ? (
                <div className="py-8 text-center text-muted-foreground">
                  No policies found. Click &quot;New Policy&quot; to create one.
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Scope</TableHead>
                      <TableHead>Resource</TableHead>
                      <TableHead>Limits</TableHead>
                      <TableHead>Priority</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Updated</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {policies.map((policy, index) => {
                      const rowKey = policy.id ? `policy-${policy.id}` : `policy-index-${index}`;
                      const policyId = policy.id != null ? String(policy.id) : '';
                      const isDeleting = policyId !== '' && deletingPolicyId === policyId;
                      return (
                        <TableRow key={rowKey}>
                          <TableCell className="font-medium">
                            <div>{policy.name}</div>
                            {policy.description && (
                              <div className="text-xs text-muted-foreground">{policy.description}</div>
                            )}
                          </TableCell>
                          <TableCell>{getScopeDisplay(policy)}</TableCell>
                          <TableCell>
                            <Badge variant="outline">
                              {policy.resource_type?.replaceAll('_', ' ') || 'all'}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-sm">{getLimitsDisplay(policy)}</TableCell>
                          <TableCell>{policy.priority ?? 0}</TableCell>
                          <TableCell>
                            <Badge variant={policy.enabled ? 'default' : 'secondary'}>
                              {policy.enabled ? 'Enabled' : 'Disabled'}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {formatPolicyDate(policy.updated_at)}
                          </TableCell>
                          <TableCell>
                            <div className="flex gap-1">
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleEditPolicy(policy)}
                                title="Edit policy"
                              >
                                <Edit2 className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleDeletePolicy(policy)}
                                title={isDeleting ? 'Deleting policy' : 'Delete policy'}
                                aria-label={isDeleting ? 'Deleting policy' : 'Delete policy'}
                                disabled={isDeleting}
                              >
                                {isDeleting ? (
                                  <RefreshCw className="h-4 w-4 animate-spin" />
                                ) : (
                                  <Trash2 className="h-4 w-4" />
                                )}
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })}
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
