import { useCallback, useEffect, useMemo, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { useAuth } from '@/hooks/useAuth';
import { useIsAdmin } from '@/hooks/useIsAdmin';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useToast } from '@/components/ui/ToastProvider';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import type { User } from '@/lib/auth';

type ByokKeyItem = {
  provider: string;
  has_key: boolean;
  source: 'user' | 'team' | 'org' | 'server_default' | 'none' | 'disabled';
  key_hint?: string | null;
  last_used_at?: string | null;
};

type ByokKeysResponse = {
  items: ByokKeyItem[];
};

export default function ProfilePage() {
  const { user: authUser, isAuthenticated } = useAuth();
  const isAdmin = useIsAdmin();
  const { show } = useToast();
  const [profile, setProfile] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [byokItems, setByokItems] = useState<ByokKeyItem[]>([]);
  const [byokLoading, setByokLoading] = useState(false);
  const [byokError, setByokError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [provider, setProvider] = useState('');
  const [customProvider, setCustomProvider] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [orgId, setOrgId] = useState('');
  const [projectId, setProjectId] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [testModel, setTestModel] = useState('');
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const providerOptions = useMemo(() => {
    const options = byokItems.map((item) => item.provider).filter(Boolean);
    return Array.from(new Set(options)).sort((a, b) => a.localeCompare(b));
  }, [byokItems]);

  const selectedProvider = providerOptions.length > 0 ? provider : customProvider;
  const selectedItem = useMemo(
    () => byokItems.find((item) => item.provider === selectedProvider),
    [byokItems, selectedProvider]
  );

  const canDelete = !!selectedItem?.has_key;

  const formatLastUsed = (value?: string | null) => {
    if (!value) return '—';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleString();
  };

  const getErrorMessage = (err: unknown, fallback: string) => {
    if (err instanceof Error && err.message) return err.message;
    if (typeof err === 'string' && err.trim().length > 0) return err;
    return fallback;
  };

  const fetchByokKeys = useCallback(async () => {
    if (!isAuthenticated) return;
    setByokLoading(true);
    setByokError(null);
    try {
      const data = await apiClient.get<ByokKeysResponse>('/users/keys');
      const items = Array.isArray(data.items) ? data.items : [];
      setByokItems(items);
    } catch (err) {
      setByokError(getErrorMessage(err, 'Failed to load BYOK keys.'));
    } finally {
      setByokLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    const fetchProfile = async () => {
      if (!isAuthenticated) return;
      setLoading(true);
      setError(null);
      try {
        const data = await apiClient.get<User>('/users/me');
        setProfile(data);
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Failed to load profile.';
        setError(message);
      } finally {
        setLoading(false);
      }
    };

    fetchProfile();
  }, [isAuthenticated]);

  useEffect(() => {
    fetchByokKeys();
  }, [fetchByokKeys]);

  useEffect(() => {
    if (!provider && providerOptions.length > 0) {
      setProvider(providerOptions[0]);
    }
  }, [provider, providerOptions]);

  const buildCredentialFields = () => {
    const fields: Record<string, string> = {};
    if (orgId.trim()) fields.org_id = orgId.trim();
    if (projectId.trim()) fields.project_id = projectId.trim();
    if (baseUrl.trim()) fields.base_url = baseUrl.trim();
    return fields;
  };

  const handleSaveKey = async () => {
    const activeProvider = selectedProvider?.trim();
    if (!activeProvider) {
      setFormError('Provider is required.');
      return;
    }
    if (!apiKey.trim()) {
      setFormError('API key is required.');
      return;
    }
    setFormError(null);
    setSaving(true);
    try {
      const credentialFields = buildCredentialFields();
      await apiClient.post('/users/keys', {
        provider: activeProvider,
        api_key: apiKey.trim(),
        credential_fields: Object.keys(credentialFields).length ? credentialFields : undefined,
      });
      setApiKey('');
      show({ title: 'BYOK key saved', description: `${activeProvider} key stored and validated.`, variant: 'success' });
      fetchByokKeys();
    } catch (err) {
      const message = getErrorMessage(err, 'Failed to save key.');
      setFormError(message);
      show({ title: 'Save failed', description: message, variant: 'danger' });
    } finally {
      setSaving(false);
    }
  };

  const handleTestKey = async () => {
    const activeProvider = selectedProvider?.trim();
    if (!activeProvider) {
      setFormError('Provider is required.');
      return;
    }
    setFormError(null);
    setTesting(true);
    try {
      const payload: { provider: string; model?: string } = { provider: activeProvider };
      if (testModel.trim()) payload.model = testModel.trim();
      await apiClient.post('/users/keys/test', payload);
      show({ title: 'Key valid', description: `${activeProvider} stored key validated.`, variant: 'success' });
      fetchByokKeys();
    } catch (err) {
      const message = getErrorMessage(err, 'Failed to validate key.');
      setFormError(message);
      show({ title: 'Validation failed', description: message, variant: 'danger' });
    } finally {
      setTesting(false);
    }
  };

  const handleDeleteKey = async () => {
    const activeProvider = selectedProvider?.trim();
    if (!activeProvider) {
      setFormError('Provider is required.');
      return;
    }
    setDeleting(true);
    try {
      await apiClient.delete(`/users/keys/${encodeURIComponent(activeProvider)}`);
      show({ title: 'Key deleted', description: `${activeProvider} key removed.`, variant: 'success' });
      fetchByokKeys();
    } catch (err) {
      const message = getErrorMessage(err, 'Failed to delete key.');
      setFormError(message);
      show({ title: 'Delete failed', description: message, variant: 'danger' });
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  };

  const effectiveUser = profile || authUser;

  return (
    <Layout>
      <div className="mx-auto max-w-3xl space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Profile</h1>
          <p className="mt-1 text-sm text-gray-600">
            View the current authenticated user and their roles as reported by the API.
          </p>
        </div>

        {!isAuthenticated && (
          <div className="rounded-md border border-dashed border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
            You are not currently authenticated. Log in or configure API credentials to view profile information.
          </div>
        )}

        {isAuthenticated && (
          <div className="space-y-4">
            {loading && (
              <div className="rounded-md border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
                Loading profile…
              </div>
            )}

            {error && (
              <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                {error}
              </div>
            )}

            {effectiveUser && (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-3">
                  <div>
                    <div className="text-sm text-gray-500">Username</div>
                    <div className="text-lg font-semibold text-gray-900">
                      {effectiveUser.username || '(unknown)'}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="inline-flex items-center rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-800">
                      {isAdmin ? 'Admin' : 'Standard user'}
                    </span>
                    {effectiveUser.role && (
                      <span className="inline-flex items-center rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-800">
                        Role: {effectiveUser.role}
                      </span>
                    )}
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2 rounded-lg border border-gray-200 bg-white p-4">
                    <h2 className="text-sm font-semibold text-gray-800">Identity</h2>
                    <dl className="space-y-1 text-sm">
                      <div className="flex justify-between gap-3">
                        <dt className="text-gray-500">User ID</dt>
                        <dd className="text-gray-900 break-all">
                          {effectiveUser.id ?? '—'}
                        </dd>
                      </div>
                      <div className="flex justify-between gap-3">
                        <dt className="text-gray-500">Email</dt>
                        <dd className="text-gray-900 break-all">
                          {effectiveUser.email ?? '—'}
                        </dd>
                      </div>
                      <div className="flex justify-between gap-3">
                        <dt className="text-gray-500">Active</dt>
                        <dd className="text-gray-900">
                          {effectiveUser.is_active === undefined ? '—' : effectiveUser.is_active ? 'Yes' : 'No'}
                        </dd>
                      </div>
                      <div className="flex justify-between gap-3">
                        <dt className="text-gray-500">Verified</dt>
                        <dd className="text-gray-900">
                          {effectiveUser.is_verified === undefined ? '—' : effectiveUser.is_verified ? 'Yes' : 'No'}
                        </dd>
                      </div>
                    </dl>
                  </div>

                  <div className="space-y-2 rounded-lg border border-gray-200 bg-white p-4">
                    <h2 className="text-sm font-semibold text-gray-800">Usage</h2>
                    <dl className="space-y-1 text-sm">
                      <div className="flex justify-between gap-3">
                        <dt className="text-gray-500">Media count</dt>
                        <dd className="text-gray-900">{effectiveUser.media_count ?? '—'}</dd>
                      </div>
                      <div className="flex justify-between gap-3">
                        <dt className="text-gray-500">Notes count</dt>
                        <dd className="text-gray-900">{effectiveUser.notes_count ?? '—'}</dd>
                      </div>
                      <div className="flex justify-between gap-3">
                        <dt className="text-gray-500">Prompts count</dt>
                        <dd className="text-gray-900">{effectiveUser.prompts_count ?? '—'}</dd>
                      </div>
                      <div className="flex justify-between gap-3">
                        <dt className="text-gray-500">Storage used</dt>
                        <dd className="text-gray-900">
                          {effectiveUser.storage_used_mb !== undefined
                            ? `${effectiveUser.storage_used_mb} MB`
                            : '—'}
                        </dd>
                      </div>
                      <div className="flex justify-between gap-3">
                        <dt className="text-gray-500">Storage quota</dt>
                        <dd className="text-gray-900">
                          {effectiveUser.storage_quota_mb !== undefined
                            ? `${effectiveUser.storage_quota_mb} MB`
                            : '—'}
                        </dd>
                      </div>
                    </dl>
                  </div>
                </div>

                <div className="space-y-2 rounded-lg border border-gray-200 bg-white p-4">
                  <h2 className="text-sm font-semibold text-gray-800">Roles & Permissions</h2>
                  <div className="text-xs text-gray-500 mb-1">
                    Values are taken from the current user object; use this panel to verify server-side role configuration.
                  </div>
                  <dl className="space-y-1 text-sm">
                    <div className="flex flex-wrap gap-2">
                      <span className="text-gray-500">Roles:</span>
                      {(() => {
                        const roles = effectiveUser.roles;
                        if (!roles) return <span className="text-gray-900">—</span>;
                        const arr = Array.isArray(roles) ? roles : [roles];
                        return arr.map((r) => (
                          <span
                            key={String(r)}
                            className="inline-flex items-center rounded-full bg-purple-50 px-2 py-0.5 text-xs font-medium text-purple-800"
                          >
                            {String(r)}
                          </span>
                        ));
                      })()}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span className="text-gray-500">Permissions:</span>
                      {(() => {
                        const perms = effectiveUser.permissions;
                        if (!perms) return <span className="text-gray-900">—</span>;
                        const arr = Array.isArray(perms) ? perms : [perms];
                        return arr.map((p) => (
                          <span
                            key={String(p)}
                            className="inline-flex items-center rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-800"
                          >
                            {String(p)}
                          </span>
                        ));
                      })()}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span className="text-gray-500">Scopes:</span>
                      {(() => {
                        const scopes = effectiveUser.scopes;
                        if (!scopes) return <span className="text-gray-900">—</span>;
                        const arr = Array.isArray(scopes) ? scopes : [scopes];
                        return arr.map((s) => (
                          <span
                            key={String(s)}
                            className="inline-flex items-center rounded-full bg-yellow-50 px-2 py-0.5 text-xs font-medium text-yellow-800"
                          >
                            {String(s)}
                          </span>
                        ));
                      })()}
                    </div>
                  </dl>
                </div>

                <div className="space-y-3 rounded-lg border border-gray-200 bg-white p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <h2 className="text-sm font-semibold text-gray-800">BYOK: Provider Keys</h2>
                      <p className="text-xs text-gray-500">
                        Manage your provider keys. Keys are validated on save and never displayed after storage.
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Button size="sm" variant="secondary" onClick={fetchByokKeys} disabled={byokLoading}>
                        {byokLoading ? 'Refreshing…' : 'Refresh'}
                      </Button>
                    </div>
                  </div>

                  {byokError && (
                    <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
                      {byokError}
                    </div>
                  )}

                  <div className="grid gap-4 lg:grid-cols-3">
                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                      <div className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Key Status</div>
                      <div className="mt-2 space-y-2 text-sm">
                        {byokLoading && (
                          <div className="rounded border border-gray-200 bg-white px-2 py-1 text-gray-500">
                            Loading BYOK keys…
                          </div>
                        )}
                        {!byokLoading && byokItems.length === 0 && (
                          <div className="rounded border border-gray-200 bg-white px-2 py-1 text-gray-500">
                            No providers available yet.
                          </div>
                        )}
                        {byokItems.map((entry) => {
                          const isActive = entry.provider === selectedProvider;
                          const sourceLabel = {
                            user: 'Your key',
                            team: 'Team shared',
                            org: 'Org shared',
                            server_default: 'Server default',
                            none: 'No key',
                            disabled: 'Disabled',
                          }[entry.source];
                          const sourceClass = {
                            user: 'text-green-700',
                            team: 'text-blue-700',
                            org: 'text-blue-700',
                            server_default: 'text-gray-600',
                            none: 'text-gray-500',
                            disabled: 'text-red-700',
                          }[entry.source];
                          return (
                            <button
                              type="button"
                              key={entry.provider}
                              className={`w-full rounded border px-2 py-1 text-left ${
                                isActive ? 'border-blue-300 bg-white' : 'border-gray-200 bg-white hover:bg-gray-50'
                              }`}
                              onClick={() => setProvider(entry.provider)}
                            >
                              <div className="flex items-center justify-between gap-2">
                                <div>
                                  <div className="text-gray-900 font-medium">{entry.provider}</div>
                                  <div className={`text-xs ${sourceClass}`}>{sourceLabel}</div>
                                </div>
                                <div className="text-xs text-gray-500">
                                  {entry.has_key ? 'Stored' : 'No key'}
                                </div>
                              </div>
                              <div className="mt-1 flex items-center justify-between text-xs text-gray-500">
                                <span>{entry.key_hint ? `•••• ${entry.key_hint}` : '—'}</span>
                                <span>Last used: {formatLastUsed(entry.last_used_at)}</span>
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                      <div className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Save or Update</div>
                      <div className="mt-2 space-y-2 text-sm">
                        {providerOptions.length > 0 ? (
                          <label className="block text-xs text-gray-500">
                            Provider
                            <select
                              className="mt-1 w-full rounded border border-gray-200 bg-white px-2 py-1 text-sm"
                              value={provider}
                              onChange={(e) => setProvider(e.target.value)}
                            >
                              {providerOptions.map((opt) => (
                                <option key={opt} value={opt}>{opt}</option>
                              ))}
                            </select>
                          </label>
                        ) : (
                          <Input
                            label="Provider"
                            placeholder="openai"
                            value={customProvider}
                            onChange={(e) => setCustomProvider(e.target.value)}
                          />
                        )}
                        <Input
                          label="API key"
                          type="password"
                          placeholder="sk-..."
                          value={apiKey}
                          onChange={(e) => setApiKey(e.target.value)}
                        />
                        <Input
                          label="Org ID (optional)"
                          placeholder="org_123"
                          value={orgId}
                          onChange={(e) => setOrgId(e.target.value)}
                        />
                        <Input
                          label="Project ID (optional)"
                          placeholder="proj_456"
                          value={projectId}
                          onChange={(e) => setProjectId(e.target.value)}
                        />
                        <Input
                          label="Base URL (optional, allowlisted providers only)"
                          placeholder="https://api.example.com"
                          value={baseUrl}
                          onChange={(e) => setBaseUrl(e.target.value)}
                        />
                        {formError && (
                          <div className="rounded border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700">
                            {formError}
                          </div>
                        )}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button size="sm" onClick={handleSaveKey} disabled={saving || !selectedProvider}>
                          {saving ? 'Saving…' : 'Save key'}
                        </Button>
                        <Button
                          size="sm"
                          variant="danger"
                          onClick={() => setConfirmDelete(true)}
                          disabled={!canDelete || deleting || !selectedProvider}
                        >
                          Delete key
                        </Button>
                      </div>
                    </div>

                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                      <div className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Test Stored Key</div>
                      <div className="mt-2 space-y-2 text-sm">
                        <div className="text-xs text-gray-500">
                          Tests the stored key for the selected provider. Save first if no key is stored.
                        </div>
                        <Input
                          label="Model (optional)"
                          placeholder="gpt-4o-mini"
                          value={testModel}
                          onChange={(e) => setTestModel(e.target.value)}
                        />
                        {selectedItem && (
                          <div className="rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-600">
                            Current source: {selectedItem.source}
                          </div>
                        )}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button size="sm" variant="secondary" onClick={handleTestKey} disabled={testing || !selectedProvider}>
                          {testing ? 'Testing…' : 'Test stored key'}
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>

                <ConfirmDialog
                  open={confirmDelete}
                  title="Delete BYOK key?"
                  message="This removes your stored key for the selected provider. Requests will fall back to shared or server defaults."
                  confirmText={deleting ? 'Deleting…' : 'Delete'}
                  destructive
                  onCancel={() => setConfirmDelete(false)}
                  onConfirm={handleDeleteKey}
                />

                {/* Debug panel with raw /users/me JSON to aid troubleshooting */}
                {profile && (
                  <details className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-800">
                    <summary className="cursor-pointer text-sm font-semibold text-gray-800">
                      Debug: Raw <code className="font-mono text-xs">/users/me</code> response
                    </summary>
                    <pre className="mt-2 max-h-80 overflow-auto rounded bg-gray-900 p-3 text-xs text-gray-100">
                      {JSON.stringify(profile, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </Layout>
  );
}
