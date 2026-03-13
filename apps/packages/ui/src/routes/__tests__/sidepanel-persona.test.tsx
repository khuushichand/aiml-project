import React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import {
  act,
  fireEvent,
  render as rtlRender,
  screen,
  waitFor,
  within
} from "@testing-library/react"
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  isOnline: true,
  capabilitiesState: {
    capabilities: { hasPersona: true, hasPersonalization: true },
    loading: false
  } as {
    capabilities:
      | { hasPersona: boolean; hasPersonalization?: boolean }
      | null
    loading: boolean
  },
  navigate: vi.fn(),
  location: {
    pathname: "/persona",
    search: "",
    hash: "",
    state: null,
    key: "persona-route"
  },
  useBlocker: vi.fn(),
  blocker: {
    state: "unblocked" as "unblocked" | "blocked" | "proceeding",
    proceed: vi.fn(),
    reset: vi.fn()
  },
  getConfig: vi.fn(),
  fetchWithAuth: vi.fn(),
  buildPersonaWebSocketUrl: vi.fn(() => "ws://persona.test/api/v1/persona/stream"),
  fetchCompanionConversationPrompts: vi.fn()
}))

vi.mock("@/hooks/useServerOnline", () => ({
  useServerOnline: () => mocks.isOnline
}))

vi.mock("@/hooks/useServerCapabilities", () => ({
  useServerCapabilities: () => mocks.capabilitiesState
}))

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom"
  )
  return {
    ...actual,
    UNSAFE_DataRouterContext: React.createContext({ router: {} }),
    useNavigate: () => mocks.navigate,
    useLocation: () => mocks.location,
    useBlocker: (...args: unknown[]) =>
      (mocks.useBlocker as (...args: unknown[]) => unknown)(...args)
  }
})

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    getConfig: (...args: unknown[]) =>
      (mocks.getConfig as (...args: unknown[]) => unknown)(...args),
    fetchWithAuth: (...args: unknown[]) =>
      (mocks.fetchWithAuth as (...args: unknown[]) => unknown)(...args)
  }
}))

vi.mock("@/services/persona-stream", () => ({
  buildPersonaWebSocketUrl: (...args: unknown[]) =>
    (mocks.buildPersonaWebSocketUrl as (...args: unknown[]) => unknown)(...args)
}))

vi.mock("@/services/companion", () => ({
  isCompanionConsentRequiredResponse: (
    response:
      | {
          status?: number
          error?: string | null
        }
      | null
      | undefined
  ) =>
    response?.status === 409 &&
    String(response?.error || "").includes(
      "Enable personalization before using companion."
    ),
  fetchCompanionConversationPrompts: (...args: unknown[]) =>
    (mocks.fetchCompanionConversationPrompts as (...args: unknown[]) => unknown)(
      ...args
  )
}))

vi.mock("@/hooks/useResolvedPersonaVoiceDefaults", () => ({
  useResolvedPersonaVoiceDefaults: () => ({
    sttLanguage: "en-US",
    sttModel: "whisper-1",
    ttsProvider: "tldw",
    ttsVoice: "af_heart",
    confirmationMode: "destructive_only",
    voiceChatTriggerPhrases: ["hey helper"],
    autoResume: true,
    bargeIn: false
  })
}))

vi.mock("@/components/Common/FeatureEmptyState", () => ({
  default: ({
    title,
    description,
    primaryActionLabel,
    onPrimaryAction
  }: {
    title: string
    description?: string
    primaryActionLabel?: string
    onPrimaryAction?: () => void
  }) => (
    <div data-testid="feature-empty-state">
      <div>{title}</div>
      {description ? <div>{description}</div> : null}
      {primaryActionLabel ? (
        <button type="button" onClick={onPrimaryAction}>
          {primaryActionLabel}
        </button>
      ) : null}
    </div>
  )
}))

vi.mock("@/components/Option/MCPHub", () => ({
  PersonaPolicySummary: ({ personaId }: { personaId?: string | null }) => (
    <div data-testid="persona-policy-summary">{personaId || "none"}</div>
  )
}))

vi.mock("~/components/Sidepanel/Chat/SidepanelHeaderSimple", () => ({
  SidepanelHeaderSimple: ({ activeTitle }: { activeTitle?: string }) => (
    <div data-testid="sidepanel-header">{activeTitle || "header"}</div>
  )
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?:
        | string
        | {
            defaultValue?: string
          }
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions
      if (defaultValueOrOptions?.defaultValue) return defaultValueOrOptions.defaultValue
      return key
    }
  })
}))

vi.mock("antd", async () => {
  const actual = await vi.importActual<typeof import("antd")>("antd")
  const Input = {
    ...actual.Input,
    TextArea: ({
      autoSize: _autoSize,
      onPressEnter,
      onKeyDown,
      value,
      onChange,
      ...rest
    }: any) => (
      <textarea
        {...rest}
        value={value ?? ""}
        onChange={(event) => onChange?.(event)}
        onKeyDown={(event) => {
          onKeyDown?.(event)
          if (event.key === "Enter") {
            onPressEnter?.(event)
          }
        }}
      />
    )
  }
  return {
    ...actual,
    Input
  }
})

import SidepanelPersona from "../sidepanel-persona"

class MockWebSocket {
  static instances: MockWebSocket[] = []

  url: string
  binaryType = "blob"
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  send = vi.fn<(payload: string) => void>()
  close = vi.fn<() => void>()

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
    this.close.mockImplementation(() => {
      this.onclose?.({} as CloseEvent)
    })
  }

  emitOpen() {
    this.onopen?.(new Event("open"))
  }

  emitMessage(data: string | ArrayBuffer) {
    this.onmessage?.({ data } as MessageEvent)
  }
}

const getSentPayloads = (ws: MockWebSocket) =>
  ws.send.mock.calls.map(([payload]) => JSON.parse(String(payload)))

const render = (ui: React.ReactElement) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false
      }
    }
  })

  return rtlRender(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  )
}

