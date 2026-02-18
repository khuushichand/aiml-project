export type MediaSortBy =
  | 'relevance'
  | 'date_desc'
  | 'date_asc'
  | 'title_asc'
  | 'title_desc'

export type MediaSearchMode = 'full_text' | 'metadata'

export type MediaSearchField = 'title' | 'content'

export interface MediaBoostFields {
  title?: number
  content?: number
}

export const DEFAULT_MEDIA_SEARCH_FIELDS: MediaSearchField[] = ['title', 'content']

export interface MediaDateRange {
  startDate: string | null
  endDate: string | null
}

interface HasMediaSearchFiltersArgs {
  mediaTypes: string[]
  includeKeywords: string[]
  excludeKeywords: string[]
  sortBy: MediaSortBy
  dateRange: MediaDateRange
  exactPhrase?: string
  fields?: MediaSearchField[]
  boostFields?: MediaBoostFields
}

interface BuildMediaSearchPayloadArgs extends HasMediaSearchFiltersArgs {
  query: string
}

const normalizeTokens = (tokens: string[]): string[] => {
  return Array.from(
    new Set(
      tokens
        .map((token) => token.trim())
        .filter(Boolean)
    )
  )
}

export const normalizeMediaSearchFields = (
  fields?: MediaSearchField[]
): MediaSearchField[] => {
  if (!fields || fields.length === 0) {
    return [...DEFAULT_MEDIA_SEARCH_FIELDS]
  }

  const provided = new Set(fields)
  const normalized = DEFAULT_MEDIA_SEARCH_FIELDS.filter((field) => provided.has(field))
  if (normalized.length === 0) {
    return [...DEFAULT_MEDIA_SEARCH_FIELDS]
  }

  return normalized
}

export const hasDefaultMediaSearchFields = (
  fields?: MediaSearchField[]
): boolean => {
  const normalized = normalizeMediaSearchFields(fields)
  return (
    normalized.length === DEFAULT_MEDIA_SEARCH_FIELDS.length &&
    normalized.every((field, index) => field === DEFAULT_MEDIA_SEARCH_FIELDS[index])
  )
}

const normalizeMediaBoostFields = (
  boostFields?: MediaBoostFields
): MediaBoostFields | null => {
  if (!boostFields) return null

  const normalized: MediaBoostFields = {}
  const title = Number(boostFields.title)
  const content = Number(boostFields.content)

  if (Number.isFinite(title) && title > 0) {
    normalized.title = title
  }
  if (Number.isFinite(content) && content > 0) {
    normalized.content = content
  }

  return Object.keys(normalized).length > 0 ? normalized : null
}

export const hasMediaSearchFilters = ({
  mediaTypes,
  includeKeywords,
  excludeKeywords,
  sortBy,
  dateRange,
  exactPhrase,
  fields,
  boostFields,
}: HasMediaSearchFiltersArgs): boolean => {
  const normalizedBoost = normalizeMediaBoostFields(boostFields)
  return (
    mediaTypes.length > 0 ||
    includeKeywords.length > 0 ||
    excludeKeywords.length > 0 ||
    Boolean(dateRange.startDate || dateRange.endDate) ||
    sortBy !== 'relevance' ||
    Boolean(exactPhrase?.trim()) ||
    !hasDefaultMediaSearchFields(fields) ||
    Boolean(normalizedBoost)
  )
}

export const buildMediaSearchPayload = ({
  query,
  mediaTypes,
  includeKeywords,
  excludeKeywords,
  sortBy,
  dateRange,
  exactPhrase,
  fields,
  boostFields,
}: BuildMediaSearchPayloadArgs): Record<string, unknown> => {
  const normalizedFields = normalizeMediaSearchFields(fields)
  const normalizedBoost = normalizeMediaBoostFields(boostFields)

  const body: Record<string, unknown> = {
    query: query.trim().length > 0 ? query : null,
    fields: normalizedFields,
    sort_by: sortBy,
  }

  const trimmedExactPhrase = exactPhrase?.trim()
  if (trimmedExactPhrase) {
    body.exact_phrase = trimmedExactPhrase
  }

  if (mediaTypes.length > 0) {
    body.media_types = mediaTypes
  }

  const mustHave = normalizeTokens(includeKeywords)
  if (mustHave.length > 0) {
    body.must_have = mustHave
  }

  const mustNotHave = normalizeTokens(excludeKeywords)
  if (mustNotHave.length > 0) {
    body.must_not_have = mustNotHave
  }

  if (dateRange.startDate || dateRange.endDate) {
    body.date_range = {
      ...(dateRange.startDate ? {
        start: dateRange.startDate,
        start_date: dateRange.startDate,
      } : {}),
      ...(dateRange.endDate ? {
        end: dateRange.endDate,
        end_date: dateRange.endDate,
      } : {}),
    }
  }

  if (normalizedBoost) {
    body.boost_fields = normalizedBoost
  }

  return body
}
