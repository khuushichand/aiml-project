import type { SkillResponse } from "@/types/skill"

const SUPPORTING_FILE_NAME_REGEX = /^[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}$/

export interface SupportingFileFormEntry {
  filename?: string
  content?: string
  originalFilename?: string
}

const quoteYamlString = (value: string): string => JSON.stringify(value)

const pushYamlLine = (lines: string[], key: string, value: string | null | undefined): void => {
  if (typeof value !== "string") return
  const trimmed = value.trim()
  if (!trimmed) return
  lines.push(`${key}: ${quoteYamlString(trimmed)}`)
}

const serializeSkillFrontmatter = (skill: SkillResponse): string => {
  const lines: string[] = [`name: ${quoteYamlString(skill.name)}`]

  pushYamlLine(lines, "description", skill.description)
  pushYamlLine(lines, "argument-hint", skill.argument_hint)

  if (skill.disable_model_invocation) {
    lines.push("disable-model-invocation: true")
  }
  if (!skill.user_invocable) {
    lines.push("user-invocable: false")
  }
  if (skill.allowed_tools && skill.allowed_tools.length > 0) {
    lines.push(`allowed-tools: ${quoteYamlString(skill.allowed_tools.join(", "))}`)
  }
  pushYamlLine(lines, "model", skill.model)

  if (skill.context === "fork") {
    lines.push("context: fork")
  }

  return lines.join("\n")
}

export const buildInitialSkillContent = (skill: SkillResponse): string => {
  if (skill.raw_content && skill.raw_content.trim()) {
    return skill.raw_content
  }
  const frontmatter = serializeSkillFrontmatter(skill)
  const body = skill.content || ""
  return `---\n${frontmatter}\n---\n\n${body}`
}

const validateSupportingFilename = (filename: string): void => {
  if (!SUPPORTING_FILE_NAME_REGEX.test(filename)) {
    throw new Error(
      "Supporting file names must be 1-100 chars and use letters, numbers, dot, underscore, or hyphen."
    )
  }
  if (filename.toLowerCase() === "skill.md") {
    throw new Error("SKILL.md is reserved and cannot be used as a supporting file name.")
  }
}

const normalizeSupportingRows = (
  rows: SupportingFileFormEntry[] | undefined
): SupportingFileFormEntry[] => {
  const entries = rows ?? []
  const dedupe = new Set<string>()
  const normalized: SupportingFileFormEntry[] = []

  for (const row of entries) {
    const filename = (row.filename ?? "").trim()
    const content = row.content ?? ""
    const originalFilename = (row.originalFilename ?? "").trim()

    if (!filename && !content && !originalFilename) {
      continue
    }
    if (!filename) {
      throw new Error("Each supporting file needs a filename.")
    }

    validateSupportingFilename(filename)

    if (dedupe.has(filename)) {
      throw new Error(`Duplicate supporting file name: ${filename}`)
    }
    dedupe.add(filename)

    normalized.push({
      filename,
      content,
      originalFilename: originalFilename || undefined
    })
  }

  return normalized
}

export const buildSupportingFilesForCreate = (
  rows: SupportingFileFormEntry[] | undefined
): Record<string, string> | undefined => {
  const normalized = normalizeSupportingRows(rows)
  if (!normalized.length) {
    return undefined
  }

  const files: Record<string, string> = {}
  for (const row of normalized) {
    files[row.filename!] = row.content ?? ""
  }
  return Object.keys(files).length ? files : undefined
}

export const buildSupportingFilesForUpdate = (
  initialFiles: Record<string, string> | null | undefined,
  rows: SupportingFileFormEntry[] | undefined
): Record<string, string | null> | undefined => {
  const initial = initialFiles ?? {}
  const normalized = normalizeSupportingRows(rows)
  const remainingInitial = new Set(Object.keys(initial))
  const updates: Record<string, string | null> = {}

  for (const row of normalized) {
    const filename = row.filename!
    const content = row.content ?? ""
    const originalFilename = row.originalFilename

    if (originalFilename && Object.prototype.hasOwnProperty.call(initial, originalFilename)) {
      remainingInitial.delete(originalFilename)
      if (filename !== originalFilename) {
        updates[originalFilename] = null
        updates[filename] = content
      } else if (initial[originalFilename] !== content) {
        updates[filename] = content
      }
      continue
    }

    if (!Object.prototype.hasOwnProperty.call(initial, filename) || initial[filename] !== content) {
      updates[filename] = content
    }
  }

  for (const deletedName of remainingInitial) {
    updates[deletedName] = null
  }

  return Object.keys(updates).length ? updates : undefined
}
