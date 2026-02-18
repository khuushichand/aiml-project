export type WikilinkCandidate = {
  id: string
  title: string
}

export type WikilinkToken = {
  raw: string
  title: string
  start: number
  end: number
}

export type ActiveWikilinkQuery = {
  start: number
  end: number
  query: string
}

const WIKILINK_PATTERN = /\[\[([^[\]\n]+?)\]\]/g

export const normalizeWikilinkTitle = (title: string): string =>
  title.trim().replace(/\s+/g, " ").toLowerCase()

export const buildWikilinkIndex = (
  candidates: WikilinkCandidate[]
): Map<string, WikilinkCandidate[]> => {
  const index = new Map<string, WikilinkCandidate[]>()
  const seen = new Set<string>()

  for (const candidate of candidates) {
    const id = String(candidate.id || "").trim()
    const title = String(candidate.title || "").trim()
    if (!id || !title) continue
    const key = normalizeWikilinkTitle(title)
    if (!key) continue
    const dedupeKey = `${key}::${id}`
    if (seen.has(dedupeKey)) continue
    seen.add(dedupeKey)
    const bucket = index.get(key)
    if (bucket) {
      bucket.push({ id, title })
    } else {
      index.set(key, [{ id, title }])
    }
  }

  for (const [key, bucket] of index.entries()) {
    index.set(
      key,
      bucket.sort((a, b) => a.title.localeCompare(b.title) || a.id.localeCompare(b.id))
    )
  }

  return index
}

export const tokenizeWikilinks = (content: string): WikilinkToken[] => {
  const tokens: WikilinkToken[] = []
  const input = String(content || "")
  for (const match of input.matchAll(WIKILINK_PATTERN)) {
    const raw = String(match[0] || "")
    const title = String(match[1] || "").trim()
    const index = match.index ?? -1
    if (!raw || !title || index < 0) continue
    tokens.push({
      raw,
      title,
      start: index,
      end: index + raw.length
    })
  }
  return tokens
}

export const resolveWikilinkTitle = (
  title: string,
  index: Map<string, WikilinkCandidate[]>
): string | null => {
  const query = String(title || "").trim()
  if (!query) return null
  const normalized = normalizeWikilinkTitle(query)
  const candidates = index.get(normalized) || []
  if (candidates.length === 0) return null
  if (candidates.length === 1) return candidates[0].id

  const exactTitleMatches = candidates.filter((candidate) => candidate.title.trim() === query)
  if (exactTitleMatches.length === 1) return exactTitleMatches[0].id

  const deterministicPool = exactTitleMatches.length > 0 ? exactTitleMatches : candidates
  return deterministicPool
    .slice()
    .sort((a, b) => a.title.localeCompare(b.title) || a.id.localeCompare(b.id))[0].id
}

export const renderContentWithResolvedWikilinks = (
  content: string,
  index: Map<string, WikilinkCandidate[]>
): string => {
  const input = String(content || "")
  const tokens = tokenizeWikilinks(input)
  if (tokens.length === 0) return input

  let cursor = 0
  let output = ""
  for (const token of tokens) {
    output += input.slice(cursor, token.start)
    const noteId = resolveWikilinkTitle(token.title, index)
    if (!noteId) {
      output += token.raw
    } else {
      output += `[${token.raw}](note://${encodeURIComponent(noteId)})`
    }
    cursor = token.end
  }
  output += input.slice(cursor)
  return output
}

export const getActiveWikilinkQuery = (
  content: string,
  cursorIndex: number
): ActiveWikilinkQuery | null => {
  const input = String(content || "")
  const safeCursor = Math.max(0, Math.min(cursorIndex, input.length))
  const start = input.lastIndexOf("[[", safeCursor)
  if (start < 0) return null

  const closeBeforeCursor = input.indexOf("]]", start + 2)
  if (closeBeforeCursor >= 0 && closeBeforeCursor < safeCursor) return null

  const rawQuery = input.slice(start + 2, safeCursor)
  if (!rawQuery) {
    return { start, end: safeCursor, query: "" }
  }
  if (rawQuery.includes("\n")) return null
  if (rawQuery.includes("[") || rawQuery.includes("]")) return null

  return {
    start,
    end: safeCursor,
    query: rawQuery
  }
}

export const insertWikilinkAtCursor = (
  content: string,
  activeQuery: ActiveWikilinkQuery,
  title: string
): { content: string; cursor: number } => {
  const nextTitle = String(title || "").trim()
  const replacement = `[[${nextTitle}]]`
  const nextContent = `${content.slice(0, activeQuery.start)}${replacement}${content.slice(activeQuery.end)}`
  const nextCursor = activeQuery.start + replacement.length
  return { content: nextContent, cursor: nextCursor }
}
