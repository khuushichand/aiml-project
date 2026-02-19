import { describe, expect, it } from "vitest"
import {
  buildFlashcardsStudyRouteFromQuiz,
  buildQuizAssessmentRouteFromFlashcards,
  parseFlashcardsStudyIntentFromLocation,
  parseFlashcardsStudyIntentFromSearch,
  parseQuizAssessmentIntentFromLocation,
  parseQuizAssessmentIntentFromSearch
} from "@/services/tldw/quiz-flashcards-handoff"

describe("quiz/flashcards cross-navigation handoff helpers", () => {
  it("builds flashcards study routes with contextual quiz identifiers", () => {
    const route = buildFlashcardsStudyRouteFromQuiz({
      quizId: 42,
      attemptId: 501,
      deckId: 7
    })

    expect(route.startsWith("/flashcards?")).toBe(true)
    const params = new URLSearchParams(route.slice(route.indexOf("?") + 1))
    expect(params.get("tab")).toBe("review")
    expect(params.get("study_source")).toBe("quiz")
    expect(params.get("quiz_id")).toBe("42")
    expect(params.get("attempt_id")).toBe("501")
    expect(params.get("deck_id")).toBe("7")
  })

  it("parses flashcards study intent from search and ignores invalid IDs", () => {
    const valid = parseFlashcardsStudyIntentFromSearch(
      "?study_source=quiz&quiz_id=42&attempt_id=501&deck_id=9"
    )
    expect(valid).toEqual({
      quizId: 42,
      attemptId: 501,
      deckId: 9
    })

    const invalid = parseFlashcardsStudyIntentFromSearch(
      "?study_source=quiz&quiz_id=abc&attempt_id=-1&deck_id=0"
    )
    expect(invalid).toBeNull()
  })

  it("parses flashcards study intent from hash-based routes", () => {
    const intent = parseFlashcardsStudyIntentFromLocation({
      search: "",
      hash: "#/flashcards?study_source=quiz&quiz_id=88&attempt_id=12"
    })
    expect(intent).toEqual({
      quizId: 88,
      attemptId: 12,
      deckId: undefined
    })
  })

  it("builds quiz assessment routes and defaults highlight to start quiz", () => {
    const route = buildQuizAssessmentRouteFromFlashcards({
      startQuizId: 77,
      deckId: 11,
      deckName: "Biology Recovery",
      sourceAttemptId: 600
    })
    const params = new URLSearchParams(route.slice(route.indexOf("?") + 1))
    expect(params.get("tab")).toBe("take")
    expect(params.get("source")).toBe("flashcards")
    expect(params.get("start_quiz_id")).toBe("77")
    expect(params.get("highlight_quiz_id")).toBe("77")
    expect(params.get("deck_id")).toBe("11")
    expect(params.get("deck_name")).toBe("Biology Recovery")
    expect(params.get("source_attempt_id")).toBe("600")
  })

  it("parses quiz assessment intent and handles invalid params gracefully", () => {
    const valid = parseQuizAssessmentIntentFromSearch(
      "?source=flashcards&start_quiz_id=99&highlight_quiz_id=100&deck_id=5&deck_name=Chem"
    )
    expect(valid).toEqual({
      startQuizId: 99,
      highlightQuizId: 100,
      deckId: 5,
      deckName: "Chem",
      sourceAttemptId: undefined,
      assignmentMode: undefined,
      assignmentDueAt: undefined,
      assignmentNote: undefined,
      assignedByRole: undefined
    })

    const invalid = parseQuizAssessmentIntentFromSearch(
      "?source=flashcards&start_quiz_id=-2&highlight_quiz_id=zero&deck_id=abc"
    )
    expect(invalid).toBeNull()
  })

  it("parses quiz assessment intent from hash-based routes", () => {
    const intent = parseQuizAssessmentIntentFromLocation({
      search: "",
      hash: "#/quiz?source=flashcards&start_quiz_id=123&source_attempt_id=10"
    })
    expect(intent).toEqual({
      startQuizId: 123,
      highlightQuizId: undefined,
      deckId: undefined,
      deckName: undefined,
      sourceAttemptId: 10,
      assignmentMode: undefined,
      assignmentDueAt: undefined,
      assignmentNote: undefined,
      assignedByRole: undefined
    })
  })

  it("parses shared assignment metadata from quiz links", () => {
    const intent = parseQuizAssessmentIntentFromSearch(
      "?start_quiz_id=44&assignment_mode=shared&assignment_due_at=2026-03-01T14:30:00.000Z&assignment_note=Review+chapters+2-3&assigned_by_role=lead"
    )

    expect(intent).toEqual({
      startQuizId: 44,
      highlightQuizId: undefined,
      deckId: undefined,
      deckName: undefined,
      sourceAttemptId: undefined,
      assignmentMode: "shared",
      assignmentDueAt: "2026-03-01T14:30:00.000Z",
      assignmentNote: "Review chapters 2-3",
      assignedByRole: "lead"
    })
  })
})
