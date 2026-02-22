import { afterEach, describe, expect, it } from 'vitest'
import {
  __resetMediaTypesCacheForTests,
  getImmediateCachedMediaTypes,
  isMediaTypesCacheFresh,
  MEDIA_TYPES_CACHE_KEY,
  MEDIA_TYPES_CACHE_TTL_MS,
  normalizeMediaTypesCacheRecord,
  seedMediaTypesCache
} from '../mediaTypeCache'

const createStorageStub = () => {
  const map = new Map<string, string>()
  return {
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => {
      map.set(key, value)
    }
  }
}

describe('mediaTypeCache helpers', () => {
  afterEach(() => {
    __resetMediaTypesCacheForTests()
  })

  it('normalizes cache records and deduplicates type values', () => {
    const normalized = normalizeMediaTypesCacheRecord({
      types: ['pdf', 'pdf', ' video ', '', 'audio'],
      cachedAt: 1700000000000
    })

    expect(normalized).toEqual({
      types: ['pdf', 'video', 'audio'],
      cachedAt: 1700000000000
    })
  })

  it('applies ttl freshness checks correctly', () => {
    const now = 1700000000000
    const freshCachedAt = now - (MEDIA_TYPES_CACHE_TTL_MS - 1)
    const staleCachedAt = now - MEDIA_TYPES_CACHE_TTL_MS

    expect(isMediaTypesCacheFresh(freshCachedAt, now)).toBe(true)
    expect(isMediaTypesCacheFresh(staleCachedAt, now)).toBe(false)
  })

  it('reads fresh cached media types from storage when in-memory cache is empty', () => {
    const storage = createStorageStub()
    const now = 1700000000000
    storage.setItem(
      MEDIA_TYPES_CACHE_KEY,
      JSON.stringify({
        types: ['pdf', 'video'],
        cachedAt: now - 1000
      })
    )

    const cachedTypes = getImmediateCachedMediaTypes({ storage, now })
    expect(cachedTypes).toEqual(['pdf', 'video'])
  })

  it('ignores stale storage cache and keeps uncached fallback empty', () => {
    const storage = createStorageStub()
    const now = 1700000000000
    storage.setItem(
      MEDIA_TYPES_CACHE_KEY,
      JSON.stringify({
        types: ['pdf', 'video'],
        cachedAt: now - MEDIA_TYPES_CACHE_TTL_MS
      })
    )

    const cachedTypes = getImmediateCachedMediaTypes({ storage, now })
    expect(cachedTypes).toEqual([])
  })

  it('seeds cache into memory and storage for immediate re-use', () => {
    const storage = createStorageStub()
    const now = 1700000000000
    const seeded = seedMediaTypesCache(['pdf', 'pdf', 'audio'], {
      cachedAt: now,
      storage
    })

    expect(seeded).toEqual({
      types: ['pdf', 'audio'],
      cachedAt: now
    })
    expect(storage.getItem(MEDIA_TYPES_CACHE_KEY)).toContain('"pdf"')

    const immediate = getImmediateCachedMediaTypes({
      storage: createStorageStub(),
      now: now + 1000
    })
    expect(immediate).toEqual(['pdf', 'audio'])
  })
})
