import { afterEach, describe, expect, it, vi } from "vitest"

describe("useDeferredComposerInput", () => {
  afterEach(() => {
    vi.resetModules()
    vi.doUnmock("react")
  })

  it("returns live and deferred values using React.useDeferredValue", async () => {
    const mockedUseDeferredValue = vi.fn((value: string) => `${value}-deferred`)
    vi.doMock("react", async () => {
      const actual = await vi.importActual<Record<string, unknown>>("react")
      return {
        ...actual,
        default: {
          ...(actual.default as Record<string, unknown>),
          useDeferredValue: mockedUseDeferredValue
        },
        useDeferredValue: mockedUseDeferredValue
      }
    })

    const { useDeferredComposerInput } = await import("../useDeferredComposerInput")
    const result = useDeferredComposerInput("hello")

    expect(mockedUseDeferredValue).toHaveBeenCalledWith("hello")
    expect(result.liveInput).toBe("hello")
    expect(result.deferredInput).toBe("hello-deferred")
  })
})

