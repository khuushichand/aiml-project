import { describe, expect, it } from "vitest"
import { createRenderPerfTracker } from "../render-profiler"

describe("createRenderPerfTracker", () => {
  it("does not record entries when disabled", () => {
    const tracker = createRenderPerfTracker({
      enabled: false
    })

    tracker.onRender("composer", "update", 3.2, 4.1, 100, 105)

    expect(tracker.snapshot()).toEqual([])
    expect(tracker.summarize()).toEqual([])
  })

  it("records profiler entries and summarizes by id", () => {
    const tracker = createRenderPerfTracker({
      enabled: true
    })

    tracker.onRender("toolbar", "mount", 5, 5.2, 10, 12)
    tracker.onRender("toolbar", "update", 2, 2.5, 20, 22)
    tracker.onRender("textarea", "update", 1, 1.4, 30, 31)

    const snapshot = tracker.snapshot()
    expect(snapshot).toHaveLength(3)
    expect(snapshot[0]).toMatchObject({
      id: "toolbar",
      phase: "mount",
      actualDurationMs: 5
    })

    const summary = tracker.summarize()
    expect(summary).toHaveLength(2)
    expect(summary[0]).toMatchObject({
      id: "toolbar",
      renders: 2,
      updates: 1,
      totalActualDurationMs: 7,
      maxActualDurationMs: 5
    })
    expect(summary[1]).toMatchObject({
      id: "textarea",
      renders: 1,
      updates: 1,
      totalActualDurationMs: 1
    })
  })

  it("keeps only recent entries up to maxEntries", () => {
    const tracker = createRenderPerfTracker({
      enabled: true,
      maxEntries: 2
    })

    tracker.onRender("first", "update", 1, 1, 1, 2)
    tracker.onRender("second", "update", 1, 1, 2, 3)
    tracker.onRender("third", "update", 1, 1, 3, 4)

    expect(tracker.snapshot().map((entry) => entry.id)).toEqual([
      "second",
      "third"
    ])
  })
})
