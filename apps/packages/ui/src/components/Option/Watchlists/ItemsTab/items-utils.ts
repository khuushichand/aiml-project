import type { ScrapedItem, WatchlistSource } from "@/types/watchlists"

export const SOURCE_LOAD_PAGE_SIZE = 200
export const SOURCE_LOAD_MAX_ITEMS = 1000
export const ITEM_PAGE_SIZE = 25

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
