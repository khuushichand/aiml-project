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
