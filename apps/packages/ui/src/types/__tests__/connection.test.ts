import { describe, expect, it } from "vitest"
import { ConnectionPhase, deriveConnectionUxState, type ConnectionState } from "../connection"

const makeState = (overrides: Partial<ConnectionState> = {}): ConnectionState => ({
  phase: ConnectionPhase.SEARCHING,
  serverUrl: "http://127.0.0.1:8000",
  lastCheckedAt: null,
  lastError: null,
  lastStatusCode: null,
  isConnected: false,
  isChecking: false,
  consecutiveFailures: 0,
  offlineBypass: false,
  knowledgeStatus: "unknown",
  knowledgeLastCheckedAt: null,
  knowledgeError: null,
  mode: "normal",
  configStep: "none",
  errorKind: "none",
  hasCompletedFirstRun: false,
  lastConfigUpdatedAt: null,
  checksSinceConfigChange: 0,
  ...overrides
})

describe("deriveConnectionUxState", () => {
  it("keeps connected UX during background checks", () => {
    const state = makeState({
      phase: ConnectionPhase.CONNECTED,
      isConnected: true,
      isChecking: true
    })
    expect(deriveConnectionUxState(state)).toBe("connected_ok")
  })

  it("shows testing while actively searching before connection", () => {
    const state = makeState({
      phase: ConnectionPhase.SEARCHING,
      isConnected: false,
      isChecking: true
    })
    expect(deriveConnectionUxState(state)).toBe("testing")
  })
})
