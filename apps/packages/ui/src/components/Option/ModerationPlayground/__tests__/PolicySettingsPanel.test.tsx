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
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>
}))

// ---------------------------------------------------------------------------
// Helper — mock settings object
// ---------------------------------------------------------------------------

interface MakeSettingsOpts {
  piiEnabled?: boolean
  categoriesEnabled?: string[]
  persist?: boolean
  isDirty?: boolean
  policyData?: Record<string, any>
}

function makeSettings(opts: MakeSettingsOpts = {}) {
  const {
    piiEnabled = false,
    categoriesEnabled = ["violence", "gambling"],
    persist = false,
    isDirty = false,
    policyData = {
      enabled: true,
      input_action: "block",
      output_action: "redact",
      blocklist_count: 5,
      redact_replacement: "[REMOVED]"
    }
  } = opts

  return {
    draft: { piiEnabled, categoriesEnabled, persist },
    setDraft: vi.fn(),
    baseline: { piiEnabled, categoriesEnabled, persist },
    isDirty,
    save: vi.fn().mockResolvedValue(undefined),
    reset: vi.fn(),
    reload: vi.fn().mockResolvedValue(undefined),
    settingsQuery: {
      data: undefined,
      isLoading: false,
      refetch: vi.fn()
    },
    policyQuery: {
      data: policyData,
      isLoading: false,
      refetch: vi.fn()
    }
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

import PolicySettingsPanel from "../PolicySettingsPanel"

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("PolicySettingsPanel", () => {
  let messageApi: ReturnType<typeof makeMessageApi>

  beforeEach(() => {
    vi.clearAllMocks()
    messageApi = makeMessageApi()
  })

  it("renders PII toggle with 'Personal Data Protection' text", () => {
    const settings = makeSettings()
    render(<PolicySettingsPanel settings={settings as any} messageApi={messageApi} />)
    expect(screen.getByText("Personal Data Protection")).toBeInTheDocument()
  })

  it("renders category picker showing category names", () => {
    const settings = makeSettings({ categoriesEnabled: ["violence", "gambling"] })
    render(<PolicySettingsPanel settings={settings as any} messageApi={messageApi} />)
    // CategoryPicker renders CATEGORY_SUGGESTIONS labels
    expect(screen.getByText("Violence")).toBeInTheDocument()
    expect(screen.getByText("Gambling")).toBeInTheDocument()
  })

  it("renders Save button", () => {
    const settings = makeSettings()
    render(<PolicySettingsPanel settings={settings as any} messageApi={messageApi} />)
    expect(screen.getByRole("button", { name: /save runtime settings/i })).toBeInTheDocument()
  })

  it("renders Reset button as disabled when not dirty", () => {
    const settings = makeSettings({ isDirty: false })
    render(<PolicySettingsPanel settings={settings as any} messageApi={messageApi} />)
    const resetBtn = screen.getByRole("button", { name: /reset changes/i })
    expect(resetBtn).toBeDisabled()
  })

  it("renders Reset button as enabled when isDirty=true", () => {
    const settings = makeSettings({ isDirty: true })
    render(<PolicySettingsPanel settings={settings as any} messageApi={messageApi} />)
    const resetBtn = screen.getByRole("button", { name: /reset changes/i })
    expect(resetBtn).toBeEnabled()
  })

  it("displays master toggle as read-only from policy", () => {
    const settings = makeSettings({ policyData: { enabled: true, input_action: "block", output_action: "warn" } })
    render(<PolicySettingsPanel settings={settings as any} messageApi={messageApi} />)
    expect(screen.getByText("Moderation Enabled")).toBeInTheDocument()
    // The toggle should reflect the policy's enabled state
    const toggle = screen.getByRole("switch", { name: /moderation enabled/i })
    expect(toggle).toHaveAttribute("aria-checked", "true")
    // Read-only toggle is disabled
    expect(toggle).toBeDisabled()
  })

  it("shows input and output action labels from policy", () => {
    const settings = makeSettings({
      policyData: { enabled: true, input_action: "block", output_action: "redact" }
    })
    render(<PolicySettingsPanel settings={settings as any} messageApi={messageApi} />)
    expect(screen.getByText("Block")).toBeInTheDocument()
    expect(screen.getByText("Redact")).toBeInTheDocument()
  })

  it("shows active policy summary section", () => {
    const settings = makeSettings()
    render(<PolicySettingsPanel settings={settings as any} messageApi={messageApi} />)
    expect(screen.getByText("Active Policy Summary")).toBeInTheDocument()
  })
})
