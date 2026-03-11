import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (_k: string, fb?: string) => fb || _k })
}))

vi.mock("antd", () => ({
  Modal: { confirm: vi.fn() },
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  Select: () => null
}))

vi.mock("lucide-react", () => ({
  Trash2: ({ size }: { size?: number }) => <span data-testid="trash-icon" />,
  Search: ({ size }: { size?: number }) => <span data-testid="search-icon" />
}))

// ---------------------------------------------------------------------------
// Helpers — mock ctx and overrides
// ---------------------------------------------------------------------------

function makeCtx(overrideProps: Partial<ReturnType<typeof makeCtx>> = {}) {
  return {
    scope: "user" as const,
    setScope: vi.fn(),
    userIdDraft: "",
    setUserIdDraft: vi.fn(),
    activeUserId: null as string | null,
    setActiveUserId: vi.fn(),
    loadUser: vi.fn(),
    clearUser: vi.fn(),
    ...overrideProps
  }
}

function makeOverrides(overrideProps: Partial<ReturnType<typeof makeOverrides>> = {}) {
  return {
    draft: {
      enabled: true,
      input_enabled: true,
      output_enabled: true,
      input_action: "block" as const,
      output_action: "redact" as const,
      redact_replacement: "[REMOVED]",
      categories_enabled: [] as string[],
      rules: []
    },
    updateDraft: vi.fn(),
    isDirty: false,
    loaded: true,
    loading: false,
    userIdError: null as string | null,
    rules: [] as any[],
    bannedRules: [] as any[],
    notifyRules: [] as any[],
    reset: vi.fn(),
    save: vi.fn().mockResolvedValue(undefined),
    remove: vi.fn().mockResolvedValue(undefined),
    bulkDelete: vi.fn().mockResolvedValue([]),
    addRule: vi.fn().mockReturnValue(true),
    removeRule: vi.fn(),
    applyPreset: vi.fn().mockResolvedValue(undefined),
    setDraft: vi.fn(),
    baseline: null,
    overridesQuery: {
      data: {
        overrides: {
          alice: { enabled: true, input_action: "block" },
          bob: { enabled: false, output_action: "warn", rules: [{ id: "r1" }] }
        }
      },
      isLoading: false,
      refetch: vi.fn()
    },
    ...overrideProps
  }
}

function makeMessageApi() {
  return {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn()
  }
}

// ---------------------------------------------------------------------------
// Import component under test (after mocks)
// ---------------------------------------------------------------------------

import UserOverridesPanel from "../UserOverridesPanel"

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("UserOverridesPanel", () => {
  let messageApi: ReturnType<typeof makeMessageApi>

  beforeEach(() => {
    vi.clearAllMocks()
    messageApi = makeMessageApi()
  })

  it("renders user picker input when no active user", () => {
    const ctx = makeCtx({ activeUserId: null })
    const overrides = makeOverrides()
    render(<UserOverridesPanel ctx={ctx as any} overrides={overrides as any} messageApi={messageApi} />)
    expect(screen.getByPlaceholderText("Search or enter user ID")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /load \/ create/i })).toBeInTheDocument()
  })

  it("renders preset buttons when user is active", () => {
    const ctx = makeCtx({ activeUserId: "alice" })
    const overrides = makeOverrides()
    render(<UserOverridesPanel ctx={ctx as any} overrides={overrides as any} messageApi={messageApi} />)
    expect(screen.getByRole("button", { name: /strict/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /balanced/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /monitor/i })).toBeInTheDocument()
  })

  it("shows configuring badge when user is active", () => {
    const ctx = makeCtx({ activeUserId: "alice" })
    const overrides = makeOverrides()
    render(<UserOverridesPanel ctx={ctx as any} overrides={overrides as any} messageApi={messageApi} />)
    expect(screen.getByText(/configuring: alice/i)).toBeInTheDocument()
  })

  it("renders phrase add form with pattern input", () => {
    const ctx = makeCtx({ activeUserId: "alice" })
    const overrides = makeOverrides()
    render(<UserOverridesPanel ctx={ctx as any} overrides={overrides as any} messageApi={messageApi} />)
    expect(screen.getByPlaceholderText(/pattern/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /^add rule$/i })).toBeInTheDocument()
  })

  it("renders banned and notify phrase list sections", () => {
    const ctx = makeCtx({ activeUserId: "alice" })
    const overrides = makeOverrides({
      bannedRules: [
        { id: "r1", pattern: "badword", is_regex: false, action: "block", phase: "both" }
      ],
      notifyRules: [
        { id: "r2", pattern: "watchword", is_regex: false, action: "warn", phase: "input" }
      ]
    })
    render(<UserOverridesPanel ctx={ctx as any} overrides={overrides as any} messageApi={messageApi} />)
    expect(screen.getByText("Banned Phrases")).toBeInTheDocument()
    expect(screen.getByText("Notify Phrases")).toBeInTheDocument()
    expect(screen.getByText("badword")).toBeInTheDocument()
    expect(screen.getByText("watchword")).toBeInTheDocument()
  })

  it("renders save, reset, and delete buttons when user is active", () => {
    const ctx = makeCtx({ activeUserId: "alice" })
    const overrides = makeOverrides()
    render(<UserOverridesPanel ctx={ctx as any} overrides={overrides as any} messageApi={messageApi} />)
    expect(screen.getByRole("button", { name: /save override/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /reset changes/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /delete override/i })).toBeInTheDocument()
  })

  it("disables reset button when not dirty", () => {
    const ctx = makeCtx({ activeUserId: "alice" })
    const overrides = makeOverrides({ isDirty: false })
    render(<UserOverridesPanel ctx={ctx as any} overrides={overrides as any} messageApi={messageApi} />)
    expect(screen.getByRole("button", { name: /reset changes/i })).toBeDisabled()
  })

  it("enables reset button when dirty", () => {
    const ctx = makeCtx({ activeUserId: "alice" })
    const overrides = makeOverrides({ isDirty: true })
    render(<UserOverridesPanel ctx={ctx as any} overrides={overrides as any} messageApi={messageApi} />)
    expect(screen.getByRole("button", { name: /reset changes/i })).toBeEnabled()
  })

  it("renders the overrides table", () => {
    const ctx = makeCtx({ activeUserId: null })
    const overrides = makeOverrides()
    render(<UserOverridesPanel ctx={ctx as any} overrides={overrides as any} messageApi={messageApi} />)
    expect(screen.getByText("All User Overrides")).toBeInTheDocument()
    expect(screen.getByTestId("overrides-table")).toBeInTheDocument()
    // Shows both alice and bob from mock data
    expect(screen.getByText("alice")).toBeInTheDocument()
    expect(screen.getByText("bob")).toBeInTheDocument()
  })

  it("shows user ID error when present", () => {
    const ctx = makeCtx({ activeUserId: "missing-user" })
    const overrides = makeOverrides({ userIdError: "No override found for \"missing-user\". You can create a new one." })
    render(<UserOverridesPanel ctx={ctx as any} overrides={overrides as any} messageApi={messageApi} />)
    expect(screen.getByText(/no override found/i)).toBeInTheDocument()
  })
})
