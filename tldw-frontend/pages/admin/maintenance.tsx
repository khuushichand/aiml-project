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

  const resolveUrl = (path: string) => `${base}${path.startsWith('/') ? '' : '/'}${path}`;

  const callPost = async (path: string, label: string) => {
    setBusy(label);
    try {
      const url = resolveUrl(path);
      const resp = await fetch(url, { method: 'POST', headers: buildAuthHeaders('POST') });
      const ok = resp.ok;
      const text = await resp.text();
      let _data: unknown = null;
      try { _data = JSON.parse(text); } catch { _data = text; }
      show({ title: ok ? 'Success' : 'Request failed', description: ok ? `${label} completed` : `${resp.status} ${resp.statusText}`, variant: ok ? 'success' : 'warning' });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      show({ title: 'Request error', description: message, variant: 'danger' });
    } finally {
      setBusy(null);
    }
  };

  const fetchEffectiveConfig = async () => {
    const label = 'Fetch Effective Config';
    setBusy(label);
    setEffectiveConfigError(null);
    try {
      const url = resolveUrl(effectiveConfigPath);
      const resp = await fetch(url, { method: 'GET', headers: buildAuthHeaders('GET') });
      const ok = resp.ok;
      const text = await resp.text();
      let data: EffectiveConfigResponse | string = text;
      try { data = JSON.parse(text) as EffectiveConfigResponse; } catch { data = text; }
      if (!ok) {
        setEffectiveConfig(null);
        setEffectiveConfigError(typeof data === 'string' ? data : JSON.stringify(data, null, 2));
        show({ title: 'Request failed', description: `${resp.status} ${resp.statusText}`, variant: 'warning' });
        return;
      }
      setEffectiveConfig(typeof data === 'string' ? data : JSON.stringify(data, null, 2));
      show({ title: 'Success', description: 'Effective config fetched', variant: 'success' });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      setEffectiveConfig(null);
      setEffectiveConfigError(message);
      show({ title: 'Request error', description: message, variant: 'danger' });
    } finally {
      setBusy(null);
    }
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
