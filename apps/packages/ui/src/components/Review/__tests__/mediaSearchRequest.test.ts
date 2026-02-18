import { describe, expect, it } from 'vitest'
import {
  buildMediaSearchPayload,
  hasMediaSearchFilters,
} from '../mediaSearchRequest'

describe('mediaSearchRequest', () => {
  it('builds default payload with relevance sort', () => {
    const payload = buildMediaSearchPayload({
      query: 'quantum',
      mediaTypes: [],
      includeKeywords: [],
      excludeKeywords: [],
      sortBy: 'relevance',
      dateRange: { startDate: null, endDate: null }
    })

    expect(payload).toEqual({
      query: 'quantum',
      fields: ['title', 'content'],
      sort_by: 'relevance'
    })
  })

  it('includes sort, date range, and keyword filters when provided', () => {
    const payload = buildMediaSearchPayload({
      query: '',
      mediaTypes: ['pdf', 'audio'],
      includeKeywords: ['alpha', 'alpha', ' beta '],
      excludeKeywords: ['gamma', ' gamma  '],
      sortBy: 'date_desc',
      fields: ['title', 'content'],
      dateRange: {
        startDate: '2026-01-01T00:00:00.000Z',
        endDate: '2026-01-31T23:59:59.999Z'
      }
    })

    expect(payload).toEqual({
      query: null,
      fields: ['title', 'content'],
      sort_by: 'date_desc',
      media_types: ['pdf', 'audio'],
      must_have: ['alpha', 'beta'],
      must_not_have: ['gamma'],
      date_range: {
        start: '2026-01-01T00:00:00.000Z',
        start_date: '2026-01-01T00:00:00.000Z',
        end: '2026-01-31T23:59:59.999Z',
        end_date: '2026-01-31T23:59:59.999Z'
      }
    })
  })

  it('serializes exact phrase, field scope, and boost fields for advanced search', () => {
    const payload = buildMediaSearchPayload({
      query: 'paper',
      mediaTypes: [],
      includeKeywords: [],
      excludeKeywords: [],
      sortBy: 'relevance',
      dateRange: { startDate: null, endDate: null },
      exactPhrase: 'systematic review',
      fields: ['title'],
      boostFields: {
        title: 2.5,
        content: 0.8
      }
    })

    expect(payload).toEqual({
      query: 'paper',
      fields: ['title'],
      sort_by: 'relevance',
      exact_phrase: 'systematic review',
      boost_fields: {
        title: 2.5,
        content: 0.8
      }
    })
  })

  it('detects active filters from exclude keywords, date range, or non-default sort', () => {
    expect(hasMediaSearchFilters({
      mediaTypes: [],
      includeKeywords: [],
      excludeKeywords: [],
      sortBy: 'relevance',
      dateRange: { startDate: null, endDate: null },
      fields: ['title', 'content']
    })).toBe(false)

    expect(hasMediaSearchFilters({
      mediaTypes: [],
      includeKeywords: [],
      excludeKeywords: ['private'],
      sortBy: 'relevance',
      dateRange: { startDate: null, endDate: null },
      fields: ['title', 'content']
    })).toBe(true)

    expect(hasMediaSearchFilters({
      mediaTypes: [],
      includeKeywords: [],
      excludeKeywords: [],
      sortBy: 'title_asc',
      dateRange: { startDate: null, endDate: null },
      fields: ['title', 'content']
    })).toBe(true)

    expect(hasMediaSearchFilters({
      mediaTypes: [],
      includeKeywords: [],
      excludeKeywords: [],
      sortBy: 'relevance',
      dateRange: { startDate: '2026-01-01T00:00:00.000Z', endDate: null },
      fields: ['title', 'content']
    })).toBe(true)

    expect(hasMediaSearchFilters({
      mediaTypes: [],
      includeKeywords: [],
      excludeKeywords: [],
      sortBy: 'relevance',
      dateRange: { startDate: null, endDate: null },
      exactPhrase: 'deep learning',
      fields: ['title', 'content']
    })).toBe(true)

    expect(hasMediaSearchFilters({
      mediaTypes: [],
      includeKeywords: [],
      excludeKeywords: [],
      sortBy: 'relevance',
      dateRange: { startDate: null, endDate: null },
      fields: ['title']
    })).toBe(true)

    expect(hasMediaSearchFilters({
      mediaTypes: [],
      includeKeywords: [],
      excludeKeywords: [],
      sortBy: 'relevance',
      dateRange: { startDate: null, endDate: null },
      fields: ['title', 'content'],
      boostFields: { title: 2, content: 1 }
    })).toBe(true)
  })
})
