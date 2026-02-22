import { describe, expect, it } from "vitest"
import { buildQuickChatPageTutorialEntries } from "../QuickChatGuidesPanel"

describe("quick chat per-page tutorials", () => {
  it("returns page tutorials for canonical /chat route", () => {
    const entries = buildQuickChatPageTutorialEntries("/chat", [])

    expect(entries.length).toBeGreaterThan(0)
    expect(entries.some((entry) => entry.tutorial.id === "playground-basics")).toBe(
      true
    )
  })

  it("normalizes legacy route aliases", () => {
    const entries = buildQuickChatPageTutorialEntries("/options/playground", [])

    expect(entries.some((entry) => entry.tutorial.id === "playground-basics")).toBe(
      true
    )
  })

  it("returns media page tutorials for /media route", () => {
    const entries = buildQuickChatPageTutorialEntries("/media", [])

    expect(entries.some((entry) => entry.tutorial.id === "media-basics")).toBe(true)
  })

  it("maps /options/media alias to media tutorials", () => {
    const entries = buildQuickChatPageTutorialEntries("/options/media", [])

    expect(entries.some((entry) => entry.tutorial.id === "media-basics")).toBe(true)
  })

  it("marks advanced tutorials locked until prerequisites are complete", () => {
    const entries = buildQuickChatPageTutorialEntries("/chat", [])
    const toolsTutorial = entries.find(
      (entry) => entry.tutorial.id === "playground-tools"
    )

    expect(toolsTutorial?.isLocked).toBe(true)

    const unlockedEntries = buildQuickChatPageTutorialEntries("/chat", [
      "playground-basics"
    ])
    const unlockedToolsTutorial = unlockedEntries.find(
      (entry) => entry.tutorial.id === "playground-tools"
    )

    expect(unlockedToolsTutorial?.isLocked).toBe(false)
  })

  it("returns empty tutorial list for routes without definitions", () => {
    const entries = buildQuickChatPageTutorialEntries("/settings/health", [])
    expect(entries).toEqual([])
  })
})
