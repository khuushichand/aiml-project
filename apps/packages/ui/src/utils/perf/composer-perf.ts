export type ComposerPerfEntry = {
  label: string
  durationMs: number
  atMs: number
}

export type ComposerPerfTracker = {
  start: (label: string) => () => void
  snapshot: () => ComposerPerfEntry[]
  clear: () => void
  isEnabled: () => boolean
}

type CreateComposerPerfTrackerOptions = {
  enabled: boolean
  now?: () => number
  maxEntries?: number
}

const noop = () => {}

export const createComposerPerfTracker = ({
  enabled,
  now = () =>
    typeof performance !== "undefined" && typeof performance.now === "function"
      ? performance.now()
      : Date.now(),
  maxEntries = 200
}: CreateComposerPerfTrackerOptions): ComposerPerfTracker => {
  const entries: ComposerPerfEntry[] = []

  const push = (entry: ComposerPerfEntry) => {
    entries.push(entry)
    if (entries.length > maxEntries) {
      entries.splice(0, entries.length - maxEntries)
    }
  }

  return {
    start(label: string) {
      if (!enabled) return noop
      const startedAt = now()
      return () => {
        const endedAt = now()
        push({
          label,
          durationMs: Math.max(0, endedAt - startedAt),
          atMs: endedAt
        })
      }
    },
    snapshot() {
      return [...entries]
    },
    clear() {
      entries.length = 0
    },
    isEnabled() {
      return enabled
    }
  }
}

