import type { WizardQueueItem } from "./types"

/**
 * Base processing time estimators by media type.
 * Each function takes file size in bytes and returns estimated seconds.
 */
const BASE_ESTIMATORS: Record<string, (sizeBytes: number) => number> = {
  document: (s) => 3 + (s / 1_000_000) * 0.5,
  audio: (s) => 10 + (s / 1_000_000) * 2.0,
  video: (s) => 15 + (s / 1_000_000) * 3.0,
  url: (_) => 8,
  web: (_) => 8,
  pdf: (s) => 3 + (s / 1_000_000) * 0.8,
  ebook: (s) => 5 + (s / 1_000_000) * 1.0,
  image: (s) => 2 + (s / 1_000_000) * 0.3,
}

/**
 * Preset speed multipliers.
 * Quick does less work, deep does significantly more.
 */
const PRESET_MULTIPLIERS: Record<string, number> = {
  quick: 0.5,
  standard: 1.0,
  deep: 2.5,
}

const DEFAULT_BASE_SECONDS = 5
const DEFAULT_MULTIPLIER = 1.0

/**
 * Estimate processing time in seconds for a single item.
 *
 * @param fileSize  - File size in bytes (0 for URLs).
 * @param mediaType - Detected media type string (e.g. "audio", "video", "pdf").
 * @param preset    - Preset identifier ("quick", "standard", "deep", or "custom").
 * @returns Estimated seconds (always >= 0).
 */
export function estimateIngestSeconds(
  fileSize: number,
  mediaType: string,
  preset: string
): number {
  const estimator = BASE_ESTIMATORS[mediaType]
  const baseSeconds = estimator ? estimator(fileSize) : DEFAULT_BASE_SECONDS
  const multiplier = PRESET_MULTIPLIERS[preset] ?? DEFAULT_MULTIPLIER
  return Math.max(0, baseSeconds * multiplier)
}

/**
 * Estimate total processing time for a list of queue items.
 *
 * @param items  - Array of wizard queue items.
 * @param preset - Preset identifier.
 * @returns Total estimated seconds (sum of per-item estimates).
 */
export function estimateTotalSeconds(
  items: WizardQueueItem[],
  preset: string
): number {
  return items.reduce(
    (total, item) =>
      total + estimateIngestSeconds(item.fileSize, item.detectedType, preset),
    0
  )
}

/**
 * Format an estimate in seconds into a human-readable string.
 *
 * @param seconds - Estimated seconds (may be fractional).
 * @returns A string like "~5 sec", "~3 min", or "~1 hr".
 */
export function formatEstimate(seconds: number): string {
  const rounded = Math.round(seconds)
  if (rounded < 60) {
    return `~${rounded} sec`
  }
  if (rounded < 3600) {
    const minutes = Math.round(rounded / 60)
    return `~${minutes} min`
  }
  const hours = Math.round(rounded / 3600)
  return `~${hours} hr`
}
