import { useEffect, useMemo, useState } from 'react';
import { apiClient } from '@/lib/api';

type BackendsMap = Record<string, { available: boolean } | boolean>;

interface UseVlmBackendsResult {
  loading: boolean;
  error: string | null;
  endpoint: string | null;
  backends: Record<string, boolean> | null;
  reload: () => void;
}

/**
 * Fetches RAG capabilities to discover the VLM backends endpoint,
 * then fetches and returns the available/unavailable map.
 */
export function useVlmBackends(): UseVlmBackendsResult {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [endpoint, setEndpoint] = useState<string | null>(null);
  const [rawBackends, setRawBackends] = useState<BackendsMap | null>(null);
  const [reloadKey, setReloadKey] = useState<number>(0);

  useEffect(() => {
    let cancelled = false;
    async function run() {
      setLoading(true);
      setError(null);
      try {
        const caps: any = await apiClient.get('/rag/capabilities');
        const ep: string | undefined = caps?.features?.vlm_late_chunking?.backends_endpoint;
        const discovered = ep && typeof ep === 'string' ? ep : '/api/v1/rag/vlm/backends';
        setEndpoint(discovered);

        // Normalize endpoint to be relative to api base (remove /api/v1 prefix if present)
        const rel = '/' + discovered.replace(/^\/?api\/?v1\//, '/').replace(/^\/+/, '');
        const finalPath = rel.startsWith('/rag/') ? rel : `/rag/${rel.replace(/^rag\//, '')}`;

        const data: any = await apiClient.get(finalPath);
        const map: BackendsMap = data?.backends || {};
        if (!cancelled) setRawBackends(map);
      } catch (e: any) {
        if (!cancelled) setError(e?.message || 'Failed to load VLM backends');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    run();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const backends = useMemo(() => {
    if (!rawBackends) return null;
    const out: Record<string, boolean> = {};
    for (const [k, v] of Object.entries(rawBackends)) {
      out[k] = typeof v === 'object' && v !== null ? !!v.available : !!v;
    }
    return out;
  }, [rawBackends]);

  const reload = () => setReloadKey((k) => k + 1);

  return { loading, error, endpoint, backends, reload };
}

export default useVlmBackends;
