export type OpmlPreflightStatus =
  | "ready"
  | "duplicate_existing"
  | "duplicate_file"
  | "missing_url"
  | "invalid_url"

export interface OpmlPreflightItem {
  name: string
  url: string
  status: OpmlPreflightStatus
}

export interface OpmlPreflightSummary {
  items: OpmlPreflightItem[]
  total: number
  ready: number
  duplicateExisting: number
  duplicateFile: number
  missingUrl: number
  invalidUrl: number
  parseError: boolean
}

interface BuildOpmlPreflightOptions {
  existingUrls?: Iterable<string>
}

const OUTLINE_TAG_REGEX = /<outline\b([^>]*)>/gi
const ATTRIBUTE_REGEX = /([a-zA-Z_:][\w:.-]*)\s*=\s*(['"])(.*?)\2/g

const asNormalizedKey = (value: string): string => {
  try {
    const parsed = new URL(value.trim())
    parsed.hash = ""
    return parsed.toString()
  } catch {
    return ""
  }
}

const parseOutlineAttributes = (rawAttributes: string): Record<string, string> => {
  const attrs: Record<string, string> = {}
  let match: RegExpExecArray | null = null
  ATTRIBUTE_REGEX.lastIndex = 0
  while ((match = ATTRIBUTE_REGEX.exec(rawAttributes)) !== null) {
    const key = String(match[1] || "").toLowerCase()
    const value = String(match[3] || "").trim()
    attrs[key] = value
  }
  return attrs
}

export const buildOpmlPreflightSummary = (
  rawOpml: string,
  options: BuildOpmlPreflightOptions = {}
): OpmlPreflightSummary => {
  const existingSet = new Set<string>()
  for (const existingUrl of options.existingUrls || []) {
    const normalized = asNormalizedKey(existingUrl)
    if (normalized) existingSet.add(normalized)
  }

  const items: OpmlPreflightItem[] = []
  const seenInFile = new Set<string>()
  let parseError = false
  let match: RegExpExecArray | null = null
  let foundOutline = false

  OUTLINE_TAG_REGEX.lastIndex = 0
  while ((match = OUTLINE_TAG_REGEX.exec(rawOpml)) !== null) {
    foundOutline = true
    const attrs = parseOutlineAttributes(String(match[1] || ""))
    const rawUrl = String(attrs.xmlurl || "").trim()
    const label = String(attrs.title || attrs.text || rawUrl || "Untitled")

    if (!rawUrl) {
      items.push({ name: label, url: "", status: "missing_url" })
      continue
    }

    const normalized = asNormalizedKey(rawUrl)
    if (!normalized) {
      items.push({ name: label, url: rawUrl, status: "invalid_url" })
      continue
    }

    if (existingSet.has(normalized)) {
      items.push({ name: label, url: rawUrl, status: "duplicate_existing" })
      continue
    }

    if (seenInFile.has(normalized)) {
      items.push({ name: label, url: rawUrl, status: "duplicate_file" })
      continue
    }

    seenInFile.add(normalized)
    items.push({ name: label, url: rawUrl, status: "ready" })
  }

  if (!foundOutline && rawOpml.trim().length > 0) {
    parseError = true
  }

  const ready = items.filter((item) => item.status === "ready").length
  const duplicateExisting = items.filter((item) => item.status === "duplicate_existing").length
  const duplicateFile = items.filter((item) => item.status === "duplicate_file").length
  const missingUrl = items.filter((item) => item.status === "missing_url").length
  const invalidUrl = items.filter((item) => item.status === "invalid_url").length

  return {
    items,
    total: items.length,
    ready,
    duplicateExisting,
    duplicateFile,
    missingUrl,
    invalidUrl,
    parseError
  }
}
