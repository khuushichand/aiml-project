import React from "react"
import { act, fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"

import { KnowledgeQA } from "../index"

const state = {
  settingsPanelOpen: false,
  setSettingsPanelOpen: vi.fn(),
  currentThreadId: null as string | null,
  selectThread: vi.fn(),
  selectSharedThread: vi.fn(),
}

const connectivity = {
  online: true,
  isChecking: false,
  lastCheckedAt: Date.now(),
  uxState: "connected_ok" as
    | "connected_ok"
    | "testing"
    | "configuring_url"
    | "configuring_auth"
    | "error_auth"
    | "error_unreachable"
    | "unconfigured",
  checkOnce: vi.fn(),
  navigate: vi.fn()
}

const capabilitiesState = {
  loading: false,
  capabilities: { hasRag: true },
  refresh: vi.fn(),
}

const layoutModeState = {
  mode: "simple" as "simple" | "research" | "expert",
  isSimple: true,
  isResearch: false,
  showPromotionToast: false,
}

vi.mock("../KnowledgeQAProvider", () => ({
  KnowledgeQAProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useKnowledgeQA: () => state
}))

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom"
  )
  return {
    ...actual,
    useNavigate: () => connectivity.navigate
  }
})

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => connectivity.online
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => ({
    loading: capabilitiesState.loading,
    capabilities: capabilitiesState.capabilities,
    refresh: capabilitiesState.refresh,
  })
}))

vi.mock("@/hooks/useConnectionState", () => ({
  useConnectionActions: () => ({
    checkOnce: connectivity.checkOnce,
  }),
  useConnectionState: () => ({
    isChecking: connectivity.isChecking,
    lastCheckedAt: connectivity.lastCheckedAt,
  }),
  useConnectionUxState: () => ({
    uxState: connectivity.uxState,
    hasCompletedFirstRun: true,
  }),
}))

vi.mock("@/hooks/useMediaQuery", () => ({
  useMobile: () => false,
  useDesktop: () => true,
}))

vi.mock("../hooks/useLayoutMode", () => ({
  useLayoutMode: () => ({
    mode: layoutModeState.mode,
    setLayoutMode: vi.fn(),
    isSimple: layoutModeState.isSimple,
    isResearch: layoutModeState.isResearch,
    showPromotionToast: layoutModeState.showPromotionToast,
    dismissPromotion: vi.fn(),
    acceptPromotion: vi.fn(),
  }),
}))

vi.mock("../SearchBar", () => ({
  SearchBar: () => <input aria-label="Search your knowledge base" />
}))

vi.mock("../HistorySidebar", () => ({
  HistorySidebar: () => <div />
}))

vi.mock("../AnswerPanel", () => ({
  AnswerPanel: () => <div />
}))

vi.mock("../SearchDetailsPanel", () => ({
  SearchDetailsPanel: () => <div />
}))

vi.mock("../SourceList", () => ({
  SourceList: () => <div />
}))

vi.mock("../FollowUpInput", () => ({
  FollowUpInput: () => <div />
}))

vi.mock("../ConversationThread", () => ({
  ConversationThread: () => <div />
}))

vi.mock("../SettingsPanel", () => ({
  SettingsPanel: () => <div />
}))

vi.mock("../ExportDialog", () => ({
  ExportDialog: () => <div />
}))

describe("KnowledgeQA connection states", () => {
  const renderKnowledgeQa = () =>
    render(
      <MemoryRouter initialEntries={["/knowledge"]}>
        <KnowledgeQA />
      </MemoryRouter>
    )

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
    connectivity.online = true
    connectivity.isChecking = false
    connectivity.lastCheckedAt = Date.now()
    connectivity.uxState = "connected_ok"
    capabilitiesState.loading = false
    capabilitiesState.capabilities = { hasRag: true }
  })

  it("shows credential guidance instead of the generic offline screen", () => {
    connectivity.online = false
    connectivity.uxState = "error_auth"

    renderKnowledgeQa()

    expect(
      screen.getByText("Add your credentials to use Knowledge QA")
    ).toBeInTheDocument()
    expect(screen.queryByText("Server Offline")).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Open Settings" }))
    expect(connectivity.navigate).toHaveBeenCalledWith("/settings/tldw")
  })

  it("shows setup guidance and routes users to setup", () => {
    connectivity.online = false
    connectivity.uxState = "unconfigured"

    renderKnowledgeQa()

    expect(
      screen.getByText("Finish setup to use Knowledge QA")
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Finish Setup" }))
    expect(connectivity.navigate).toHaveBeenCalledWith("/")
  })

  it("keeps retry behavior for unreachable servers", () => {
    vi.useFakeTimers()
    connectivity.online = false
    connectivity.uxState = "error_unreachable"
    connectivity.lastCheckedAt = Date.now() - 1_000

    renderKnowledgeQa()

    expect(
      screen.getByText("Can't reach your tldw server right now")
    ).toBeInTheDocument()
    expect(screen.getByText(/Retrying automatically in/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Retry connection" }))
    expect(connectivity.checkOnce).toHaveBeenCalled()

    act(() => {
      vi.runOnlyPendingTimers()
    })
  })

  it("stretches the knowledge workspace root to the full route width", () => {
    renderKnowledgeQa()

    expect(screen.getByTestId("knowledge-page-root")).toHaveClass("w-full")
    expect(screen.getByTestId("knowledge-page-root")).toHaveClass("flex-1")
    expect(screen.getByTestId("knowledge-page-root")).toHaveClass("min-w-0")
  })
})
