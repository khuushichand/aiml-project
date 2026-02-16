import { act, cleanup, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import {
  getConnectionPollerSnapshot,
  useServerOnline
} from "@/hooks/useServerOnline"
import { useConnectionStore } from "@/store/connection"
import { ConnectionPhase } from "@/types/connection"

const setDisconnectedState = () => {
  const prev = useConnectionStore.getState().state
  useConnectionStore.setState({
    state: {
      ...prev,
      mode: "normal",
      phase: ConnectionPhase.ERROR,
      isConnected: false,
      isChecking: false,
      lastCheckedAt: null,
      lastError: "offline",
      lastStatusCode: 0
    }
  })
}

describe("useServerOnline", () => {
  let initialStore: ReturnType<typeof useConnectionStore.getState>

  beforeEach(() => {
    vi.useFakeTimers()
    initialStore = useConnectionStore.getState()
    setDisconnectedState()
  })

  afterEach(() => {
    cleanup()
    useConnectionStore.setState(initialStore, true)
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
  })

  it("keeps polling while disconnected and flips online after reconnect", async () => {
    const checkOnce = vi.fn(async () => {
      const callCount = checkOnce.mock.calls.length
      const prev = useConnectionStore.getState().state
      const connected = callCount >= 2
      useConnectionStore.setState({
        state: {
          ...prev,
          phase: connected ? ConnectionPhase.CONNECTED : ConnectionPhase.ERROR,
          isConnected: connected,
          isChecking: false,
          lastCheckedAt: Date.now(),
          lastError: connected ? null : "offline",
          lastStatusCode: connected ? null : 0
        }
      })
    })

    useConnectionStore.setState({ checkOnce })

    const { result, unmount } = renderHook(() => useServerOnline())

    await act(async () => {
      await Promise.resolve()
    })

    expect(checkOnce).toHaveBeenCalledTimes(1)
    expect(result.current).toBe(false)
    expect(getConnectionPollerSnapshot().intervalMs).toBe(5000)

    await act(async () => {
      vi.advanceTimersByTime(5000)
      await Promise.resolve()
    })

    expect(checkOnce).toHaveBeenCalledTimes(2)
    await act(async () => {
      await Promise.resolve()
    })
    expect(result.current).toBe(true)
    expect(getConnectionPollerSnapshot().intervalMs).toBe(30000)

    unmount()
    expect(getConnectionPollerSnapshot().subscribers).toBe(0)
  })
})
