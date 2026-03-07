import { describe, it, expect, vi, beforeEach } from "vitest"

// ── Hoisted mock state (must be declared via vi.hoisted for vi.mock factory) ─

const { rows, mockTable, uuidState } = vi.hoisted(() => {
  const rows = new Map<string, any>()

  const mockTable = {
    put: vi.fn(async (row: any) => {
      rows.set(row.id, row)
      return row.id
    }),
    get: vi.fn(async (id: string) => rows.get(id)),
    delete: vi.fn(async (id: string) => {
      rows.delete(id)
    }),
    bulkDelete: vi.fn(async (ids: string[]) => {
      for (const id of ids) rows.delete(id)
    }),
    orderBy: vi.fn((field: string) => ({
      reverse: vi.fn(() => ({
        toArray: vi.fn(async () => {
          const all = Array.from(rows.values())
          all.sort((a, b) => b[field] - a[field])
          return all
        })
      })),
      toArray: vi.fn(async () => {
        const all = Array.from(rows.values())
        all.sort((a, b) => a[field] - b[field])
        return all
      })
    })),
    count: vi.fn(async () => rows.size)
  }

  const uuidState = { counter: 0 }

  return { rows, mockTable, uuidState }
})

// ── Mock the Dexie db singleton ──────────────────────────────────────────────

vi.mock("@/db/dexie/schema", () => ({
  db: {
    sttRecordings: mockTable
  }
}))

// Stable UUID counter for deterministic tests
vi.stubGlobal("crypto", {
  ...globalThis.crypto,
  randomUUID: () => `uuid-${++uuidState.counter}`
})

// ── Import the module under test (after mocks) ──────────────────────────────

import {
  saveSttRecording,
  getSttRecording,
  deleteSttRecording,
  listSttRecordings,
  STT_RECORDING_CAP
} from "../stt-recordings"

// ── Helpers ──────────────────────────────────────────────────────────────────

function fakeBlob(size = 1024): Blob {
  return new Blob([new Uint8Array(size)], { type: "audio/webm" })
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("stt-recordings", () => {
  beforeEach(() => {
    rows.clear()
    uuidState.counter = 0
    vi.clearAllMocks()
  })

  // ── save + retrieve ──────────────────────────────────────────────────────

  it("saves a recording and retrieves it by id", async () => {
    const blob = fakeBlob()
    const id = await saveSttRecording({
      blob,
      durationMs: 5000,
      mimeType: "audio/webm"
    })

    expect(id).toBe("uuid-1")
    expect(mockTable.put).toHaveBeenCalledTimes(1)

    const recording = await getSttRecording(id)
    expect(recording).toBeDefined()
    expect(recording!.blob).toBe(blob)
    expect(recording!.mimeType).toBe("audio/webm")
    expect(recording!.durationMs).toBe(5000)
    expect(typeof recording!.createdAt).toBe("number")
  })

  it("returns undefined for a non-existent id", async () => {
    const result = await getSttRecording("does-not-exist")
    expect(result).toBeUndefined()
  })

  // ── list ordering ────────────────────────────────────────────────────────

  it("lists recordings sorted by createdAt descending", async () => {
    const now = Date.now()

    rows.set("a", { id: "a", blob: fakeBlob(), mimeType: "audio/webm", durationMs: 100, createdAt: now - 2000 })
    rows.set("b", { id: "b", blob: fakeBlob(), mimeType: "audio/webm", durationMs: 200, createdAt: now - 1000 })
    rows.set("c", { id: "c", blob: fakeBlob(), mimeType: "audio/webm", durationMs: 300, createdAt: now })

    const list = await listSttRecordings()
    expect(list).toHaveLength(3)
    // Most recent first
    expect(list[0].id).toBe("c")
    expect(list[1].id).toBe("b")
    expect(list[2].id).toBe("a")
  })

  // ── delete ───────────────────────────────────────────────────────────────

  it("deletes a recording by id", async () => {
    rows.set("x", { id: "x", blob: fakeBlob(), mimeType: "audio/webm", durationMs: 100, createdAt: Date.now() })

    await deleteSttRecording("x")
    expect(mockTable.delete).toHaveBeenCalledWith("x")
    expect(rows.has("x")).toBe(false)
  })

  // ── eviction at cap ──────────────────────────────────────────────────────

  it("evicts oldest recordings when cap is exceeded", async () => {
    const now = Date.now()
    for (let i = 1; i <= STT_RECORDING_CAP; i++) {
      rows.set(`old-${i}`, {
        id: `old-${i}`,
        blob: fakeBlob(),
        mimeType: "audio/webm",
        durationMs: 100,
        createdAt: now - (STT_RECORDING_CAP - i + 1) * 1000
      })
    }
    expect(rows.size).toBe(STT_RECORDING_CAP)

    // Save one more — should evict the oldest
    const id = await saveSttRecording({
      blob: fakeBlob(),
      durationMs: 999,
      mimeType: "audio/webm"
    })

    expect(id).toBeDefined()
    // The oldest entry (old-1) should have been evicted
    expect(mockTable.bulkDelete).toHaveBeenCalled()
    const deletedIds: string[] = mockTable.bulkDelete.mock.calls[0][0]
    expect(deletedIds).toContain("old-1")
  })

  it("does not evict when under the cap", async () => {
    await saveSttRecording({ blob: fakeBlob(), durationMs: 100, mimeType: "audio/webm" })
    expect(mockTable.bulkDelete).not.toHaveBeenCalled()
  })

  // ── cap constant ─────────────────────────────────────────────────────────

  it("exports STT_RECORDING_CAP as 20", () => {
    expect(STT_RECORDING_CAP).toBe(20)
  })
})
