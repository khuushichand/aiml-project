import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Button } from '@/components/ui/Button';
import { useToast } from '@/components/ui/ToastProvider';
import { buildAuthHeaders, getApiBaseUrl } from '@/lib/api';
import { useIsAdmin } from '@/hooks/useIsAdmin';
import type { EffectiveConfigResponse } from '@/types/config';

export default function AdminMaintenancePage() {
  const { show } = useToast();
  const isAdmin = useIsAdmin();
  const [busy, setBusy] = useState<string | null>(null);
  const [effectiveConfig, setEffectiveConfig] = useState<string | null>(null);
  const [effectiveConfigError, setEffectiveConfigError] = useState<string | null>(null);
  const base = getApiBaseUrl();
  const effectiveConfigPath = '/admin/config/effective?include_defaults=false';

  useEffect(() => {
    // no-op: placeholder for any preflight admin checks later
  }, []);

  const resolveUrl = (path: string) => {
    const normalizedBase = base.endsWith('/') ? base : `${base}/`;
    const normalizedPath = path.startsWith('/') ? path.slice(1) : path;
    return new URL(normalizedPath, normalizedBase).toString();
  };

  const apiFetch = async <T>({
    path,
    method,
    label,
    onSuccess,
    onError,
    successMessage,
  }: {
    path: string;
    method: 'GET' | 'POST';
    label: string;
    onSuccess?: (data: T | string) => void;
    onError?: (errorMessage: string) => void;
    successMessage?: string;
  }) => {
    setBusy(label);
    try {
      const url = resolveUrl(path);
      const resp = await fetch(url, { method, headers: buildAuthHeaders(method) });
      const text = await resp.text();
      let data: T | string = text;
      try { data = JSON.parse(text) as T; } catch { data = text; }

      if (!resp.ok) {
        const errorMessage = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
        onError?.(errorMessage);
        show({ title: 'Request failed', description: `${resp.status} ${resp.statusText}`, variant: 'warning' });
        return;
      }

      onSuccess?.(data);
      show({ title: 'Success', description: successMessage ?? `${label} completed`, variant: 'success' });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      onError?.(message);
      show({ title: 'Request error', description: message, variant: 'danger' });
    } finally {
      setBusy(null);
    }
  };

  const callPost = (path: string, label: string) =>
    apiFetch({ path, method: 'POST', label });

  const fetchEffectiveConfig = async () => {
    const label = 'Fetch Effective Config';
    setEffectiveConfigError(null);
    await apiFetch<EffectiveConfigResponse>({
      path: effectiveConfigPath,
      method: 'GET',
      label,
      successMessage: 'Effective config fetched',
      onSuccess: (data) => {
        setEffectiveConfig(typeof data === 'string' ? data : JSON.stringify(data, null, 2));
      },
      onError: (errorMessage) => {
        setEffectiveConfig(null);
        setEffectiveConfigError(errorMessage);
      },
    });
  };

  if (!isAdmin) {
    return (
      <Layout>
        <div className="mx-auto max-w-3xl">
          <h1 className="mb-4 text-2xl font-bold text-gray-900">Admin Maintenance</h1>
          <div className="rounded-md border bg-white p-4 text-sm text-gray-700">Admin access required.</div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="mx-auto max-w-3xl space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Admin Maintenance</h1>

        <div className="rounded-md border bg-white p-4">
          <div className="mb-2 text-lg font-semibold text-gray-800">Admin Data Ops</div>
          <p className="mb-3 text-sm text-gray-600">Manage backups, retention policies, and exports.</p>
          <Link
            href="/admin/data-ops"
            className="inline-flex items-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Open Data Ops
          </Link>
        </div>

        <div className="rounded-md border bg-white p-4">
          <div className="mb-2 text-lg font-semibold text-gray-800">Chat Model Aliases Cache</div>
          <p className="mb-3 text-sm text-gray-600">Reloads cached chat model lists and alias overrides so changes to model_pricing.json or environment variables take effect without restarting the server.</p>
          <div className="flex items-center gap-2">
            <Button onClick={() => callPost('/admin/chat/model-aliases/reload', 'Reload Chat Model Aliases')} disabled={busy !== null}>
              {busy === 'Reload Chat Model Aliases' ? 'Reloading…' : 'Reload Chat Model Aliases'}
            </Button>
            <code className="truncate rounded bg-gray-50 px-2 py-1 text-xs text-gray-700">POST {base}/admin/chat/model-aliases/reload</code>
          </div>
        </div>

        <div className="rounded-md border bg-white p-4">
          <div className="mb-2 text-lg font-semibold text-gray-800">LLM Pricing Catalog</div>
          <p className="mb-3 text-sm text-gray-600">Reloads the pricing catalog from environment and Config_Files/model_pricing.json.</p>
          <div className="flex items-center gap-2">
            <Button onClick={() => callPost('/admin/llm-usage/pricing/reload', 'Reload Pricing Catalog')} disabled={busy !== null}>
              {busy === 'Reload Pricing Catalog' ? 'Reloading…' : 'Reload Pricing Catalog'}
            </Button>
            <code className="truncate rounded bg-gray-50 px-2 py-1 text-xs text-gray-700">POST {base}/admin/llm-usage/pricing/reload</code>
          </div>
        </div>

        <div className="rounded-md border bg-white p-4">
          <div className="mb-2 text-lg font-semibold text-gray-800">Effective Config (Redacted)</div>
          <p className="mb-3 text-sm text-gray-600">Fetches the current effective configuration with redacted secrets and source tags.</p>
          <div className="flex items-center gap-2">
            <Button onClick={fetchEffectiveConfig} disabled={busy !== null}>
              {busy === 'Fetch Effective Config' ? 'Fetching…' : 'Fetch Effective Config'}
            </Button>
            <code className="truncate rounded bg-gray-50 px-2 py-1 text-xs text-gray-700">GET {base}{effectiveConfigPath}</code>
          </div>
          {effectiveConfigError ? (
            <div className="mt-3 rounded border border-red-200 bg-red-50 p-3 text-xs text-red-700">
              {effectiveConfigError}
            </div>
          ) : null}
          {effectiveConfig ? (
            <pre className="mt-3 max-h-96 overflow-auto rounded border bg-gray-50 p-3 text-xs text-gray-800">
              {effectiveConfig}
            </pre>
          ) : null}
        </div>
      </div>
    </Layout>
  );
}
