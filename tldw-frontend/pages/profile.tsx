import { useEffect, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { useAuth } from '@/hooks/useAuth';
import { useIsAdmin } from '@/hooks/useIsAdmin';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import type { User } from '@/lib/auth';

export default function ProfilePage() {
  const { user: authUser, isAuthenticated } = useAuth();
  const isAdmin = useIsAdmin();
  const [profile, setProfile] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const placeholderKeys = [
    { provider: 'OpenAI', source: 'Your key', status: 'Stored' },
    { provider: 'Anthropic', source: 'Org shared', status: 'Available' },
    { provider: 'OpenRouter', source: 'Team shared', status: 'Available' },
  ];
  const placeholderShared = [
    { scope: 'Org', name: 'Primary org key', status: 'Enabled' },
    { scope: 'Team', name: 'Research pod', status: 'Enabled' },
  ];

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
                      <h2 className="text-sm font-semibold text-gray-800">BYOK: Provider Keys (Preview)</h2>
                      <p className="text-xs text-gray-500">
                        Placeholder UI for upcoming BYOK key management and validation workflows.
                      </p>
                    </div>
                    <span className="inline-flex items-center rounded-full bg-yellow-50 px-3 py-1 text-xs font-medium text-yellow-800">
                      Coming soon
                    </span>
                  </div>

                  <div className="grid gap-4 lg:grid-cols-3">
                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                      <div className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Your Keys</div>
                      <ul className="mt-2 space-y-2 text-sm">
                        {placeholderKeys.map((entry) => (
                          <li key={entry.provider} className="flex items-center justify-between gap-2 rounded border border-gray-200 bg-white px-2 py-1">
                            <div>
                              <div className="text-gray-900 font-medium">{entry.provider}</div>
                              <div className="text-xs text-gray-500">{entry.source}</div>
                            </div>
                            <span className="text-xs font-medium text-green-700">{entry.status}</span>
                          </li>
                        ))}
                      </ul>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button size="sm" disabled>Add key</Button>
                        <Button size="sm" variant="secondary" disabled>Update</Button>
                        <Button size="sm" variant="danger" disabled>Delete</Button>
                      </div>
                    </div>

                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                      <div className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Shared Keys</div>
                      <div className="mt-1 text-xs text-gray-500">Active scope: Org/Team (from token claims)</div>
                      <ul className="mt-2 space-y-2 text-sm">
                        {placeholderShared.map((entry) => (
                          <li key={`${entry.scope}-${entry.name}`} className="flex items-center justify-between gap-2 rounded border border-gray-200 bg-white px-2 py-1">
                            <div>
                              <div className="text-gray-900 font-medium">{entry.name}</div>
                              <div className="text-xs text-gray-500">{entry.scope} shared</div>
                            </div>
                            <span className="text-xs font-medium text-blue-700">{entry.status}</span>
                          </li>
                        ))}
                      </ul>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button size="sm" variant="secondary" disabled>Request access</Button>
                        <Button size="sm" variant="secondary" disabled>View policies</Button>
                      </div>
                    </div>

                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                      <div className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Validate & Save</div>
                      <div className="mt-2 space-y-2 text-sm">
                        <label className="block text-xs text-gray-500">
                          Provider
                          <select className="mt-1 w-full rounded border border-gray-200 bg-white px-2 py-1 text-sm" disabled>
                            <option>OpenAI</option>
                          </select>
                        </label>
                        <label className="block text-xs text-gray-500">
                          API key
                          <input className="mt-1 w-full rounded border border-gray-200 bg-white px-2 py-1 text-sm" placeholder="sk-..." disabled />
                        </label>
                        <label className="block text-xs text-gray-500">
                          Credential fields
                          <input className="mt-1 w-full rounded border border-gray-200 bg-white px-2 py-1 text-sm" placeholder="org_id, project_id" disabled />
                        </label>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button size="sm" disabled>Validate key</Button>
                        <Button size="sm" variant="secondary" disabled>Save</Button>
                      </div>
                    </div>
                  </div>
                </div>

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
