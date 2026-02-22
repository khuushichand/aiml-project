import { describe, expect, it } from 'vitest'
import {
  buildMetadataSearchPath,
  createMetadataSearchFilter,
  getAllowedMetadataOperators,
  normalizeMetadataSearchFilters,
  validateMetadataSearchFilters,
} from '../mediaMetadataSearchRequest'

describe('mediaMetadataSearchRequest', () => {
  it('normalizes filters by trimming and dropping empty values', () => {
    const normalized = normalizeMetadataSearchFilters([
      { id: '1', field: 'doi', op: 'eq', value: ' 10.1000/xyz ' },
      { id: '2', field: 'journal', op: 'icontains', value: '   ' },
    ])

    expect(normalized).toEqual([
      { id: '1', field: 'doi', op: 'eq', value: '10.1000/xyz' }
    ])
  })

  it('builds metadata-search path with serialized filters and pagination', () => {
    const path = buildMetadataSearchPath({
      filters: [
        { id: '1', field: 'doi', op: 'eq', value: '10.1000/xyz' },
        { id: '2', field: 'journal', op: 'icontains', value: 'Nature' },
      ],
      matchMode: 'all',
      page: 2,
      perPage: 50,
    })

    expect(path).toContain('/api/v1/media/metadata-search?')
    expect(path).toContain('match_mode=all')
    expect(path).toContain('page=2')
    expect(path).toContain('per_page=50')
    expect(decodeURIComponent(path)).toContain('"field":"doi"')
    expect(decodeURIComponent(path)).toContain('"field":"journal"')
  })

  it('serializes optional standard metadata constraints', () => {
    const path = buildMetadataSearchPath({
      filters: [{ id: '1', field: 'doi', op: 'eq', value: '10.1000/xyz' }],
      matchMode: 'all',
      page: 1,
      perPage: 20,
      textQuery: 'nature medicine',
      mediaTypes: ['document', 'pdf'],
      includeKeywords: ['biology', 'review'],
      excludeKeywords: ['private'],
      dateRange: {
        startDate: '2026-01-01T00:00:00.000Z',
        endDate: '2026-01-31T23:59:59.999Z'
      },
      sortBy: 'date_desc'
    })

    expect(path).toContain('q=nature+medicine')
    expect(path).toContain('media_types=document%2Cpdf')
    expect(path).toContain('must_have=biology%2Creview')
    expect(path).toContain('must_not_have=private')
    expect(path).toContain('date_start=2026-01-01T00%3A00%3A00.000Z')
    expect(path).toContain('date_end=2026-01-31T23%3A59%3A59.999Z')
    expect(path).toContain('sort_by=date_desc')
  })

  it('validates invalid operator combinations for identifier fields', () => {
    expect(validateMetadataSearchFilters([
      { id: '1', field: 'doi', op: 'contains', value: '10.1000/xyz' }
    ])).toContain('DOI requires the "equals" operator.')

    expect(validateMetadataSearchFilters([
      { id: '1', field: 'journal', op: 'icontains', value: 'Nature' }
    ])).toBeNull()
  })

  it('returns allowed operator sets for metadata fields', () => {
    expect(getAllowedMetadataOperators('pmid')).toEqual(['eq'])
    expect(getAllowedMetadataOperators('journal')).toEqual([
      'eq',
      'contains',
      'icontains',
      'startswith',
      'endswith',
    ])
  })

  it('creates a default metadata filter', () => {
    const filter = createMetadataSearchFilter()
    expect(filter.field).toBe('doi')
    expect(filter.op).toBe('eq')
    expect(filter.value).toBe('')
    expect(filter.id.length).toBeGreaterThan(0)
  })
})
