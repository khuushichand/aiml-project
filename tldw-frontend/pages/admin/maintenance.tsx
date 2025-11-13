import { useEffect, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Button } from '@/components/ui/Button';
import { useToast } from '@/components/ui/ToastProvider';
import { buildAuthHeaders, getApiBaseUrl } from '@/lib/api';
import { useIsAdmin } from '@/hooks/useIsAdmin';

export default function AdminMaintenancePage() {
  const { show } = useToast();
  const isAdmin = useIsAdmin();
  const [busy, setBusy] = useState<string | null>(null);
  const base = getApiBaseUrl();

  useEffect(() => {
    // no-op: placeholder for any preflight admin checks later
  }, []);

  const callPost = async (path: string, label: string) => {
    setBusy(label);
    try {
      const url = `${base}${path.startsWith('/') ? '' : '/'}${path}`;
      const resp = await fetch(url, { method: 'POST', headers: buildAuthHeaders('POST') });
      const ok = resp.ok;
      const text = await resp.text();
      let data: any = null;
      try { data = JSON.parse(text); } catch { data = text; }
      show({ title: ok ? 'Success' : 'Request failed', description: ok ? `${label} completed` : `${resp.status} ${resp.statusText}`, variant: ok ? 'success' : 'warning' });
    } catch (e: any) {
      show({ title: 'Request error', description: e?.message || String(e), variant: 'danger' });
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
      </div>
    </Layout>
  );
}

