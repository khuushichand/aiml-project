/**
 * Utility for serializing/deserializing media filter state to/from URL search params.
 * Enables bookmarkable filtered views and browser back/forward navigation.
 */

import type { MediaSortBy, MediaSearchMode, MediaSearchField, MediaBoostFields, MediaDateRange } from './mediaSearchRequest'

/** Filter state that can be serialized to URL params. */
export interface MediaFilterParams {
  q?: string
  types?: string[]
  keywords?: string[]
  excludeKeywords?: string[]
  sort?: MediaSortBy
  dateStart?: string | null
  dateEnd?: string | null
  searchMode?: MediaSearchMode
  exactPhrase?: string
  fields?: MediaSearchField[]
  page?: number
  pageSize?: number
}

const PARAM_KEYS = {
  q: 'q',
  types: 'types',
  keywords: 'kw',
  excludeKeywords: 'exkw',
  sort: 'sort',
  dateStart: 'from',
  dateEnd: 'to',
  searchMode: 'mode',
  exactPhrase: 'exact',
  fields: 'fields',
  page: 'page',
  pageSize: 'size'
} as const

/** Parse filter state from URL search params. */
export function parseMediaFilterParams(search: string): MediaFilterParams {
  const params = new URLSearchParams(search)
  const result: MediaFilterParams = {}

  const q = params.get(PARAM_KEYS.q)
  if (q) result.q = q

  const types = params.get(PARAM_KEYS.types)
  if (types) result.types = types.split(',').filter(Boolean)

  const kw = params.get(PARAM_KEYS.keywords)
  if (kw) result.keywords = kw.split(',').filter(Boolean)

  const exkw = params.get(PARAM_KEYS.excludeKeywords)
  if (exkw) result.excludeKeywords = exkw.split(',').filter(Boolean)

  const sort = params.get(PARAM_KEYS.sort) as MediaSortBy | null
  if (sort && ['relevance', 'date_desc', 'date_asc', 'title_asc', 'title_desc'].includes(sort)) {
    result.sort = sort
  }

  const dateStart = params.get(PARAM_KEYS.dateStart)
  if (dateStart) result.dateStart = dateStart

  const dateEnd = params.get(PARAM_KEYS.dateEnd)
  if (dateEnd) result.dateEnd = dateEnd

  const mode = params.get(PARAM_KEYS.searchMode) as MediaSearchMode | null
  if (mode && (mode === 'full_text' || mode === 'metadata')) {
    result.searchMode = mode
  }

  const exact = params.get(PARAM_KEYS.exactPhrase)
  if (exact) result.exactPhrase = exact

  const fields = params.get(PARAM_KEYS.fields)
  if (fields) result.fields = fields.split(',').filter(Boolean) as MediaSearchField[]

  const page = params.get(PARAM_KEYS.page)
  if (page) {
    const n = parseInt(page, 10)
    if (n > 0) result.page = n
  }

  const size = params.get(PARAM_KEYS.pageSize)
  if (size) {
    const n = parseInt(size, 10)
    if ([20, 50, 100].includes(n)) result.pageSize = n
  }

  return result
}

/** Build URL search string from filter state. Preserves existing non-filter params (like `id`). */
export function buildMediaFilterSearch(
  currentSearch: string,
  filters: MediaFilterParams
): string {
  const params = new URLSearchParams(currentSearch)

  // Set or delete each param
  const setOrDelete = (key: string, value: string | null | undefined) => {
    if (value && value.length > 0) {
      params.set(key, value)
    } else {
      params.delete(key)
    }
  }

  setOrDelete(PARAM_KEYS.q, filters.q || undefined)
  setOrDelete(PARAM_KEYS.types, filters.types?.length ? filters.types.join(',') : undefined)
  setOrDelete(PARAM_KEYS.keywords, filters.keywords?.length ? filters.keywords.join(',') : undefined)
  setOrDelete(PARAM_KEYS.excludeKeywords, filters.excludeKeywords?.length ? filters.excludeKeywords.join(',') : undefined)
  setOrDelete(PARAM_KEYS.sort, filters.sort !== 'relevance' ? filters.sort : undefined)
  setOrDelete(PARAM_KEYS.dateStart, filters.dateStart || undefined)
  setOrDelete(PARAM_KEYS.dateEnd, filters.dateEnd || undefined)
  setOrDelete(PARAM_KEYS.searchMode, filters.searchMode !== 'full_text' ? filters.searchMode : undefined)
  setOrDelete(PARAM_KEYS.exactPhrase, filters.exactPhrase || undefined)
  setOrDelete(PARAM_KEYS.fields, filters.fields?.length ? filters.fields.join(',') : undefined)
  setOrDelete(PARAM_KEYS.page, filters.page && filters.page > 1 ? String(filters.page) : undefined)
  setOrDelete(PARAM_KEYS.pageSize, filters.pageSize && filters.pageSize !== 20 ? String(filters.pageSize) : undefined)

  const serialized = params.toString()
  return serialized ? `?${serialized}` : ''
}

/** Check if URL contains any filter params. */
export function hasMediaFilterParams(search: string): boolean {
  const params = new URLSearchParams(search)
  return Object.values(PARAM_KEYS).some((key) => params.has(key))
}
