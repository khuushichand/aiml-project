export type RenderProfilerPhase = "mount" | "update" | "nested-update"

export type RenderPerfEntry = {
  id: string
  phase: RenderProfilerPhase
  actualDurationMs: number
  baseDurationMs: number
  startTimeMs: number
  commitTimeMs: number
}

export type RenderPerfSummaryEntry = {
  id: string
  renders: number
  updates: number
  totalActualDurationMs: number
  avgActualDurationMs: number
  maxActualDurationMs: number
}

export type RenderPerfTracker = {
  onRender: (
    id: string,
    phase: RenderProfilerPhase,
    actualDuration: number,
    baseDuration: number,
    startTime: number,
    commitTime: number
  ) => void
  snapshot: () => RenderPerfEntry[]
  summarize: () => RenderPerfSummaryEntry[]
  clear: () => void
  isEnabled: () => boolean
}

type CreateRenderPerfTrackerOptions = {
  enabled: boolean
  maxEntries?: number
}

const sortSummaryEntries = (
  left: RenderPerfSummaryEntry,
  right: RenderPerfSummaryEntry
) => {
  if (right.totalActualDurationMs !== left.totalActualDurationMs) {
    return right.totalActualDurationMs - left.totalActualDurationMs
  }
  if (right.renders !== left.renders) {
    return right.renders - left.renders
  }
  return left.id.localeCompare(right.id)
}

export const createRenderPerfTracker = ({
  enabled,
  maxEntries = 500
}: CreateRenderPerfTrackerOptions): RenderPerfTracker => {
  const entries: RenderPerfEntry[] = []

  const push = (entry: RenderPerfEntry) => {
    entries.push(entry)
    if (entries.length > maxEntries) {
      entries.splice(0, entries.length - maxEntries)
    }
  }

  return {
    onRender(
      id,
      phase,
      actualDuration,
      baseDuration,
      startTime,
      commitTime
    ) {
      if (!enabled) return
      push({
        id,
        phase,
        actualDurationMs: Math.max(0, Number(actualDuration) || 0),
        baseDurationMs: Math.max(0, Number(baseDuration) || 0),
        startTimeMs: Math.max(0, Number(startTime) || 0),
        commitTimeMs: Math.max(0, Number(commitTime) || 0)
      })
    },
    snapshot() {
      return [...entries]
    },
    summarize() {
      const stats = new Map<string, RenderPerfSummaryEntry>()

      for (const entry of entries) {
        const current = stats.get(entry.id) ?? {
          id: entry.id,
          renders: 0,
          updates: 0,
          totalActualDurationMs: 0,
          avgActualDurationMs: 0,
          maxActualDurationMs: 0
        }
        current.renders += 1
        if (entry.phase !== "mount") {
          current.updates += 1
        }
        current.totalActualDurationMs += entry.actualDurationMs
        current.maxActualDurationMs = Math.max(
          current.maxActualDurationMs,
          entry.actualDurationMs
        )
        stats.set(entry.id, current)
      }

      return Array.from(stats.values())
        .map((entry) => ({
          ...entry,
          avgActualDurationMs:
            entry.renders > 0
              ? entry.totalActualDurationMs / entry.renders
              : 0
        }))
        .sort(sortSummaryEntries)
    },
    clear() {
      entries.length = 0
    },
    isEnabled() {
      return enabled
    }
  }
}
