import type { ReadingDigestSchedule } from "@/types/collections"
import type {
  IngestionSourceItem,
  IngestionSourceItemsListResponse,
  IngestionSourceListResponse,
  IngestionSourceSummary,
  IngestionSourceSyncSummary,
  IngestionSourceSyncTriggerResponse
} from "@/types/ingestion-sources"

export const normalizeReadingDigestSchedule = (
  schedule: any
): ReadingDigestSchedule => ({
  ...schedule,
  id: String(schedule?.id ?? ""),
  name: schedule?.name ?? null,
  cron: String(schedule?.cron ?? ""),
  timezone: schedule?.timezone ?? null,
  enabled: Boolean(schedule?.enabled),
  require_online: Boolean(schedule?.require_online),
  format: schedule?.format === "html" ? "html" : "md",
  template_id:
    typeof schedule?.template_id === "number" &&
    Number.isFinite(schedule.template_id)
      ? schedule.template_id
      : null,
  template_name: schedule?.template_name ?? null,
  retention_days:
    typeof schedule?.retention_days === "number" &&
    Number.isFinite(schedule.retention_days)
      ? schedule.retention_days
      : null,
  filters:
    schedule?.filters &&
    typeof schedule.filters === "object" &&
    !Array.isArray(schedule.filters)
      ? schedule.filters
      : null,
  last_run_at: schedule?.last_run_at ?? null,
  next_run_at: schedule?.next_run_at ?? null,
  last_status: schedule?.last_status ?? null,
  created_at: schedule?.created_at ?? null,
  updated_at: schedule?.updated_at ?? null
})

export const toFiniteNumber = (value: unknown, fallback = 0): number => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value
  }
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }
  return fallback
}

export const toOptionalString = (value: unknown): string | null => {
  if (value === null || typeof value === "undefined") {
    return null
  }
  return String(value)
}

export const toRecord = (value: unknown): Record<string, unknown> => {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {}
  }
  return { ...(value as Record<string, unknown>) }
}

export const normalizeIngestionSourceSyncSummary = (
  summary: unknown
): IngestionSourceSyncSummary | null => {
  if (!summary || typeof summary !== "object" || Array.isArray(summary)) {
    return null
  }
  const record = summary as Record<string, unknown>
  return {
    changed_count: toFiniteNumber(record.changed_count),
    degraded_count: toFiniteNumber(record.degraded_count),
    conflict_count: toFiniteNumber(record.conflict_count),
    sink_failure_count: toFiniteNumber(record.sink_failure_count),
    ingestion_failure_count: toFiniteNumber(record.ingestion_failure_count),
    created_count: toFiniteNumber(record.created_count),
    updated_count: toFiniteNumber(record.updated_count),
    deleted_count: toFiniteNumber(record.deleted_count),
    unchanged_count: toFiniteNumber(record.unchanged_count)
  }
}

export const normalizeIngestionSourceType = (
  value: unknown
): IngestionSourceSummary["source_type"] => {
  if (value === "archive_snapshot" || value === "git_repository") {
    return value
  }
  return "local_directory"
}

export const normalizeIngestionSource = (
  source: any
): IngestionSourceSummary => ({
  id: String(source?.id ?? ""),
  user_id: toFiniteNumber(source?.user_id),
  source_type: normalizeIngestionSourceType(source?.source_type),
  sink_type: source?.sink_type === "notes" ? "notes" : "media",
  policy: source?.policy === "import_only" ? "import_only" : "canonical",
  enabled: Boolean(source?.enabled),
  schedule_enabled: Boolean(source?.schedule_enabled),
  schedule_config: toRecord(source?.schedule_config),
  config: toRecord(source?.config),
  active_job_id: toOptionalString(source?.active_job_id),
  last_successful_snapshot_id: toOptionalString(
    source?.last_successful_snapshot_id
  ),
  last_sync_started_at: toOptionalString(source?.last_sync_started_at),
  last_sync_completed_at: toOptionalString(source?.last_sync_completed_at),
  last_sync_status: toOptionalString(source?.last_sync_status),
  last_error: toOptionalString(source?.last_error),
  last_successful_sync_summary: normalizeIngestionSourceSyncSummary(
    source?.last_successful_sync_summary
  ),
  created_at: toOptionalString(source?.created_at),
  updated_at: toOptionalString(source?.updated_at)
})

export const normalizeIngestionSourceListResponse = (
  payload: any
): IngestionSourceListResponse => {
  const rawSources = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.sources)
      ? payload.sources
      : []
  const sources = rawSources.map((source: any) =>
    normalizeIngestionSource(source)
  )
  return {
    sources,
    total: toFiniteNumber(payload?.total, sources.length)
  }
}

export const normalizeIngestionSourceItem = (
  item: any
): IngestionSourceItem => ({
  id: String(item?.id ?? ""),
  source_id: String(item?.source_id ?? ""),
  normalized_relative_path: String(item?.normalized_relative_path ?? ""),
  content_hash: item?.content_hash == null ? null : String(item.content_hash),
  sync_status: String(item?.sync_status ?? "unknown"),
  binding: toRecord(item?.binding),
  present_in_source: Boolean(item?.present_in_source),
  created_at: toOptionalString(item?.created_at),
  updated_at: toOptionalString(item?.updated_at)
})

export const normalizeIngestionSourceItemsListResponse = (
  payload: any
): IngestionSourceItemsListResponse => {
  const rawItems = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.items)
      ? payload.items
      : []
  const items = rawItems.map((item: any) => normalizeIngestionSourceItem(item))
  return {
    items,
    total: toFiniteNumber(payload?.total, items.length)
  }
}

export const normalizeIngestionSourceSyncTrigger = (
  payload: any
): IngestionSourceSyncTriggerResponse => ({
  status: String(payload?.status ?? ""),
  source_id: String(payload?.source_id ?? ""),
  job_id: toOptionalString(payload?.job_id),
  snapshot_status: toOptionalString(payload?.snapshot_status)
})
