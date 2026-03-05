import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"
import { ModerationPlayground } from "../index"

const useQueryMock = vi.fn()

vi.mock("@tanstack/react-query", () => ({
  useQuery: (options: unknown) => useQueryMock(options)
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback || _key
  })
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("ModerationPlayground disclosure UX", () => {
  const originalMatchMedia = window.matchMedia

  const settingsQueryResult = {
    data: {
      pii_enabled: false,
      categories_enabled: [] as string[],
      effective: { categories_enabled: [] as string[] }
    },
    isFetching: false
  }

  const policyQueryResult = {
    data: {
      enabled: true,
      input_enabled: true,
      output_enabled: true,
      input_action: "warn",
      output_action: "warn",
      categories_enabled: [] as string[],
      blocklist_count: 0
    },
    isFetching: false
  }

  const overridesQueryResult = {
    data: { overrides: {} as Record<string, unknown> },
    isFetching: false,
    error: null
  }

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
    localStorage.removeItem("moderation-playground-onboarded")

    useQueryMock.mockImplementation((options: { queryKey?: unknown[] } | undefined) => {
      const firstKey = options?.queryKey?.[0]
      const queryKey = typeof firstKey === "string" ? firstKey : ""
      if (queryKey === "moderation-settings") {
        return { ...settingsQueryResult, error: null }
      }
      if (queryKey === "moderation-policy") {
        return { ...policyQueryResult, error: null }
      }
      if (queryKey === "moderation-overrides") {
        return overridesQueryResult
      }
      return { data: null, isFetching: false, error: null }
    })
  })

  it("allows dismissing onboarding and persists dismissal", async () => {
    render(<ModerationPlayground />)

    expect(
      screen.getByText("Welcome to Moderation Playground")
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Got it, let's start" }))

    await waitFor(() => {
      expect(
        screen.queryByText("Welcome to Moderation Playground")
      ).not.toBeInTheDocument()
    })

    expect(localStorage.getItem("moderation-playground-onboarded")).toBe("true")
  })

  it("starts with advanced content hidden and reveals it on demand", async () => {
    render(<ModerationPlayground />)

    expect(
      screen.getByText("Looking for blocklist rules or user overrides?")
    ).toBeInTheDocument()
    expect(screen.queryByText("Blocklist Studio")).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Enable Advanced mode" }))

    await waitFor(() => {
      expect(screen.getByText("Blocklist Studio")).toBeInTheDocument()
    })
  })

  it("prioritizes server setup by hiding per-user configuration in server scope", () => {
    render(<ModerationPlayground />)

    expect(screen.getByText("Global Server Rules")).toBeInTheDocument()
    expect(screen.queryByText("Per-User Safety Rules")).not.toBeInTheDocument()
  })

  it("shows explicit admin-permission error state instead of fallback policy defaults", () => {
    useQueryMock.mockImplementation((options: { queryKey?: unknown[] } | undefined) => {
      const firstKey = options?.queryKey?.[0]
      const queryKey = typeof firstKey === "string" ? firstKey : ""
      if (queryKey === "moderation-settings") {
        return {
          data: null,
          isFetching: false,
          error: { status: 403, message: "Forbidden" }
        }
      }
      if (queryKey === "moderation-policy") {
        return { ...policyQueryResult, error: null }
      }
      if (queryKey === "moderation-overrides") {
        return overridesQueryResult
      }
      return { data: null, isFetching: false, error: null }
    })

    render(<ModerationPlayground />)

    expect(screen.getByText("Admin moderation access required")).toBeInTheDocument()
    expect(screen.queryByText("Current Policy Status")).not.toBeInTheDocument()
  })
})
