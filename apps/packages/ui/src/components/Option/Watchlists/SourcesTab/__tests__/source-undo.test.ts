import { describe, expect, it, vi } from "vitest"
import type { WatchlistSource } from "@/types/watchlists"
import {
  resolveBulkSourceUndoWindow,
  resolveSourceUndoWindowSeconds,
  restoreDeletedSources,
  toSourceRestoreId
} from "../source-undo"

const makeSource = (id: number): WatchlistSource => ({
  id,
  name: `Source ${id}`,
  url: `https://example.com/${id}.xml`,
  source_type: "rss",
  active: id % 2 === 0,
  tags: ["tag-a", "tag-b"],
  settings: { depth: id },
  created_at: "2026-02-18T00:00:00Z",
  updated_at: "2026-02-18T00:00:00Z"
})

describe("source undo helpers", () => {
  it("extracts source id for restore endpoint calls", () => {
    const source = makeSource(1)
    expect(toSourceRestoreId(source)).toBe(1)
  })

  it("counts restored and failed sources during bulk restore", async () => {
    const restore = vi
      .fn()
      .mockResolvedValueOnce({ id: 1001 })
      .mockRejectedValueOnce(new Error("duplicate"))
      .mockResolvedValueOnce({ id: 1003 })

    const summary = await restoreDeletedSources(
      [makeSource(1), makeSource(2), makeSource(3)],
      restore
    )

    expect(restore).toHaveBeenCalledTimes(3)
    expect(summary).toEqual({ restored: 2, failed: 1 })
  })

  it("returns zero counts when there are no deleted sources", async () => {
    const restore = vi.fn()
    const summary = await restoreDeletedSources([], restore)

    expect(restore).not.toHaveBeenCalled()
    expect(summary).toEqual({ restored: 0, failed: 0 })
  })

  it("counts permission-denied restore attempts as failed without throwing", async () => {
    const restore = vi.fn().mockRejectedValue(new Error("403 forbidden"))
    const summary = await restoreDeletedSources([makeSource(1), makeSource(2)], restore)

    expect(restore).toHaveBeenCalledTimes(2)
    expect(summary).toEqual({ restored: 0, failed: 2 })
  })

  it("resolves undo window seconds and falls back on invalid values", () => {
    expect(resolveSourceUndoWindowSeconds(18)).toBe(18)
    expect(resolveSourceUndoWindowSeconds("12")).toBe(12)
    expect(resolveSourceUndoWindowSeconds(0)).toBe(10)
    expect(resolveSourceUndoWindowSeconds(undefined)).toBe(10)
    expect(resolveSourceUndoWindowSeconds(-5, 22)).toBe(22)
  })

  it("picks the shortest backend undo window for bulk deletes", () => {
    const summary = resolveBulkSourceUndoWindow([
      { restore_window_seconds: 20 },
      { restore_window_seconds: 12 },
      { restore_window_seconds: "15" }
    ])

    expect(summary).toEqual({ seconds: 12, hasMixedWindows: true })
  })

  it("uses fallback undo window when bulk responses omit valid windows", () => {
    const summary = resolveBulkSourceUndoWindow(
      [{ restore_window_seconds: 0 }, { restore_window_seconds: undefined }],
      25
    )

    expect(summary).toEqual({ seconds: 25, hasMixedWindows: false })
  })
})
