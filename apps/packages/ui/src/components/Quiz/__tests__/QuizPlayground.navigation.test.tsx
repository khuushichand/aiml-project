import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { QuizPlayground } from "../QuizPlayground"

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

vi.mock("antd", () => ({
  Tabs: ({ items, activeKey, onChange }: any) => {
    const activeItem = Array.isArray(items)
      ? items.find((item: any) => item.key === activeKey)
      : null

    return (
      <div>
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
  TakeQuizTab: ({ startQuizId, highlightQuizId, navigationSource }: any) => (
    <div data-testid="take-intent">
      {JSON.stringify({ startQuizId, highlightQuizId, navigationSource })}
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
  CreateTab: ({ onNavigateToTake }: any) => (
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
  ),
  ManageTab: ({ onStartQuiz }: any) => (
    <button type="button" onClick={() => onStartQuiz(99)}>
      Mock Manage Start
    </button>
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
  it("routes generate navigation payload into Take tab intent", () => {
    render(<QuizPlayground />)

    fireEvent.click(screen.getByRole("button", { name: "Generate" }))
    fireEvent.click(screen.getByRole("button", { name: "Mock Generate Navigate" }))

    expect(screen.getByTestId("active-tab")).toHaveTextContent("take")
    expect(screen.getByTestId("take-intent")).toHaveTextContent(
      JSON.stringify({ startQuizId: null, highlightQuizId: 77, navigationSource: "generate" })
    )
  })

  it("routes results retake payload into Take tab intent", () => {
    render(<QuizPlayground />)

    fireEvent.click(screen.getByRole("button", { name: "Results" }))
    fireEvent.click(screen.getByRole("button", { name: "Mock Results Retake" }))

    expect(screen.getByTestId("active-tab")).toHaveTextContent("take")
    expect(screen.getByTestId("take-intent")).toHaveTextContent(
      JSON.stringify({ startQuizId: 7, highlightQuizId: 7, navigationSource: "results" })
    )
  })
})
