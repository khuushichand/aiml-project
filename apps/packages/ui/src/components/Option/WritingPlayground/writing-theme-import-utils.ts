const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

export type ImportedThemeItem = {
  name: string
  className: string | null
  css: string | null
  schemaVersion: number
  isDefault: boolean
  order: number
}

const toThemeItem = (
  item: Record<string, unknown>,
  fallbackName?: string
): ImportedThemeItem | null => {
  const nameCandidate =
    typeof item.name === "string" && item.name.trim().length > 0
      ? item.name.trim()
      : typeof item.title === "string" && item.title.trim().length > 0
        ? item.title.trim()
        : typeof fallbackName === "string" && fallbackName.trim().length > 0
          ? fallbackName.trim()
          : ""
  if (!nameCandidate) return null

  const rawClassName =
    (item as { class_name?: unknown; className?: unknown }).class_name ??
    (item as { className?: unknown }).className
  const rawCss = (item as { css?: unknown }).css
  const rawSchemaVersion =
    (item as { schema_version?: unknown; schemaVersion?: unknown })
      .schema_version ??
    (item as { schemaVersion?: unknown }).schemaVersion
  const rawIsDefault =
    (item as { is_default?: unknown; isDefault?: unknown }).is_default ??
    (item as { isDefault?: unknown }).isDefault
  const rawOrder = (item as { order?: unknown }).order

  const schemaVersion =
    typeof rawSchemaVersion === "number" && Number.isFinite(rawSchemaVersion)
      ? rawSchemaVersion
      : 1
  const isDefault =
    typeof rawIsDefault === "boolean"
      ? rawIsDefault
      : typeof rawIsDefault === "string"
        ? rawIsDefault.trim().toLowerCase() === "true"
        : false
  const order =
    typeof rawOrder === "number" && Number.isFinite(rawOrder) ? rawOrder : 0

  return {
    name: nameCandidate,
    className: typeof rawClassName === "string" ? rawClassName : null,
    css: typeof rawCss === "string" ? rawCss : null,
    schemaVersion,
    isDefault,
    order
  }
}

const toThemeItemsFromArray = (value: unknown[]): ImportedThemeItem[] => {
  const out: ImportedThemeItem[] = []
  for (const item of value) {
    if (!isRecord(item)) continue
    const normalized = toThemeItem(item)
    if (normalized) out.push(normalized)
  }
  return out
}

const toThemeItemsFromMap = (
  value: Record<string, unknown>
): ImportedThemeItem[] => {
  const out: ImportedThemeItem[] = []
  for (const [name, item] of Object.entries(value)) {
    if (!isRecord(item)) continue
    const normalized = toThemeItem(item, name)
    if (normalized) out.push(normalized)
  }
  return out
}

const isThemePayloadLike = (value: Record<string, unknown>): boolean =>
  "css" in value ||
  "className" in value ||
  "class_name" in value ||
  "isDefault" in value ||
  "is_default" in value

export const extractImportedThemeItems = (value: unknown): ImportedThemeItem[] => {
  if (Array.isArray(value)) {
    return toThemeItemsFromArray(value)
  }
  if (!isRecord(value)) {
    return []
  }

  if (Array.isArray(value.themes)) {
    return toThemeItemsFromArray(value.themes)
  }
  if (isRecord(value.themes)) {
    return toThemeItemsFromMap(value.themes)
  }

  const single = toThemeItem(value)
  if (single) {
    return [single]
  }

  const entries = Object.entries(value)
  if (entries.length === 0) return []
  const recordEntries = entries.filter(
    (entry): entry is [string, Record<string, unknown>] => isRecord(entry[1])
  )
  if (recordEntries.length !== entries.length) {
    return []
  }
  if (!recordEntries.every(([, item]) => isThemePayloadLike(item))) {
    return []
  }
  return toThemeItemsFromMap(value)
}
