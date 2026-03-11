// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: null, isFetching: false, error: null, refetch: vi.fn() })
}))
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (_k: string, fb?: string) => fb || _k })
}))
vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => true
}))
vi.mock("@/services/moderation", () => ({
  getModerationSettings: vi.fn(),
  getEffectivePolicy: vi.fn(),
  reloadModeration: vi.fn(),
  listUserOverrides: vi.fn(),
  testModeration: vi.fn(),
  getUserOverride: vi.fn()
}))

import { ModerationPlaygroundShell } from "../ModerationPlaygroundShell"

describe("ModerationPlaygroundShell", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.setItem("moderation-playground-onboarded", "true")
  })

  it("renders 5 tab buttons", () => {
    render(<ModerationPlaygroundShell />)
    expect(screen.getByRole("tab", { name: /policy/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /blocklist/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /overrides/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /test/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /advanced/i })).toBeInTheDocument()
  })

  it("shows Policy tab content by default", async () => {
    render(<ModerationPlaygroundShell />)
    expect(await screen.findByText(/personal data protection/i)).toBeInTheDocument()
  })

  it("switches to Blocklist tab on click", async () => {
    render(<ModerationPlaygroundShell />)
    fireEvent.click(screen.getByRole("tab", { name: /blocklist/i }))
    expect(await screen.findByText(/syntax reference/i)).toBeInTheDocument()
  })

  it("renders context bar with scope selector", () => {
    render(<ModerationPlaygroundShell />)
    // The scope selector is a <select> with Server and User options
    const option = screen.getByRole("option", { name: /server/i }) as HTMLOptionElement
    expect(option).toBeInTheDocument()
    expect(option.selected).toBe(true)
  })
})
