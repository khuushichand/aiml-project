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
    fireEvent.change(screen.getByPlaceholderText("Ask Persona..."), {
      target: { value: "memory toggle payload" }
    })
    fireEvent.click(screen.getByRole("button", { name: "Send" }))

    await waitFor(() => {
      const sentPayloads = getSentPayloads(ws)
      const userMessage = sentPayloads.find((payload) => payload.type === "user_message")
      expect(userMessage).toBeTruthy()
      expect(userMessage?.use_memory_context).toBe(false)
      expect(userMessage?.memory_top_k).toBe(3)
    })
  })
})
