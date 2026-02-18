import React from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { usePromptStudioStore } from "../../../../store/prompt-studio"
import {
  StudioTabContainer,
  getStudioStatusRefetchInterval
} from "../Studio/StudioTabContainer"

const state = vi.hoisted(() => ({
  isOnline: true,
  isMobile: false,
  processing: 0
}))

const useQueryMock = vi.hoisted(() => vi.fn())

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string; [k: string]: unknown }
    ) => {
      if (typeof fallbackOrOptions === "string") return fallbackOrOptions
      if (fallbackOrOptions && typeof fallbackOrOptions === "object") {
        return fallbackOrOptions.defaultValue || key
      }
      return key
    }
  })
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => state.isOnline
}))

vi.mock("@/hooks/useMediaQuery", () => ({
  useMobile: () => state.isMobile
}))

vi.mock("@tanstack/react-query", () => ({
  useQuery: (...args: unknown[]) =>
    (useQueryMock as (...args: unknown[]) => unknown)(...args)
}))

vi.mock("antd", () => ({
  Segmented: ({ value, options, onChange, ...rest }: any) => (
    <div data-testid={rest["data-testid"] || "mock-segmented"}>
      <div data-testid="seg-value">{String(value)}</div>
      {options.map((option: any) => (
        <button
          key={String(option.value)}
          type="button"
          data-testid={`seg-option-${option.value}`}
          disabled={Boolean(option.disabled)}
          onClick={() => onChange?.(option.value)}
        >
          {String(option.value)}
        </button>
      ))}
    </div>
  ),
  Select: ({ value, options, ...rest }: any) => (
    <div data-testid={rest["data-testid"] || "mock-select"}>
      <div data-testid="select-value">{String(value)}</div>
      {options?.map((option: any) => (
        <div key={String(option.value)} data-testid={`select-option-${option.value}`}>
          {String(option.label)}
        </div>
      ))}
    </div>
  ),
  Badge: ({ count }: any) => <span data-testid="mock-badge">{count}</span>,
  Tooltip: ({ children }: any) => <>{children}</>
}))

vi.mock("../Studio/QueueHealthWidget", () => ({
  QueueHealthWidget: () => <div data-testid="mock-queue-health-widget" />
}))

vi.mock("../Studio/Projects/ProjectsTab", () => ({
  ProjectsTab: () => <div data-testid="projects-tab-content" />
}))

vi.mock("../Studio/Prompts/StudioPromptsTab", () => ({
  StudioPromptsTab: () => <div data-testid="prompts-tab-content" />
}))

vi.mock("../Studio/TestCases/TestCasesTab", () => ({
  TestCasesTab: () => <div data-testid="test-cases-tab-content" />
}))

vi.mock("../Studio/Evaluations/EvaluationsTab", () => ({
  EvaluationsTab: () => <div data-testid="evaluations-tab-content" />
}))

vi.mock("../Studio/Optimizations/OptimizationsTab", () => ({
  OptimizationsTab: () => <div data-testid="optimizations-tab-content" />
}))

describe("StudioTabContainer stage 6 navigation and polling", () => {
  let statusQueryOptions: any

  beforeEach(() => {
    statusQueryOptions = null
    state.isOnline = true
    state.isMobile = false
    state.processing = 0
    usePromptStudioStore.setState({
      activeSubTab: "projects",
      selectedProjectId: null
    })
    useQueryMock.mockReset()
    useQueryMock.mockImplementation((options: any) => {
      const key = String(options?.queryKey?.[1] || "")
      if (key === "capability") {
        return { data: true, isLoading: false }
      }
      if (key === "status") {
        statusQueryOptions = options
        return {
          data: {
            data: {
              data: {
                queue_depth: 0,
                processing: state.processing,
                leases: {},
                success_rate: 1
              }
            }
          }
        }
      }
      return { data: undefined, isLoading: false }
    })
  })

  it("shows project-first guidance and keeps project-required tabs disabled", () => {
    render(
      <MemoryRouter>
        <StudioTabContainer />
      </MemoryRouter>
    )

    expect(
      screen.getByText(
        "Select a project in the Projects tab to unlock Prompts, Test Cases, Evaluations, and Optimizations."
      )
    ).toBeInTheDocument()
    expect(screen.getByTestId("seg-option-prompts")).toBeDisabled()
    expect(screen.getByTestId("seg-option-testCases")).toBeDisabled()
    expect(screen.getByTestId("seg-option-evaluations")).toBeDisabled()
    expect(screen.getByTestId("seg-option-optimizations")).toBeDisabled()
  })

  it("renders full-text mobile selector labels with project prerequisite hint", () => {
    state.isMobile = true

    render(
      <MemoryRouter>
        <StudioTabContainer />
      </MemoryRouter>
    )

    expect(screen.getByTestId("studio-subtab-select-mobile")).toBeInTheDocument()
    expect(screen.getByTestId("select-option-projects")).toHaveTextContent("Projects")
    expect(screen.getByTestId("select-option-prompts")).toHaveTextContent(
      "Prompts (Select a project first)"
    )
  })

  it("uses adaptive refetch intervals for idle and active job states", () => {
    render(
      <MemoryRouter>
        <StudioTabContainer />
      </MemoryRouter>
    )

    const getInterval = statusQueryOptions?.refetchInterval
    expect(typeof getInterval).toBe("function")
    expect(
      getInterval({
        state: { data: { data: { data: { processing: 0 } } } }
      })
    ).toBe(30000)
    expect(
      getInterval({
        state: { data: { data: { data: { processing: 2 } } } }
      })
    ).toBe(5000)

    expect(getStudioStatusRefetchInterval({ processing: 0 })).toBe(30000)
    expect(getStudioStatusRefetchInterval({ processing: 1 })).toBe(5000)
  })
})
