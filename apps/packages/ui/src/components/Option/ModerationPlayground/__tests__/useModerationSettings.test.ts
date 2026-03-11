import { describe, expect, it, vi, beforeEach } from "vitest"
import { renderHook, act, waitFor } from "@testing-library/react"

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------
const refetchMock = vi.fn().mockResolvedValue({})

// Store stable return values to avoid infinite re-renders from new object refs
let settingsReturn = { data: undefined as any, isLoading: false, refetch: refetchMock }
let policyReturn = { data: undefined as any, isLoading: false, refetch: refetchMock }

const useQueryMock = vi.fn().mockImplementation((opts: any) => {
  const key = opts?.queryKey?.[0]
  if (key === "moderation-settings") return settingsReturn
  if (key === "moderation-policy") return policyReturn
  return { data: undefined, isLoading: false, refetch: refetchMock }
})

vi.mock("@tanstack/react-query", () => ({ useQuery: (opts: unknown) => useQueryMock(opts) }))
vi.mock("@/hooks/useServerOnline", () => ({ useServerOnline: () => true }))

const updateModerationSettingsMock = vi.fn()
const reloadModerationMock = vi.fn()
vi.mock("@/services/moderation", () => ({
  getModerationSettings: vi.fn(),
  getEffectivePolicy: vi.fn(),
  updateModerationSettings: (...args: unknown[]) => updateModerationSettingsMock(...args),
  reloadModeration: (...args: unknown[]) => reloadModerationMock(...args)
}))

import { useModerationSettings } from "../hooks/useModerationSettings"

describe("useModerationSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    settingsReturn = { data: undefined, isLoading: false, refetch: refetchMock }
    policyReturn = { data: undefined, isLoading: false, refetch: refetchMock }
    useQueryMock.mockImplementation((opts: any) => {
      const key = opts?.queryKey?.[0]
      if (key === "moderation-settings") return settingsReturn
      if (key === "moderation-policy") return policyReturn
      return { data: undefined, isLoading: false, refetch: refetchMock }
    })
  })

  it("returns initial draft with defaults", () => {
    const { result } = renderHook(() => useModerationSettings())
    expect(result.current.draft).toEqual({
      piiEnabled: false,
      categoriesEnabled: [],
      persist: false
    })
    expect(result.current.isDirty).toBe(false)
    expect(result.current.baseline).toBeNull()
  })

  it("syncs draft from settingsQuery.data via effect", async () => {
    settingsReturn = {
      data: {
        pii_enabled: true,
        categories_enabled: ["violence", "pii"],
        effective: { pii_enabled: true, categories_enabled: ["violence", "pii"] }
      },
      isLoading: false,
      refetch: refetchMock
    }

    const { result } = renderHook(() => useModerationSettings())

    await waitFor(() => {
      expect(result.current.draft.piiEnabled).toBe(true)
    })
    expect(result.current.draft.categoriesEnabled).toEqual(["violence", "pii"])
  })

  it("isDirty is false when draft matches baseline", () => {
    const { result } = renderHook(() => useModerationSettings())
    expect(result.current.isDirty).toBe(false)
  })

  it("isDirty detects changes to draft", async () => {
    settingsReturn = {
      data: {
        pii_enabled: false,
        categories_enabled: [],
        effective: { pii_enabled: false, categories_enabled: [] }
      },
      isLoading: false,
      refetch: refetchMock
    }

    const { result } = renderHook(() => useModerationSettings())

    await waitFor(() => {
      expect(result.current.baseline).not.toBeNull()
    })

    act(() => {
      result.current.setDraft((prev) => ({ ...prev, piiEnabled: true }))
    })

    expect(result.current.isDirty).toBe(true)
  })

  it("save calls updateModerationSettings and refetches", async () => {
    updateModerationSettingsMock.mockResolvedValue({})

    const { result } = renderHook(() => useModerationSettings())

    act(() => {
      result.current.setDraft({ piiEnabled: true, categoriesEnabled: ["pii"], persist: false })
    })

    await act(async () => {
      await result.current.save()
    })

    expect(updateModerationSettingsMock).toHaveBeenCalledWith({
      pii_enabled: true,
      categories_enabled: ["pii"],
      persist: false
    })
    expect(refetchMock).toHaveBeenCalled()
  })

  it("reset restores draft from baseline", async () => {
    settingsReturn = {
      data: {
        pii_enabled: true,
        categories_enabled: ["violence"],
        effective: { pii_enabled: true, categories_enabled: ["violence"] }
      },
      isLoading: false,
      refetch: refetchMock
    }

    const { result } = renderHook(() => useModerationSettings())

    await waitFor(() => {
      expect(result.current.baseline).not.toBeNull()
    })

    // Change the draft
    act(() => {
      result.current.setDraft((prev) => ({ ...prev, piiEnabled: false, categoriesEnabled: [] }))
    })
    expect(result.current.isDirty).toBe(true)

    // Reset
    act(() => {
      result.current.reset()
    })

    expect(result.current.draft.piiEnabled).toBe(true)
    expect(result.current.draft.categoriesEnabled).toEqual(["violence"])
  })

  it("reload calls reloadModeration and refetches", async () => {
    reloadModerationMock.mockResolvedValue({})

    const { result } = renderHook(() => useModerationSettings())

    await act(async () => {
      await result.current.reload()
    })

    expect(reloadModerationMock).toHaveBeenCalled()
    expect(refetchMock).toHaveBeenCalled()
  })
})
