import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ResultsTab } from "../ResultsTab"
import { useAllAttemptsQuery, useAttemptQuery, useQuizzesQuery } from "../../hooks"

const interpolate = (template: string, values: Record<string, unknown> | undefined) => {
  return template.replace(/\{\{\s*([^\s}]+)\s*\}\}/g, (_, key: string) => {
    const value = values?.[key]
    return value == null ? "" : String(value)
  })
}

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
            [key: string]: unknown
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      const defaultValue = defaultValueOrOptions?.defaultValue
      if (typeof defaultValue === "string") {
        return interpolate(defaultValue, defaultValueOrOptions)
      }
      return key
    }
  })
}))

vi.mock("../../hooks", () => ({
  useAllAttemptsQuery: vi.fn(),
  useQuizzesQuery: vi.fn(),
  useAttemptQuery: vi.fn()
}))

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("ResultsTab filters and retake workflow", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.sessionStorage.clear()

    vi.mocked(useAllAttemptsQuery).mockReturnValue({
      data: {
        items: [
          {
            id: 301,
            quiz_id: 7,
            started_at: "2026-02-18T10:00:00Z",
            completed_at: "2026-02-18T10:03:00Z",
            score: 2,
            total_possible: 3,
            time_spent_seconds: 180,
            answers: []
          },
          {
            id: 302,
            quiz_id: 8,
            started_at: "2026-02-17T10:00:00Z",
            completed_at: "2026-02-17T10:05:00Z",
            score: 1,
            total_possible: 5,
            time_spent_seconds: 300,
            answers: []
          }
        ],
        count: 2
      },
      isLoading: false
    } as any)

    vi.mocked(useQuizzesQuery).mockReturnValue({
      data: {
        items: [
          { id: 7, name: "Biology Basics", total_questions: 3 },
          { id: 8, name: "Chemistry Basics", total_questions: 5 }
        ],
        count: 2
      },
      isLoading: false
    } as any)

    vi.mocked(useAttemptQuery).mockReturnValue({
      data: null,
      isLoading: false,
      isFetching: false
    } as any)
  })

  it("applies persisted quiz filter to attempts query and supports retake action", () => {
    window.sessionStorage.setItem("quiz-results-filters-v1", JSON.stringify({
      page: 1,
      pageSize: 10,
      quizFilterId: 7,
      passFilter: "all",
      dateRangeFilter: "all"
    }))

    const onRetakeQuiz = vi.fn()
    render(<ResultsTab onRetakeQuiz={onRetakeQuiz} />)

    expect(useAllAttemptsQuery).toHaveBeenCalledWith(expect.objectContaining({ quiz_id: 7 }))

    fireEvent.click(screen.getByRole("button", { name: /Retake/i }))
    expect(onRetakeQuiz).toHaveBeenCalledWith({
      startQuizId: 7,
      highlightQuizId: 7,
      sourceTab: "results",
      attemptId: 301
    })
  })

  it("shows no-match empty state when persisted pass filter excludes all attempts", () => {
    window.sessionStorage.setItem("quiz-results-filters-v1", JSON.stringify({
      page: 1,
      pageSize: 10,
      quizFilterId: null,
      passFilter: "pass",
      dateRangeFilter: "all"
    }))

    vi.mocked(useAllAttemptsQuery).mockReturnValue({
      data: {
        items: [
          {
            id: 401,
            quiz_id: 7,
            started_at: "2026-02-18T10:00:00Z",
            completed_at: "2026-02-18T10:03:00Z",
            score: 1,
            total_possible: 5,
            time_spent_seconds: 180,
            answers: []
          }
        ],
        count: 1
      },
      isLoading: false
    } as any)

    render(<ResultsTab />)

    expect(screen.getByText("No attempts match the selected filters.")).toBeInTheDocument()
  })

  it("restores persisted pagination state on remount", () => {
    window.sessionStorage.setItem("quiz-results-filters-v1", JSON.stringify({
      page: 2,
      pageSize: 1,
      quizFilterId: null,
      passFilter: "all",
      dateRangeFilter: "all"
    }))

    render(<ResultsTab />)

    expect(screen.getByText("Chemistry Basics")).toBeInTheDocument()
    expect(screen.queryByText("Biology Basics")).not.toBeInTheDocument()
  })

  it("uses quiz-specific passing_score when applying pass/fail filters", () => {
    window.sessionStorage.setItem("quiz-results-filters-v1", JSON.stringify({
      page: 1,
      pageSize: 10,
      quizFilterId: null,
      passFilter: "pass",
      dateRangeFilter: "all"
    }))

    vi.mocked(useQuizzesQuery).mockReturnValue({
      data: {
        items: [
          { id: 7, name: "Biology Basics", total_questions: 3, passing_score: 90 }
        ],
        count: 1
      },
      isLoading: false
    } as any)

    vi.mocked(useAllAttemptsQuery).mockReturnValue({
      data: {
        items: [
          {
            id: 501,
            quiz_id: 7,
            started_at: "2026-02-18T10:00:00Z",
            completed_at: "2026-02-18T10:04:00Z",
            score: 4,
            total_possible: 5,
            time_spent_seconds: 240,
            answers: []
          }
        ],
        count: 1
      },
      isLoading: false
    } as any)

    render(<ResultsTab />)

    expect(screen.getByText("No attempts match the selected filters.")).toBeInTheDocument()
  })

  it("renders score trend visualization when at least two attempts exist", () => {
    render(<ResultsTab />)

    expect(screen.getByText("Score Trend")).toBeInTheDocument()
    const chart = screen.getByLabelText("Score percentage trend over recent attempts")
    expect(chart.querySelector("polyline")).not.toBeNull()
  })
})
