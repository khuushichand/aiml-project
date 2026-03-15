// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach } from "vitest"
import { renderHook, act } from "@testing-library/react"

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------
const testModerationMock = vi.fn()

vi.mock("@/services/moderation", () => ({
  testModeration: (...args: unknown[]) => testModerationMock(...args)
}))

import { useModerationTest } from "../hooks/useModerationTest"
import type { TestHistoryEntry } from "../hooks/useModerationTest"

describe("useModerationTest", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("returns initial state", () => {
    const { result } = renderHook(() => useModerationTest())
    expect(result.current.phase).toBe("input")
    expect(result.current.text).toBe("")
    expect(result.current.userId).toBe("")
    expect(result.current.result).toBeNull()
    expect(result.current.history).toEqual([])
    expect(result.current.running).toBe(false)
  })

  it("runTest calls testModeration with correct payload", async () => {
    const mockResponse = { flagged: true, action: "block" as const, effective: {} }
    testModerationMock.mockResolvedValue(mockResponse)

    const { result } = renderHook(() => useModerationTest())

    act(() => {
      result.current.setText("bad content")
      result.current.setUserId("user1")
      result.current.setPhase("output")
    })

    await act(async () => {
      await result.current.runTest()
    })

    expect(testModerationMock).toHaveBeenCalledWith({
      user_id: "user1",
      phase: "output",
      text: "bad content"
    })
    expect(result.current.result).toEqual(mockResponse)
  })

  it("runTest omits user_id when empty", async () => {
    testModerationMock.mockResolvedValue({ flagged: false, action: "pass", effective: {} })

    const { result } = renderHook(() => useModerationTest())

    act(() => {
      result.current.setText("safe content")
    })

    await act(async () => {
      await result.current.runTest()
    })

    expect(testModerationMock).toHaveBeenCalledWith({
      user_id: undefined,
      phase: "input",
      text: "safe content"
    })
  })

  it("runTest throws if text is empty", async () => {
    const { result } = renderHook(() => useModerationTest())

    await expect(
      act(async () => {
        await result.current.runTest()
      })
    ).rejects.toThrow("Enter sample text to test")
  })

  it("runTest adds entry to history (most recent first)", async () => {
    testModerationMock
      .mockResolvedValueOnce({ flagged: false, action: "pass", effective: {} })
      .mockResolvedValueOnce({ flagged: true, action: "block", effective: {} })

    const { result } = renderHook(() => useModerationTest())

    act(() => result.current.setText("first"))
    await act(async () => {
      await result.current.runTest()
    })

    act(() => result.current.setText("second"))
    await act(async () => {
      await result.current.runTest()
    })

    expect(result.current.history).toHaveLength(2)
    expect(result.current.history[0].text).toBe("second")
    expect(result.current.history[1].text).toBe("first")
  })

  it("history is capped at 20 entries", async () => {
    testModerationMock.mockResolvedValue({ flagged: false, action: "pass", effective: {} })

    const { result } = renderHook(() => useModerationTest())

    for (let i = 0; i < 25; i++) {
      act(() => result.current.setText(`text-${i}`))
      await act(async () => {
        await result.current.runTest()
      })
    }

    expect(result.current.history).toHaveLength(20)
    // Most recent should be first
    expect(result.current.history[0].text).toBe("text-24")
  })

  it("clearHistory empties the history", async () => {
    testModerationMock.mockResolvedValue({ flagged: false, action: "pass", effective: {} })

    const { result } = renderHook(() => useModerationTest())

    act(() => result.current.setText("test"))
    await act(async () => {
      await result.current.runTest()
    })

    expect(result.current.history).toHaveLength(1)

    act(() => {
      result.current.clearHistory()
    })

    expect(result.current.history).toEqual([])
  })

  it("loadFromHistory restores text, phase, userId, and result", () => {
    const entry: TestHistoryEntry = {
      phase: "output",
      text: "restored text",
      userId: "restored-user",
      result: { flagged: true, action: "block", effective: {} },
      timestamp: Date.now()
    }

    const { result } = renderHook(() => useModerationTest())

    act(() => {
      result.current.loadFromHistory(entry)
    })

    expect(result.current.text).toBe("restored text")
    expect(result.current.phase).toBe("output")
    expect(result.current.userId).toBe("restored-user")
    expect(result.current.result).toEqual(entry.result)
  })

  it("running is true during test execution", async () => {
    let resolvePromise: (value: unknown) => void
    testModerationMock.mockImplementation(() => new Promise((resolve) => {
      resolvePromise = resolve
    }))

    const { result } = renderHook(() => useModerationTest())

    act(() => result.current.setText("test"))

    let promise: Promise<void>
    act(() => {
      promise = result.current.runTest()
    })

    // running should be true while waiting
    expect(result.current.running).toBe(true)

    await act(async () => {
      resolvePromise!({ flagged: false, action: "pass", effective: {} })
      await promise!
    })

    expect(result.current.running).toBe(false)
  })

  it("running resets to false even on error", async () => {
    testModerationMock.mockRejectedValue(new Error("API error"))

    const { result } = renderHook(() => useModerationTest())

    act(() => result.current.setText("test"))

    await expect(
      act(async () => {
        await result.current.runTest()
      })
    ).rejects.toThrow("API error")

    expect(result.current.running).toBe(false)
  })
})
