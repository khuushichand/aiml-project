import type { ScrapedItem, WatchlistSource } from "@/types/watchlists"

export const SOURCE_LOAD_PAGE_SIZE = 200
export const SOURCE_LOAD_MAX_ITEMS = 1000
export const ITEM_PAGE_SIZE = 25
export const ITEM_PAGE_SIZE_OPTIONS = [20, 25, 50, 100] as const
export const ITEMS_PAGE_SIZE_STORAGE_KEY = "watchlists:items:page-size"
export const ITEMS_VIEW_PRESETS_STORAGE_KEY = "watchlists:items:view-presets"

export interface PersistedItemsViewPreset {
  id: string
  name: string
  sourceId: number | null
  smartFilter: string
  statusFilter: string
  searchQuery: string
}

export const normalizeItemPageSize = (value: unknown): number => {
  const parsed = Number(value)
  if (ITEM_PAGE_SIZE_OPTIONS.includes(parsed as typeof ITEM_PAGE_SIZE_OPTIONS[number])) {
    return parsed
  }
  return ITEM_PAGE_SIZE
}

export const loadPersistedItemPageSize = (
  storage: Pick<Storage, "getItem"> | null | undefined
): number => {
  try {
    const raw = storage?.getItem(ITEMS_PAGE_SIZE_STORAGE_KEY)
    if (raw == null) return ITEM_PAGE_SIZE
    return normalizeItemPageSize(raw)
  } catch {
    return ITEM_PAGE_SIZE
  }
}

export const persistItemPageSize = (
  storage: Pick<Storage, "setItem"> | null | undefined,
  pageSize: number
): void => {
  try {
    storage?.setItem(ITEMS_PAGE_SIZE_STORAGE_KEY, String(normalizeItemPageSize(pageSize)))
  } catch {
    // Ignore storage write errors (private browsing, quota, etc.)
  }
}

const isPersistedItemsViewPreset = (value: unknown): value is PersistedItemsViewPreset => {
  if (!value || typeof value !== "object") return false
  const candidate = value as Record<string, unknown>
  if (typeof candidate.id !== "string" || candidate.id.trim().length === 0) return false
  if (typeof candidate.name !== "string" || candidate.name.trim().length === 0) return false
  const sourceId = candidate.sourceId
  if (sourceId !== null && typeof sourceId !== "number") return false
  if (typeof candidate.smartFilter !== "string") return false
  if (typeof candidate.statusFilter !== "string") return false
  if (typeof candidate.searchQuery !== "string") return false
  return true
}

export const loadPersistedItemsViewPresets = (
  storage: Pick<Storage, "getItem"> | null | undefined
): PersistedItemsViewPreset[] => {
  try {
    const raw = storage?.getItem(ITEMS_VIEW_PRESETS_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(isPersistedItemsViewPreset)
  } catch {
    return []
  }
}

export const persistItemsViewPresets = (
  storage: Pick<Storage, "setItem"> | null | undefined,
  presets: PersistedItemsViewPreset[]
): void => {
  try {
    storage?.setItem(
      ITEMS_VIEW_PRESETS_STORAGE_KEY,
      JSON.stringify(presets.filter(isPersistedItemsViewPreset))
    )
  } catch {
    // Ignore storage write errors (private browsing, quota, etc.)
  }
}

export const filterSourcesForReader = (
  sources: WatchlistSource[],
  query: string
): WatchlistSource[] => {
  const trimmed = query.trim().toLowerCase()
  if (!trimmed) return sources

  return sources.filter((source) => {
    if (source.name.toLowerCase().includes(trimmed)) return true
    if (source.url.toLowerCase().includes(trimmed)) return true
    return source.tags.some((tag) => tag.toLowerCase().includes(trimmed))
  })
}

export const resolveSelectedItemId = (
  currentId: number | null,
  items: ScrapedItem[]
): number | null => {
  if (items.length === 0) return null
  if (currentId && items.some((item) => item.id === currentId)) return currentId
  return items[0].id
}

export const stripHtmlToText = (value: string): string => {
  return value
    .replace(/<style[\s\S]*?>[\s\S]*?<\/style>/gi, " ")
    .replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/\s+/g, " ")
    .trim()
}

export const extractImageUrl = (value: string | null | undefined): string | null => {
  if (!value) return null

  const htmlMatch = value.match(/<img[^>]+src=["']([^"']+)["']/i)
  if (htmlMatch?.[1]) return htmlMatch[1]

  const markdownMatch = value.match(/!\[[^\]]*]\((https?:\/\/[^)\s]+)\)/i)
  if (markdownMatch?.[1]) return markdownMatch[1]

  return null
}
