import type { WatchlistJob, WatchlistJobCreate } from "@/types/watchlists"

export const JOB_DELETE_UNDO_WINDOW_SECONDS = 10

export const toJobCreatePayload = (job: WatchlistJob): WatchlistJobCreate => ({
  name: job.name,
  description: job.description ?? undefined,
  scope: {
    sources: job.scope.sources ? [...job.scope.sources] : undefined,
    groups: job.scope.groups ? [...job.scope.groups] : undefined,
    tags: job.scope.tags ? [...job.scope.tags] : undefined
  },
  schedule_expr: job.schedule_expr ?? undefined,
  timezone: job.timezone ?? undefined,
  active: job.active,
  max_concurrency: job.max_concurrency ?? undefined,
  per_host_delay_ms: job.per_host_delay_ms ?? undefined,
  retry_policy: job.retry_policy ?? undefined,
  output_prefs: job.output_prefs ?? undefined,
  job_filters: job.job_filters ?? undefined
})
