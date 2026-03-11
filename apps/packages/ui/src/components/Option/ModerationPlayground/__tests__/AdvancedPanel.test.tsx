// @vitest-environment jsdom
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("antd", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>
}))

vi.mock("@/services/moderation", () => ({
  setUserOverride: vi.fn().mockResolvedValue({})
}))

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeSettings(policyData: Record<string, any> | null = null) {
  return {
    draft: { piiEnabled: false, categoriesEnabled: [], persist: false },
    setDraft: vi.fn(),
    baseline: null,
    isDirty: false,
    save: vi.fn().mockResolvedValue(undefined),
    reset: vi.fn(),
    reload: vi.fn().mockResolvedValue(undefined),
    settingsQuery: { data: undefined, isLoading: false, refetch: vi.fn() },
    policyQuery: { data: policyData, isLoading: false, refetch: vi.fn() }
  }
}

function makeBlocklist() {
  return {
    rawText: "",
    setRawText: vi.fn(),
    rawLint: null,
    managedItems: [],
    managedVersion: "",
    managedLine: "",
    setManagedLine: vi.fn(),
    managedLint: null,
    loading: false,
    loadRaw: vi.fn().mockResolvedValue(undefined),
    saveRaw: vi.fn().mockResolvedValue(undefined),
    lintRaw: vi.fn().mockResolvedValue(undefined),
    loadManaged: vi.fn().mockResolvedValue(undefined),
    appendManaged: vi.fn().mockResolvedValue(undefined),
    deleteManaged: vi.fn().mockResolvedValue(undefined),
    lintManagedLine: vi.fn().mockResolvedValue(undefined)
  }
}

function makeOverrides() {
  return {
    draft: {},
    setDraft: vi.fn(),
    baseline: null,
    loaded: false,
    loading: false,
    userIdError: null,
    isDirty: false,
    rules: [],
    bannedRules: [],
    notifyRules: [],
    overridesQuery: { data: { overrides: [] }, isLoading: false, refetch: vi.fn() },
    updateDraft: vi.fn(),
    reset: vi.fn(),
    save: vi.fn().mockResolvedValue(undefined),
    remove: vi.fn().mockResolvedValue(undefined),
    bulkDelete: vi.fn().mockResolvedValue([]),
    addRule: vi.fn().mockReturnValue(true),
    removeRule: vi.fn(),
    applyPreset: vi.fn().mockResolvedValue(undefined)
  }
}

function makeMessageApi() {
  return { success: vi.fn(), error: vi.fn(), warning: vi.fn() }
}

// ---------------------------------------------------------------------------
// Import component under test (after mocks)
// ---------------------------------------------------------------------------

import AdvancedPanel from "../AdvancedPanel"

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AdvancedPanel", () => {
  let messageApi: ReturnType<typeof makeMessageApi>

  beforeEach(() => {
    vi.clearAllMocks()
    messageApi = makeMessageApi()
  })

  it("renders performance tuning section with field labels", () => {
    const settings = makeSettings({ max_scan_chars: 150000, max_replacements_per_pattern: 500 })
    render(
      <AdvancedPanel
        settings={settings as any}
        blocklist={makeBlocklist() as any}
        overrides={makeOverrides() as any}
        messageApi={messageApi}
      />
    )
    expect(screen.getByText("Performance Tuning")).toBeInTheDocument()
    expect(screen.getByLabelText("max_scan_chars")).toHaveValue("150000")
    expect(screen.getByLabelText("max_replacements_per_pattern")).toHaveValue("500")
    expect(screen.getByLabelText("match_window_chars")).toBeInTheDocument()
    expect(screen.getByLabelText("blocklist_write_debounce_ms")).toBeInTheDocument()
  })

  it("renders export buttons for blocklist and overrides", () => {
    render(
      <AdvancedPanel
        settings={makeSettings() as any}
        blocklist={makeBlocklist() as any}
        overrides={makeOverrides() as any}
        messageApi={messageApi}
      />
    )
    expect(screen.getByRole("button", { name: /download blocklist/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /download overrides/i })).toBeInTheDocument()
  })

  it("renders reload button", () => {
    render(
      <AdvancedPanel
        settings={makeSettings() as any}
        blocklist={makeBlocklist() as any}
        overrides={makeOverrides() as any}
        messageApi={messageApi}
      />
    )
    expect(screen.getByRole("button", { name: /reload from disk/i })).toBeInTheDocument()
  })

  it("renders config viewer collapsible", () => {
    render(
      <AdvancedPanel
        settings={makeSettings({ enabled: true }) as any}
        blocklist={makeBlocklist() as any}
        overrides={makeOverrides() as any}
        messageApi={messageApi}
      />
    )
    expect(screen.getByText("View current configuration")).toBeInTheDocument()
  })

  it("shows default values when policy data is null", () => {
    render(
      <AdvancedPanel
        settings={makeSettings(null) as any}
        blocklist={makeBlocklist() as any}
        overrides={makeOverrides() as any}
        messageApi={messageApi}
      />
    )
    expect(screen.getByLabelText("max_scan_chars")).toHaveValue("200000")
    expect(screen.getByLabelText("max_replacements_per_pattern")).toHaveValue("1000")
    expect(screen.getByLabelText("match_window_chars")).toHaveValue("4096")
    expect(screen.getByLabelText("blocklist_write_debounce_ms")).toHaveValue("0")
  })
})
