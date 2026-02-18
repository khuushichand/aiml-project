import type { SavedWorkspace } from "@/types/workspace"

const getTimeDelta = (date: Date, now: Date): number => {
  return Math.max(0, now.getTime() - date.getTime())
}

export const formatWorkspaceLastAccessed = (
  lastAccessedAt: Date,
  now: Date = new Date()
): string => {
  const deltaMs = getTimeDelta(lastAccessedAt, now)
  const minute = 60 * 1000
  const hour = 60 * minute
  const day = 24 * hour
  const week = 7 * day

  if (deltaMs < minute) return "just now"
  if (deltaMs < hour) return `${Math.floor(deltaMs / minute)}m ago`
  if (deltaMs < day) return `${Math.floor(deltaMs / hour)}h ago`
  if (deltaMs < week) return `${Math.floor(deltaMs / day)}d ago`

  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric"
  }).format(lastAccessedAt)
}

export const filterSavedWorkspaces = (
  workspaces: SavedWorkspace[],
  query: string
): SavedWorkspace[] => {
  const normalizedQuery = query.trim().toLowerCase()
  if (!normalizedQuery) return workspaces

  return workspaces.filter((workspace) => {
    const haystack = `${workspace.name} ${workspace.tag}`.toLowerCase()
    return haystack.includes(normalizedQuery)
  })
}
