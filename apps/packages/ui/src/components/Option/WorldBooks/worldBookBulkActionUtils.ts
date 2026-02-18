export const clampBulkPriority = (value: unknown, fallback = 50): number => {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return fallback
  return Math.max(0, Math.min(100, Math.round(numeric)))
}

export const normalizeBulkEntryIds = (entryIds: unknown): number[] => {
  if (!Array.isArray(entryIds)) return []
  return entryIds
    .map((id) => Number(id))
    .filter((id) => Number.isFinite(id) && id > 0)
}

export const buildBulkSetPriorityPayload = (
  entryIds: unknown,
  priority: unknown
): { entry_ids: number[]; operation: "set_priority"; priority: number } => ({
  entry_ids: normalizeBulkEntryIds(entryIds),
  operation: "set_priority",
  priority: clampBulkPriority(priority)
})
