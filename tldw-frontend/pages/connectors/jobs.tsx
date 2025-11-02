import { useEffect, useState } from 'react'

type Job = { id: string; status: string; progress_percent?: number; counts?: Record<string, number> }

export default function Jobs() {
  const url = new URL(typeof window !== 'undefined' ? window.location.href : 'http://local/')
  const jobIdInit = url.searchParams.get('job_id') || ''
  const [jobId, setJobId] = useState(jobIdInit)
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setError(null)
    if (!jobId) return
    try {
      const r = await fetch(`/api/v1/connectors/jobs/${jobId}`)
      if (!r.ok) throw new Error(`Job fetch failed (${r.status})`)
      setJob(await r.json())
    } catch (e: any) {
      setError(e?.message || 'Failed to load job')
    }
  }

  useEffect(() => { load() }, [jobId])

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-xl font-semibold">Import Job Status</h1>
      <div className="flex items-center gap-2">
        <input value={jobId} onChange={e => setJobId(e.target.value)} placeholder="Job ID" className="border rounded px-2 py-1" />
        <button onClick={load} className="px-3 py-1 rounded bg-gray-800 text-white">Refresh</button>
      </div>
      {error && <div className="text-red-600 text-sm">{error}</div>}
      {job && (
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
