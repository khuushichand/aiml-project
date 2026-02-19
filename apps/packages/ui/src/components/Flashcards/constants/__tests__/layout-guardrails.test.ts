import { describe, expect, it } from "vitest"
import {
  FLASHCARDS_LAYOUT_GUARDRAILS,
  type FlashcardsSurfaceState,
  type FlashcardsTabSurface
} from "../layout-guardrails"

const expectedStates: FlashcardsSurfaceState[] = ["empty", "active", "success", "error"]
const expectedTabs: FlashcardsTabSurface[] = ["review", "manage", "transfer"]

describe("flashcards layout guardrails", () => {
  it("defines a complete state map for each flashcards tab surface", () => {
    for (const tab of expectedTabs) {
      const rule = FLASHCARDS_LAYOUT_GUARDRAILS[tab]
      expect(rule).toBeDefined()
      expect(new Set(rule.statePriority)).toEqual(new Set(expectedStates))
      expect(Object.keys(rule.primaryActionPlacement).sort()).toEqual([...expectedStates].sort())
      expect(Object.keys(rule.maxTopbarPrimaryCtas).sort()).toEqual([...expectedStates].sort())
    }
  })

  it("enforces review top-bar CTA budgets for active and success states", () => {
    const reviewRule = FLASHCARDS_LAYOUT_GUARDRAILS.review
    expect(reviewRule.maxTopbarPrimaryCtas.active).toBe(0)
    expect(reviewRule.maxTopbarPrimaryCtas.success).toBe(0)
    expect(reviewRule.maxTopbarPrimaryCtas.empty).toBeLessThanOrEqual(1)
  })

  it("enforces zero top-bar primary CTA budgets for manage and transfer surfaces", () => {
    for (const tab of ["manage", "transfer"] as const) {
      const rule = FLASHCARDS_LAYOUT_GUARDRAILS[tab]
      for (const state of expectedStates) {
        expect(rule.maxTopbarPrimaryCtas[state]).toBe(0)
      }
    }
  })
})
