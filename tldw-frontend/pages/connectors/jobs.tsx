import { useEffect, useState } from 'react'
import { apiClient, getApiBaseUrl, buildAuthHeaders } from '@/lib/api'

type Job = { id: string; status: string; progress_percent?: number; counts?: Record<string, number> }

export default function Jobs() {
  const url = new URL(typeof window !== 'undefined' ? window.location.href : 'http://local/')
  const jobIdInit = url.searchParams.get('job_id') || ''
  const [jobId, setJobId] = useState(jobIdInit)
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notEnabled, setNotEnabled] = useState(false)

  async function load() {
    setError(null)
    if (!jobId) return
    try {
      const data = await apiClient.get<Job>(`/connectors/jobs/${jobId}`)
      setJob(data)
    } catch (e: any) {
      setError(e?.message || 'Failed to load job')
    }
  }

  useEffect(() => {
    const ping = async () => {
      try {
        const url = `${getApiBaseUrl()}/connectors/providers`
        const resp = await fetch(url, { headers: buildAuthHeaders('GET') })
        if (resp.status === 404) { setNotEnabled(true); return }
        await load()
      } catch {
        await load()
      }
    }
    ping()
  }, [jobId, load])

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-xl font-semibold">Import Job Status</h1>
      {notEnabled && (
        <div className="rounded border border-yellow-300 bg-yellow-50 p-3 text-sm text-yellow-800">
          Connectors backend not enabled. This feature is optional and may be disabled on your server.
        </div>
      )}
      <div className="flex items-center gap-2">
        <input value={jobId} onChange={e => setJobId(e.target.value)} placeholder="Job ID" className="border rounded px-2 py-1" />
        <button onClick={load} className="px-3 py-1 rounded bg-gray-800 text-white">Refresh</button>
      </div>
      {!notEnabled && error && <div className="text-red-600 text-sm">{error}</div>}
      {!notEnabled && job && (
        <div className="border rounded p-3">
          <div className="font-medium">Job {job.id}</div>
          <div className="text-sm">Status: {job.status} {typeof (job as any).progress_percent !== 'undefined' ? `• ${ (job as any).progress_percent }%` : ''}</div>
          {job.counts && (
            <div className="text-xs text-gray-600">Counts: processed {job.counts['processed'] || 0}, skipped {job.counts['skipped'] || 0}, failed {job.counts['failed'] || 0}</div>
          )}
        </div>
      )}
    </div>
  )
}
