import { describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  emitSplashAfterLoginSuccess: vi.fn()
}))

vi.mock("@/services/splash-events", () => ({
  emitSplashAfterLoginSuccess: mocks.emitSplashAfterLoginSuccess
}))

import { emitSplashAfterSingleUserAuthSuccess } from "@/services/splash-auth"

describe("emitSplashAfterSingleUserAuthSuccess", () => {
  it("emits splash when single-user auth succeeds", () => {
    mocks.emitSplashAfterLoginSuccess.mockReset()
    emitSplashAfterSingleUserAuthSuccess("single-user", true)
    expect(mocks.emitSplashAfterLoginSuccess).toHaveBeenCalledTimes(1)
  })

  it("does not emit splash for multi-user mode", () => {
    mocks.emitSplashAfterLoginSuccess.mockReset()
    emitSplashAfterSingleUserAuthSuccess("multi-user", true)
    expect(mocks.emitSplashAfterLoginSuccess).not.toHaveBeenCalled()
  })

  it("does not emit splash when not connected", () => {
    mocks.emitSplashAfterLoginSuccess.mockReset()
    emitSplashAfterSingleUserAuthSuccess("single-user", false)
    expect(mocks.emitSplashAfterLoginSuccess).not.toHaveBeenCalled()
  })
})

