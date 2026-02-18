import { describe, expect, it, vi } from "vitest"
import type { WatchlistSource } from "@/types/watchlists"
import {
  restoreDeletedSources,
  toSourceCreatePayload
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
  it("converts a source into a create payload for restore", () => {
    const source = makeSource(1)
    expect(toSourceCreatePayload(source)).toEqual({
      name: "Source 1",
      url: "https://example.com/1.xml",
      source_type: "rss",
      active: false,
      tags: ["tag-a", "tag-b"],
      settings: { depth: 1 }
    })
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
})
