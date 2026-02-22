import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  sendMessage: vi.fn(),
  tldwRequest: vi.fn(),
  storageGet: vi.fn(async () => ({ serverUrl: "http://127.0.0.1:8000" }))
}))

vi.mock("wxt/browser", () => ({
  browser: {
    runtime: {
      id: "test-extension",
      sendMessage: (...args: unknown[]) =>
        (mocks.sendMessage as (...args: unknown[]) => unknown)(...args)
    }
  }
}))

vi.mock("@/services/tldw/request-core", () => ({
  tldwRequest: (...args: unknown[]) =>
    (mocks.tldwRequest as (...args: unknown[]) => unknown)(...args)
}))

vi.mock("@/utils/safe-storage", () => ({
  createSafeStorage: () => ({
    get: (...args: unknown[]) =>
      (mocks.storageGet as (...args: unknown[]) => unknown)(...args)
  })
}))

const importApiSend = async () => import("@/services/api-send")

describe("apiSend timeout fallback policy", () => {
  beforeEach(() => {
    vi.resetModules()
    vi.useRealTimers()
    mocks.sendMessage.mockReset()
    mocks.tldwRequest.mockReset()
    mocks.storageGet.mockReset()
    mocks.storageGet.mockResolvedValue({ serverUrl: "http://127.0.0.1:8000" })
  })

  it("falls back to direct request for GET timeout", async () => {
    vi.useFakeTimers()
    mocks.sendMessage.mockImplementation(() => new Promise(() => undefined))
    mocks.tldwRequest.mockResolvedValue({ ok: true, status: 200, data: { ok: true } })

    const { apiSend } = await importApiSend()
    const pending = apiSend({ path: "/api/v1/health", method: "GET" })

    await vi.advanceTimersByTimeAsync(10001)

    await expect(pending).resolves.toMatchObject({ ok: true, status: 200 })
    expect(mocks.tldwRequest).toHaveBeenCalledTimes(1)
  })

  it("does not fall back to direct request for POST timeout", async () => {
    vi.useFakeTimers()
    mocks.sendMessage.mockImplementation(() => new Promise(() => undefined))
    mocks.tldwRequest.mockResolvedValue({ ok: true, status: 200, data: { ok: true } })

    const { apiSend } = await importApiSend()
    const pending = apiSend({
      path: "/api/v1/notes/search/",
      method: "POST",
      body: { q: "hello" }
    })
    const assertion = expect(pending).rejects.toThrow("Extension messaging timeout")

    await vi.advanceTimersByTimeAsync(10001)

    await assertion
    expect(mocks.tldwRequest).not.toHaveBeenCalled()
  })
})
