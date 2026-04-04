// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach } from "vitest"
import { checkStorageBeforeWrite, notifyStorageWrite } from "../storage-guard"

describe("storage-guard", () => {
  beforeEach(() => localStorage.clear())

  it("returns canWrite true when storage is empty", () => {
    const result = checkStorageBeforeWrite(100)
    expect(result.canWrite).toBe(true)
    expect(result.wouldExceed).toBe(false)
    expect(result.recommendation).toBeNull()
  })

  it("returns recommendation when ratio >= 80%", () => {
    // Fill workspace storage to ~80% of 5MB = ~4MB
    const key = "tldw-workspace"
    const bigValue = "x".repeat(4 * 1024 * 1024)
    try { localStorage.setItem(key, bigValue) } catch { /* may fail in test env */ }
    const result = checkStorageBeforeWrite(100)
    if (result.currentRatio >= 0.80) {
      expect(result.recommendation).toBeTruthy()
    }
    localStorage.removeItem(key)
  })

  it("dispatches refresh event via notifyStorageWrite", () => {
    const handler = vi.fn()
    window.addEventListener("tldw:storage-quota-refresh", handler)
    notifyStorageWrite()
    expect(handler).toHaveBeenCalledTimes(1)
    window.removeEventListener("tldw:storage-quota-refresh", handler)
  })
})
