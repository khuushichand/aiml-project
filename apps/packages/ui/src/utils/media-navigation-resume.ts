import type { MediaNavigationNode } from "@/hooks/useMediaNavigation"
import { createSafeStorage } from "@/utils/safe-storage"
import {
  buildMediaNavigationTreeIndex,
  sortMediaNavigationNodes
} from "@/utils/media-navigation-tree"

const storage = createSafeStorage({ area: "local" })

const MEDIA_NAVIGATION_RESUME_STORAGE_PREFIX =
  "tldw:media:navigation:resume:"

export const MEDIA_NAVIGATION_RESUME_MAX_ENTRIES_PER_SCOPE = 1000
export const MEDIA_NAVIGATION_RESUME_MAX_AGE_MS = 90 * 24 * 60 * 60 * 1000

export type MediaNavigationResumeRestoreOutcome =
  | "exact"
  | "path_label"
  | "title_depth"
  | "root_fallback"

export type MediaNavigationResumeEntry = {
  media_id: string
  node_id: string | null
  navigation_version: string | null
  path_label: string | null
  title: string | null
  level: number | null
  last_accessed_at: number
  updated_at: number
}

type MediaNavigationResumeStore = {
  version: 1
  entries: MediaNavigationResumeEntry[]
}

export type MediaNavigationResumeEvictionStats = {
  evicted_lru_count: number
  evicted_stale_count: number
}

type UpsertResumeEntriesInput = {
  entries: MediaNavigationResumeEntry[]
  nextEntry: Omit<MediaNavigationResumeEntry, "last_accessed_at" | "updated_at">
  now?: number
  maxEntries?: number
  maxAgeMs?: number
}

export type UpsertResumeEntriesResult = MediaNavigationResumeEvictionStats & {
  entries: MediaNavigationResumeEntry[]
}

type ResolveResumeSelectionInput = {
  nodes: MediaNavigationNode[]
  navigationVersion: string | null | undefined
  resumeEntry: MediaNavigationResumeEntry | null
}

export type ResolveResumeSelectionResult = {
  nodeId: string
  outcome: MediaNavigationResumeRestoreOutcome
}

type SaveResumeSelectionInput = {
  scopeKey: string
  mediaId: string | number
  node: Pick<MediaNavigationNode, "id" | "path_label" | "title" | "level">
  navigationVersion: string | null | undefined
}

const DEFAULT_STORE: MediaNavigationResumeStore = {
  version: 1,
  entries: []
}

const normalize = (value: string | null | undefined) =>
  String(value || "")
    .trim()
    .toLowerCase()

const sanitizeLevel = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.max(0, Math.floor(value))
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      return Math.max(0, Math.floor(parsed))
    }
  }
  return null
}

const sanitizeTimestamp = (value: unknown, fallback: number): number => {
  if (typeof value === "number" && Number.isFinite(value) && value > 0) {
    return Math.floor(value)
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value)
    if (Number.isFinite(parsed) && parsed > 0) {
      return Math.floor(parsed)
    }
  }
  return fallback
}

const sanitizeResumeEntry = (raw: unknown): MediaNavigationResumeEntry | null => {
  if (!raw || typeof raw !== "object") return null
  const obj = raw as Record<string, unknown>
  const mediaId = String(obj.media_id || "").trim()
  if (!mediaId) return null

  const now = Date.now()
  return {
    media_id: mediaId,
    node_id:
      obj.node_id == null ? null : String(obj.node_id || "").trim() || null,
    navigation_version:
      obj.navigation_version == null
        ? null
        : String(obj.navigation_version || "").trim() || null,
    path_label:
      obj.path_label == null ? null : String(obj.path_label || "").trim() || null,
    title: obj.title == null ? null : String(obj.title || "").trim() || null,
    level: sanitizeLevel(obj.level),
    last_accessed_at: sanitizeTimestamp(obj.last_accessed_at, now),
    updated_at: sanitizeTimestamp(obj.updated_at, now)
  }
}

const sanitizeResumeStore = (raw: unknown): MediaNavigationResumeStore => {
  if (!raw || typeof raw !== "object") return DEFAULT_STORE
  const obj = raw as Record<string, unknown>
  const entriesRaw = Array.isArray(obj.entries) ? obj.entries : []
  const entries = entriesRaw
    .map(sanitizeResumeEntry)
    .filter((entry): entry is MediaNavigationResumeEntry => Boolean(entry))

  return {
    version: 1,
    entries
  }
}

const storageKeyForScope = (scopeKey: string) =>
  `${MEDIA_NAVIGATION_RESUME_STORAGE_PREFIX}${scopeKey}`

const sortEntriesByAccessDesc = (a: MediaNavigationResumeEntry, b: MediaNavigationResumeEntry) => {
  if (a.last_accessed_at !== b.last_accessed_at) {
    return b.last_accessed_at - a.last_accessed_at
  }
  return a.media_id.localeCompare(b.media_id)
}

