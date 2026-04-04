// @vitest-environment jsdom
import { describe, expect, it } from "vitest"

/**
 * Mirrors the condition used in QuizPlayground.tsx to decide whether
 * to auto-switch to the "generate" tab on first load.
 */
function shouldDefaultToGenerate(
  totalQuizzes: number,
  initialAssessmentIntent: unknown
): boolean {
  return totalQuizzes === 0 && !initialAssessmentIntent
}

/**
 * Mirrors the condition used in GenerateTab.tsx to decide whether
 * to show the "no media content" info alert.
 */
function shouldShowNoMediaAlert(
  isLoadingList: boolean,
  loadedMediaItemsLength: number
): boolean {
  return !isLoadingList && loadedMediaItemsLength === 0
}

/**
 * Mirrors the condition used in ResultsTab.tsx to decide whether
 * to show the empty state with a "Take a Quiz" CTA.
 */
function shouldShowEmptyResultsCTA(
  attemptsLength: number,
  hasActiveFilters: boolean
): boolean {
  return attemptsLength === 0 && !hasActiveFilters
}

describe("Quiz FTUX behaviors", () => {
  describe("Task 11: default tab resolution", () => {
    it("should resolve to 'generate' when totalQuizzes is 0 and no assessment intent", () => {
      expect(shouldDefaultToGenerate(0, null)).toBe(true)
    })

    it("should NOT switch when there are quizzes", () => {
      expect(shouldDefaultToGenerate(5, null)).toBe(false)
    })

    it("should NOT switch when there is an assessment intent", () => {
      expect(shouldDefaultToGenerate(0, { startQuizId: 42 })).toBe(false)
    })

    it("should NOT switch when totalQuizzes is > 0 even with no intent", () => {
      expect(shouldDefaultToGenerate(1, null)).toBe(false)
    })
  })

  describe("Task 12: empty-media alert condition", () => {
    it("should show alert when media list is loaded and empty", () => {
      expect(shouldShowNoMediaAlert(false, 0)).toBe(true)
    })

    it("should NOT show alert while still loading", () => {
      expect(shouldShowNoMediaAlert(true, 0)).toBe(false)
    })

    it("should NOT show alert when media items exist", () => {
      expect(shouldShowNoMediaAlert(false, 3)).toBe(false)
    })
  })

  describe("Task 13: Results tab empty state CTA condition", () => {
    it("should show CTA when no attempts and no active filters", () => {
      expect(shouldShowEmptyResultsCTA(0, false)).toBe(true)
    })

    it("should NOT show CTA when there are attempts", () => {
      expect(shouldShowEmptyResultsCTA(2, false)).toBe(false)
    })

    it("should NOT show CTA when filters are active (even with no results)", () => {
      expect(shouldShowEmptyResultsCTA(0, true)).toBe(false)
    })
  })
})
