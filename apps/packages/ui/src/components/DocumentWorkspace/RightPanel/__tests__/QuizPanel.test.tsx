import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { QuizPanel } from "../QuizPanel"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"

const persistAnswerMock = vi.fn()

const mockQuiz = {
  quizId: "quiz-1",
  mediaId: 42,
  generatedAt: "2026-03-11T10:00:00.000Z",
  questions: [
    {
      question: "What is the first planet from the Sun?",
      options: ["Mercury", "Venus", "Earth"],
      correctAnswer: "Mercury",
      explanation: "Mercury is closest to the Sun."
    }
  ]
}

vi.mock("@/hooks/document-workspace/useDocumentQuiz", () => ({
  useDocumentQuiz: () => ({
    quiz: mockQuiz,
    isGenerating: false,
    error: null,
    generateQuiz: vi.fn(),
    clearQuiz: vi.fn(),
    loadQuiz: vi.fn(),
    persistAnswer: persistAnswerMock
  }),
  useQuizHistory: () => ({
    history: [],
    isLoading: false,
    refresh: vi.fn()
  }),
  QUESTION_TYPE_INFO: {
    multiple_choice: { label: "Multiple Choice", description: "" },
    true_false: { label: "True/False", description: "" },
    short_answer: { label: "Short Answer", description: "" },
    mixed: { label: "Mixed", description: "" }
  },
  DIFFICULTY_INFO: {
    easy: { label: "Easy", description: "" },
    medium: { label: "Medium", description: "" },
    hard: { label: "Hard", description: "" }
  }
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, defaultValue?: string) => defaultValue || _key
  })
}))

describe("QuizPanel", () => {
  beforeEach(() => {
    persistAnswerMock.mockReset()
    useDocumentWorkspaceStore.setState({ activeDocumentId: 42 })
  })

  it("persists answer progress as soon as the user selects an answer", () => {
    render(<QuizPanel />)

    fireEvent.click(screen.getByRole("radio", { name: "Mercury" }))

    expect(persistAnswerMock).toHaveBeenCalledWith(
      { 0: "Mercury" },
      100,
      expect.any(Number)
    )
  })
})
