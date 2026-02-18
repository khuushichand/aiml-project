import { describe, expect, it } from 'vitest'
import {
  buildMediaPermalinkSearch,
  getMediaPermalinkIdFromSearch,
  normalizeMediaPermalinkId
} from '../mediaPermalink'

describe('mediaPermalink utilities', () => {
  it('normalizes permalink ids from raw values', () => {
    expect(normalizeMediaPermalinkId(' 123 ')).toBe('123')
    expect(normalizeMediaPermalinkId('')).toBeNull()
    expect(normalizeMediaPermalinkId('   ')).toBeNull()
    expect(normalizeMediaPermalinkId(null)).toBeNull()
    expect(normalizeMediaPermalinkId(undefined)).toBeNull()
  })

  it('extracts permalink id from URL search', () => {
    expect(getMediaPermalinkIdFromSearch('?id=abc-123')).toBe('abc-123')
    expect(getMediaPermalinkIdFromSearch('id=456')).toBe('456')
    expect(getMediaPermalinkIdFromSearch('?foo=bar')).toBeNull()
    expect(getMediaPermalinkIdFromSearch('?id=%20%20')).toBeNull()
  })

  it('builds search params while preserving unrelated params', () => {
    expect(buildMediaPermalinkSearch('?foo=bar&page=2', ' 77 ')).toBe(
      '?foo=bar&page=2&id=77'
    )
    expect(buildMediaPermalinkSearch('?id=11&foo=bar', '22')).toBe('?id=22&foo=bar')
  })

  it('removes permalink id when media id is null', () => {
    expect(buildMediaPermalinkSearch('?id=11&foo=bar', null)).toBe('?foo=bar')
    expect(buildMediaPermalinkSearch('?id=11', null)).toBe('')
  })
})
