import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { QuizWorkspace } from "../QuizWorkspace"

const mocks = vi.hoisted(() => ({
  isOnline: true,
  demoEnabled: false,
  capabilities: {
    hasQuizzes: true,
    specVersion: "test-spec"
  } as {
    hasQuizzes: boolean
    specVersion: string | null
  },
  capsLoading: false,
  navigate: vi.fn(),
  scrollToServerCard: vi.fn(),
  checkOnce: vi.fn()
}))

const interpolate = (template: string, values?: Record<string, unknown>) =>
  template.replace(/\{\{(\w+)\}\}/g, (_, key) => String(values?.[key] ?? ""))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?:
        | string
        | {
            defaultValue?: string
            [k: string]: unknown
          }
    ) => {
      if (typeof fallbackOrOptions === "string") return fallbackOrOptions
      const template = fallbackOrOptions?.defaultValue || key
      return interpolate(template, fallbackOrOptions as Record<string, unknown> | undefined)
    }
  })
}))

vi.mock("react-router-dom", () => ({
  useNavigate: () => mocks.navigate
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => mocks.isOnline
}))

vi.mock("@/context/demo-mode", () => ({
  useDemoMode: () => ({ demoEnabled: mocks.demoEnabled })
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    capabilities: mocks.capabilities,
    loading: mocks.capsLoading
  })
}))

vi.mock("@/hooks/useScrollToServerCard", () => ({
  useScrollToServerCard: () => mocks.scrollToServerCard
}))

vi.mock("@/hooks/useConnectionState", () => ({
  useConnectionActions: () => ({
    checkOnce: mocks.checkOnce
  })
}))

vi.mock("../QuizPlayground", () => ({
  QuizPlayground: () => <div data-testid="quiz-playground" />
}))

describe("QuizWorkspace connection and availability states", () => {
  beforeEach(() => {
    mocks.isOnline = true
    mocks.demoEnabled = false
    mocks.capabilities = { hasQuizzes: true, specVersion: "test-spec" }
    mocks.capsLoading = false
    mocks.navigate.mockReset()
    mocks.scrollToServerCard.mockReset()
    mocks.checkOnce.mockReset()
  })

  it("renders an interactive local demo quiz flow when offline demo mode is enabled", async () => {
    mocks.isOnline = false
    mocks.demoEnabled = true

    render(<QuizWorkspace />)

    expect(screen.getByText("Explore Quiz Playground in demo mode")).toBeInTheDocument()
    expect(screen.getByTestId("quiz-demo-preview")).toBeInTheDocument()
    expect(
      screen.getAllByText("Demo quiz: Research workflow fundamentals").length
    ).toBeGreaterThan(0)

    fireEvent.click(screen.getByTestId("quiz-demo-start"))
    expect(screen.getByTestId("quiz-demo-taking")).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText("Generate"))
    fireEvent.click(screen.getByRole("button", { name: "Next" }))

    fireEvent.click(screen.getByLabelText("True"))
    fireEvent.click(screen.getByRole("button", { name: "Next" }))

    fireEvent.change(screen.getByPlaceholderText("Enter one word"), {
      target: { value: "trends" }
    })
    fireEvent.click(screen.getByTestId("quiz-demo-submit"))

    await waitFor(() => {
      expect(screen.getByTestId("quiz-demo-results")).toBeInTheDocument()
      expect(screen.getByTestId("quiz-demo-score")).toHaveTextContent("100%")
    })
  })

  it("shows actionable capability guidance with diagnostics and setup actions", () => {
    mocks.capabilities = { hasQuizzes: false, specVersion: "2026.02" }

    render(<QuizWorkspace />)

    expect(screen.getByText("Quiz API not available on this server")).toBeInTheDocument()
    expect(screen.getByText(/reported: 2026.02/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Health & diagnostics" }))
    fireEvent.click(screen.getByRole("button", { name: "Open setup guide" }))

    expect(mocks.navigate).toHaveBeenCalledWith("/settings/health")
    expect(mocks.navigate).toHaveBeenCalledWith("/documentation")
  })

  it("exposes beta semantics via an accessible tooltip badge without blocking main content", async () => {
    render(<QuizWorkspace />)

    expect(screen.getByTestId("quiz-playground")).toBeInTheDocument()

    fireEvent.click(screen.getByTestId("quiz-beta-badge"))

    expect(screen.getByTestId("quiz-beta-tooltip")).toHaveTextContent(
      "Quiz Playground is in beta."
    )

    fireEvent.keyDown(window, { key: "Escape" })

    await waitFor(() => {
      expect(screen.queryByTestId("quiz-beta-tooltip")).not.toBeInTheDocument()
    })
  })
})
