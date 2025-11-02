import { Button } from '@/components/ui/Button';
import { useVlmBackends } from '@/hooks/useVlmBackends';

export function VlmBackendsCard() {
  const { loading, error, endpoint, backends, reload } = useVlmBackends();

  const entries = Object.entries(backends || {}).sort(([a], [b]) => a.localeCompare(b));

  return (
    <details className="rounded border p-3">
      <summary className="cursor-pointer text-sm font-semibold">VLM Backends</summary>
      <div className="mt-2 text-sm">
        {endpoint && (
          <div className="mb-2 text-xs text-gray-500">Endpoint: <code>{endpoint}</code></div>
        )}
        {loading && <div className="text-gray-600">Loading backends…</div>}
        {error && (
          <div className="mb-2 rounded bg-red-50 p-2 text-red-800">
            {error}
          </div>
        )}
        {!loading && !error && (!entries.length ? (
          <div className="text-gray-600">No VLM backends reported.</div>
        ) : (
          <ul className="space-y-1">
            {entries.map(([name, available]) => (
              <li key={name} className="flex items-center justify-between rounded bg-gray-50 px-2 py-1">
                <span className="font-mono text-xs text-gray-800">{name}</span>
                <span className={available ? 'text-green-700' : 'text-gray-500'}>
                  {available ? 'Available' : 'Unavailable'}
                </span>
              </li>
            ))}
          </ul>
        ))}
        <div className="mt-2">
          <Button variant="secondary" size="sm" onClick={reload} disabled={loading}>
            Refresh
          </Button>
        </div>
      </div>
    </details>
  );
}

export default VlmBackendsCard;
