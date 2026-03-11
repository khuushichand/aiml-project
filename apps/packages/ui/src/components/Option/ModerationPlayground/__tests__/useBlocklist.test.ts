import { describe, expect, it, vi, beforeEach } from "vitest"
import { renderHook, act } from "@testing-library/react"

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------
const getBlocklistMock = vi.fn()
const updateBlocklistMock = vi.fn()
const lintBlocklistMock = vi.fn()
const getManagedBlocklistMock = vi.fn()
const appendManagedBlocklistMock = vi.fn()
const deleteManagedBlocklistItemMock = vi.fn()

vi.mock("@/services/moderation", () => ({
  getBlocklist: (...args: unknown[]) => getBlocklistMock(...args),
  updateBlocklist: (...args: unknown[]) => updateBlocklistMock(...args),
  lintBlocklist: (...args: unknown[]) => lintBlocklistMock(...args),
  getManagedBlocklist: (...args: unknown[]) => getManagedBlocklistMock(...args),
  appendManagedBlocklist: (...args: unknown[]) => appendManagedBlocklistMock(...args),
  deleteManagedBlocklistItem: (...args: unknown[]) => deleteManagedBlocklistItemMock(...args)
}))

import { useBlocklist } from "../hooks/useBlocklist"

describe("useBlocklist", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("returns initial state", () => {
    const { result } = renderHook(() => useBlocklist())
    expect(result.current.rawText).toBe("")
    expect(result.current.rawLint).toBeNull()
    expect(result.current.managedItems).toEqual([])
    expect(result.current.managedVersion).toBe("")
    expect(result.current.managedLine).toBe("")
    expect(result.current.managedLint).toBeNull()
    expect(result.current.loading).toBe(false)
  })

  it("loadRaw fetches blocklist and joins lines", async () => {
    getBlocklistMock.mockResolvedValue(["line1", "line2", "line3"])

    const { result } = renderHook(() => useBlocklist())

    await act(async () => {
      await result.current.loadRaw()
    })

    expect(result.current.rawText).toBe("line1\nline2\nline3")
    expect(result.current.rawLint).toBeNull()
  })

  it("loadRaw handles null response", async () => {
    getBlocklistMock.mockResolvedValue(null)

    const { result } = renderHook(() => useBlocklist())

    await act(async () => {
      await result.current.loadRaw()
    })

    expect(result.current.rawText).toBe("")
  })

  it("saveRaw splits text and calls updateBlocklist", async () => {
    updateBlocklistMock.mockResolvedValue({ status: "ok", count: 2 })

    const { result } = renderHook(() => useBlocklist())

    act(() => {
      result.current.setRawText("rule1\nrule2  ")
    })

    await act(async () => {
      await result.current.saveRaw()
    })

    expect(updateBlocklistMock).toHaveBeenCalledWith(["rule1", "rule2"])
  })

  it("lintRaw calls lintBlocklist and stores result", async () => {
    const lintResult = { items: [], valid_count: 1, invalid_count: 0 }
    lintBlocklistMock.mockResolvedValue(lintResult)

    const { result } = renderHook(() => useBlocklist())

    act(() => {
      result.current.setRawText("test rule")
    })

    await act(async () => {
      await result.current.lintRaw()
    })

    expect(lintBlocklistMock).toHaveBeenCalledWith({ lines: ["test rule"] })
    expect(result.current.rawLint).toEqual(lintResult)
  })

  it("loadManaged fetches managed blocklist", async () => {
    getManagedBlocklistMock.mockResolvedValue({
      data: { version: "v1", items: [{ id: 1, line: "bad-word" }] },
      etag: "etag1"
    })

    const { result } = renderHook(() => useBlocklist())

    await act(async () => {
      await result.current.loadManaged()
    })

    expect(result.current.managedItems).toEqual([{ id: 1, line: "bad-word" }])
    expect(result.current.managedVersion).toBe("v1")
  })

  it("loadManaged falls back to etag for version", async () => {
    getManagedBlocklistMock.mockResolvedValue({
      data: { version: "", items: [] },
      etag: "etag-fallback"
    })

    const { result } = renderHook(() => useBlocklist())

    await act(async () => {
      await result.current.loadManaged()
    })

    expect(result.current.managedVersion).toBe("etag-fallback")
  })

  it("appendManaged throws if no version loaded", async () => {
    const { result } = renderHook(() => useBlocklist())

    act(() => {
      result.current.setManagedLine("new rule")
    })

    await expect(
      act(async () => {
        await result.current.appendManaged()
      })
    ).rejects.toThrow("Load the managed blocklist first")
  })

  it("appendManaged throws if line is empty", async () => {
    getManagedBlocklistMock.mockResolvedValue({
      data: { version: "v1", items: [] },
      etag: null
    })

    const { result } = renderHook(() => useBlocklist())

    await act(async () => {
      await result.current.loadManaged()
    })

    await expect(
      act(async () => {
        await result.current.appendManaged()
      })
    ).rejects.toThrow("Enter a line to append")
  })

  it("appendManaged calls API and reloads", async () => {
    appendManagedBlocklistMock.mockResolvedValue({ version: "v2", index: 1, count: 2 })
    getManagedBlocklistMock
      .mockResolvedValueOnce({
        data: { version: "v1", items: [{ id: 1, line: "old" }] },
        etag: null
      })
      .mockResolvedValueOnce({
        data: { version: "v2", items: [{ id: 1, line: "old" }, { id: 2, line: "new" }] },
        etag: null
      })

    const { result } = renderHook(() => useBlocklist())

    await act(async () => {
      await result.current.loadManaged()
    })

    act(() => {
      result.current.setManagedLine("new")
    })

    await act(async () => {
      await result.current.appendManaged()
    })

    expect(appendManagedBlocklistMock).toHaveBeenCalledWith("v1", "new")
    expect(result.current.managedLine).toBe("")
    expect(result.current.managedItems).toHaveLength(2)
    expect(result.current.managedVersion).toBe("v2")
  })

  it("deleteManaged calls API and reloads", async () => {
    deleteManagedBlocklistItemMock.mockResolvedValue({ version: "v2", count: 0 })
    getManagedBlocklistMock
      .mockResolvedValueOnce({
        data: { version: "v1", items: [{ id: 1, line: "bad" }] },
        etag: null
      })
      .mockResolvedValueOnce({
        data: { version: "v2", items: [] },
        etag: null
      })

    const { result } = renderHook(() => useBlocklist())

    await act(async () => {
      await result.current.loadManaged()
    })

    await act(async () => {
      await result.current.deleteManaged(1)
    })

    expect(deleteManagedBlocklistItemMock).toHaveBeenCalledWith("v1", 1)
    expect(result.current.managedItems).toEqual([])
  })

  it("lintManagedLine throws if line is empty", async () => {
    const { result } = renderHook(() => useBlocklist())

    await expect(
      act(async () => {
        await result.current.lintManagedLine()
      })
    ).rejects.toThrow("Enter a line to lint")
  })

  it("lintManagedLine calls lintBlocklist with single line", async () => {
    const lintResult = { items: [{ index: 0, line: "test", ok: true }], valid_count: 1, invalid_count: 0 }
    lintBlocklistMock.mockResolvedValue(lintResult)

    const { result } = renderHook(() => useBlocklist())

    act(() => {
      result.current.setManagedLine("test")
    })

    await act(async () => {
      await result.current.lintManagedLine()
    })

    expect(lintBlocklistMock).toHaveBeenCalledWith({ line: "test" })
    expect(result.current.managedLint).toEqual(lintResult)
  })
})
