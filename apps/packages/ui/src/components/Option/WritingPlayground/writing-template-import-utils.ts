const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

export type ImportedTemplateItem = {
  name: string
  payload: Record<string, unknown>
  schemaVersion: number
  isDefault: boolean
}

const TEMPLATE_METADATA_KEYS = new Set([
  "id",
  "name",
  "title",
  "payload",
  "schema_version",
  "schemaVersion",
  "version",
  "is_default",
  "isDefault"
])

const TEMPLATE_PAYLOAD_HINT_KEYS = new Set([
  "sys_pre",
  "sysPre",
  "sys_prefix",
  "system_prefix",
  "systemPrefix",
  "sys_suf",
  "sysSuf",
  "sys_suffix",
  "system_suffix",
  "systemSuffix",
  "inst_pre",
  "instPre",
  "user_prefix",
  "userPrefix",
  "inst_suf",
  "instSuf",
  "assistant_prefix",
  "assistantPrefix",
  "assistant_pre",
  "assistantPre",
  "user_suffix",
  "userSuffix",
  "assistant_suffix",
  "assistantSuffix",
  "assistant_suf",
  "assistantSuf",
  "fim_template",
  "fimTemplate",
  "fim"
])

const toTemplatePayload = (item: Record<string, unknown>): Record<string, unknown> => {
  if (isRecord(item.payload)) {
    return item.payload
  }
  const payload: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(item)) {
    if (TEMPLATE_METADATA_KEYS.has(key)) continue
    payload[key] = value
  }
  return payload
}

const toTemplateItem = (
  item: Record<string, unknown>,
  fallbackName?: string
): ImportedTemplateItem | null => {
  const nameCandidate =
    typeof item.name === "string" && item.name.trim().length > 0
      ? item.name.trim()
      : typeof item.title === "string" && item.title.trim().length > 0
        ? item.title.trim()
        : typeof fallbackName === "string" && fallbackName.trim().length > 0
          ? fallbackName.trim()
          : ""
  if (!nameCandidate) return null

  const payload = toTemplatePayload(item)
  const schemaVersion =
    typeof item.schema_version === "number"
      ? item.schema_version
      : typeof item.schemaVersion === "number"
        ? item.schemaVersion
        : 1
  const isDefault =
    typeof item.is_default === "boolean"
      ? item.is_default
      : typeof item.isDefault === "boolean"
        ? item.isDefault
        : false

  return {
    name: nameCandidate,
    payload,
    schemaVersion,
    isDefault
  }
}

const isTemplatePayloadLike = (value: Record<string, unknown>): boolean =>
  Object.keys(value).some((key) => TEMPLATE_PAYLOAD_HINT_KEYS.has(key))

const toTemplateItemsFromArray = (value: unknown[]): ImportedTemplateItem[] => {
  const out: ImportedTemplateItem[] = []
  for (const item of value) {
    if (!isRecord(item)) continue
    const normalized = toTemplateItem(item)
    if (normalized) out.push(normalized)
  }
  return out
}

const toTemplateItemsFromMap = (
  value: Record<string, unknown>
): ImportedTemplateItem[] => {
  const out: ImportedTemplateItem[] = []
  for (const [name, item] of Object.entries(value)) {
    if (!isRecord(item)) continue
    const normalized = toTemplateItem(item, name)
    if (normalized) out.push(normalized)
  }
  return out
}

export const extractImportedTemplateItems = (
  value: unknown
): ImportedTemplateItem[] => {
  if (Array.isArray(value)) {
    return toTemplateItemsFromArray(value)
  }
  if (!isRecord(value)) {
    return []
  }

  if (Array.isArray(value.templates)) {
    return toTemplateItemsFromArray(value.templates)
  }
  if (isRecord(value.templates)) {
    return toTemplateItemsFromMap(value.templates)
  }

  if (isRecord(value.instructTemplates)) {
    return toTemplateItemsFromMap(value.instructTemplates)
  }

  const single = toTemplateItem(value)
  if (single) {
    return [single]
  }

  const entries = Object.entries(value)
  if (entries.length === 0) {
    return []
  }
  const recordEntries = entries.filter(
    (entry): entry is [string, Record<string, unknown>] => isRecord(entry[1])
  )
  if (recordEntries.length !== entries.length) {
    return []
  }
  if (!recordEntries.every(([, item]) => isTemplatePayloadLike(item))) {
    return []
  }

  const out: ImportedTemplateItem[] = []
  for (const [name, item] of recordEntries) {
    const normalized = toTemplateItem(item, name)
    if (normalized) out.push(normalized)
  }
  return out
}
