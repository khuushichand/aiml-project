import { afterEach, describe, expect, it, vi } from "vitest"

import { SPLASH_CARDS, randomSplashCard } from "../splash-cards"

describe("randomSplashCard selection", () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("returns the only enabled splash card when filtered to one name", () => {
    const selected = SPLASH_CARDS[3]
    const card = randomSplashCard({ enabledNames: [selected.name] })
    expect(card.name).toBe(selected.name)
  })

  it("falls back to the default pool when enabled names filter resolves empty", () => {
    vi.spyOn(Math, "random").mockReturnValue(0)
    const card = randomSplashCard({ enabledNames: ["not-a-real-card"] })
    expect(card.name).toBe(SPLASH_CARDS[0].name)
  })
})

