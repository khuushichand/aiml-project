import { Button } from '@web/components/ui/Button';
import { useVlmBackends } from '@web/hooks/useVlmBackends';

export function VlmBackendsCard() {
  const { loading, error, endpoint, backends, reload } = useVlmBackends();

  const entries = Object.entries(backends || {}).sort(([a], [b]) => a.localeCompare(b));

  return (
    <details className="rounded border p-3">
      <summary className="cursor-pointer text-sm font-semibold">VLM Backends</summary>
      <div className="mt-2 text-sm">
        {endpoint && (
          <div className="mb-2 text-xs text-text-muted">Endpoint: <code>{endpoint}</code></div>
        )}
        {loading && <div className="text-text-muted">Loading backends…</div>}
        {error && (
          <div className="mb-2 rounded bg-danger/10 p-2 text-danger">
            {error}
          </div>
        )}
        {!loading && !error && (!entries.length ? (
          <div className="text-text-muted">No VLM backends reported.</div>
        ) : (
          <ul className="space-y-1">
            {entries.map(([name, available]) => (
              <li key={name} className="flex items-center justify-between rounded bg-bg px-2 py-1">
                <span className="font-mono text-xs text-text">{name}</span>
                <span className={available ? 'text-success' : 'text-text-muted'}>
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
