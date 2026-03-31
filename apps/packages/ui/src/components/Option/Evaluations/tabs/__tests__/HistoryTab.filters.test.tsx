// @vitest-environment jsdom

import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { HistoryTab } from "../HistoryTab"

const fetchSpy = vi.fn()

const storeState = {
  historyResults: [
    {
      id: "eval-123",
      eval_type: "rag",
      created_at: "2026-03-29T12:00:00Z",
      user_id: "user_123"
    }
  ]
}

vi.mock("antd", async () => {
  const actual = await vi.importActual<any>("antd")

  return {
    ...actual,
    Select: ({ options = [], value, onChange, placeholder }: any) => (
      <select
        aria-label={placeholder || "select"}
        value={value ?? ""}
        onChange={(event) => onChange?.(event.target.value || undefined)}
      >
        <option value="">{placeholder || "Select"}</option>
        {options.map((option: any) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    )
  }
})

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
            count?: number
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) {
        return defaultValueOrOptions.defaultValue.replace(
          "{{count}}",
          String(defaultValueOrOptions.count ?? "")
        )
      }
      return key
    }
  })
}))

vi.mock("@/store/evaluations", () => ({
  useEvaluationsStore: (selector: (state: typeof storeState) => unknown) =>
    selector(storeState)
}))

vi.mock("../../components", () => ({
  CopyButton: () => null
}))

vi.mock("../../hooks/useHistory", async () => {
  const actual = await vi.importActual<any>("../../hooks/useHistory")
  return {
    ...actual,
    useFetchHistory: () => ({
      mutate: fetchSpy,
      isPending: false
    })
  }
})

if (!(globalThis as any).ResizeObserver) {
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

describe("HistoryTab filters and rendering", () => {
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
  })

  it("uses evaluation_type filters and renders backend evaluation rows", async () => {
    render(<HistoryTab />)

    expect(screen.getByRole("option", { name: "rag" })).toBeInTheDocument()
    expect(
      screen.queryByRole("option", { name: "evaluation.completed" })
    ).not.toBeInTheDocument()
    expect(screen.getByText("eval-123")).toBeInTheDocument()
    expect(screen.getByText("user_123")).toBeInTheDocument()

    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "rag" }
    })
    fireEvent.change(screen.getByPlaceholderText("user_123"), {
      target: { value: "user_123" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Fetch history" }))

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          evaluation_type: "rag",
          user_id: "user_123"
        })
      )
    })
  })
})