describe("SidepanelPersona", () => {
  const originalWebSocket = globalThis.WebSocket
  const originalResizeObserver = globalThis.ResizeObserver

  beforeAll(() => {
    globalThis.WebSocket = MockWebSocket as unknown as typeof WebSocket
    class MockResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
    globalThis.ResizeObserver =
      MockResizeObserver as unknown as typeof ResizeObserver
  })

  afterAll(() => {
    globalThis.WebSocket = originalWebSocket
    if (originalResizeObserver) {
      globalThis.ResizeObserver = originalResizeObserver
    } else {
      delete (globalThis as { ResizeObserver?: typeof ResizeObserver })
        .ResizeObserver
    }
  })

  beforeEach(() => {
    MockWebSocket.instances = []
    window.localStorage.clear()
    mocks.isOnline = true
    mocks.capabilitiesState.capabilities = {
      hasPersona: true,
      hasPersonalization: true
    }
    mocks.capabilitiesState.loading = false
    mocks.navigate.mockReset()
    mocks.location.pathname = "/persona"
    mocks.location.search = ""
    mocks.location.hash = ""
    mocks.location.state = null
    mocks.location.key = "persona-route"
    mocks.useBlocker.mockReset()
    mocks.blocker.state = "unblocked"
    mocks.blocker.proceed.mockReset()
    mocks.blocker.reset.mockReset()
    mocks.useBlocker.mockImplementation(() => mocks.blocker)
    mocks.getConfig.mockReset()
    mocks.fetchWithAuth.mockReset()
    mocks.buildPersonaWebSocketUrl.mockReset()
    mocks.fetchCompanionConversationPrompts.mockReset()
    mocks.buildPersonaWebSocketUrl.mockReturnValue(
      "ws://persona.test/api/v1/persona/stream"
    )
    mocks.fetchCompanionConversationPrompts.mockResolvedValue({
      prompt_source_kind: "reflection",
      prompt_source_id: "reflection-1",
      prompts: [
        {
          prompt_id: "prompt-1",
          label: "Next concrete step",
          prompt_text: "What is the next concrete step for project alpha?",
          prompt_type: "clarify_priority",
          source_reflection_id: "reflection-1",
          source_evidence_ids: ["activity-1"]
        }
      ]
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("shows connect empty state while offline and navigates to settings", () => {
    mocks.isOnline = false
    render(<SidepanelPersona />)

    expect(screen.getByTestId("sidepanel-header")).toHaveTextContent("Persona Garden")
    expect(screen.getByText("Connect to use Persona")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Settings" }))
    expect(mocks.navigate).toHaveBeenCalledWith("/settings")
  })

  it("shows unavailable state when persona capability is missing", () => {
    mocks.capabilitiesState.capabilities = {
      hasPersona: false,
      hasPersonalization: true
    }
    render(<SidepanelPersona />)

    expect(screen.getByTestId("sidepanel-header")).toHaveTextContent("Persona Garden")
    expect(screen.getByText("Persona unavailable")).toBeInTheDocument()
  })

  it("renders Persona Garden framing while keeping live session controls", () => {
    render(<SidepanelPersona />)

    expect(screen.getByTestId("sidepanel-header")).toHaveTextContent("Persona Garden")
    expect(screen.getByRole("tab", { name: "Commands" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "Test Lab" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "Live Session" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "Profiles" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "Voice & Examples" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "Connections" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "State Docs" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "Scopes" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "Policies" })).toBeInTheDocument()
    expect(screen.getByTestId("persona-memory-toggle")).toBeInTheDocument()
    expect(screen.getByTestId("persona-resume-session-select")).toBeInTheDocument()
  })

  it("boots persona selection and active tab from query params", async () => {
    mocks.location.search = "?persona_id=garden-helper&tab=profiles"
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: ""
    })
    mocks.fetchWithAuth.mockImplementation((path: string, init?: { body?: any }) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [
            { id: "research_assistant", name: "Research Assistant" },
            { id: "garden-helper", name: "Garden Helper" }
          ]
        })
      }
      if (path.includes("/persona/profiles/garden-helper")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "garden-helper",
            use_persona_state_context_default: true
          })
        })
      }
      if (path.includes("/persona/sessions?persona_id=garden-helper")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            session_id: "sess-garden-helper",
            persona: { id: init?.body?.persona_id || null }
          })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)

    expect(screen.getByRole("tab", { name: "Profiles" })).toHaveAttribute(
      "aria-selected",
      "true"
    )

    fireEvent.click(screen.getByRole("tab", { name: "Live Session" }))
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))

    await waitFor(() => {
      expect(mocks.fetchWithAuth).toHaveBeenCalled()
    })
    const calledPaths = mocks.fetchWithAuth.mock.calls.map(([path]) => String(path))
    expect(
      calledPaths.some((path) => path.includes("/persona/profiles/garden-helper"))
    ).toBe(true)
    expect(
      calledPaths.some((path) =>
        path.includes("/persona/sessions?persona_id=garden-helper")
      )
    ).toBe(true)
    const createSessionCall = mocks.fetchWithAuth.mock.calls.find(
      ([path]) => String(path) === "/api/v1/persona/session"
    )
    expect(createSessionCall?.[1]).toEqual(
      expect.objectContaining({
        method: "POST",
        body: expect.objectContaining({
          persona_id: "garden-helper"
        })
      })
    )
  })

  it("renders a dedicated companion conversation mode", () => {
    render(<SidepanelPersona mode="companion" />)

    expect(screen.getByTestId("sidepanel-header")).toHaveTextContent("Companion")
    expect(screen.getByPlaceholderText("Ask Companion...")).toBeInTheDocument()
    expect(screen.queryByLabelText("Select persona")).not.toBeInTheDocument()
    expect(screen.queryByTestId("persona-companion-context-toggle")).not.toBeInTheDocument()
    expect(screen.queryByTestId("persona-state-context-toggle")).not.toBeInTheDocument()
    expect(
      screen.queryByTestId("persona-state-editor-toggle-button")
    ).not.toBeInTheDocument()
  })

  it("records the current draft as a companion check-in", async () => {
    mocks.fetchWithAuth.mockImplementation((path: string, init?: { body?: any }) => {
      if (path.includes("/api/v1/companion/check-ins")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "activity-checkin-1",
            event_type: "companion_check_in_recorded",
            source_type: "companion_check_in",
            source_id: "checkin-1",
            surface: String(init?.body?.surface || "companion.workspace"),
            tags: [],
            provenance: {
              capture_mode: "explicit",
              route: "/api/v1/companion/check-ins",
              action: "manual_check_in"
            },
            metadata: {
              summary: String(init?.body?.summary || "")
            },
            created_at: "2026-03-10T12:30:00Z"
          })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)

    const draft = "Log this as an explicit companion check-in from persona."
    fireEvent.change(screen.getByPlaceholderText("Ask Persona..."), {
      target: { value: draft }
    })
    fireEvent.click(screen.getByRole("button", { name: "Save check-in" }))

    await waitFor(() => {
      expect(mocks.fetchWithAuth).toHaveBeenCalledWith(
        "/api/v1/companion/check-ins",
        {
          method: "POST",
          body: {
            summary: draft,
            surface: "persona.sidepanel"
          }
        }
      )
    })
    expect(screen.getByText("Saved draft to companion")).toBeInTheDocument()
    expect(screen.getByPlaceholderText("Ask Persona...")).toHaveValue(draft)
  })

  it("records companion-mode drafts with the companion conversation surface", async () => {
    mocks.fetchWithAuth.mockImplementation((path: string, init?: { body?: any }) => {
      if (path.includes("/api/v1/companion/check-ins")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "activity-checkin-2",
            event_type: "companion_check_in_recorded",
            source_type: "companion_check_in",
            source_id: "checkin-2",
            surface: String(init?.body?.surface || "companion.workspace"),
            tags: [],
            provenance: {
              capture_mode: "explicit",
              route: "/api/v1/companion/check-ins",
              action: "manual_check_in"
            },
            metadata: {
              summary: String(init?.body?.summary || "")
            },
            created_at: "2026-03-10T12:45:00Z"
          })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona mode="companion" />)

    const draft = "Capture this from the dedicated companion conversation."
    fireEvent.change(screen.getByPlaceholderText("Ask Companion..."), {
      target: { value: draft }
    })
    fireEvent.click(screen.getByRole("button", { name: "Save check-in" }))

    await waitFor(() => {
      expect(mocks.fetchWithAuth).toHaveBeenCalledWith(
        "/api/v1/companion/check-ins",
        {
          method: "POST",
          body: {
            summary: draft,
            surface: "companion.conversation"
          }
        }
      )
    })
    expect(screen.getByText("Saved draft to companion")).toBeInTheDocument()
  })

  it("renders companion conversation prompt chips and inserts text into the draft", async () => {
    render(<SidepanelPersona mode="companion" />)

    const chip = await screen.findByRole("button", { name: "Next concrete step" })
    fireEvent.click(chip)

    expect(screen.getByPlaceholderText("Ask Companion...")).toHaveValue(
      "What is the next concrete step for project alpha?"
    )
  })

  it("does not auto-send when a companion prompt chip is clicked", async () => {
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: ""
    })
    mocks.fetchWithAuth.mockImplementation((path: string, init?: { body?: any }) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/sessions?")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path === "/api/v1/persona/session") {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            session_id: "sess-companion",
            persona: { id: "research_assistant" }
          })
        })
      }
      if (path.includes("/persona/sessions/sess-companion")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ preferences: {} })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona mode="companion" />)

    fireEvent.click(screen.getByRole("button", { name: "Connect" }))
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    const ws = MockWebSocket.instances[0]
    ws.emitOpen()
    await screen.findByText("Persona stream connected")

    fireEvent.click(await screen.findByRole("button", { name: "Next concrete step" }))

    expect(getSentPayloads(ws).some((payload) => payload.type === "user_message")).toBe(
      false
    )
    expect(screen.getByPlaceholderText("Ask Companion...")).toHaveValue(
      "What is the next concrete step for project alpha?"
    )
  })

  it("shows a consent-required error when saving a companion check-in without opt-in", async () => {
    mocks.fetchWithAuth.mockImplementation((path: string) => {
      if (path.includes("/api/v1/companion/check-ins")) {
        return Promise.resolve({
          ok: false,
          status: 409,
          error: "Enable personalization before using companion.",
          json: async () => ({ detail: "Enable personalization before using companion." })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)

    fireEvent.change(screen.getByPlaceholderText("Ask Persona..."), {
      target: { value: "Do not save this silently." }
    })
    fireEvent.click(screen.getByRole("button", { name: "Save check-in" }))

    expect(
      await screen.findByText("Enable personalization before saving to companion.")
    ).toBeInTheDocument()
  })

  it.each([390, 1280])(
    "keeps new-session and memory controls discoverable at %ipx viewport width",
    (width) => {
      Object.defineProperty(window, "innerWidth", {
        configurable: true,
        writable: true,
        value: width
      })
      window.dispatchEvent(new Event("resize"))

      render(<SidepanelPersona />)

      expect(screen.getByLabelText("Resume session")).toBeInTheDocument()
      expect(screen.getByTestId("persona-memory-toggle")).toBeInTheDocument()
      expect(screen.getByTestId("persona-state-context-toggle")).toBeInTheDocument()
      expect(
        screen.getByTestId("persona-state-context-default-toggle")
      ).toBeInTheDocument()
      expect(screen.getByLabelText("Memory results")).toBeInTheDocument()
      expect(screen.getByText("Memory results: 3")).toBeInTheDocument()
      expect(screen.queryByText("k=3")).not.toBeInTheDocument()
    }
  )

  it("connects persona websocket and supports message/plan confirm-cancel flow", async () => {
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-12345" })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)

    fireEvent.click(screen.getByRole("button", { name: "Connect" }))

    await waitFor(() => {
      expect(mocks.fetchWithAuth).toHaveBeenCalled()
    })
    const calledPaths = mocks.fetchWithAuth.mock.calls.map(([path]) => String(path))
    expect(calledPaths.some((path) => path.includes("/persona/sessions"))).toBe(true)
    expect(calledPaths.some((path) => path.includes("/persona/session"))).toBe(true)
    expect(calledPaths.some((path) => path.includes("/persona/catalog"))).toBe(true)
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    expect(mocks.buildPersonaWebSocketUrl).toHaveBeenCalledTimes(1)

    const ws = MockWebSocket.instances[0]
    ws.emitOpen()

    await screen.findByText("Persona stream connected")

    fireEvent.change(screen.getByPlaceholderText("Ask Persona..."), {
      target: { value: "hello persona" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Send" }))

    await waitFor(() => {
      const sentPayloads = getSentPayloads(ws)
      expect(
        sentPayloads.some(
          (payload) =>
            payload.type === "user_message" &&
            payload.session_id === "sess-12345" &&
            payload.text === "hello persona"
        )
      ).toBe(true)
    })

    ws.emitMessage(
      JSON.stringify({
        event: "tool_plan",
        plan_id: "plan-1",
        steps: [
          { idx: 0, tool: "ingest_url", description: "ingest" },
          { idx: 1, tool: "rag_search", description: "search" }
        ]
      })
    )

    await screen.findByText("Pending tool plan")
    const planRoot = screen.getByText("Pending tool plan").closest("div")
    expect(planRoot).not.toBeNull()
    const checkboxes = within(planRoot as HTMLElement).getAllByRole("checkbox")
    fireEvent.click(checkboxes[0])
    fireEvent.click(screen.getByRole("button", { name: "Confirm plan" }))

    await waitFor(() => {
      const sentPayloads = getSentPayloads(ws)
      expect(
        sentPayloads.some(
          (payload) =>
            payload.type === "confirm_plan" &&
            payload.plan_id === "plan-1" &&
            JSON.stringify(payload.approved_steps) === JSON.stringify([1])
        )
      ).toBe(true)
    })

    ws.emitMessage(
      JSON.stringify({
        event: "tool_plan",
        plan_id: "plan-2",
        steps: [{ idx: 0, tool: "summarize", description: "summarize" }]
      })
    )
    await screen.findByText("Pending tool plan")
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }))

    await waitFor(() => {
      const sentPayloads = getSentPayloads(ws)
      expect(
        sentPayloads.some(
          (payload) =>
            payload.type === "cancel" &&
            payload.session_id === "sess-12345" &&
            payload.reason === "user_cancelled"
        )
      ).toBe(true)
    })
  })

  it("hydrates persisted session preferences when connecting to a resumed session", async () => {
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string) => {
      if (path.includes("/persona/profiles/research_assistant/state")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            soul_md: null,
            identity_md: null,
            heartbeat_md: null
          })
        })
      }
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/profiles/research_assistant")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "research_assistant",
            use_persona_state_context_default: true
          })
        })
      }
      if (path.includes("/persona/sessions/sess-pref-hydrated")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            session_id: "sess-pref-hydrated",
            preferences: {
              use_memory_context: false,
              use_companion_context: false,
              use_persona_state_context: false,
              memory_top_k: 7
            },
            turns: []
          })
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ session_id: "sess-pref-hydrated" }]
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-pref-hydrated" })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)

    fireEvent.click(screen.getByRole("button", { name: "Connect" }))

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    const ws = MockWebSocket.instances[0]
    ws.emitOpen()

    await screen.findByText("Persona stream connected")
    await screen.findByText("Memory results: 7")

    await waitFor(() => {
      expect(
        screen.getByTestId("persona-memory-toggle") as HTMLInputElement
      ).not.toBeChecked()
      expect(
        screen.getByTestId("persona-companion-context-toggle") as HTMLInputElement
      ).not.toBeChecked()
      expect(
        screen.getByTestId("persona-state-context-toggle") as HTMLInputElement
      ).not.toBeChecked()
    })
  })

  it("creates companion-mode persona sessions with the companion conversation surface", async () => {
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-companion" })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona mode="companion" />)

    fireEvent.click(screen.getByRole("button", { name: "Connect" }))

    await waitFor(() => {
      expect(mocks.fetchWithAuth).toHaveBeenCalledWith("/api/v1/persona/session", {
        method: "POST",
        body: {
          persona_id: "research_assistant",
          resume_session_id: undefined,
          surface: "companion.conversation"
        }
      })
    })
  })

  it("filters companion-mode session history to companion conversations", async () => {
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ session_id: "sess-companion-only" }]
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-companion-only" })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona mode="companion" />)

    fireEvent.click(screen.getByRole("button", { name: "Connect" }))

    await waitFor(() => {
      expect(
        mocks.fetchWithAuth.mock.calls.some(([path]) =>
          String(path).includes(
            "/api/v1/persona/sessions?persona_id=research_assistant&surface=companion.conversation&limit=50"
          )
        )
      ).toBe(true)
    })
  })

  it("prefers tool_result.output and falls back to legacy result alias", async () => {
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-legacy" })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })

    const ws = MockWebSocket.instances[0]
    ws.emitOpen()

    await screen.findByText("Persona stream connected")

    ws.emitMessage(
      JSON.stringify({
        event: "tool_result",
        step_idx: 2,
        output: "canonical-output",
        result: "legacy-alias"
      })
    )
    await screen.findByText("Result step 2: canonical-output")
    expect(screen.queryByText("Result step 2: legacy-alias")).not.toBeInTheDocument()

    ws.emitMessage(
      JSON.stringify({
        event: "tool_result",
        step_idx: 3,
        result: "legacy-only"
      })
    )
    await screen.findByText("Result step 3: legacy-only")
  })

  it("renders runtime approval requests and retries the tool after approval", async () => {
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string, init?: { method?: string; body?: any }) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-approval" })
        })
      }
      if (path.includes("/mcp/hub/approval-decisions")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: 101,
            approval_policy_id: init?.body?.approval_policy_id ?? 17,
            context_key: init?.body?.context_key,
            conversation_id: init?.body?.conversation_id,
            tool_name: init?.body?.tool_name,
            scope_key: init?.body?.scope_key,
            decision: init?.body?.decision,
            consume_on_match: init?.body?.duration === "once",
            expires_at: init?.body?.duration === "session" ? "2099-01-01T00:00:00Z" : null
          })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })

    const ws = MockWebSocket.instances[0]
    ws.emitOpen()

    ws.emitMessage(
      JSON.stringify({
        event: "tool_result",
        session_id: "sess-approval",
        plan_id: "plan-approval",
        step_idx: 0,
        step_type: "mcp_tool",
        tool: "knowledge.search",
        args: { query: "approval needed" },
        why: "Need to search notes",
        ok: false,
        error: "Runtime approval required",
        reason_code: "APPROVAL_REQUIRED",
        approval: {
          approval_policy_id: 17,
          mode: "ask_outside_profile",
          tool_name: "knowledge.search",
          context_key: "user:1|group:|persona:research_assistant",
          conversation_id: "sess-approval",
          scope_key: "tool:knowledge.search",
          reason: "outside_profile",
          duration_options: ["once", "session"],
          arguments_summary: { query: "approval needed" }
        }
      })
    )

    await screen.findByText("Runtime approval required")
    await screen.findByText("knowledge.search")
    await screen.findByText("outside_profile")

    fireEvent.click(screen.getByRole("button", { name: "Approve and retry" }))

    await waitFor(() => {
      const approvalCall = mocks.fetchWithAuth.mock.calls.find(([path]) =>
        String(path).includes("/mcp/hub/approval-decisions")
      )
      expect(approvalCall).toBeTruthy()
      expect(
        (
          approvalCall?.[1] as {
            body?: {
              approval_policy_id?: number
              tool_name?: string
              decision?: string
              duration?: string
            }
          }
        )?.body
      ).toMatchObject({
        approval_policy_id: 17,
        tool_name: "knowledge.search",
        decision: "approved",
        duration: "once",
      })
      const sentPayloads = getSentPayloads(ws)
      expect(
        sentPayloads.some(
          (payload) =>
            payload.type === "retry_tool_call" &&
            payload.plan_id === "plan-approval" &&
            payload.step_idx === 0 &&
            payload.tool === "knowledge.search"
        )
      ).toBe(true)
    })
  })

  it("records deny as current-request-only and does not retry the tool", async () => {
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string, init?: { method?: string; body?: any }) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-deny" })
        })
      }
      if (path.includes("/mcp/hub/approval-decisions")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: 102,
            approval_policy_id: init?.body?.approval_policy_id ?? 17,
            context_key: init?.body?.context_key,
            conversation_id: init?.body?.conversation_id,
            tool_name: init?.body?.tool_name,
            scope_key: init?.body?.scope_key,
            decision: init?.body?.decision,
            consume_on_match: false,
            expires_at: null
          })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })

    const ws = MockWebSocket.instances[0]
    ws.emitOpen()

    ws.emitMessage(
      JSON.stringify({
        event: "tool_result",
        session_id: "sess-deny",
        plan_id: "plan-deny",
        step_idx: 0,
        step_type: "mcp_tool",
        tool: "knowledge.search",
        args: { query: "deny me" },
        why: "Need to search notes",
        ok: false,
        error: "Runtime approval required",
        reason_code: "APPROVAL_REQUIRED",
        approval: {
          approval_policy_id: 17,
          mode: "ask_outside_profile",
          tool_name: "knowledge.search",
          context_key: "user:1|group:|persona:research_assistant",
          conversation_id: "sess-deny",
          scope_key: "tool:knowledge.search",
          reason: "outside_profile",
          duration_options: ["once", "session"],
          arguments_summary: { query: "deny me" }
        }
      })
    )

    await screen.findByText("Runtime approval required")
    fireEvent.click(screen.getByRole("button", { name: "Deny" }))

    await waitFor(() => {
      const approvalCall = mocks.fetchWithAuth.mock.calls.find(([path, init]) =>
        String(path).includes("/mcp/hub/approval-decisions") &&
        init?.body?.decision === "denied"
      )
      expect(approvalCall).toBeTruthy()
      const body = (
        approvalCall?.[1] as {
          body?: {
            decision?: string
            duration?: string
          }
        }
      )?.body
      expect(body?.decision).toBe("denied")
      expect(body?.duration).toBe("once")
      const sentPayloads = getSentPayloads(ws)
      expect(sentPayloads.some((payload) => payload.type === "retry_tool_call")).toBe(false)
    })
  })

  it("renders policy metadata and keeps blocked steps out of approvals", async () => {
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-policy" })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })

    const ws = MockWebSocket.instances[0]
    ws.emitOpen()

    ws.emitMessage(
      JSON.stringify({
        event: "tool_plan",
        plan_id: "plan-policy",
        steps: [
          {
            idx: 0,
            tool: "export_report",
            description: "Export report",
            policy: {
              allow: false,
              requires_confirmation: true,
              required_scope: "write:export",
              reason_code: "POLICY_EXPORT_DISABLED",
              reason: "Export tools are disabled by persona policy."
            }
          },
          {
            idx: 1,
            tool: "rag_search",
            description: "Search notes",
            policy: {
              allow: true,
              requires_confirmation: false,
              required_scope: "read"
            }
          }
        ]
      })
    )

    await screen.findByText("Pending tool plan")
    await screen.findByText("scope: write:export")
    await screen.findByText("blocked: POLICY_EXPORT_DISABLED")
    await screen.findByText("Export tools are disabled by persona policy.")

    const planRoot = screen.getByText("Pending tool plan").closest("div")
    expect(planRoot).not.toBeNull()
    const checkboxes = within(planRoot as HTMLElement).getAllByRole("checkbox")
    expect(checkboxes[0]).toBeDisabled()
    expect(checkboxes[0]).not.toBeChecked()
    expect(checkboxes[1]).toBeChecked()

    fireEvent.click(screen.getByRole("button", { name: "Confirm plan" }))
    await waitFor(() => {
      const sentPayloads = getSentPayloads(ws)
      expect(
        sentPayloads.some(
          (payload) =>
            payload.type === "confirm_plan" &&
            payload.plan_id === "plan-policy" &&
            JSON.stringify(payload.approved_steps) === JSON.stringify([1])
        )
      ).toBe(true)
    })
  })

  it("sends per-message memory controls in user_message payload", async () => {
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-memory-controls" })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })

    const ws = MockWebSocket.instances[0]
    ws.emitOpen()

    await screen.findByText("Memory results: 3")
    expect(screen.queryByText("k=3")).not.toBeInTheDocument()

    ws.emitMessage(
      JSON.stringify({
        event: "tool_plan",
        plan_id: "plan-memory-labels",
        memory: {
          enabled: true,
          requested_top_k: 4,
          applied_count: 2
        },
        companion: {
          enabled: true,
          requested_enabled: true,
          applied_card_count: 1,
          applied_activity_count: 2
        },
        steps: [{ idx: 0, tool: "rag_search", description: "search" }]
      })
    )
    await screen.findByText("requested memory results: 4")
    await screen.findByText("applied results: 2")
    await screen.findByText("companion on")
    await screen.findByText("applied cards: 1")
    await screen.findByText("applied activity: 2")

    fireEvent.click(screen.getByTestId("persona-memory-toggle"))
    fireEvent.click(screen.getByTestId("persona-state-context-toggle"))
    fireEvent.click(screen.getByTestId("persona-companion-context-toggle"))
    fireEvent.change(screen.getByPlaceholderText("Ask Persona..."), {
      target: { value: "memory toggle payload" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Send" }))

    await waitFor(() => {
      const sentPayloads = getSentPayloads(ws)
      const userMessage = sentPayloads.find((payload) => payload.type === "user_message")
      expect(userMessage).toBeTruthy()
      expect(userMessage?.use_memory_context).toBe(false)
      expect(userMessage?.use_persona_state_context).toBe(false)
      expect(userMessage?.use_companion_context).toBe(false)
      expect(userMessage?.memory_top_k).toBe(3)
    })
  })

  it("updates persona state-context profile default and applies it to outgoing messages", async () => {
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string, init?: { method?: string; body?: any }) => {
      if (path.includes("/persona/profiles/research_assistant/state")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            soul_md: null,
            identity_md: null,
            heartbeat_md: null
          })
        })
      }
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/profiles/research_assistant")) {
        if (String(init?.method || "GET").toUpperCase() === "PATCH") {
          const nextDefault = Boolean(init?.body?.use_persona_state_context_default)
          return Promise.resolve({
            ok: true,
            json: async () => ({
              id: "research_assistant",
              use_persona_state_context_default: nextDefault
            })
          })
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "research_assistant",
            use_persona_state_context_default: false
          })
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-state-default" })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    const ws = MockWebSocket.instances[0]
    ws.emitOpen()

    const stateToggleInput = screen.getByTestId(
      "persona-state-context-toggle"
    ) as HTMLInputElement
    const stateDefaultToggleInput = screen.getByTestId(
      "persona-state-context-default-toggle"
    ) as HTMLInputElement

    await waitFor(() => {
      expect(stateToggleInput).not.toBeChecked()
      expect(stateDefaultToggleInput).not.toBeChecked()
      expect(stateDefaultToggleInput).not.toBeDisabled()
    })

    fireEvent.click(screen.getByTestId("persona-state-context-default-toggle"))

    await waitFor(() => {
      const patchCall = mocks.fetchWithAuth.mock.calls.find(
        ([calledPath, calledInit]) =>
          String(calledPath).includes("/persona/profiles/research_assistant") &&
          String((calledInit as { method?: string } | undefined)?.method || "").toUpperCase() ===
            "PATCH"
      )
      expect(patchCall).toBeTruthy()
      expect(
        (patchCall?.[1] as { body?: { use_persona_state_context_default?: boolean } } | undefined)
          ?.body
      ).toEqual({ use_persona_state_context_default: true })
      expect(stateToggleInput).toBeChecked()
      expect(stateDefaultToggleInput).toBeChecked()
    })

    fireEvent.change(screen.getByPlaceholderText("Ask Persona..."), {
      target: { value: "state default payload" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Send" }))

    await waitFor(() => {
      const sentPayloads = getSentPayloads(ws)
      const userMessage = sentPayloads.find((payload) => payload.type === "user_message")
      expect(userMessage).toBeTruthy()
      expect(userMessage?.use_persona_state_context).toBe(true)
    })
  })

  it("loads, saves, and restores persona state docs from sidepanel controls", async () => {
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string, init?: { method?: string; body?: any }) => {
      const method = String(init?.method || "GET").toUpperCase()
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state/history")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            entries: [
              {
                entry_id: "hist-1",
                field: "soul_md",
                content: "archived soul version",
                is_active: false,
                version: 1
              }
            ]
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state/restore")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            soul_md: "restored soul version",
            identity_md: "initial identity",
            heartbeat_md: "initial heartbeat"
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state")) {
        if (method === "PUT") {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              persona_id: "research_assistant",
              soul_md: init?.body?.soul_md ?? null,
              identity_md: init?.body?.identity_md ?? null,
              heartbeat_md: init?.body?.heartbeat_md ?? null,
              last_modified: "2026-02-22T08:00:00Z"
            })
          })
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            soul_md: "initial soul",
            identity_md: "initial identity",
            heartbeat_md: "initial heartbeat",
            last_modified: "2026-02-22T07:00:00Z"
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "research_assistant",
            use_persona_state_context_default: true
          })
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-state-docs" })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    MockWebSocket.instances[0].emitOpen()

    const soulInput = screen.getByTestId("persona-state-soul-input") as HTMLTextAreaElement
    const identityInput = screen.getByTestId(
      "persona-state-identity-input"
    ) as HTMLTextAreaElement
    const heartbeatInput = screen.getByTestId(
      "persona-state-heartbeat-input"
    ) as HTMLTextAreaElement

    await waitFor(() => {
      expect(soulInput.value).toBe("initial soul")
      expect(identityInput.value).toBe("initial identity")
      expect(heartbeatInput.value).toBe("initial heartbeat")
    })

    fireEvent.change(soulInput, { target: { value: "updated soul draft" } })
    fireEvent.click(screen.getByTestId("persona-state-save-button"))

    await waitFor(() => {
      const putCall = mocks.fetchWithAuth.mock.calls.find(
        ([calledPath, calledInit]) =>
          String(calledPath).includes("/persona/profiles/research_assistant/state") &&
          String((calledInit as { method?: string } | undefined)?.method || "").toUpperCase() ===
            "PUT"
      )
      expect(putCall).toBeTruthy()
      expect(
        (putCall?.[1] as { body?: { soul_md?: string } } | undefined)?.body?.soul_md
      ).toBe("updated soul draft")
    })

    fireEvent.click(screen.getByTestId("persona-state-history-button"))
    await screen.findByText("archived soul version")

    fireEvent.click(screen.getByTestId("persona-state-restore-hist-1"))
    await waitFor(() => {
      const restoreCall = mocks.fetchWithAuth.mock.calls.find(
        ([calledPath, calledInit]) =>
          String(calledPath).includes("/persona/profiles/research_assistant/state/restore") &&
          String((calledInit as { method?: string } | undefined)?.method || "").toUpperCase() ===
            "POST"
      )
      expect(restoreCall).toBeTruthy()
      expect(
        (
          restoreCall?.[1] as { body?: { entry_id?: string } } | undefined
        )?.body?.entry_id
      ).toBe("hist-1")
      expect(soulInput.value).toBe("restored soul version")
    })
  })

  it("targets catalog-resolved persona for profile and state writes when connected", async () => {
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string, init?: { method?: string; body?: any }) => {
      const method = String(init?.method || "GET").toUpperCase()
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "builder_bot", name: "Builder Bot" }]
        })
      }
      if (path.includes("/persona/profiles/builder_bot/state")) {
        if (method === "PUT") {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              persona_id: "builder_bot",
              soul_md: init?.body?.soul_md ?? null,
              identity_md: init?.body?.identity_md ?? null,
              heartbeat_md: init?.body?.heartbeat_md ?? null
            })
          })
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "builder_bot",
            soul_md: "builder soul",
            identity_md: "builder identity",
            heartbeat_md: "builder heartbeat"
          })
        })
      }
      if (path.includes("/persona/profiles/builder_bot")) {
        if (method === "PATCH") {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              id: "builder_bot",
              use_persona_state_context_default: Boolean(
                init?.body?.use_persona_state_context_default
              )
            })
          })
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "builder_bot",
            use_persona_state_context_default: false
          })
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            session_id: "sess-builder",
            persona: { id: "builder_bot" }
          })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    MockWebSocket.instances[0].emitOpen()

    await waitFor(() => {
      const sessionCall = mocks.fetchWithAuth.mock.calls.find(([calledPath]) =>
        String(calledPath).includes("/persona/sessions?persona_id=builder_bot")
      )
      expect(sessionCall).toBeTruthy()
      const profileGetCall = mocks.fetchWithAuth.mock.calls.find(
        ([calledPath, calledInit]) =>
          String(calledPath).includes("/persona/profiles/builder_bot") &&
          String((calledInit as { method?: string } | undefined)?.method || "").toUpperCase() ===
            "GET"
      )
      expect(profileGetCall).toBeTruthy()
    })

    fireEvent.click(screen.getByTestId("persona-state-context-default-toggle"))
    fireEvent.change(screen.getByTestId("persona-state-soul-input"), {
      target: { value: "builder state update" }
    })
    fireEvent.click(screen.getByTestId("persona-state-save-button"))

    await waitFor(() => {
      const profilePatchCall = mocks.fetchWithAuth.mock.calls.find(
        ([calledPath, calledInit]) =>
          String(calledPath).includes("/persona/profiles/builder_bot") &&
          String((calledInit as { method?: string } | undefined)?.method || "").toUpperCase() ===
            "PATCH"
      )
      expect(profilePatchCall).toBeTruthy()
      const statePutCall = mocks.fetchWithAuth.mock.calls.find(
        ([calledPath, calledInit]) =>
          String(calledPath).includes("/persona/profiles/builder_bot/state") &&
          String((calledInit as { method?: string } | undefined)?.method || "").toUpperCase() ===
            "PUT"
      )
      expect(statePutCall).toBeTruthy()
      expect(
        String(profilePatchCall?.[0]).includes("/persona/profiles/research_assistant")
      ).toBe(false)
      expect(
        String(statePutCall?.[0]).includes("/persona/profiles/research_assistant/state")
      ).toBe(false)
    })
  })

  it("loads and saves persona assistant defaults from the Profiles tab", async () => {
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string, init?: { method?: string; body?: any }) => {
      const method = String(init?.method || "GET").toUpperCase()
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            soul_md: "persona soul",
            identity_md: "persona identity",
            heartbeat_md: "persona heartbeat"
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant")) {
        if (method === "PATCH") {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              id: "research_assistant",
              use_persona_state_context_default: true,
              voice_defaults: init?.body?.voice_defaults
            })
          })
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "research_assistant",
            use_persona_state_context_default: true,
            voice_defaults: {
              stt_language: "en-US",
              stt_model: "whisper-1",
              tts_provider: "tldw",
              tts_voice: "af_heart",
              confirmation_mode: "destructive_only",
              voice_chat_trigger_phrases: ["hey helper"],
              auto_resume: true,
              barge_in: false
            }
          })
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            session_id: "sess-assistant-defaults",
            persona: { id: "research_assistant" }
          })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    MockWebSocket.instances[0].emitOpen()
    await screen.findByText("Persona stream connected")

    fireEvent.click(screen.getByRole("tab", { name: "Profiles" }))
    const profileTabPanel = screen.getByRole("tabpanel", { name: "Profiles" })

    await waitFor(() => {
      expect(within(profileTabPanel).getByLabelText("STT language")).toHaveValue(
        "en-US"
      )
    })
    expect(
      within(profileTabPanel).getByText(
        "Persona defaults stay separate from browser-wide fallback settings. The preview below shows the effective values after local fallback is applied."
      )
    ).toBeInTheDocument()

    fireEvent.change(within(profileTabPanel).getByLabelText("STT language"), {
      target: { value: "fr-FR" }
    })
    fireEvent.change(within(profileTabPanel).getByLabelText("Trigger phrases"), {
      target: { value: "bonjour helper\nstatus helper" }
    })
    fireEvent.click(
      within(profileTabPanel).getByRole("button", {
        name: "Save assistant defaults"
      })
    )

    await waitFor(() => {
      const patchCall = mocks.fetchWithAuth.mock.calls.find(
        ([calledPath, calledInit]) =>
          String(calledPath).includes("/persona/profiles/research_assistant") &&
          String((calledInit as { method?: string } | undefined)?.method || "").toUpperCase() ===
            "PATCH" &&
          Boolean(
            (calledInit as { body?: { voice_defaults?: unknown } } | undefined)?.body
              ?.voice_defaults
          )
      )
      expect(patchCall).toBeTruthy()
      expect(
        (
          patchCall?.[1] as {
            body?: {
              voice_defaults?: {
                stt_language?: string
                voice_chat_trigger_phrases?: string[]
              }
            }
          } | undefined
        )?.body?.voice_defaults
      ).toEqual(
        expect.objectContaining({
          stt_language: "fr-FR",
          voice_chat_trigger_phrases: ["bonjour helper", "status helper"]
        })
      )
    })

    expect(within(profileTabPanel).getByText("Assistant defaults saved.")).toBeInTheDocument()
  })

  it("sends persona voice_config on connect and when live session overrides change", async () => {
    mocks.capabilitiesState.capabilities = {
      hasPersona: true,
      hasPersonalization: true,
      hasAudio: true
    } as any
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            soul_md: "persona soul",
            identity_md: "persona identity",
            heartbeat_md: "persona heartbeat"
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "research_assistant",
            use_persona_state_context_default: true,
            voice_defaults: {
              stt_language: "en-US",
              stt_model: "whisper-1",
              tts_provider: "tldw",
              tts_voice: "af_heart",
              confirmation_mode: "destructive_only",
              voice_chat_trigger_phrases: ["hey helper"],
              auto_resume: true,
              barge_in: false
            }
          })
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            session_id: "sess-live-voice",
            persona: { id: "research_assistant" }
          })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    const ws = MockWebSocket.instances[0]
    ws.emitOpen()
    await screen.findByText("Persona stream connected")

    await waitFor(() => {
      expect(getSentPayloads(ws)).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            type: "voice_config",
            session_id: "sess-live-voice",
            voice: expect.objectContaining({
              trigger_phrases: ["hey helper"],
              auto_resume: true,
              barge_in: false
            }),
            stt: expect.objectContaining({
              language: "en-US",
              model: "whisper-1"
            }),
            tts: expect.objectContaining({
              provider: "tldw",
              voice: "af_heart"
            })
          })
        ])
      )
    })

    fireEvent.click(screen.getByTestId("live-voice-auto-resume"))
    fireEvent.click(screen.getByTestId("live-voice-barge-in"))

    await waitFor(() => {
      expect(getSentPayloads(ws)).toEqual(
        expect.arrayContaining([
          expect.objectContaining({
            type: "voice_config",
            session_id: "sess-live-voice",
            voice: expect.objectContaining({
              auto_resume: false,
              barge_in: true
            })
          })
        ])
      )
    })
  })

  it("does not append tool processing notices into the visible persona log", async () => {
    mocks.capabilitiesState.capabilities = {
      hasPersona: true,
      hasPersonalization: true,
      hasAudio: true
    } as any
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            soul_md: "persona soul",
            identity_md: "persona identity",
            heartbeat_md: "persona heartbeat"
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "research_assistant",
            use_persona_state_context_default: true
          })
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            session_id: "sess-processing-notice",
            persona: { id: "research_assistant" }
          })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })

    const ws = MockWebSocket.instances[0]
    ws.emitOpen()
    await screen.findByText("Persona stream connected")

    act(() => {
      ws.emitMessage(
        JSON.stringify({
          event: "notice",
          reason_code: "VOICE_TURN_PROCESSING",
          message: "Still processing this voice turn."
        })
      )
    })

    expect(
      screen.queryByText("Still processing this voice turn.")
    ).not.toBeInTheDocument()

    act(() => {
      ws.emitMessage(
        JSON.stringify({
          event: "notice",
          reason_code: "VOICE_TOOL_EXECUTION_PROCESSING",
          tool: "search_notes",
          step_idx: 0,
          message: "Tool execution is still in progress."
        })
      )
    })

    expect(
      screen.queryByText("Tool execution is still in progress.")
    ).not.toBeInTheDocument()
  })

  it("copies the last committed voice command into the composer and reconnects the persona session from recovery", async () => {
    mocks.capabilitiesState.capabilities = {
      hasPersona: true,
      hasPersonalization: true,
      hasAudio: true
    } as any
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })

    const issuedSessionIds = ["sess-live-voice", "sess-live-voice-2"]
    let sessionCallCount = 0

    mocks.fetchWithAuth.mockImplementation((path: string) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            soul_md: "persona soul",
            identity_md: "persona identity",
            heartbeat_md: "persona heartbeat"
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "research_assistant",
            use_persona_state_context_default: true,
            voice_defaults: {
              stt_language: "en-US",
              stt_model: "whisper-1",
              tts_provider: "tldw",
              tts_voice: "af_heart",
              confirmation_mode: "destructive_only",
              voice_chat_trigger_phrases: ["hey helper"],
              auto_resume: true,
              barge_in: false
            }
          })
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        const nextSessionId = issuedSessionIds[sessionCallCount] || `sess-live-voice-${sessionCallCount + 1}`
        sessionCallCount += 1
        return Promise.resolve({
          ok: true,
          json: async () => ({
            session_id: nextSessionId,
            persona: { id: "research_assistant" }
          })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })

    const firstWs = MockWebSocket.instances[0]
    firstWs.emitOpen()
    await screen.findByText("Persona stream connected")
    vi.useFakeTimers()

    firstWs.emitMessage(
      JSON.stringify({
        event: "notice",
        reason_code: "VOICE_TURN_COMMITTED",
        transcript: "search my notes",
        commit_source: "vad_auto"
      })
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(8000)
    })

    expect(screen.getByText("Assistant response is delayed")).toBeInTheDocument()

    fireEvent.click(screen.getByTestId("live-voice-recovery-copy-command"))
    expect(screen.getByPlaceholderText("Ask Persona...")).toHaveValue("search my notes")

    vi.useRealTimers()
    fireEvent.click(screen.getByTestId("live-voice-recovery-reconnect"))

    await waitFor(() => {
      expect(firstWs.close).toHaveBeenCalledTimes(1)
      expect(MockWebSocket.instances).toHaveLength(2)
    })

    MockWebSocket.instances[1].emitOpen()
    await waitFor(() => {
      expect(
        mocks.fetchWithAuth.mock.calls.filter(
          ([path]) => String(path) === "/api/v1/persona/session"
        )
      ).toHaveLength(2)
    })
  })

  it("tracks dirty state and supports reverting state docs without saving", async () => {
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            soul_md: "stable soul",
            identity_md: "stable identity",
            heartbeat_md: "stable heartbeat"
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "research_assistant",
            use_persona_state_context_default: true
          })
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-dirty-revert" })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    MockWebSocket.instances[0].emitOpen()

    const soulInput = screen.getByTestId("persona-state-soul-input") as HTMLTextAreaElement
    const dirtyTag = screen.getByTestId("persona-state-dirty-tag")
    const saveButton = screen.getByTestId("persona-state-save-button")
    const revertButton = screen.getByTestId("persona-state-revert-button")

    await waitFor(() => {
      expect(soulInput.value).toBe("stable soul")
      expect(dirtyTag).toHaveTextContent("saved")
      expect(saveButton).toBeDisabled()
      expect(revertButton).toBeDisabled()
    })

    fireEvent.change(soulInput, { target: { value: "edited soul" } })
    await waitFor(() => {
      expect(dirtyTag).toHaveTextContent("unsaved")
      expect(saveButton).not.toBeDisabled()
      expect(revertButton).not.toBeDisabled()
    })

    fireEvent.click(revertButton)
    await waitFor(() => {
      expect(soulInput.value).toBe("stable soul")
      expect(dirtyTag).toHaveTextContent("saved")
      expect(saveButton).toBeDisabled()
      expect(revertButton).toBeDisabled()
    })

    const putCall = mocks.fetchWithAuth.mock.calls.find(
      ([calledPath, calledInit]) =>
        String(calledPath).includes("/persona/profiles/research_assistant/state") &&
        String((calledInit as { method?: string } | undefined)?.method || "").toUpperCase() ===
          "PUT"
    )
    expect(putCall).toBeUndefined()
  })

  it("registers and removes beforeunload guard based on draft dirty state", async () => {
    const addEventListenerSpy = vi.spyOn(window, "addEventListener")
    const removeEventListenerSpy = vi.spyOn(window, "removeEventListener")
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            soul_md: "stable soul",
            identity_md: "stable identity",
            heartbeat_md: "stable heartbeat"
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "research_assistant",
            use_persona_state_context_default: true
          })
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-beforeunload-guard" })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    MockWebSocket.instances[0].emitOpen()

    const soulInput = screen.getByTestId("persona-state-soul-input") as HTMLTextAreaElement
    const revertButton = screen.getByTestId("persona-state-revert-button")
    await waitFor(() => {
      expect(soulInput.value).toBe("stable soul")
    })

    fireEvent.change(soulInput, { target: { value: "unsaved beforeunload draft" } })

    let beforeUnloadHandler: ((event: BeforeUnloadEvent) => string | undefined) | null = null
    await waitFor(() => {
      const beforeUnloadCall = addEventListenerSpy.mock.calls.find(
        ([eventName]) => eventName === "beforeunload"
      )
      expect(beforeUnloadCall).toBeTruthy()
      beforeUnloadHandler = beforeUnloadCall?.[1] as
        | ((event: BeforeUnloadEvent) => string | undefined)
        | null
      expect(beforeUnloadHandler).toBeTruthy()
    })

    const beforeUnloadEvent = new Event("beforeunload", { cancelable: true }) as BeforeUnloadEvent
    const beforeUnloadResult = beforeUnloadHandler?.(beforeUnloadEvent)
    expect(beforeUnloadEvent.defaultPrevented).toBe(true)
    expect(String(beforeUnloadResult || "")).toContain(
      "You have unsaved state-doc changes"
    )
    expect(String(beforeUnloadResult || "")).toContain("Leave this page without saving")

    fireEvent.click(revertButton)
    await waitFor(() => {
      expect(soulInput.value).toBe("stable soul")
      const removeCall = removeEventListenerSpy.mock.calls.find(
        ([eventName, handler]) =>
          eventName === "beforeunload" && handler === beforeUnloadHandler
      )
      expect(removeCall).toBeTruthy()
    })

    addEventListenerSpy.mockRestore()
    removeEventListenerSpy.mockRestore()
  })

  it("resets blocked in-app navigation when unsaved draft discard is declined", async () => {
    const confirmSpy = vi.spyOn(window, "confirm")
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            soul_md: "stable soul",
            identity_md: "stable identity",
            heartbeat_md: "stable heartbeat"
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "research_assistant",
            use_persona_state_context_default: true
          })
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-router-block-decline" })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    MockWebSocket.instances[0].emitOpen()

    const soulInput = screen.getByTestId("persona-state-soul-input") as HTMLTextAreaElement
    await waitFor(() => {
      expect(soulInput.value).toBe("stable soul")
    })
    fireEvent.change(soulInput, { target: { value: "dirty route blocker draft" } })

    await waitFor(() => {
      expect(mocks.useBlocker.mock.calls.some(([when]) => when === true)).toBe(true)
    })

    confirmSpy.mockClear()
    mocks.blocker.proceed.mockClear()
    mocks.blocker.reset.mockClear()
    mocks.blocker.state = "blocked"
    confirmSpy.mockReturnValueOnce(false)
    fireEvent.change(soulInput, { target: { value: "dirty route blocker draft v2" } })

    await waitFor(() => {
      expect(confirmSpy).toHaveBeenCalled()
      expect(mocks.blocker.reset).toHaveBeenCalledTimes(1)
      expect(mocks.blocker.proceed).not.toHaveBeenCalled()
    })
    expect(String(confirmSpy.mock.calls[0]?.[0] || "")).toContain(
      "Leave this page and discard local drafts"
    )
    confirmSpy.mockRestore()
  })

  it("proceeds blocked in-app navigation when unsaved draft discard is confirmed", async () => {
    const confirmSpy = vi.spyOn(window, "confirm")
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            soul_md: "stable soul",
            identity_md: "stable identity",
            heartbeat_md: "stable heartbeat"
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "research_assistant",
            use_persona_state_context_default: true
          })
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-router-block-confirm" })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    MockWebSocket.instances[0].emitOpen()

    const soulInput = screen.getByTestId("persona-state-soul-input") as HTMLTextAreaElement
    await waitFor(() => {
      expect(soulInput.value).toBe("stable soul")
    })
    fireEvent.change(soulInput, { target: { value: "dirty route blocker confirm draft" } })

    await waitFor(() => {
      expect(mocks.useBlocker.mock.calls.some(([when]) => when === true)).toBe(true)
    })

    confirmSpy.mockClear()
    mocks.blocker.proceed.mockClear()
    mocks.blocker.reset.mockClear()
    mocks.blocker.state = "blocked"
    confirmSpy.mockReturnValueOnce(true)
    fireEvent.change(soulInput, { target: { value: "dirty route blocker confirm draft v2" } })

    await waitFor(() => {
      expect(confirmSpy).toHaveBeenCalled()
      expect(mocks.blocker.proceed).toHaveBeenCalledTimes(1)
      expect(mocks.blocker.reset).not.toHaveBeenCalled()
    })
    expect(String(confirmSpy.mock.calls[0]?.[0] || "")).toContain(
      "Leave this page and discard local drafts"
    )
    confirmSpy.mockRestore()
  })

  it("refreshes loaded state history after saving updated state docs", async () => {
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    let historyFetchCount = 0
    mocks.fetchWithAuth.mockImplementation((path: string, init?: { method?: string; body?: any }) => {
      const method = String(init?.method || "GET").toUpperCase()
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state/history")) {
        historyFetchCount += 1
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            entries: [
              {
                entry_id: "hist-refresh",
                field: "soul_md",
                content: "history value",
                is_active: false,
                version: historyFetchCount
              }
            ]
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state")) {
        if (method === "PUT") {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              persona_id: "research_assistant",
              soul_md: init?.body?.soul_md ?? null,
              identity_md: init?.body?.identity_md ?? null,
              heartbeat_md: init?.body?.heartbeat_md ?? null
            })
          })
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            soul_md: "history base soul",
            identity_md: "history base identity",
            heartbeat_md: "history base heartbeat"
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "research_assistant",
            use_persona_state_context_default: true
          })
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-history-refresh" })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    MockWebSocket.instances[0].emitOpen()
    await screen.findByText("Persona stream connected")

    fireEvent.click(screen.getByTestId("persona-state-history-button"))
    await waitFor(() => {
      expect(historyFetchCount).toBe(1)
    })

    fireEvent.change(screen.getByTestId("persona-state-soul-input"), {
      target: { value: "history refresh update" }
    })
    fireEvent.click(screen.getByTestId("persona-state-save-button"))

    await waitFor(() => {
      expect(historyFetchCount).toBeGreaterThanOrEqual(2)
    })
  })

  it("orders state history entries and displays metadata", async () => {
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state/history")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            entries: [
              {
                entry_id: "older-entry",
                field: "soul_md",
                content: "older history content",
                is_active: false,
                version: 1,
                created_at: "2026-02-20T01:00:00Z",
                last_modified: "2026-02-20T01:10:00Z"
              },
              {
                entry_id: "newer-entry",
                field: "soul_md",
                content: "newer history content",
                is_active: false,
                version: 2,
                created_at: "2026-02-21T01:00:00Z",
                last_modified: "2026-02-21T01:10:00Z"
              }
            ]
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            soul_md: "base soul",
            identity_md: "base identity",
            heartbeat_md: "base heartbeat"
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "research_assistant",
            use_persona_state_context_default: true
          })
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-history-order" })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    MockWebSocket.instances[0].emitOpen()
    await screen.findByText("Persona stream connected")

    fireEvent.click(screen.getByTestId("persona-state-history-button"))
    await screen.findByText("newer history content")
    await screen.findByText("older history content")

    const newestCards = screen.getAllByTestId(/persona-state-history-entry-/)
    expect(newestCards[0]).toHaveTextContent("newer history content")
    expect(screen.getByTestId("persona-state-history-meta-newer-entry")).toHaveTextContent(
      "created 2026-02-21T01:00:00Z"
    )
    expect(screen.getByTestId("persona-state-history-meta-newer-entry")).toHaveTextContent(
      "updated 2026-02-21T01:10:00Z"
    )

    fireEvent.click(screen.getByTestId("persona-state-history-order-oldest-button"))
    const oldestCards = screen.getAllByTestId(/persona-state-history-entry-/)
    expect(oldestCards[0]).toHaveTextContent("older history content")
  })

  it("restores and persists state history/editor preferences via localStorage", async () => {
    window.localStorage.setItem("sidepanel:persona:state-editor-expanded", "false")
    window.localStorage.setItem("sidepanel:persona:state-history-order", "oldest")

    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state/history")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            entries: [
              {
                entry_id: "pref-older",
                field: "soul_md",
                content: "pref older content",
                is_active: false,
                version: 1,
                created_at: "2026-02-20T01:00:00Z"
              },
              {
                entry_id: "pref-newer",
                field: "soul_md",
                content: "pref newer content",
                is_active: false,
                version: 2,
                created_at: "2026-02-21T01:00:00Z"
              }
            ]
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            soul_md: "pref soul",
            identity_md: "pref identity",
            heartbeat_md: "pref heartbeat"
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "research_assistant",
            use_persona_state_context_default: true
          })
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-pref-persist" })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    MockWebSocket.instances[0].emitOpen()
    await screen.findByText("Persona stream connected")

    expect(screen.queryByTestId("persona-state-soul-input")).not.toBeInTheDocument()
    expect(screen.getByText("Show editor")).toBeInTheDocument()

    fireEvent.click(screen.getByTestId("persona-state-editor-toggle-button"))
    expect(screen.getByTestId("persona-state-soul-input")).toBeInTheDocument()

    fireEvent.click(screen.getByTestId("persona-state-history-button"))
    await screen.findByText("pref older content")
    await screen.findByText("pref newer content")

    const oldestDefaultCards = screen.getAllByTestId(/persona-state-history-entry-/)
    expect(oldestDefaultCards[0]).toHaveTextContent("pref older content")

    fireEvent.click(screen.getByTestId("persona-state-history-order-newest-button"))
    const newestCards = screen.getAllByTestId(/persona-state-history-entry-/)
    expect(newestCards[0]).toHaveTextContent("pref newer content")
    expect(window.localStorage.getItem("sidepanel:persona:state-history-order")).toBe(
      "newest"
    )

    fireEvent.click(screen.getByTestId("persona-state-editor-toggle-button"))
    expect(window.localStorage.getItem("sidepanel:persona:state-editor-expanded")).toBe(
      "false"
    )
  })

  it("blocks connect when unsaved drafts exist and discard prompt is declined", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false)
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            soul_md: "server soul",
            identity_md: "server identity",
            heartbeat_md: "server heartbeat"
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "research_assistant",
            use_persona_state_context_default: true
          })
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-connect-guard" })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.change(screen.getByTestId("persona-state-soul-input"), {
      target: { value: "local draft soul" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))

    await waitFor(() => {
      expect(confirmSpy).toHaveBeenCalled()
      expect(MockWebSocket.instances).toHaveLength(0)
    })
    const connectSessionCall = mocks.fetchWithAuth.mock.calls.find(([path]) =>
      String(path).includes("/persona/session")
    )
    expect(connectSessionCall).toBeFalsy()
    expect(String(confirmSpy.mock.calls[0]?.[0] || "")).toContain(
      "Connect and discard local drafts"
    )
    confirmSpy.mockRestore()
  })

  it("keeps session connected when unsaved drafts exist and disconnect prompt is declined", async () => {
    const confirmSpy = vi.spyOn(window, "confirm")
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            soul_md: "connected soul",
            identity_md: "connected identity",
            heartbeat_md: "connected heartbeat"
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "research_assistant",
            use_persona_state_context_default: true
          })
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-disconnect-guard" })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    MockWebSocket.instances[0].emitOpen()
    await screen.findByText("Persona stream connected")
    confirmSpy.mockClear()

    fireEvent.change(screen.getByTestId("persona-state-soul-input"), {
      target: { value: "unsaved disconnect draft" }
    })

    confirmSpy.mockReturnValueOnce(false)
    fireEvent.click(screen.getByRole("button", { name: /Disconnect/i }))
    await waitFor(() => {
      expect(confirmSpy).toHaveBeenCalled()
    })
    expect(String(confirmSpy.mock.calls[0]?.[0] || "")).toContain(
      "Disconnect and discard local drafts"
    )
    expect(screen.getByRole("button", { name: /Disconnect/i })).toBeInTheDocument()

    confirmSpy.mockReturnValueOnce(true)
    fireEvent.click(screen.getByRole("button", { name: /Disconnect/i }))
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /^(?:loading)?Connect$/i })
      ).toBeInTheDocument()
    })
    confirmSpy.mockRestore()
  })

  it("blocks restore when unsaved drafts exist until discard is confirmed", async () => {
    const confirmSpy = vi.spyOn(window, "confirm")
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation(
      (path: string, init?: { method?: string; body?: Record<string, unknown> }) => {
        const method = String(init?.method || "GET").toUpperCase()
        if (path.includes("/persona/catalog")) {
          return Promise.resolve({
            ok: true,
            json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
          })
        }
        if (path.includes("/persona/profiles/research_assistant/state/history")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              persona_id: "research_assistant",
              entries: [
                {
                  entry_id: "restore-guard-entry",
                  field: "soul_md",
                  content: "history soul version",
                  is_active: false,
                  version: 1
                }
              ]
            })
          })
        }
        if (path.includes("/persona/profiles/research_assistant/state/restore")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              persona_id: "research_assistant",
              soul_md: "restored from history",
              identity_md: "initial identity",
              heartbeat_md: "initial heartbeat"
            })
          })
        }
        if (path.includes("/persona/profiles/research_assistant/state")) {
          if (method === "PUT") {
            return Promise.resolve({
              ok: true,
              json: async () => ({
                persona_id: "research_assistant",
                soul_md: init?.body?.soul_md ?? null,
                identity_md: init?.body?.identity_md ?? null,
                heartbeat_md: init?.body?.heartbeat_md ?? null
              })
            })
          }
          return Promise.resolve({
            ok: true,
            json: async () => ({
              persona_id: "research_assistant",
              soul_md: "initial soul",
              identity_md: "initial identity",
              heartbeat_md: "initial heartbeat"
            })
          })
        }
        if (path.includes("/persona/profiles/research_assistant")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              id: "research_assistant",
              use_persona_state_context_default: true
            })
          })
        }
        if (path.includes("/persona/sessions")) {
          return Promise.resolve({
            ok: true,
            json: async () => []
          })
        }
        if (path.includes("/persona/session")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({ session_id: "sess-restore-guard" })
          })
        }
        return Promise.resolve({
          ok: false,
          error: `unhandled path: ${path}`,
          json: async () => ({})
        })
      }
    )

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    MockWebSocket.instances[0].emitOpen()
    await screen.findByText("Persona stream connected")
    confirmSpy.mockClear()

    const soulInput = screen.getByTestId("persona-state-soul-input") as HTMLTextAreaElement
    await waitFor(() => {
      expect(soulInput.value).toBe("initial soul")
    })
    fireEvent.click(screen.getByTestId("persona-state-history-button"))
    await screen.findByText("history soul version")

    fireEvent.change(soulInput, {
      target: { value: "unsaved local draft before restore" }
    })

    confirmSpy.mockReturnValueOnce(false)
    fireEvent.click(screen.getByTestId("persona-state-restore-restore-guard-entry"))
    await waitFor(() => {
      expect(confirmSpy).toHaveBeenCalled()
    })
    expect(String(confirmSpy.mock.calls[0]?.[0] || "")).toContain(
      "Restore this state version and discard local drafts"
    )
    const declinedRestoreCall = mocks.fetchWithAuth.mock.calls.find(
      ([calledPath, calledInit]) =>
        String(calledPath).includes("/persona/profiles/research_assistant/state/restore") &&
        String((calledInit as { method?: string } | undefined)?.method || "").toUpperCase() ===
          "POST"
    )
    expect(declinedRestoreCall).toBeFalsy()
    expect(soulInput.value).toBe("unsaved local draft before restore")

    confirmSpy.mockReturnValueOnce(true)
    fireEvent.click(screen.getByTestId("persona-state-restore-restore-guard-entry"))
    await waitFor(() => {
      const acceptedRestoreCall = mocks.fetchWithAuth.mock.calls.find(
        ([calledPath, calledInit]) =>
          String(calledPath).includes("/persona/profiles/research_assistant/state/restore") &&
          String((calledInit as { method?: string } | undefined)?.method || "").toUpperCase() ===
            "POST"
      )
      expect(acceptedRestoreCall).toBeTruthy()
      expect(soulInput.value).toBe("restored from history")
    })
    confirmSpy.mockRestore()
  })

  it("shows empty history message and supports state editor collapse/expand", async () => {
    mocks.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "persona-key"
    })
    mocks.fetchWithAuth.mockImplementation((path: string) => {
      if (path.includes("/persona/catalog")) {
        return Promise.resolve({
          ok: true,
          json: async () => [{ id: "research_assistant", name: "Research Assistant" }]
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state/history")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            entries: []
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant/state")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            persona_id: "research_assistant",
            soul_md: "state soul",
            identity_md: "state identity",
            heartbeat_md: "state heartbeat"
          })
        })
      }
      if (path.includes("/persona/profiles/research_assistant")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: "research_assistant",
            use_persona_state_context_default: true
          })
        })
      }
      if (path.includes("/persona/sessions")) {
        return Promise.resolve({
          ok: true,
          json: async () => []
        })
      }
      if (path.includes("/persona/session")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: "sess-empty-history" })
        })
      }
      return Promise.resolve({
        ok: false,
        error: `unhandled path: ${path}`,
        json: async () => ({})
      })
    })

    render(<SidepanelPersona />)
    fireEvent.click(screen.getByRole("button", { name: "Connect" }))
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    MockWebSocket.instances[0].emitOpen()
    await screen.findByText("Persona stream connected")

    fireEvent.click(screen.getByTestId("persona-state-history-button"))
    await screen.findByTestId("persona-state-history-empty")
    expect(screen.getByText("No state history entries yet.")).toBeInTheDocument()

    fireEvent.click(screen.getByTestId("persona-state-editor-toggle-button"))
    expect(screen.queryByTestId("persona-state-soul-input")).not.toBeInTheDocument()
    expect(screen.getByText("Show editor")).toBeInTheDocument()

    fireEvent.click(screen.getByTestId("persona-state-editor-toggle-button"))
    expect(screen.getByTestId("persona-state-soul-input")).toBeInTheDocument()
    expect(screen.getByText("Hide editor")).toBeInTheDocument()
  })
})
