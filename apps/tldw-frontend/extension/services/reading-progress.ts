import { createLocalRegistryBucket } from "@/services/settings/local-bucket"

export type ReadingProgress = {
  percent: number
  scrollTop: number
  scrollHeight: number
  clientHeight: number
}

export type ReadingProgressRecord = ReadingProgress & { updatedAt: number }

const BUCKET_PREFIX = "registry:reading-progress:"

const progressBucket = createLocalRegistryBucket<ReadingProgress>({
  prefix: BUCKET_PREFIX
})

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value))

const isValidProgress = (value: unknown): value is ReadingProgress => {
  if (!value || typeof value !== "object") return false
  const payload = value as ReadingProgress
  return (
    Number.isFinite(payload.percent) &&
    Number.isFinite(payload.scrollTop) &&
    Number.isFinite(payload.scrollHeight) &&
    Number.isFinite(payload.clientHeight)
  )
}

const normalizeProgress = (progress: ReadingProgress): ReadingProgress => {
  return {
    percent: clamp(progress.percent, 0, 100),
    scrollTop: Math.max(0, progress.scrollTop),
    scrollHeight: Math.max(0, progress.scrollHeight),
    clientHeight: Math.max(0, progress.clientHeight)
  }
}

export const getReadingProgress = async (
  itemId: string
): Promise<ReadingProgressRecord | null> => {
  if (!itemId) return null
  const record = await progressBucket.get(String(itemId))
  if (!record || !isValidProgress(record.value)) return null
  return {
    ...normalizeProgress(record.value),
    updatedAt: record.updatedAt
  }
}

export const setReadingProgress = async (
  itemId: string,
  progress: ReadingProgress
): Promise<void> => {
  if (!itemId || !isValidProgress(progress)) return
  await progressBucket.set(String(itemId), normalizeProgress(progress))
}

export const clearReadingProgress = async (itemId: string): Promise<void> => {
  if (!itemId) return
  await progressBucket.remove(String(itemId))
}
