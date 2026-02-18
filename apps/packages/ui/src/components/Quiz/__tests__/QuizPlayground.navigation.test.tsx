import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { QuizPlayground } from "../QuizPlayground"
import { RESULTS_FILTER_PREFS_KEY, TAKE_QUIZ_LIST_PREFS_KEY } from "../stateKeys"
import { useAttemptsQuery, useQuizzesQuery } from "../hooks"

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
      if (typeof defaultValueOrOptions?.defaultValue === "string") {
        return defaultValueOrOptions.defaultValue
      }
      return key
    }
  })
}))

vi.mock("../hooks", () => ({
  useQuizzesQuery: vi.fn(() => ({ data: { items: [], count: 5 }, isLoading: false })),
  useAttemptsQuery: vi.fn(() => ({ data: { items: [], count: 12 }, isLoading: false }))
}))

vi.mock("antd", () => ({
  Button: ({ children, onClick, ...rest }: any) => (
    <button type="button" onClick={onClick} {...rest}>
      {children}
    </button>
  ),
  Tabs: ({ items, activeKey, onChange, destroyInactiveTabPane }: any) => {
    const activeItem = Array.isArray(items)
      ? items.find((item: any) => item.key === activeKey)
      : null

    return (
      <div>
        <div data-testid="destroy-inactive-tab-pane">
          {String(destroyInactiveTabPane)}
        </div>
        <div>
          {Array.isArray(items)
            ? items.map((item: any) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => onChange?.(item.key)}
                >
                  {item.label}
                </button>
              ))
            : null}
        </div>
        <div data-testid="active-tab">{activeKey}</div>
        <div>{activeItem?.children}</div>
      </div>
    )
  }
}))

vi.mock("../tabs", () => ({
  TakeQuizTab: ({ startQuizId, highlightQuizId, navigationSource, externalSearchQuery }: any) => (
    <div data-testid="take-intent">
      {JSON.stringify({ startQuizId, highlightQuizId, navigationSource, externalSearchQuery })}
    </div>
  ),
  GenerateTab: ({ onNavigateToTake }: any) => (
    <button
      type="button"
      onClick={() =>
        onNavigateToTake({
          highlightQuizId: 77,
          sourceTab: "generate"
        })
      }
    >
      Mock Generate Navigate
    </button>
  ),
  CreateTab: ({ onNavigateToTake, onDirtyStateChange }: any) => (
    <div>
      <button
        type="button"
        onClick={() =>
          onNavigateToTake({
            highlightQuizId: 88,
            sourceTab: "create"
          })
        }
      >
        Mock Create Navigate
      </button>
      <button type="button" onClick={() => onDirtyStateChange?.(true)}>
        Mock Mark Create Dirty
      </button>
    </div>
  ),
  ManageTab: ({ onStartQuiz, externalSearchQuery }: any) => (
    <div>
      <button type="button" onClick={() => onStartQuiz(99)}>
        Mock Manage Start
      </button>
      <div data-testid="manage-search-intent">{externalSearchQuery ?? ""}</div>
    </div>
  ),
  ResultsTab: ({ onRetakeQuiz }: any) => (
    <button
      type="button"
      onClick={() =>
        onRetakeQuiz?.({
          startQuizId: 7,
          highlightQuizId: 7,
          sourceTab: "results",
          attemptId: 301
        })
      }
    >
      Mock Results Retake
    </button>
  )
}))

