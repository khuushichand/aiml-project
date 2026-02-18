import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"
import { TakeQuizTab } from "../TakeQuizTab"
import {
  useAttemptsQuery,
  useQuizzesQuery,
  useQuizQuery,
  useStartAttemptMutation,
  useSubmitAttemptMutation
} from "../../hooks"
import { useQuizAutoSave } from "../../hooks/useQuizAutoSave"
import { useQuizTimer } from "../../hooks/useQuizTimer"

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

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

vi.mock("../../hooks", () => ({
  useAttemptsQuery: vi.fn(),
  useQuizzesQuery: vi.fn(),
  useQuizQuery: vi.fn(),
  useStartAttemptMutation: vi.fn(),
  useSubmitAttemptMutation: vi.fn()
}))

vi.mock("../../hooks/useQuizTimer", () => ({
  useQuizTimer: vi.fn(() => null)
}))

vi.mock("../../hooks/useQuizAutoSave", () => ({
  useQuizAutoSave: vi.fn(() => ({
    storageUnavailable: false,
    restoreSavedAnswers: vi.fn(async () => false),
    clearSavedProgress: vi.fn(async () => {}),
    hasSavedProgress: vi.fn(async () => false),
    getSavedProgress: vi.fn(async () => null),
    forceSave: vi.fn(async () => {})
  }))
}))

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("TakeQuizTab start flow", () => {
  const originalMatchMedia = window.matchMedia

  beforeAll(() => {
    if (typeof window.matchMedia !== "function") {
      Object.defineProperty(window, "matchMedia", {
        writable: true,
        value: vi.fn().mockImplementation((query: string) => ({
          matches: false,
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn()
        }))
      })
    }
  })

  afterAll(() => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: originalMatchMedia
    })
  })

  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()

    vi.mocked(useAttemptsQuery).mockReturnValue({
      data: {
        items: [
          {
            id: 99,
            quiz_id: 7,
            started_at: "2026-02-17T12:00:00Z",
            completed_at: "2026-02-17T12:10:00Z",
            score: 8,
            total_possible: 10,
            answers: []
          }
        ],
        count: 1
      }
    } as any)

    vi.mocked(useQuizzesQuery).mockReturnValue({
      data: {
        items: [
          {
            id: 7,
            name: "Biology Basics",
            description: "Cell structures and functions",
            total_questions: 12,
            time_limit_seconds: 900,
            passing_score: 75,
            media_id: 42,
            created_at: "2026-02-16T12:00:00Z"
          }
        ],
        count: 1
      },
      isLoading: false
    } as any)

    vi.mocked(useQuizQuery).mockReturnValue({
      data: null
    } as any)

    vi.mocked(useStartAttemptMutation).mockReturnValue({
      mutateAsync: vi.fn(async () => ({
        id: 123,
        quiz_id: 7,
        started_at: "2026-02-18T10:00:00Z",
        total_possible: 12,
        answers: [],
        questions: [
          {
            id: 1,
            quiz_id: 7,
            question_type: "true_false",
            question_text: "Cells are alive.",
            options: null,
            points: 1,
            order_index: 0,
            tags: null,
            deleted: false,
            client_id: "test",
            version: 1
          }
        ]
      }))
    } as any)

    vi.mocked(useSubmitAttemptMutation).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false
    } as any)

    vi.mocked(useQuizTimer).mockReturnValue(null)
  })

  it("requires pre-quiz confirmation before creating an attempt", async () => {
    const mutateAsync = vi.fn(async () => ({
      id: 123,
      quiz_id: 7,
      started_at: "2026-02-18T10:00:00Z",
      total_possible: 12,
      answers: [],
      questions: []
    }))
    vi.mocked(useStartAttemptMutation).mockReturnValue({ mutateAsync } as any)

    render(
      <TakeQuizTab
        onNavigateToGenerate={() => {}}
        onNavigateToCreate={() => {}}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /Start Quiz/i }))

    expect(screen.getByText("Ready to begin?")).toBeInTheDocument()
    expect(mutateAsync).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole("button", { name: "Begin Quiz" }))

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith(7)
    })
  }, 15000)

  it("renders expanded quiz metadata on list cards", () => {
    render(
      <TakeQuizTab
        onNavigateToGenerate={() => {}}
        onNavigateToCreate={() => {}}
      />
    )

    expect(screen.getByText("Pass: 75%")).toBeInTheDocument()
    expect(screen.getByText("Last score: 80%")).toBeInTheDocument()
    expect(screen.getByText(/Created:/)).toBeInTheDocument()

    const sourceLink = screen.getByRole("link", { name: /Source media #42/i })
    expect(sourceLink).toHaveAttribute("href", "/media?id=42")
  }, 15000)

  it("shows autosave warning when local storage is unavailable", () => {
    vi.mocked(useQuizAutoSave).mockReturnValue({
      storageUnavailable: true,
      restoreSavedAnswers: vi.fn(async () => false),
      clearSavedProgress: vi.fn(async () => {}),
      hasSavedProgress: vi.fn(async () => false),
      getSavedProgress: vi.fn(async () => null),
      forceSave: vi.fn(async () => {})
    } as any)

    render(
      <TakeQuizTab
        onNavigateToGenerate={() => {}}
        onNavigateToCreate={() => {}}
      />
    )

    expect(
      screen.getByText(
        "Auto-save unavailable — your progress won't be preserved if you navigate away."
      )
    ).toBeInTheDocument()
  }, 15000)

  it("does not enter attempt mode when the quiz has zero questions", async () => {
    vi.mocked(useStartAttemptMutation).mockReturnValue({
      mutateAsync: vi.fn(async () => ({
        id: 777,
        quiz_id: 7,
        started_at: "2026-02-18T10:00:00Z",
        total_possible: 0,
        answers: [],
        questions: []
      }))
    } as any)

    render(
      <TakeQuizTab
        onNavigateToGenerate={() => {}}
        onNavigateToCreate={() => {}}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /Start Quiz/i }))
    fireEvent.click(screen.getByRole("button", { name: "Begin Quiz" }))

    await waitFor(() => {
      expect(screen.getByText("Select a quiz to begin")).toBeInTheDocument()
    })
    expect(screen.queryByText("Question navigator")).not.toBeInTheDocument()
  }, 15000)

  it("adds semantic grouping for question radios and labels progress", async () => {
    render(
      <TakeQuizTab
        onNavigateToGenerate={() => {}}
        onNavigateToCreate={() => {}}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /Start Quiz/i }))
    fireEvent.click(screen.getByRole("button", { name: "Begin Quiz" }))

    expect(await screen.findByText("True or false for: Cells are alive.")).toBeInTheDocument()
    const completionProgress = screen.getByRole("progressbar", { name: "Quiz completion progress" })
    expect(completionProgress).toHaveAttribute("aria-valuemin", "0")
    expect(completionProgress).toHaveAttribute("aria-valuemax", "100")
  }, 15000)

  it("announces danger-zone timer updates in assertive live region", async () => {
    vi.mocked(useQuizTimer).mockReturnValue({
      minutes: 0,
      seconds: 58,
      totalSeconds: 58,
      isWarning: false,
      isDanger: true,
      isExpired: false,
      formattedTime: "0:58"
    })

    render(
      <TakeQuizTab
        onNavigateToGenerate={() => {}}
        onNavigateToCreate={() => {}}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /Start Quiz/i }))
    fireEvent.click(screen.getByRole("button", { name: "Begin Quiz" }))

    const liveRegion = await screen.findByText("58 seconds remaining")
    expect(liveRegion).toHaveAttribute("aria-live", "assertive")
  }, 15000)
})
