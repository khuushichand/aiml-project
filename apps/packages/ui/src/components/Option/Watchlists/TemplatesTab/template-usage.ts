import type { WatchlistJob } from "@/types/watchlists"

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null

const normalizeName = (value: unknown): string | null => {
  if (typeof value !== "string") return null
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed.toLowerCase() : null
}

const collectTemplateNames = (outputPrefs: unknown): Set<string> => {
  const names = new Set<string>()
  const root = asRecord(outputPrefs)
  if (!root) return names

  const directKeys = ["template_name", "mece_template_name", "tts_template_name"]
  directKeys.forEach((key) => {
    const normalized = normalizeName(root[key])
    if (normalized) names.add(normalized)
  })

  const templateBlock = asRecord(root.template)
  if (templateBlock) {
    const nestedKeys = ["default_name", "name"]
    nestedKeys.forEach((key) => {
      const normalized = normalizeName(templateBlock[key])
      if (normalized) names.add(normalized)
    })
  }

  return names
}

export interface TemplateUsage {
  id: number
  name: string
}

export const findActiveTemplateUsage = (
  jobs: Pick<WatchlistJob, "id" | "name" | "active" | "output_prefs">[],
  templateName: string
): TemplateUsage[] => {
  const normalizedTarget = normalizeName(templateName)
  if (!normalizedTarget) return []

  return jobs
    .filter((job) => job.active)
    .filter((job) => collectTemplateNames(job.output_prefs).has(normalizedTarget))
    .map((job) => ({ id: job.id, name: job.name }))
}
