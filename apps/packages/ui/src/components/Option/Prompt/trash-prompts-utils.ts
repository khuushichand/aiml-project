export type TrashPromptLike = {
  name?: string | null
  title?: string | null
  deletedAt?: number | null
}

export const TRASH_AUTO_PURGE_DAYS = 30
const DAY_MS = 24 * 60 * 60 * 1000

export const filterTrashPromptsByName = <T extends TrashPromptLike>(
  prompts: T[],
  query: string
): T[] => {
  const normalized = query.trim().toLowerCase()
  if (!normalized) {
    return prompts
  }

  return prompts.filter((prompt) => {
    const haystack = [prompt?.name, prompt?.title]
    return haystack.some((field) =>
      typeof field === "string" ? field.toLowerCase().includes(normalized) : false
    )
  })
}

export const getTrashDaysSinceDeleted = (
  deletedAt: number | null | undefined,
  nowMs = Date.now()
): number => {
  if (typeof deletedAt !== "number" || Number.isNaN(deletedAt)) {
    return 0
  }
  const diffMs = Math.max(0, nowMs - deletedAt)
  return Math.floor(diffMs / DAY_MS)
}

export const getTrashDaysRemaining = (
  deletedAt: number | null | undefined,
  nowMs = Date.now(),
  retentionDays = TRASH_AUTO_PURGE_DAYS
): number => {
  const daysSinceDeleted = getTrashDaysSinceDeleted(deletedAt, nowMs)
  return Math.max(0, retentionDays - daysSinceDeleted)
}

export type TrashRemainingSeverity = "danger" | "warning" | "normal"

export const getTrashRemainingSeverity = (
  daysRemaining: number
): TrashRemainingSeverity => {
  if (daysRemaining <= 7) {
    return "danger"
  }
  if (daysRemaining <= 14) {
    return "warning"
  }
  return "normal"
}
