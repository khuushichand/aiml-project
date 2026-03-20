import { afterEach, describe, expect, it, vi } from "vitest"

const originalEnv = { ...process.env }

afterEach(() => {
  process.env = { ...originalEnv }
  vi.resetModules()
  vi.restoreAllMocks()
})

describe("real-server extension launch wrappers", () => {
  it("does not force a default timeout for launchWithExtensionOrSkip", async () => {
    const launchWithExtension = vi.fn().mockResolvedValue({ ok: true })

    vi.doMock("./extension", () => ({
      launchWithExtension,
    }))

    const { launchWithExtensionOrSkip } = await import("./real-server")
    const test = { skip: vi.fn() } as any

    await launchWithExtensionOrSkip(test, "/tmp/ext")

    expect(launchWithExtension).toHaveBeenCalledWith("/tmp/ext", {})
    expect(test.skip).not.toHaveBeenCalled()
  })

  it("does not force a default timeout for launchWithBuiltExtensionOrSkip", async () => {
    const launchWithBuiltExtension = vi.fn().mockResolvedValue({ ok: true })

    vi.doMock("./extension-build", () => ({
      launchWithBuiltExtension,
    }))

    const { launchWithBuiltExtensionOrSkip } = await import("./real-server")
    const test = { skip: vi.fn() } as any

    await launchWithBuiltExtensionOrSkip(test)

    expect(launchWithBuiltExtension).toHaveBeenCalledWith({})
    expect(test.skip).not.toHaveBeenCalled()
  })
})
