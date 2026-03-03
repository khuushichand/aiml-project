import { describe, expect, it } from "vitest"
import { createComposerPerfTracker } from "../composer-perf"

describe("createComposerPerfTracker", () => {
  it("records durations only when enabled", () => {
    const tracker = createComposerPerfTracker({
      enabled: false,
      now: (() => {
        let time = 0
        return () => {
          time += 5
          return time
        }
      })()
    })

    const end = tracker.start("input-change")
    end()

    expect(tracker.snapshot()).toEqual([])
  })

  it("records label and duration when enabled", () => {
    const tracker = createComposerPerfTracker({
      enabled: true,
      now: (() => {
        const values = [10, 17, 24, 32]
        let index = 0
        return () => {
          const value = values[Math.min(index, values.length - 1)]
          index += 1
          return value
        }
      })()
    })

    const end = tracker.start("textarea-change")
    end()

    const entries = tracker.snapshot()
    expect(entries).toHaveLength(1)
    expect(entries[0]?.label).toBe("textarea-change")
    expect(entries[0]?.durationMs).toBe(7)
    expect(entries[0]?.atMs).toBe(17)
  })

  it("keeps only the most recent entries up to maxEntries", () => {
    const tracker = createComposerPerfTracker({
      enabled: true,
      maxEntries: 2,
      now: (() => {
        let time = 0
        return () => {
          time += 1
          return time
        }
      })()
    })

    tracker.start("a")()
    tracker.start("b")()
    tracker.start("c")()

    expect(tracker.snapshot().map((entry) => entry.label)).toEqual(["b", "c"])
  })
})