describe("QuizPlayground navigation intents", () => {
  it("prompts before leaving Create tab when unsaved changes are present", () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false)

    render(<QuizPlayground />)
    fireEvent.click(screen.getByRole("button", { name: "Create" }))
    fireEvent.click(screen.getByRole("button", { name: "Mock Mark Create Dirty" }))
    fireEvent.click(screen.getByRole("button", { name: "Take Quiz" }))

    expect(confirmSpy).toHaveBeenCalledWith("You have unsaved quiz changes. Leave Create tab?")
    expect(screen.getByTestId("active-tab")).toHaveTextContent("create")

    confirmSpy.mockRestore()
  })

  it("allows leaving Create tab after confirmation", () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true)

    render(<QuizPlayground />)
    fireEvent.click(screen.getByRole("button", { name: "Create" }))
    fireEvent.click(screen.getByRole("button", { name: "Mock Mark Create Dirty" }))
    fireEvent.click(screen.getByRole("button", { name: "Take Quiz" }))

    expect(screen.getByTestId("active-tab")).toHaveTextContent("take")

    confirmSpy.mockRestore()
  })

  it("applies global search to Take tab by default and navigates there", () => {
    render(<QuizPlayground />)

    fireEvent.change(screen.getByTestId("quiz-global-search-input"), {
      target: { value: "bio" }
    })
    fireEvent.click(screen.getByTestId("quiz-global-search-apply"))

    expect(screen.getByTestId("active-tab")).toHaveTextContent("take")
    expect(screen.getByTestId("take-intent")).toHaveTextContent("\"externalSearchQuery\":\"bio\"")
  })

  it("applies global search to Manage tab when Manage is active", () => {
    render(<QuizPlayground />)

    fireEvent.click(screen.getByRole("button", { name: "Manage" }))
    fireEvent.change(screen.getByTestId("quiz-global-search-input"), {
      target: { value: "chem" }
    })
    fireEvent.click(screen.getByTestId("quiz-global-search-apply"))

    expect(screen.getByTestId("active-tab")).toHaveTextContent("manage")
    expect(screen.getByTestId("manage-search-intent")).toHaveTextContent("chem")
  })

  it("resets take-tab intent and clears take-tab persisted state on explicit reset", () => {
    window.sessionStorage.setItem(TAKE_QUIZ_LIST_PREFS_KEY, JSON.stringify({ page: 2 }))
    render(<QuizPlayground />)

    fireEvent.click(screen.getByRole("button", { name: "Generate" }))
    fireEvent.click(screen.getByRole("button", { name: "Mock Generate Navigate" }))

    expect(screen.getByTestId("take-intent")).toHaveTextContent(
      JSON.stringify({
        startQuizId: null,
        highlightQuizId: 77,
        navigationSource: "generate",
        externalSearchQuery: null
      })
    )

    fireEvent.click(screen.getByTestId("quiz-reset-current-tab"))

    expect(window.sessionStorage.getItem(TAKE_QUIZ_LIST_PREFS_KEY)).toBeNull()
    expect(screen.getByTestId("take-intent")).toHaveTextContent(
      JSON.stringify({
        startQuizId: null,
        highlightQuizId: null,
        navigationSource: null,
        externalSearchQuery: null
      })
    )
  })

  it("clears results-tab persisted state on explicit reset", () => {
    window.sessionStorage.setItem(RESULTS_FILTER_PREFS_KEY, JSON.stringify({ page: 3 }))
    render(<QuizPlayground />)

    fireEvent.click(screen.getByRole("button", { name: "Results" }))
    fireEvent.click(screen.getByTestId("quiz-reset-current-tab"))

    expect(window.sessionStorage.getItem(RESULTS_FILTER_PREFS_KEY)).toBeNull()
  })

  it("keeps inactive tab panes mounted for per-tab state preservation", () => {
    render(<QuizPlayground />)
    expect(screen.getByTestId("destroy-inactive-tab-pane")).toHaveTextContent("false")
  })

  it("routes generate navigation payload into Take tab intent", () => {
    render(<QuizPlayground />)

    fireEvent.click(screen.getByRole("button", { name: "Generate" }))
    fireEvent.click(screen.getByRole("button", { name: "Mock Generate Navigate" }))

    expect(screen.getByTestId("active-tab")).toHaveTextContent("take")
    expect(screen.getByTestId("take-intent")).toHaveTextContent(
      JSON.stringify({
        startQuizId: null,
        highlightQuizId: 77,
        navigationSource: "generate",
        externalSearchQuery: null
      })
    )
  })

  it("routes results retake payload into Take tab intent", () => {
    render(<QuizPlayground />)

    fireEvent.click(screen.getByRole("button", { name: "Results" }))
    fireEvent.click(screen.getByRole("button", { name: "Mock Results Retake" }))

    expect(screen.getByTestId("active-tab")).toHaveTextContent("take")
    expect(screen.getByTestId("take-intent")).toHaveTextContent(
      JSON.stringify({
        startQuizId: 7,
        highlightQuizId: 7,
        navigationSource: "results",
        externalSearchQuery: null
      })
    )
  })

  it("renders count badges on take, manage, and results tab labels", () => {
    vi.mocked(useQuizzesQuery).mockReturnValue({
      data: { items: [], count: 9 },
      isLoading: false
    } as any)
    vi.mocked(useAttemptsQuery).mockReturnValue({
      data: { items: [], count: 4 },
      isLoading: false
    } as any)

    render(<QuizPlayground />)

    expect(screen.getByRole("button", { name: "Take Quiz" })).toHaveTextContent("9")
    expect(screen.getByRole("button", { name: "Manage" })).toHaveTextContent("9")
    expect(screen.getByRole("button", { name: "Results" })).toHaveTextContent("4")
  })
})
