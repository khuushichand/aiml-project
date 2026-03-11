// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach } from "vitest"
import { renderHook, act, waitFor } from "@testing-library/react"

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------
const useQueryMock = vi.fn()
vi.mock("@tanstack/react-query", () => ({ useQuery: (opts: unknown) => useQueryMock(opts) }))
vi.mock("@/hooks/useServerOnline", () => ({ useServerOnline: () => true }))

const getUserOverrideMock = vi.fn()
const setUserOverrideMock = vi.fn()
const deleteUserOverrideMock = vi.fn()
const listUserOverridesMock = vi.fn()

vi.mock("@/services/moderation", () => ({
  getUserOverride: (...args: unknown[]) => getUserOverrideMock(...args),
  setUserOverride: (...args: unknown[]) => setUserOverrideMock(...args),
  deleteUserOverride: (...args: unknown[]) => deleteUserOverrideMock(...args),
  listUserOverrides: (...args: unknown[]) => listUserOverridesMock(...args)
}))

import { useUserOverrides } from "../hooks/useUserOverrides"

describe("useUserOverrides", () => {
  const refetchMock = vi.fn().mockResolvedValue({})

  beforeEach(() => {
    vi.clearAllMocks()
    useQueryMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      refetch: refetchMock
    })
  })

  it("returns initial state with no active user", () => {
    const { result } = renderHook(() => useUserOverrides(null))
    expect(result.current.draft).toEqual({})
    expect(result.current.loaded).toBe(false)
    expect(result.current.loading).toBe(false)
    expect(result.current.userIdError).toBeNull()
    expect(result.current.isDirty).toBe(false)
    expect(result.current.rules).toEqual([])
    expect(result.current.bannedRules).toEqual([])
    expect(result.current.notifyRules).toEqual([])
  })

  it("loads override when activeUserId is set", async () => {
    getUserOverrideMock.mockResolvedValue({
      exists: true,
      override: {
        enabled: true,
        input_enabled: true,
        output_enabled: false,
        input_action: "block",
        output_action: "warn",
        rules: [
          { id: "r1", pattern: "bad", is_regex: false, action: "block", phase: "both" }
        ]
      }
    })

    const { result } = renderHook(() => useUserOverrides("user1"))

    await waitFor(() => {
      expect(result.current.loaded).toBe(true)
    })

    expect(result.current.draft.enabled).toBe(true)
    expect(result.current.draft.input_action).toBe("block")
    expect(result.current.rules).toHaveLength(1)
    expect(result.current.bannedRules).toHaveLength(1)
    expect(result.current.notifyRules).toHaveLength(0)
  })

  it("sets userIdError when override does not exist", async () => {
    getUserOverrideMock.mockResolvedValue({
      exists: false,
      override: {}
    })

    const { result } = renderHook(() => useUserOverrides("unknown-user"))

    await waitFor(() => {
      expect(result.current.userIdError).toContain("No override found")
    })

    expect(result.current.loaded).toBe(false)
  })

  it("clears state when activeUserId becomes null", async () => {
    getUserOverrideMock.mockResolvedValue({
      exists: true,
      override: { enabled: true }
    })

    const { result, rerender } = renderHook(
      ({ userId }) => useUserOverrides(userId),
      { initialProps: { userId: "user1" as string | null } }
    )

    await waitFor(() => {
      expect(result.current.loaded).toBe(true)
    })

    rerender({ userId: null })

    await waitFor(() => {
      expect(result.current.loaded).toBe(false)
    })
    expect(result.current.draft).toEqual({})
    expect(result.current.userIdError).toBeNull()
  })

  it("isDirty detects changes", async () => {
    getUserOverrideMock.mockResolvedValue({
      exists: true,
      override: { enabled: true, input_action: "block" }
    })

    const { result } = renderHook(() => useUserOverrides("user1"))

    await waitFor(() => {
      expect(result.current.loaded).toBe(true)
    })

    act(() => {
      result.current.updateDraft({ input_action: "warn" })
    })

    expect(result.current.isDirty).toBe(true)
  })

  it("updateDraft merges partial into draft", () => {
    const { result } = renderHook(() => useUserOverrides(null))

    act(() => {
      result.current.updateDraft({ enabled: true, input_action: "block" })
    })

    expect(result.current.draft.enabled).toBe(true)
    expect(result.current.draft.input_action).toBe("block")
  })

  it("reset restores draft from baseline", async () => {
    getUserOverrideMock.mockResolvedValue({
      exists: true,
      override: { enabled: true, input_action: "block" }
    })

    const { result } = renderHook(() => useUserOverrides("user1"))

    await waitFor(() => {
      expect(result.current.loaded).toBe(true)
    })

    act(() => {
      result.current.updateDraft({ input_action: "warn" })
    })
    expect(result.current.isDirty).toBe(true)

    act(() => {
      result.current.reset()
    })

    expect(result.current.draft.input_action).toBe("block")
    expect(result.current.isDirty).toBe(false)
  })

  it("save calls setUserOverride and refetches", async () => {
    getUserOverrideMock.mockResolvedValue({
      exists: true,
      override: { enabled: true }
    })
    setUserOverrideMock.mockResolvedValue({})

    const { result } = renderHook(() => useUserOverrides("user1"))

    await waitFor(() => {
      expect(result.current.loaded).toBe(true)
    })

    await act(async () => {
      await result.current.save()
    })

    expect(setUserOverrideMock).toHaveBeenCalledWith("user1", expect.any(Object))
    expect(refetchMock).toHaveBeenCalled()
  })

  it("save throws if no active user", async () => {
    const { result } = renderHook(() => useUserOverrides(null))

    await expect(
      act(async () => {
        await result.current.save()
      })
    ).rejects.toThrow("No active user")
  })

  it("remove calls deleteUserOverride and clears state for active user", async () => {
    getUserOverrideMock.mockResolvedValue({
      exists: true,
      override: { enabled: true }
    })
    deleteUserOverrideMock.mockResolvedValue({ status: "ok" })

    const { result } = renderHook(() => useUserOverrides("user1"))

    await waitFor(() => {
      expect(result.current.loaded).toBe(true)
    })

    await act(async () => {
      await result.current.remove()
    })

    expect(deleteUserOverrideMock).toHaveBeenCalledWith("user1")
    expect(result.current.loaded).toBe(false)
    expect(result.current.draft).toEqual({})
  })

  it("remove with explicit userId deletes that user", async () => {
    deleteUserOverrideMock.mockResolvedValue({ status: "ok" })

    const { result } = renderHook(() => useUserOverrides("user1"))

    await act(async () => {
      await result.current.remove("other-user")
    })

    expect(deleteUserOverrideMock).toHaveBeenCalledWith("other-user")
  })

  it("bulkDelete deletes multiple and returns failed", async () => {
    deleteUserOverrideMock
      .mockResolvedValueOnce({ status: "ok" })
      .mockRejectedValueOnce(new Error("fail"))
      .mockResolvedValueOnce({ status: "ok" })

    const { result } = renderHook(() => useUserOverrides(null))

    let failed: string[] = []
    await act(async () => {
      failed = await result.current.bulkDelete(["u1", "u2", "u3"])
    })

    expect(failed).toEqual(["u2"])
    expect(deleteUserOverrideMock).toHaveBeenCalledTimes(3)
    expect(refetchMock).toHaveBeenCalled()
  })

  it("bulkDelete clears state if activeUserId is in the list", async () => {
    getUserOverrideMock.mockResolvedValue({
      exists: true,
      override: { enabled: true }
    })
    deleteUserOverrideMock.mockResolvedValue({ status: "ok" })

    const { result } = renderHook(() => useUserOverrides("user1"))

    await waitFor(() => {
      expect(result.current.loaded).toBe(true)
    })

    await act(async () => {
      await result.current.bulkDelete(["user1", "user2"])
    })

    expect(result.current.loaded).toBe(false)
    expect(result.current.draft).toEqual({})
  })

  it("addRule returns false for duplicate rules", async () => {
    getUserOverrideMock.mockResolvedValue({
      exists: true,
      override: {
        rules: [{ id: "r1", pattern: "bad", is_regex: false, action: "block", phase: "both" }]
      }
    })

    const { result } = renderHook(() => useUserOverrides("user1"))

    await waitFor(() => {
      expect(result.current.rules).toHaveLength(1)
    })

    let added = false
    act(() => {
      added = result.current.addRule({ pattern: "bad", is_regex: false, action: "block", phase: "both" })
    })

    expect(added).toBe(false)
    expect(result.current.rules).toHaveLength(1)
  })

  it("addRule adds non-duplicate rule", () => {
    const { result } = renderHook(() => useUserOverrides(null))

    let added = false
    act(() => {
      added = result.current.addRule({ pattern: "new-bad", is_regex: false, action: "warn", phase: "input" })
    })

    expect(added).toBe(true)
    expect(result.current.rules).toHaveLength(1)
    expect(result.current.notifyRules).toHaveLength(1)
  })

  it("removeRule removes rule by id", () => {
    const { result } = renderHook(() => useUserOverrides(null))

    act(() => {
      result.current.addRule({ pattern: "test", is_regex: false, action: "block", phase: "both" })
    })

    const ruleId = result.current.rules[0].id

    act(() => {
      result.current.removeRule(ruleId)
    })

    expect(result.current.rules).toHaveLength(0)
  })

  it("applyPreset calls setUserOverride with preset payload", async () => {
    setUserOverrideMock.mockResolvedValue({})

    const { result } = renderHook(() => useUserOverrides("user1"))

    await act(async () => {
      await result.current.applyPreset("strict")
    })

    expect(setUserOverrideMock).toHaveBeenCalledWith("user1", expect.objectContaining({
      enabled: true,
      input_action: "block",
      output_action: "redact"
    }))
    expect(result.current.loaded).toBe(true)
  })

  it("applyPreset throws if no active user", async () => {
    const { result } = renderHook(() => useUserOverrides(null))

    await expect(
      act(async () => {
        await result.current.applyPreset("strict")
      })
    ).rejects.toThrow("No active user")
  })

  it("applyPreset throws for unknown preset", async () => {
    const { result } = renderHook(() => useUserOverrides("user1"))

    await expect(
      act(async () => {
        await result.current.applyPreset("nonexistent")
      })
    ).rejects.toThrow("Unknown preset")
  })
})
