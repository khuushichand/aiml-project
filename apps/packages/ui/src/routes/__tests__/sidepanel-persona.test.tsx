import React from "react"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  isOnline: true,
  capabilitiesState: {
    capabilities: { hasPersona: true },
    loading: false
  } as { capabilities: { hasPersona: boolean } | null; loading: boolean },
  navigate: vi.fn(),
  getConfig: vi.fn(),
  fetchWithAuth: vi.fn(),
  buildPersonaWebSocketUrl: vi.fn(() => "ws://persona.test/api/v1/persona/stream")
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
    useNavigate: () => mocks.navigate
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
    mocks.isOnline = true
    mocks.capabilitiesState.capabilities = { hasPersona: true }
    mocks.capabilitiesState.loading = false
    mocks.navigate.mockReset()
    mocks.getConfig.mockReset()
    mocks.fetchWithAuth.mockReset()
    mocks.buildPersonaWebSocketUrl.mockReset()
    mocks.buildPersonaWebSocketUrl.mockReturnValue(
      "ws://persona.test/api/v1/persona/stream"
    )
  })

  it("shows connect empty state while offline and navigates to settings", () => {
    mocks.isOnline = false
    render(<SidepanelPersona />)

    expect(screen.getByText("Connect to use Persona")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Settings" }))
    expect(mocks.navigate).toHaveBeenCalledWith("/settings")
  })

  it("shows unavailable state when persona capability is missing", () => {
    mocks.capabilitiesState.capabilities = { hasPersona: false }
    render(<SidepanelPersona />)

    expect(screen.getByText("Persona unavailable")).toBeInTheDocument()
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
        steps: [{ idx: 0, tool: "rag_search", description: "search" }]
      })
    )
    await screen.findByText("requested memory results: 4")
    await screen.findByText("applied results: 2")

    fireEvent.click(screen.getByTestId("persona-memory-toggle"))
    fireEvent.click(screen.getByTestId("persona-state-context-toggle"))
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
