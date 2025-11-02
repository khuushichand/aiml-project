import { useEffect, useMemo, useState } from 'react'

type Item = { id: string; name?: string; mimeType?: string; is_folder?: boolean; type?: string }

export default function Browse() {
  const url = new URL(typeof window !== 'undefined' ? window.location.href : 'http://local/')
  const providerInit = (url.searchParams.get('provider') as 'drive' | 'notion') || 'drive'
  const accountIdInit = Number(url.searchParams.get('account_id') || '0')
  const [provider, setProvider] = useState<'drive' | 'notion'>(providerInit)
  const [accountId, setAccountId] = useState<number>(accountIdInit)
  const [cursor, setCursor] = useState<string | null>(null)
  const [items, setItems] = useState<Item[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [parentId, setParentId] = useState<string | null>(null)

  const canBrowse = useMemo(() => accountId > 0 && ['drive','notion'].includes(provider), [accountId, provider])

  async function load(reset = false) {
    if (!canBrowse) return
    setBusy(true); setError(null)
    try {
      const params = new URLSearchParams()
      params.set('account_id', String(accountId))
      if (parentId) params.set('parent_remote_id', parentId)
      if (cursor && !reset) params.set('cursor', cursor)
      const r = await fetch(`/api/v1/connectors/providers/${provider}/sources/browse?` + params.toString())
      const j = await r.json()
      setItems(j.items || [])
      setCursor(j.next_cursor || null)
    } catch (e: any) {
      setError(e?.message || 'Browse failed')
    } finally { setBusy(false) }
  }

  useEffect(() => { load(true) }, [provider, accountId, parentId])

  async function addSource(item: Item) {
    const payload = {
      account_id: accountId,
      provider,
      remote_id: item.id,
      type: item.is_folder ? 'folder' : (item.type || 'page'),
      path: item.name || item.id,
      options: { recursive: true }
    }
    const r = await fetch('/api/v1/connectors/sources', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      throw new Error(j?.detail || 'Create source failed')
    }
    const s = await r.json()
    window.location.href = `/connectors/sources?sid=${s.id}`
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-xl font-semibold">Browse {provider} (Account {accountId})</h1>
      {error && <div className="text-red-600 text-sm">{error}</div>}
      <div className="flex gap-2 items-center">
        <label className="text-sm">Provider</label>
        <select value={provider} onChange={e => setProvider(e.target.value as any)} className="border rounded px-2 py-1">
          <option value="drive">drive</option>
          <option value="notion">notion</option>
        </select>
        <label className="text-sm">Account ID</label>
        <input value={accountId} onChange={e => setAccountId(Number(e.target.value))} className="border rounded px-2 py-1 w-28" />
        <label className="text-sm">Parent ID</label>
        <input value={parentId || ''} onChange={e => setParentId(e.target.value || null)} className="border rounded px-2 py-1" placeholder={provider === 'drive' ? 'root or folder id' : 'database id (optional)'} />
        <button onClick={() => load(true)} disabled={busy} className="px-3 py-1 rounded bg-gray-800 text-white">Refresh</button>
      </div>
      <div className="grid grid-cols-1 gap-2">
        {items.map(it => (
          <div key={it.id} className="flex items-center justify-between border rounded p-2">
            <div>
              <div className="font-medium">{it.name || it.id}</div>
              <div className="text-xs text-gray-500">{it.mimeType || it.type || ''}</div>
            </div>
            <div className="flex items-center gap-2">
              {provider === 'drive' && it.is_folder && (
                <button onClick={() => setParentId(it.id)} className="px-3 py-1 rounded bg-gray-200">Open</button>
              )}
              <button onClick={() => addSource(it)} className="px-3 py-1 rounded bg-blue-600 text-white">Add Source</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
