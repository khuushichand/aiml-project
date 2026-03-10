import { beforeEach, describe, expect, it, vi } from "vitest"
import { ConnectionPhase } from "@/types/connection"

vi.mock("@/services/tldw-server", () => ({
  getStoredTldwServerURL: vi.fn(async () => null)
}))

vi.mock("@/services/api-send", () => ({
  apiSend: vi.fn()
}))

vi.mock("@/services/tldw/TldwApiClient", () => ({
  tldwClient: {
    getConfig: vi.fn(),
    initialize: vi.fn(),
    ragHealth: vi.fn(),
    updateConfig: vi.fn()
  }
}))

import { apiSend } from "@/services/api-send"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { CONNECTION_TIMEOUT_MS, useConnectionStore } from "../connection"

const mockedApiSend = vi.mocked(apiSend)
const mockedClient = vi.mocked(tldwClient, true)

const setConnectionState = (overrides: Record<string, unknown>) => {
  const prev = useConnectionStore.getState().state
  useConnectionStore.setState({
    state: {
      ...prev,
      ...overrides
    }
  })
}

const ageLastCheck = () => {
  setConnectionState({
    lastCheckedAt: Date.now() - 60_000,
    isChecking: false
  })
}

describe("connection store stability", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.removeItem("__tldw_allow_offline")
    localStorage.removeItem("__tldw_force_unconfigured")
    localStorage.removeItem("__tldw_first_run_complete")

    setConnectionState({
      phase: ConnectionPhase.CONNECTED,
      serverUrl: "http://127.0.0.1:8000",
      isConnected: true,
      isChecking: false,
      lastCheckedAt: Date.now() - 60_000,
      lastError: null,
      lastStatusCode: null,
      errorKind: "none",
      knowledgeStatus: "ready",
      knowledgeError: null,
      knowledgeLastCheckedAt: Date.now(),
      consecutiveFailures: 0
    })

    mockedClient.getConfig.mockResolvedValue({
      serverUrl: "http://127.0.0.1:8000",
      authMode: "single-user",
      apiKey: "test-key"
    } as any)
    mockedClient.initialize.mockResolvedValue(undefined)
    mockedClient.ragHealth.mockResolvedValue({ status: "healthy" } as any)
  })

  it("keeps connected state through transient unreachable checks before threshold", async () => {
    mockedApiSend.mockResolvedValue({
      ok: false,
      status: 0,
      error: "timeout"
    })

    await useConnectionStore.getState().checkOnce()
    let state = useConnectionStore.getState().state
    expect(state.phase).toBe(ConnectionPhase.CONNECTED)
    expect(state.isConnected).toBe(true)
    expect(state.errorKind).toBe("partial")
    expect(state.consecutiveFailures).toBe(1)

    ageLastCheck()
    await useConnectionStore.getState().checkOnce()
    state = useConnectionStore.getState().state
    expect(state.phase).toBe(ConnectionPhase.CONNECTED)
    expect(state.isConnected).toBe(true)
    expect(state.consecutiveFailures).toBe(2)

    ageLastCheck()
    await useConnectionStore.getState().checkOnce()
    state = useConnectionStore.getState().state
    expect(state.phase).toBe(ConnectionPhase.ERROR)
    expect(state.isConnected).toBe(false)
    expect(state.errorKind).toBe("unreachable")
    expect(state.consecutiveFailures).toBe(3)
  })

  it("uses lightweight health liveness endpoint and resets failure streak on success", async () => {
    setConnectionState({
      consecutiveFailures: 2,
      errorKind: "partial",
      lastError: "timeout"
    })
    mockedApiSend.mockResolvedValue({
      ok: true,
      status: 200,
      data: { status: "alive" }
    })

    await useConnectionStore.getState().checkOnce()

    const state = useConnectionStore.getState().state
    expect(state.phase).toBe(ConnectionPhase.CONNECTED)
    expect(state.isConnected).toBe(true)
    expect(state.consecutiveFailures).toBe(0)
    expect(state.lastError).toBeNull()
    expect(mockedApiSend).toHaveBeenCalledWith(
      expect.objectContaining({
        path: "/api/v1/health/live",
        method: "GET",
        timeoutMs: CONNECTION_TIMEOUT_MS
      })
    )
  })

  it("surfaces a CORS hint for cross-origin network-blocked health checks", async () => {
    setConnectionState({
      phase: ConnectionPhase.SEARCHING,
      serverUrl: "http://192.168.5.186:8000",
      isConnected: false,
      isChecking: false,
      lastCheckedAt: Date.now() - 60_000,
      consecutiveFailures: 0
    })
    mockedClient.getConfig.mockResolvedValue({
      serverUrl: "http://192.168.5.186:8000",
      authMode: "single-user",
      apiKey: "test-key"
    } as any)
    mockedApiSend.mockResolvedValue({
      ok: false,
      status: 0,
      error: "NetworkError when attempting to fetch resource."
    })

    await useConnectionStore.getState().checkOnce()

    const state = useConnectionStore.getState().state
    expect(state.phase).toBe(ConnectionPhase.ERROR)
    expect(state.errorKind).toBe("unreachable")
    expect(state.lastError).toContain("Likely CORS mismatch")
    expect(state.lastError).toContain("ALLOWED_ORIGINS")
  })

  it("surfaces a CORS/network hint for aborted cross-origin health checks", async () => {
    setConnectionState({
      phase: ConnectionPhase.SEARCHING,
      serverUrl: "http://192.168.5.186:8000",
      isConnected: false,
      isChecking: false,
      lastCheckedAt: Date.now() - 60_000,
      consecutiveFailures: 0
    })
    mockedClient.getConfig.mockResolvedValue({
      serverUrl: "http://192.168.5.186:8000",
      authMode: "single-user",
      apiKey: "test-key"
    } as any)
    mockedApiSend.mockResolvedValue({
      ok: false,
      status: 0,
      error: "The operation was aborted."
    })

    await useConnectionStore.getState().checkOnce()

    const state = useConnectionStore.getState().state
    expect(state.phase).toBe(ConnectionPhase.ERROR)
    expect(state.errorKind).toBe("unreachable")
    expect(state.lastError).toContain("Likely CORS mismatch")
    expect(state.lastError).toContain("ALLOWED_ORIGINS")
  })

  it("recovers from stale LAN host by switching to current browser host when probe succeeds", async () => {
    setConnectionState({
      phase: ConnectionPhase.SEARCHING,
      serverUrl: "http://192.168.5.186:8000",
      isConnected: false,
      isChecking: false,
      lastCheckedAt: Date.now() - 60_000,
      consecutiveFailures: 0
    })
    mockedClient.getConfig.mockResolvedValue({
      serverUrl: "http://192.168.5.186:8000",
      authMode: "single-user",
      apiKey: "test-key"
    } as any)
    mockedApiSend
      .mockResolvedValueOnce({
        ok: false,
        status: 0,
        error: "NetworkError when attempting to fetch resource."
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        data: { status: "alive" }
      })

    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue({
        ok: true,
        status: 200
      } as Response)

    const originalWindow = globalThis.window
    Object.defineProperty(globalThis, "window", {
      value: {
        location: {
          origin: "http://192.168.5.184:3000",
          hostname: "192.168.5.184"
        }
      },
      configurable: true
    })

    try {
      await useConnectionStore.getState().checkOnce()
    } finally {
      fetchMock.mockRestore()
      Object.defineProperty(globalThis, "window", {
        value: originalWindow,
        configurable: true
      })
    }

    const state = useConnectionStore.getState().state
    expect(mockedClient.updateConfig).toHaveBeenCalledWith({
      serverUrl: "http://192.168.5.184:8000"
    })
    expect(state.phase).toBe(ConnectionPhase.CONNECTED)
    expect(state.isConnected).toBe(true)
    expect(state.serverUrl).toBe("http://192.168.5.184:8000")
    expect(mockedApiSend).toHaveBeenCalledTimes(2)
  })

  it("preserves persisted first-run completion when offline bypass is enabled", async () => {
    setConnectionState({
      hasCompletedFirstRun: false,
      phase: ConnectionPhase.SEARCHING,
      isConnected: false,
      isChecking: false
    })
    localStorage.setItem("__tldw_first_run_complete", "true")
    localStorage.setItem("__tldw_allow_offline", "true")

    await useConnectionStore.getState().checkOnce()

    const state = useConnectionStore.getState().state
    expect(state.phase).toBe(ConnectionPhase.CONNECTED)
    expect(state.offlineBypass).toBe(true)
    expect(state.hasCompletedFirstRun).toBe(true)
  })

  it("preserves persisted first-run completion through a successful health check", async () => {
    setConnectionState({
      hasCompletedFirstRun: false,
      phase: ConnectionPhase.SEARCHING,
      isConnected: false,
      isChecking: false
    })
    localStorage.setItem("__tldw_first_run_complete", "true")
    mockedApiSend.mockResolvedValue({
      ok: true,
      status: 200,
      data: { status: "alive" }
    })

    await useConnectionStore.getState().checkOnce()

    const state = useConnectionStore.getState().state
    expect(state.phase).toBe(ConnectionPhase.CONNECTED)
    expect(state.isConnected).toBe(true)
    expect(state.hasCompletedFirstRun).toBe(true)
  })
})
