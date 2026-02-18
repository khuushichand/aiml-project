export type PromptImportMode = "merge" | "replace"

export type PromptImportResultLike = {
  imported?: number | null
  skipped?: number | null
  failed?: number | null
}

export type PromptImportCounts = {
  imported: number
  skipped: number
  failed: number
}

export type PromptImportNotificationCopy = {
  key: string
  defaultValue: string
  values: PromptImportCounts
}

const toNonNegativeInt = (
  value: number | null | undefined,
  fallback: number
): number => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.max(0, Math.floor(value))
  }
  return Math.max(0, Math.floor(fallback))
}

export const normalizePromptImportCounts = (
  result: PromptImportResultLike | null | undefined,
  fallbackImportedCount: number
): PromptImportCounts => {
  return {
    imported: toNonNegativeInt(result?.imported, fallbackImportedCount),
    skipped: toNonNegativeInt(result?.skipped, 0),
    failed: toNonNegativeInt(result?.failed, 0)
  }
}

export const getPromptImportNotificationCopy = (
  mode: PromptImportMode,
  counts: PromptImportCounts
): PromptImportNotificationCopy => {
  if (mode === "replace") {
    return {
      key: "managePrompts.notification.replaceSuccessDetailedDesc",
      defaultValue:
        "Imported {{imported}}, skipped {{skipped}}, failed {{failed}}. Check your downloads for the backup file.",
      values: counts
    }
  }

  return {
    key: "managePrompts.notification.addSuccessDetailedDesc",
    defaultValue: "Imported {{imported}}, skipped {{skipped}}, failed {{failed}}.",
    values: counts
  }
}
