export const MEDIA_TYPES_CACHE_KEY = 'reviewMediaTypesCache'
export const MEDIA_TYPES_CACHE_TTL_MS = 24 * 60 * 60 * 1000

export type MediaTypesCacheRecord = {
  types: string[]
  cachedAt: number
}

type StorageLike = Pick<Storage, 'getItem' | 'setItem'>

let inMemoryCache: MediaTypesCacheRecord | null = null

const dedupeTypes = (types: string[]): string[] => {
  const seen = new Set<string>()
  const out: string[] = []
  for (const rawType of types) {
    if (typeof rawType !== 'string') continue
    const type = rawType.trim()
    if (!type || seen.has(type)) continue
    seen.add(type)
    out.push(type)
  }
  return out
}

export const isMediaTypesCacheFresh = (
  cachedAt: number,
  now: number = Date.now(),
  ttlMs: number = MEDIA_TYPES_CACHE_TTL_MS
): boolean => {
  if (!Number.isFinite(cachedAt) || !Number.isFinite(now) || !Number.isFinite(ttlMs)) {
    return false
  }
  if (cachedAt <= 0 || ttlMs <= 0) return false
  return now - cachedAt < ttlMs
}

export const normalizeMediaTypesCacheRecord = (
  value: unknown
): MediaTypesCacheRecord | null => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const record = value as { types?: unknown; cachedAt?: unknown }
  if (!Array.isArray(record.types)) return null
  const types = dedupeTypes(record.types.filter((entry): entry is string => typeof entry === 'string'))
  if (types.length === 0) return null
  const cachedAt =
    typeof record.cachedAt === 'number' ? record.cachedAt : Number(record.cachedAt)
  if (!Number.isFinite(cachedAt)) return null
  return { types, cachedAt }
}

const parseLocalStorageRecord = (rawValue: string | null): MediaTypesCacheRecord | null => {
  if (!rawValue) return null
  try {
    const parsed = JSON.parse(rawValue)
    return normalizeMediaTypesCacheRecord(parsed)
  } catch {
    return null
  }
}

const resolveStorage = (storage?: StorageLike | null): StorageLike | null => {
  if (storage) return storage
  if (typeof window !== 'undefined' && window.localStorage) {
    return window.localStorage
  }
  return null
}

export const getImmediateCachedMediaTypes = (options?: {
  now?: number
  ttlMs?: number
  storage?: StorageLike | null
}): string[] => {
  const now = options?.now ?? Date.now()
  const ttlMs = options?.ttlMs ?? MEDIA_TYPES_CACHE_TTL_MS
  const storage = resolveStorage(options?.storage)

  if (inMemoryCache && isMediaTypesCacheFresh(inMemoryCache.cachedAt, now, ttlMs)) {
    return [...inMemoryCache.types]
  }

  if (!storage) return []
  const parsedRecord = parseLocalStorageRecord(storage.getItem(MEDIA_TYPES_CACHE_KEY))
  if (!parsedRecord || !isMediaTypesCacheFresh(parsedRecord.cachedAt, now, ttlMs)) {
    return []
  }

  inMemoryCache = parsedRecord
  return [...parsedRecord.types]
}

export const seedMediaTypesCache = (
  types: string[],
  options?: {
    cachedAt?: number
    storage?: StorageLike | null
  }
): MediaTypesCacheRecord | null => {
  const deduped = dedupeTypes(types)
  if (deduped.length === 0) return null
  const cachedAt = options?.cachedAt ?? Date.now()
  if (!Number.isFinite(cachedAt)) return null

  const record: MediaTypesCacheRecord = {
    types: deduped,
    cachedAt
  }

  inMemoryCache = record

  const storage = resolveStorage(options?.storage)
  if (storage) {
    try {
      storage.setItem(MEDIA_TYPES_CACHE_KEY, JSON.stringify(record))
    } catch {
      // Best-effort local cache persistence.
    }
  }

  return record
}

export const __resetMediaTypesCacheForTests = (): void => {
  inMemoryCache = null
}