export const upsertMediaNavigationResumeEntries = ({
  entries,
  nextEntry,
  now = Date.now(),
  maxEntries = MEDIA_NAVIGATION_RESUME_MAX_ENTRIES_PER_SCOPE,
  maxAgeMs = MEDIA_NAVIGATION_RESUME_MAX_AGE_MS
}: UpsertResumeEntriesInput): UpsertResumeEntriesResult => {
  const nextMediaId = String(nextEntry.media_id)
  const staleCutoff = now - maxAgeMs

  const withoutStale = entries.filter(
    (entry) => entry.media_id === nextMediaId || entry.last_accessed_at >= staleCutoff
  )
  const evictedStaleCount = Math.max(0, entries.length - withoutStale.length)

  const deduped = withoutStale.filter((entry) => entry.media_id !== nextMediaId)
  deduped.push({
    ...nextEntry,
    media_id: nextMediaId,
    node_id: nextEntry.node_id ? String(nextEntry.node_id) : null,
    navigation_version: nextEntry.navigation_version
      ? String(nextEntry.navigation_version)
      : null,
    path_label: nextEntry.path_label ? String(nextEntry.path_label) : null,
    title: nextEntry.title ? String(nextEntry.title) : null,
    level: nextEntry.level == null ? null : Math.max(0, Math.floor(nextEntry.level)),
    last_accessed_at: now,
    updated_at: now
  })

  deduped.sort(sortEntriesByAccessDesc)

  const evictedLruCount = Math.max(0, deduped.length - maxEntries)
  const bounded = deduped.slice(0, maxEntries)

  return {
    entries: bounded,
    evicted_lru_count: evictedLruCount,
    evicted_stale_count: evictedStaleCount
  }
}

export const readMediaNavigationResumeStore = async (
  scopeKey: string
): Promise<MediaNavigationResumeStore> => {
  const raw = await storage.get(storageKeyForScope(scopeKey))
  return sanitizeResumeStore(raw)
}

const writeMediaNavigationResumeStore = async (
  scopeKey: string,
  store: MediaNavigationResumeStore
) => {
  await storage.set(storageKeyForScope(scopeKey), {
    version: 1,
    entries: [...store.entries]
  })
}

export const getMediaNavigationResumeEntry = async ({
  scopeKey,
  mediaId
}: {
  scopeKey: string
  mediaId: string | number
}): Promise<MediaNavigationResumeEntry | null> => {
  const store = await readMediaNavigationResumeStore(scopeKey)
  const mediaIdStr = String(mediaId)
  return store.entries.find((entry) => entry.media_id === mediaIdStr) || null
}

export const saveMediaNavigationResumeSelection = async ({
  scopeKey,
  mediaId,
  node,
  navigationVersion
}: SaveResumeSelectionInput): Promise<MediaNavigationResumeEvictionStats> => {
  const store = await readMediaNavigationResumeStore(scopeKey)
  const result = upsertMediaNavigationResumeEntries({
    entries: store.entries,
    nextEntry: {
      media_id: String(mediaId),
      node_id: node.id ? String(node.id) : null,
      navigation_version: navigationVersion
        ? String(navigationVersion)
        : null,
      path_label: node.path_label ? String(node.path_label) : null,
      title: node.title ? String(node.title) : null,
      level: node.level == null ? null : node.level
    }
  })
  await writeMediaNavigationResumeStore(scopeKey, {
    version: 1,
    entries: result.entries
  })
  return {
    evicted_lru_count: result.evicted_lru_count,
    evicted_stale_count: result.evicted_stale_count
  }
}

const selectRootFallbackNodeId = (nodes: MediaNavigationNode[]): string | null => {
  if (nodes.length === 0) return null
  const tree = buildMediaNavigationTreeIndex(nodes)
  if (tree.roots.length > 0) return tree.roots[0].id
  const sortedNodes = sortMediaNavigationNodes(nodes)
  return sortedNodes[0]?.id || null
}

export const resolveMediaNavigationResumeSelection = ({
  nodes,
  navigationVersion,
  resumeEntry
}: ResolveResumeSelectionInput): ResolveResumeSelectionResult | null => {
  if (!resumeEntry || nodes.length === 0) return null

  const sortedNodes = sortMediaNavigationNodes(nodes)
  const byId: Record<string, MediaNavigationNode> = {}
  for (const node of nodes) byId[node.id] = node

  const normalizedVersion = String(navigationVersion || "").trim()
  const entryVersion = String(resumeEntry.navigation_version || "").trim()
  const canUseExact = Boolean(normalizedVersion) && normalizedVersion === entryVersion
  if (canUseExact && resumeEntry.node_id && byId[resumeEntry.node_id]) {
    return {
      nodeId: resumeEntry.node_id,
      outcome: "exact"
    }
  }

  const desiredPathLabel = normalize(resumeEntry.path_label)
  if (desiredPathLabel) {
    const pathMatch = sortedNodes.find(
      (node) => normalize(node.path_label) === desiredPathLabel
    )
    if (pathMatch) {
      return {
        nodeId: pathMatch.id,
        outcome: "path_label"
      }
    }
  }

  const desiredTitle = normalize(resumeEntry.title)
  if (desiredTitle) {
    const titleMatches = sortedNodes.filter(
      (node) => normalize(node.title) === desiredTitle
    )
    if (titleMatches.length > 0) {
      if (resumeEntry.level == null) {
        return {
          nodeId: titleMatches[0].id,
          outcome: "title_depth"
        }
      }

      let bestMatch = titleMatches[0]
      let bestDistance = Math.abs((bestMatch.level || 0) - resumeEntry.level)
      for (let i = 1; i < titleMatches.length; i += 1) {
        const candidate = titleMatches[i]
        const distance = Math.abs((candidate.level || 0) - resumeEntry.level)
        if (distance < bestDistance) {
          bestMatch = candidate
          bestDistance = distance
        }
      }
      return {
        nodeId: bestMatch.id,
        outcome: "title_depth"
      }
    }
  }

  const rootFallbackNodeId = selectRootFallbackNodeId(nodes)
  if (!rootFallbackNodeId) return null
  return {
    nodeId: rootFallbackNodeId,
    outcome: "root_fallback"
  }
}
