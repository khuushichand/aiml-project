import { beforeEach, describe, expect, it, vi } from "vitest"

const mocks = vi.hoisted(() => ({
  sendMessage: vi.fn(),
  tldwRequest: vi.fn(),
  storageGet: vi.fn(async () => null),
  storageSet: vi.fn(async () => undefined)
}))

vi.mock("wxt/browser", () => ({
  browser: {
    runtime: {
      id: "test-extension",
      sendMessage: (...args: unknown[]) => mocks.sendMessage(...args)
    }
  }
}))

vi.mock("@/services/tldw/request-core", () => ({
  tldwRequest: (...args: unknown[]) => mocks.tldwRequest(...args)
}))

vi.mock("@/utils/safe-storage", () => ({
  createSafeStorage: () => ({
    get: (...args: unknown[]) => mocks.storageGet(...args),
    set: (...args: unknown[]) => mocks.storageSet(...args)
  })
}))

const importProxy = async () => import("@/services/background-proxy")

describe("background proxy fallback safety", () => {
  beforeEach(() => {
    vi.resetModules()
    vi.useRealTimers()
    mocks.sendMessage.mockReset()
    mocks.tldwRequest.mockReset()
    mocks.storageGet.mockReset()
    mocks.storageSet.mockReset()
    mocks.storageGet.mockResolvedValue(null)
    mocks.storageSet.mockResolvedValue(undefined)
  })

  it("does not fall back to direct request when background returns non-2xx", async () => {
    mocks.sendMessage.mockResolvedValue({ ok: false, status: 500, error: "boom" })
    mocks.tldwRequest.mockResolvedValue({ ok: true, status: 200, data: { fallback: true } })

    const { bgRequest } = await importProxy()

    await expect(
      bgRequest({ path: "/api/v1/health", method: "GET" })
    ).rejects.toMatchObject({ status: 500 })
    expect(mocks.tldwRequest).not.toHaveBeenCalled()
  })

  it("falls back to direct request on GET extension timeout", async () => {
    vi.useFakeTimers()
    mocks.sendMessage.mockImplementation(() => new Promise(() => undefined))
    mocks.tldwRequest.mockResolvedValue({ ok: true, status: 200, data: { via: "direct" } })

    const { bgRequest } = await importProxy()
    const pending = bgRequest<{ via: string }>({
      path: "/api/v1/health",
      method: "GET"
    })

    await vi.advanceTimersByTimeAsync(3001)

    await expect(pending).resolves.toEqual({ via: "direct" })
    expect(mocks.tldwRequest).toHaveBeenCalledTimes(1)
  })

  it("does not fall back to direct request on POST extension timeout", async () => {
    vi.useFakeTimers()
    mocks.sendMessage.mockImplementation(() => new Promise(() => undefined))
    mocks.tldwRequest.mockResolvedValue({ ok: true, status: 200, data: { via: "direct" } })

    const { bgRequest } = await importProxy()
    const pending = bgRequest({
      path: "/api/v1/notes/search/",
      method: "POST",
      body: { q: "hello" }
    })
    const assertion = expect(pending).rejects.toThrow("Extension messaging timeout")

    await vi.advanceTimersByTimeAsync(3001)

    await assertion
    expect(mocks.tldwRequest).not.toHaveBeenCalled()
  })

  it("does not fall back to direct upload when background returns non-2xx", async () => {
    mocks.sendMessage.mockResolvedValue({
      ok: false,
      status: 400,
      error: "bad request",
      data: { detail: "invalid" }
    })

    const { bgUpload } = await importProxy()

    await expect(
      bgUpload({
        path: "/api/v1/media/add",
        method: "POST",
        fields: { title: "example" }
      })
    ).rejects.toMatchObject({ status: 400 })
    expect(mocks.tldwRequest).not.toHaveBeenCalled()
  })

  it("does not fall back to direct upload on POST extension timeout", async () => {
    vi.useFakeTimers()
    mocks.sendMessage.mockImplementation(() => new Promise(() => undefined))

    const { bgUpload } = await importProxy()
    const pending = bgUpload({
      path: "/api/v1/media/add",
      method: "POST",
      fields: { title: "example" },
      timeoutMs: 100
    })
    const assertion = expect(pending).rejects.toThrow("Extension messaging timeout")

    await vi.advanceTimersByTimeAsync(5001)

    await assertion
    expect(mocks.tldwRequest).not.toHaveBeenCalled()
  })
})
