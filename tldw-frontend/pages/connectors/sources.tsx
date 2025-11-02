import { useEffect, useState } from 'react'

type Source = {
  id: number; account_id: number; provider: 'drive' | 'notion'; remote_id: string; type: string; path?: string;
  options?: { recursive?: boolean }; enabled?: boolean; last_synced_at?: string | null
}

export default function Sources() {
  const [sources, setSources] = useState<Source[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<number | null>(null)

  async function load() {
    setError(null)
    try {
      const r = await fetch('/api/v1/connectors/sources')
      const j = await r.json()
      setSources(j)
    } catch (e: any) {
      setError(e?.message || 'Failed to load sources')
    }
  }
  useEffect(() => { load() }, [])

  async function toggleEnable(s: Source) {
    setBusy(s.id)
    try {
      const r = await fetch(`/api/v1/connectors/sources/${s.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: !s.enabled }) })
      if (!r.ok) throw new Error('Update failed')
      await load()
    } catch (e: any) { setError(e?.message || 'Failed to update') } finally { setBusy(null) }
  }

  async function importNow(s: Source) {
    setBusy(s.id)
    try {
      const r = await fetch(`/api/v1/connectors/sources/${s.id}/import`, { method: 'POST' })
      const j = await r.json()
      const jobId = j?.id
      if (jobId) window.location.href = `/connectors/jobs?job_id=${jobId}`
    } catch (e: any) { setError(e?.message || 'Failed to import') } finally { setBusy(null) }
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-xl font-semibold">Sources</h1>
      {error && <div className="text-red-600 text-sm">{error}</div>}
      <div className="grid grid-cols-1 gap-2">
        {sources.length === 0 && <div className="text-sm text-gray-500">No sources yet. Add from Browse.</div>}
        {sources.map(s => (
          <div key={s.id} className="flex items-center justify-between border rounded p-3">
            <div>
              <div className="font-medium">[{s.provider}] {s.path || s.remote_id}</div>
              <div className="text-xs text-gray-500">{s.type} • {s.enabled ? 'enabled' : 'disabled'} {s.last_synced_at ? `• ${s.last_synced_at}`: ''}</div>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => toggleEnable(s)} disabled={busy === s.id} className="px-3 py-1 rounded bg-gray-200">{s.enabled ? 'Disable' : 'Enable'}</button>
              <button onClick={() => importNow(s)} disabled={busy === s.id} className="px-3 py-1 rounded bg-blue-600 text-white">Import</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
