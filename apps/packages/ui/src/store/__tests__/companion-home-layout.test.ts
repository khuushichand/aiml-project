import { beforeEach, describe, expect, it, vi } from "vitest"

import {
  DEFAULT_COMPANION_HOME_LAYOUT,
  loadCompanionHomeLayout,
  moveCompanionHomeCard,
  saveCompanionHomeLayout,
  setCompanionHomeCardVisibility
} from "../companion-home-layout"

const getIds = (layout: typeof DEFAULT_COMPANION_HOME_LAYOUT) =>
  layout.map((card) => card.id)

const getVisibleIds = (layout: typeof DEFAULT_COMPANION_HOME_LAYOUT) =>
  layout.filter((card) => card.visible).map((card) => card.id)

describe("companion home layout persistence", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
    Reflect.deleteProperty(globalThis, "chrome")
  })

  it("loads the shared default card list with pinned system cards intact", async () => {
    const layout = await loadCompanionHomeLayout("options")

    expect(getIds(layout)).toEqual([
      "inbox-preview",
      "needs-attention",
      "resume-work",
      "goals-focus",
      "recent-activity",
      "reading-queue"
    ])
    expect(layout.slice(0, 2)).toEqual([
      expect.objectContaining({
        id: "inbox-preview",
        fixed: true,
        visible: true
      }),
      expect.objectContaining({
        id: "needs-attention",
        fixed: true,
        visible: true
      })
    ])
  })

  it("persists per-surface overrides through localStorage when chrome storage is unavailable", async () => {
    const hiddenGoals = setCompanionHomeCardVisibility(
      DEFAULT_COMPANION_HOME_LAYOUT,
      "goals-focus",
      false
    )
    const reordered = moveCompanionHomeCard(
      hiddenGoals,
      "reading-queue",
      "up"
    )

    await saveCompanionHomeLayout("options", reordered)

    const optionsLayout = await loadCompanionHomeLayout("options")
    const sidepanelLayout = await loadCompanionHomeLayout("sidepanel")

    expect(getVisibleIds(optionsLayout)).not.toContain("goals-focus")
    expect(getIds(optionsLayout).indexOf("reading-queue")).toBeLessThan(
      getIds(optionsLayout).indexOf("recent-activity")
    )
    expect(getVisibleIds(sidepanelLayout)).toContain("goals-focus")
    expect(getIds(sidepanelLayout)).toEqual(getIds(DEFAULT_COMPANION_HOME_LAYOUT))
  })

  it("applies a chrome.storage.local override while forcing pinned system cards to remain visible", async () => {
    const chromeGet = vi.fn(async () => ({
      "tldw:companion-home-layout:options": {
        order: [
          "inbox-preview",
          "needs-attention",
          "recent-activity",
          "resume-work",
          "reading-queue",
          "goals-focus",
          "unknown-card"
        ],
        hidden: ["inbox-preview", "goals-focus"]
      }
    }))

    Object.assign(globalThis, {
      chrome: {
        storage: {
          local: {
            get: chromeGet
          }
        }
      }
    })

    const layout = await loadCompanionHomeLayout("options")

    expect(chromeGet).toHaveBeenCalledWith("tldw:companion-home-layout:options")
    expect(getIds(layout)).toEqual([
      "inbox-preview",
      "needs-attention",
      "recent-activity",
      "resume-work",
      "reading-queue",
      "goals-focus"
    ])
    expect(layout[0]).toEqual(
      expect.objectContaining({
        id: "inbox-preview",
        fixed: true,
        visible: true
      })
    )
    expect(layout.find((card) => card.id === "goals-focus")).toEqual(
      expect.objectContaining({
        id: "goals-focus",
        visible: false
      })
    )
  })

  it("re-pins fixed system cards to the front when persisted order is malformed", async () => {
    const chromeGet = vi.fn(async () => ({
      "tldw:companion-home-layout:options": {
        order: [
          "recent-activity",
          "resume-work",
          "inbox-preview",
          "reading-queue",
          "needs-attention",
          "goals-focus"
        ],
        hidden: []
      }
    }))

    Object.assign(globalThis, {
      chrome: {
        storage: {
          local: {
            get: chromeGet
          }
        }
      }
    })

    const layout = await loadCompanionHomeLayout("options")

    expect(getIds(layout)).toEqual([
      "inbox-preview",
      "needs-attention",
      "recent-activity",
      "resume-work",
      "reading-queue",
      "goals-focus"
    ])
    expect(layout.slice(0, 2)).toEqual([
      expect.objectContaining({ id: "inbox-preview", fixed: true }),
      expect.objectContaining({ id: "needs-attention", fixed: true })
    ])
  })
})
