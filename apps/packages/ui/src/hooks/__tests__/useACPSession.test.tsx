/* @vitest-environment jsdom */
import { act, cleanup, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useACPSession } from "@/hooks/useACPSession"

const { useStorageMock } = vi.hoisted(() => ({
  useStorageMock: vi.fn(),
}))

vi.mock("@plasmohq/storage/hook", () => ({
  useStorage: useStorageMock,
}))

class MockWebSocket {
  static instances: MockWebSocket[] = []
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  readonly url: string
  readyState = MockWebSocket.CONNECTING
  onopen: (() => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  close(): void {
    this.readyState = MockWebSocket.CLOSED
  }

  send(): void {}

  closeWith(code: number, reason = ""): void {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.({ code, reason } as CloseEvent)
  }
}

describe("useACPSession", () => {
  beforeEach(() => {
    vi.useFakeTimers()
    MockWebSocket.instances = []
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket)
    useStorageMock.mockImplementation((key: string, defaultValue: unknown) => {
      const overrides: Record<string, unknown> = {
        serverUrl: "http://localhost:8000",
        authMode: "single-user",
        apiKey: "test-key",
        accessToken: "",
      }
      return [overrides[key] ?? defaultValue, vi.fn(), { isLoading: false }] as const
    })
  })

  afterEach(() => {
    cleanup()
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it.each([4401, 4404, 4429])("does not reconnect for fatal close code %s", async (code) => {
    const { result } = renderHook(() =>
      useACPSession({
        sessionId: "session-1",
        autoConnect: true,
      })
    )

    await act(async () => {
      await Promise.resolve()
    })

    expect(MockWebSocket.instances).toHaveLength(1)

    await act(async () => {
      MockWebSocket.instances[0].closeWith(code)
      await Promise.resolve()
      await vi.advanceTimersByTimeAsync(60000)
    })

    expect(MockWebSocket.instances).toHaveLength(1)
    expect(result.current.state).toBe("disconnected")
  })
})
