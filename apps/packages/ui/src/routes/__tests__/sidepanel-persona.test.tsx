import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
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
    getConfig: (...args: unknown[]) => mocks.getConfig(...args),
    fetchWithAuth: (...args: unknown[]) => mocks.fetchWithAuth(...args)
  }
}))

vi.mock("@/services/persona-stream", () => ({
  buildPersonaWebSocketUrl: (...args: unknown[]) =>
    mocks.buildPersonaWebSocketUrl(...args)
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

  beforeAll(() => {
    globalThis.WebSocket = MockWebSocket as unknown as typeof WebSocket
  })

  afterAll(() => {
    globalThis.WebSocket = originalWebSocket
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
      expect(mocks.fetchWithAuth).toHaveBeenCalledTimes(2)
    })
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1)
    })
    expect(mocks.buildPersonaWebSocketUrl).toHaveBeenCalledTimes(1)

    const ws = MockWebSocket.instances[0]
    ws.emitOpen()

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Disconnect" })).toBeInTheDocument()
    })

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
    const checkboxes = screen.getAllByRole("checkbox")
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
})
