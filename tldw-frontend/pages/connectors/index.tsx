import { useEffect, useState } from 'react'

type Provider = { name: 'drive' | 'notion'; auth_type: 'oauth2'; scopes_required: string[] }
type Account = { id: number; provider: 'drive' | 'notion'; display_name: string; email?: string; created_at?: string }

export default function ConnectorsHome() {
  const [providers, setProviders] = useState<Provider[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setError(null)
    try {
      const p = await fetch('/api/v1/connectors/providers').then(r => r.json())
      setProviders(p)
      const a = await fetch('/api/v1/connectors/accounts').then(r => r.json())
      setAccounts(a)
    } catch (e: any) {
      setError(e?.message || 'Failed to load')
    }
  }

  useEffect(() => { load() }, [])

  async function startAuthorize(provider: 'drive' | 'notion') {
    setBusy(true)
    try {
      const r = await fetch(`/api/v1/connectors/providers/${provider}/authorize`, { method: 'POST' })
      const j = await r.json()
      if (j?.auth_url) {
        window.location.href = j.auth_url
      }
    } catch (e: any) {
      setError(e?.message || 'Authorize failed')
    } finally { setBusy(false) }
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-xl font-semibold">External Connectors</h1>
      {error && <div className="text-red-600 text-sm">{error}</div>}

      <section>
        <h2 className="text-lg font-medium">Providers</h2>
        <div className="mt-2 grid grid-cols-1 gap-3">
          {providers.map(p => (
            <div key={p.name} className="flex items-center justify-between rounded border p-3">
              <div>
                <div className="font-medium">{p.name}</div>
                <div className="text-xs text-gray-500">{p.scopes_required?.join(', ') || 'no scopes'}</div>
              </div>
              <button disabled={busy} onClick={() => startAuthorize(p.name)} className="px-3 py-1 rounded bg-blue-600 text-white disabled:opacity-50">Connect</button>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-lg font-medium">Linked Accounts</h2>
        <div className="mt-2 grid grid-cols-1 gap-3">
          {accounts.length === 0 && <div className="text-sm text-gray-500">No accounts linked yet.</div>}
          {accounts.map(a => (
            <div key={a.id} className="flex items-center justify-between rounded border p-3">
              <div>
                <div className="font-medium">{a.display_name}</div>
                <div className="text-xs text-gray-500">{a.provider} {a.email ? `• ${a.email}` : ''}</div>
              </div>
              <a href={`/connectors/browse?provider=${a.provider}&account_id=${a.id}`} className="px-3 py-1 rounded bg-gray-800 text-white">Browse</a>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
