export type DictionaryEntryListItem = {
  id?: number
  pattern?: string | null
  replacement?: string | null
  type?: string | null
  probability?: number | null
  group?: string | null
}

function normalizeText(value: unknown): string {
  if (typeof value !== "string") return ""
  return value.trim()
}

function normalizeLower(value: unknown): string {
  return normalizeText(value).toLocaleLowerCase()
}

export function buildDictionaryEntryGroupOptions(
  entries: DictionaryEntryListItem[]
): Array<{ label: string; value: string }> {
  const firstCaseByNormalized = new Map<string, string>()
  for (const entry of entries) {
    const group = normalizeText(entry?.group)
    if (!group) continue
    const normalized = group.toLocaleLowerCase()
    if (!firstCaseByNormalized.has(normalized)) {
      firstCaseByNormalized.set(normalized, group)
    }
  }

  return Array.from(firstCaseByNormalized.values())
    .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }))
    .map((group) => ({ label: group, value: group }))
}

export function filterDictionaryEntriesBySearchAndGroup(
  entries: DictionaryEntryListItem[],
  query: string,
  selectedGroup?: string
): DictionaryEntryListItem[] {
  const normalizedQuery = normalizeLower(query)
  const normalizedGroup = normalizeLower(selectedGroup)

  return entries.filter((entry) => {
    const entryGroup = normalizeLower(entry?.group)
    if (normalizedGroup && entryGroup !== normalizedGroup) return false
    if (!normalizedQuery) return true

    const haystack = [
      normalizeLower(entry?.pattern),
      normalizeLower(entry?.replacement),
      entryGroup
    ]
      .filter(Boolean)
      .join(" ")
    return haystack.includes(normalizedQuery)
  })
}

export const DICTIONARY_ENTRY_COLUMN_RESPONSIVE = {
  type: ["sm"] as string[],
  probability: ["md"] as string[],
  group: ["sm"] as string[],
}
