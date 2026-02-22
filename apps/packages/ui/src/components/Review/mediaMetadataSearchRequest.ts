import type { MediaDateRange, MediaSortBy } from './mediaSearchRequest'

export type MetadataMatchMode = 'all' | 'any'

export type MetadataSearchField =
  | 'doi'
  | 'pmid'
  | 'pmcid'
  | 'arxiv_id'
  | 's2_paper_id'
  | 'journal'
  | 'license'

export type MetadataSearchOperator =
  | 'eq'
  | 'contains'
  | 'icontains'
  | 'startswith'
  | 'endswith'

export interface MetadataSearchFilter {
  id: string
  field: MetadataSearchField
  op: MetadataSearchOperator
  value: string
}

interface BuildMetadataSearchPathArgs {
  filters: MetadataSearchFilter[]
  matchMode: MetadataMatchMode
  page: number
  perPage: number
  textQuery?: string
  mediaTypes?: string[]
  includeKeywords?: string[]
  excludeKeywords?: string[]
  dateRange?: MediaDateRange
  sortBy?: MediaSortBy
}

const IDENTIFIER_FIELDS = new Set<MetadataSearchField>([
  'doi',
  'pmid',
  'pmcid',
  'arxiv_id',
  's2_paper_id',
])

export const METADATA_SEARCH_FIELDS: Array<{
  value: MetadataSearchField
  label: string
}> = [
  { value: 'doi', label: 'DOI' },
  { value: 'pmid', label: 'PMID' },
  { value: 'pmcid', label: 'PMCID' },
  { value: 'arxiv_id', label: 'arXiv ID' },
  { value: 's2_paper_id', label: 'S2 Paper ID' },
  { value: 'journal', label: 'Journal' },
  { value: 'license', label: 'License' },
]

export const METADATA_SEARCH_OPERATORS: Array<{
  value: MetadataSearchOperator
  label: string
}> = [
  { value: 'eq', label: 'equals' },
  { value: 'contains', label: 'contains' },
  { value: 'icontains', label: 'contains (case-insensitive)' },
  { value: 'startswith', label: 'starts with' },
  { value: 'endswith', label: 'ends with' },
]

export const createMetadataSearchFilter = (
  partial?: Partial<Omit<MetadataSearchFilter, 'id'>>
): MetadataSearchFilter => {
  const id =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`

  return {
    id,
    field: partial?.field ?? 'doi',
    op: partial?.op ?? 'eq',
    value: partial?.value ?? ''
  }
}

export const getAllowedMetadataOperators = (
  field: MetadataSearchField
): MetadataSearchOperator[] => {
  if (IDENTIFIER_FIELDS.has(field)) {
    return ['eq']
  }
  return METADATA_SEARCH_OPERATORS.map((operator) => operator.value)
}

export const normalizeMetadataSearchFilters = (
  filters: MetadataSearchFilter[]
): MetadataSearchFilter[] => {
  return filters
    .map((filter) => ({
      ...filter,
      value: filter.value.trim(),
    }))
    .filter((filter) => filter.value.length > 0)
}

const normalizeTokens = (tokens: string[] | undefined): string[] => {
  if (!tokens || tokens.length === 0) return []
  return Array.from(
    new Set(
      tokens
        .map((token) => token.trim())
        .filter(Boolean)
    )
  )
}

export const validateMetadataSearchFilters = (
  filters: MetadataSearchFilter[]
): string | null => {
  const normalized = normalizeMetadataSearchFilters(filters)
  if (normalized.length === 0) {
    return 'Add at least one metadata filter.'
  }

  for (const filter of normalized) {
    if (IDENTIFIER_FIELDS.has(filter.field) && filter.op !== 'eq') {
      return `${filter.field.toUpperCase()} requires the "equals" operator.`
    }
  }

  return null
}

export const buildMetadataSearchPath = ({
  filters,
  matchMode,
  page,
  perPage,
  textQuery,
  mediaTypes,
  includeKeywords,
  excludeKeywords,
  dateRange,
  sortBy,
}: BuildMetadataSearchPathArgs): string => {
  const normalized = normalizeMetadataSearchFilters(filters).map((filter) => ({
    field: filter.field,
    op: filter.op,
    value: filter.value,
  }))

  const params = new URLSearchParams()
  if (normalized.length > 0) {
    params.set('filters', JSON.stringify(normalized))
  }
  params.set('match_mode', matchMode)
  params.set('group_by_media', 'true')
  params.set('page', String(page))
  params.set('per_page', String(perPage))

  const trimmedTextQuery = textQuery?.trim()
  if (trimmedTextQuery) {
    params.set('q', trimmedTextQuery)
  }

  const normalizedMediaTypes = normalizeTokens(mediaTypes)
  if (normalizedMediaTypes.length > 0) {
    params.set('media_types', normalizedMediaTypes.join(','))
  }

  const mustHave = normalizeTokens(includeKeywords)
  if (mustHave.length > 0) {
    params.set('must_have', mustHave.join(','))
  }

  const mustNotHave = normalizeTokens(excludeKeywords)
  if (mustNotHave.length > 0) {
    params.set('must_not_have', mustNotHave.join(','))
  }

  if (dateRange?.startDate) {
    params.set('date_start', dateRange.startDate)
  }
  if (dateRange?.endDate) {
    params.set('date_end', dateRange.endDate)
  }

  if (sortBy && sortBy !== 'relevance') {
    params.set('sort_by', sortBy)
  }

  return `/api/v1/media/metadata-search?${params.toString()}`
}
