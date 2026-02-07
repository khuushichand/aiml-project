import { renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useServerCapabilities } from "../useServerCapabilities"

const { getServerCapabilitiesMock } = vi.hoisted(() => ({
  getServerCapabilitiesMock: vi.fn()
}))

vi.mock("@/services/tldw/server-capabilities", () => ({
  getServerCapabilities: getServerCapabilitiesMock
}))

describe("useServerCapabilities", () => {
  beforeEach(() => {
    getServerCapabilitiesMock.mockReset()
  })

  it("returns capabilities when capability fetch succeeds", async () => {
    const caps = { hasGuardian: true, hasSelfMonitoring: true }
    getServerCapabilitiesMock.mockResolvedValue(caps)

    const { result } = renderHook(() => useServerCapabilities())
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.capabilities).toEqual(caps)
  })

  it("fails closed when capability fetch throws", async () => {
    getServerCapabilitiesMock.mockRejectedValue(new Error("capability fetch failed"))

    const { result } = renderHook(() => useServerCapabilities())
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.capabilities).toBeNull()
  })
})
