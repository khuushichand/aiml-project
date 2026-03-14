import type { Flashcard } from "@/services/flashcards"

export type DocumentQuerySortBy = "due" | "created"

export interface DocumentQueryFilterContext {
  deckId?: number | null
  query?: string
  tag?: string | null
  tags?: string[]
  sortBy?: DocumentQuerySortBy
  dueStatus?: "new" | "learning" | "due" | "all"
}

const normalizeTags = (tags?: string[] | null, singleTag?: string | null): string[] => {
  const seen = new Set<string>()
  const normalized: string[] = []

  for (const raw of [...(tags || []), singleTag || ""]) {
    const tag = String(raw || "").trim().toLowerCase()
    if (!tag || seen.has(tag)) continue
    seen.add(tag)
    normalized.push(tag)
  }

  return normalized
}

const cardHasAllTags = (card: Flashcard, normalizedTags: string[]): boolean => {
  if (normalizedTags.length === 0) return true
  const cardTags = new Set((card.tags || []).map((tag) => String(tag || "").trim().toLowerCase()))
  return normalizedTags.every((tag) => cardTags.has(tag))
}

const cardMatchesTextQuery = (card: Flashcard, query?: string): boolean => {
  const normalizedQuery = String(query || "").trim().toLowerCase()
  if (!normalizedQuery) return true
  const haystack = [
    card.front,
    card.back,
    card.notes || "",
    card.extra || "",
    ...(card.tags || [])
  ]
    .join("\n")
    .toLowerCase()
  return haystack.includes(normalizedQuery)
}

const cardMatchesDocumentFilters = (
  card: Flashcard,
  context: DocumentQueryFilterContext
): boolean => {
  if (context.deckId != null && (card.deck_id ?? null) !== context.deckId) {
    return false
  }

  const normalizedTags = normalizeTags(context.tags, context.tag)
  if (!cardHasAllTags(card, normalizedTags)) {
    return false
  }

  return cardMatchesTextQuery(card, context.query)
}

export function shouldRefetchDocumentQueryAfterRowSave(
  previous: Flashcard,
  next: Flashcard,
  context: DocumentQueryFilterContext
): boolean {
  const previousMatches = cardMatchesDocumentFilters(previous, context)
  const nextMatches = cardMatchesDocumentFilters(next, context)

  if (previousMatches !== nextMatches) {
    return true
  }

  return false
}
