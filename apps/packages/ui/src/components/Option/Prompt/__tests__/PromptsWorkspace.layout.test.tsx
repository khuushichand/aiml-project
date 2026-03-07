import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { PromptsWorkspace } from "../PromptsWorkspace"

const { useLayoutUiStoreMock } = vi.hoisted(() => ({
  useLayoutUiStoreMock: vi.fn()
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string }
    ) => {
      if (typeof fallbackOrOptions === "string") return fallbackOrOptions
      if (fallbackOrOptions && typeof fallbackOrOptions === "object") {
        return fallbackOrOptions.defaultValue || key
      }
      return key
    }
  })
}))

vi.mock("@/store/layout-ui", () => ({
  useLayoutUiStore: useLayoutUiStoreMock
}))

vi.mock("..", () => ({
  PromptBody: () => <div data-testid="prompts-body">Prompt Body</div>
}))

vi.mock("../PromptPageErrorBoundary", () => ({
  PromptPageErrorBoundary: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="prompts-error-boundary">{children}</div>
  )
}))

vi.mock("@/components/Common/PageShell", () => ({
  PageShell: ({
    children,
    maxWidthClassName,
    className
  }: {
    children: React.ReactNode
    maxWidthClassName?: string
    className?: string
  }) => (
    <div
      data-testid="prompts-page-shell"
      className={[maxWidthClassName, className].filter(Boolean).join(" ")}
    >
      {children}
    </div>
  )
}))

describe("PromptsWorkspace layout", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("uses full-width shell when the sidebar is collapsed", () => {
    useLayoutUiStoreMock.mockImplementation(
      (selector: (state: { chatSidebarCollapsed: boolean }) => boolean) =>
        selector({ chatSidebarCollapsed: true })
    )

    render(<PromptsWorkspace />)

    expect(screen.getByTestId("prompts-page-shell").className).toContain(
      "max-w-none"
    )
  })

  it("uses bounded shell when the sidebar is expanded", () => {
    useLayoutUiStoreMock.mockImplementation(
      (selector: (state: { chatSidebarCollapsed: boolean }) => boolean) =>
        selector({ chatSidebarCollapsed: false })
    )

    render(<PromptsWorkspace />)

    const shell = screen.getByTestId("prompts-page-shell")
    expect(shell.className).toContain("max-w-7xl")
    expect(shell.className).not.toContain("max-w-none")
  })
})

