import type { ReadingItemsBulkResponse } from "@/types/collections"

export const normalizeBulkTags = (raw: string): string[] => {
  if (!raw) return []
  const tags = raw
    .split(",")
    .map((entry) => entry.trim().toLowerCase())
    .filter((entry) => entry.length > 0)
  return Array.from(new Set(tags))
}

export const getBulkFailureLines = (
  response: ReadingItemsBulkResponse,
  maxLines = 10
): string[] => {
  if (!Array.isArray(response.results) || maxLines <= 0) return []
  return response.results
    .filter((entry) => !entry.success)
    .slice(0, maxLines)
    .map((entry) => `#${entry.item_id}: ${entry.error || "update_failed"}`)
}
