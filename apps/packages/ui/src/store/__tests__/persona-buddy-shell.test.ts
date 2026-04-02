// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest"

import {
  DEFAULT_PERSONA_BUDDY_POSITION_BY_BUCKET,
  clampPersonaBuddyPositionBucket,
  createPersonaBuddyShellStore,
  normalizePersonaBuddyShellPositions
} from "../persona-buddy-shell"

describe("persona-buddy-shell store", () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it("starts in compact mode by default", () => {
    const store = createPersonaBuddyShellStore()

    expect(store.getState().isCompact).toBe(true)
    expect(store.getState().isExpanded).toBe(false)
  })

  it("does not persist an expanded session across reloads", () => {
    const firstStore = createPersonaBuddyShellStore()
    firstStore.getState().setExpanded(true)

    const reloadedStore = createPersonaBuddyShellStore()

    expect(reloadedStore.getState().isCompact).toBe(true)
    expect(reloadedStore.getState().isExpanded).toBe(false)
  })

  it("remembers positions independently for web and sidepanel desktop buckets", () => {
    const store = createPersonaBuddyShellStore()

    store.getState().setPositionForBucket("web-desktop", { x: 42, y: 84 })
    store.getState().setPositionForBucket("sidepanel-desktop", { x: 12, y: 24 })

    const reloadedStore = createPersonaBuddyShellStore()

    expect(reloadedStore.getState().getPositionForBucket("web-desktop")).toEqual(
      { x: 42, y: 84 }
    )
    expect(
      reloadedStore.getState().getPositionForBucket("sidepanel-desktop")
    ).toEqual({ x: 12, y: 24 })
  })

  it("clamps unknown buckets and fills missing bucket positions with safe defaults", () => {
    expect(clampPersonaBuddyPositionBucket("unknown-bucket")).toBe(
      "web-desktop"
    )

    expect(
      normalizePersonaBuddyShellPositions({
        "web-desktop": { x: 9, y: 18 }
      })
    ).toEqual({
      "web-desktop": { x: 9, y: 18 },
      "sidepanel-desktop":
        DEFAULT_PERSONA_BUDDY_POSITION_BY_BUCKET["sidepanel-desktop"]
    })
  })
})
