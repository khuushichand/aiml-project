import { validateDictionaryImportData } from "../importValidationUtils"

export type DictionaryImportFormat = "json" | "markdown"
export type DictionaryImportMode = "file" | "paste"

export type DictionaryImportPreview = {
  format: DictionaryImportFormat
  payload:
    | { kind: "json"; data: any }
    | { kind: "markdown"; name: string; content: string }
  summary: {
    name: string
    entryCount: number
    groups: string[]
    hasAdvancedFields: boolean
  }
}

export type DictionaryImportConflictResolution = {
  preview: DictionaryImportPreview
  suggestedName: string
} | null

type BuildDictionaryImportPreviewParams = {
  importFormat: DictionaryImportFormat
  importMode: DictionaryImportMode
  importSourceContent: string
  importMarkdownName: string
}

type BuildDictionaryImportPreviewResult = {
  preview: DictionaryImportPreview | null
  errors: string[]
}

export function extractFileStem(fileName: string): string {
  const trimmed = fileName.trim()
  if (!trimmed) return "Imported Dictionary"
  const dotIndex = trimmed.lastIndexOf(".")
  if (dotIndex <= 0) return trimmed
  return trimmed.slice(0, dotIndex)
}

function hasAdvancedDictionaryEntryFields(entries: any[]): boolean {
  return entries.some((entry: any) => {
    const probability = typeof entry?.probability === "number" ? entry.probability : 1
    const caseSensitive =
      typeof entry?.case_sensitive === "boolean" ? entry.case_sensitive : undefined
    const maxReplacements =
      Number.isInteger(entry?.max_replacements) && entry.max_replacements > 0
    const timedEffects =
      entry?.timed_effects &&
      typeof entry.timed_effects === "object" &&
      ["sticky", "cooldown", "delay"].some((key) => {
        const value = Number((entry.timed_effects as any)?.[key])
        return Number.isFinite(value) && value > 0
      })
    return probability !== 1 || maxReplacements || timedEffects || caseSensitive === false
  })
}

function buildImportPreviewSummaryFromJSON(data: any) {
  const normalizedName =
    String(data?.name || "Imported Dictionary").trim() || "Imported Dictionary"
  const entries = Array.isArray(data?.entries) ? data.entries : []
  const groups: string[] = Array.from(
    new Set(
      entries
        .map((entry: any) =>
          typeof entry?.group === "string" ? entry.group.trim() : ""
        )
        .filter((group: string) => group.length > 0)
    )
  )
  const hasAdvancedFields = hasAdvancedDictionaryEntryFields(entries)

  return {
    name: normalizedName,
    entryCount: entries.length,
    groups,
    hasAdvancedFields,
  }
}

function buildImportPreviewSummaryFromMarkdown(content: string, fallbackName?: string) {
  const headingMatch = content.match(/^#\s+(.+)$/m)
  const detectedName = headingMatch?.[1]?.trim()
  const fallback = fallbackName?.trim()
  const name = detectedName || fallback || "Imported Dictionary"
  const entryMatches = content.match(/^##\s*Entry:/gm)
  const legacyEntryMatches = content.split("\n").filter((line) => {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith("#")) return false
    return trimmed.includes(":")
  })
  const groups = Array.from(
    new Set(
      Array.from(content.matchAll(/^##\s+(?!Entry:)(.+)$/gm))
        .map((match) => match[1]?.trim())
        .filter((group): group is string => Boolean(group))
    )
  )
  const hasAdvancedFields =
    /-\s+\*\*(Probability|Type|Enabled)\*\*:/.test(content) ||
    /\/.+\/[gimsuvy]*/.test(content)

  return {
    name,
    entryCount: entryMatches ? entryMatches.length : legacyEntryMatches.length,
    groups,
    hasAdvancedFields,
  }
}

export function buildDictionaryImportPreview({
  importFormat,
  importMode,
  importSourceContent,
  importMarkdownName,
}: BuildDictionaryImportPreviewParams): BuildDictionaryImportPreviewResult {
  const trimmedSource = importSourceContent.trim()
  if (!trimmedSource) {
    return {
      preview: null,
      errors: [
        importMode === "file"
          ? "Select a file before generating an import preview."
          : "Paste dictionary content before generating an import preview.",
      ],
    }
  }

  if (importFormat === "json") {
    try {
      const parsed = JSON.parse(trimmedSource)
      const validation = validateDictionaryImportData(parsed)
      if (!validation.valid) {
        return {
          preview: null,
          errors: validation.errors,
        }
      }
      return {
        preview: {
          format: "json",
          payload: {
            kind: "json",
            data: validation.normalizedData,
          },
          summary: buildImportPreviewSummaryFromJSON(validation.normalizedData),
        },
        errors: [],
      }
    } catch (error: any) {
      const parseMessage =
        error instanceof Error && error.message ? error.message : "Unable to parse JSON"
      return {
        preview: null,
        errors: [
          `Invalid JSON syntax: ${parseMessage}`,
          "Expected top-level fields: `name` and `entries`.",
        ],
      }
    }
  }

  const summary = buildImportPreviewSummaryFromMarkdown(trimmedSource, importMarkdownName)
  return {
    preview: {
      format: "markdown",
      payload: {
        kind: "markdown",
        name: summary.name,
        content: trimmedSource,
      },
      summary,
    },
    errors: [],
  }
}

export function buildRenamedImportPreview(
  preview: DictionaryImportPreview,
  nextName: string
): DictionaryImportPreview {
  return {
    ...preview,
    summary: {
      ...preview.summary,
      name: nextName,
    },
    payload:
      preview.payload.kind === "json"
        ? {
            kind: "json",
            data: {
              ...preview.payload.data,
              name: nextName,
            },
          }
        : {
            kind: "markdown",
            name: nextName,
            content: preview.payload.content,
          },
  }
}
