export type WatchlistChatArticle = {
  title?: string
  url?: string
  content?: string
  sourceType?: "item" | "output"
  mediaId?: number
}

export type WatchlistChatHandoffPayload = {
  articles: WatchlistChatArticle[]
}

const toNonEmptyString = (value: unknown): string | undefined => {
  if (typeof value !== "string") return undefined
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

const normalizeArticle = (raw: unknown): WatchlistChatArticle | undefined => {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return undefined
  const obj = raw as Record<string, unknown>
  const title = toNonEmptyString(obj.title)
  const url = toNonEmptyString(obj.url)
  const content = toNonEmptyString(obj.content)
  // Must have at least a title or content
  if (!title && !content) return undefined
  const article: WatchlistChatArticle = {}
  if (title) article.title = title
  if (url) article.url = url
  if (content) article.content = content
  if (obj.sourceType === "item" || obj.sourceType === "output") {
    article.sourceType = obj.sourceType
  }
  if (typeof obj.mediaId === "number" && Number.isFinite(obj.mediaId) && obj.mediaId > 0) {
    article.mediaId = Math.trunc(obj.mediaId)
  }
  return article
}

export const normalizeWatchlistChatHandoffPayload = (
  value: unknown
): WatchlistChatHandoffPayload | undefined => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined
  const obj = value as Record<string, unknown>
  if (!Array.isArray(obj.articles)) return undefined
  const articles = obj.articles
    .map((a: unknown) => normalizeArticle(a))
    .filter((a): a is WatchlistChatArticle => a != null)
  if (articles.length === 0) return undefined
  return { articles }
}

const formatArticleBlock = (article: WatchlistChatArticle, index?: number): string => {
  const titleText = article.title || "Untitled article"
  const header = index != null
    ? `--- Article ${index + 1}: "${titleText}" ---`
    : `--- "${titleText}" ---`
  const lines: string[] = [header]
  if (article.url) {
    lines.push(`URL: ${article.url}`)
  }
  if (article.content) {
    lines.push(article.content)
  } else {
    lines.push(`${titleText}${article.url ? ` — ${article.url}` : ""}`)
    lines.push("(Full content not available for this article)")
  }
  return lines.join("\n")
}

export const buildWatchlistChatHint = (
  payload: WatchlistChatHandoffPayload
): string => {
  const { articles } = payload
  if (articles.length === 0) return ""

  if (articles.length === 1) {
    const intro = "I'd like to discuss this article:\n\n"
    return intro + formatArticleBlock(articles[0])
  }

  const intro = "I'd like to discuss these articles:\n\n"
  const blocks = articles.map((a, i) => formatArticleBlock(a, i))
  return intro + blocks.join("\n\n")
}

export const getWatchlistChatTotalChars = (
  payload: WatchlistChatHandoffPayload
): number => {
  return payload.articles.reduce(
    (sum, a) => sum + (a.content?.length ?? 0),
    0
  )
}

export const WATCHLIST_CHAT_CONTENT_WARN_THRESHOLD = 80_000
