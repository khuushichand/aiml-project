import { beforeEach, describe, expect, it, vi } from "vitest"

const { mockTables, nextIdState, createTable } = vi.hoisted(() => {
  const mockTables = {
    pendingAnnotationQueue: [] as any[],
    quizHistory: [] as any[]
  }
  const nextIdState = { value: 1 }

  const createCollection = (rows: any[], sourceRows: any[]) => {
    const collection = {
      reverse: vi.fn(() => collection),
      sortBy: vi.fn(async (field: string) =>
        [...rows].sort((a, b) => {
          const aValue = a[field] ?? 0
          const bValue = b[field] ?? 0
          return aValue - bValue
        })
      ),
      delete: vi.fn(async () => {
        for (const row of rows) {
          const index = sourceRows.findIndex((candidate) => candidate.id === row.id)
          if (index !== -1) {
            sourceRows.splice(index, 1)
          }
        }
      })
    }

    return collection
  }

  const createTable = (rows: any[]) => ({
    add: vi.fn(async (entry: any) => {
      const id = nextIdState.value++
      rows.push({ ...entry, id })
      return id
    }),
    update: vi.fn(async (id: number, patch: Record<string, unknown>) => {
      const row = rows.find((entry) => entry.id === id)
      if (row) {
        Object.assign(row, patch)
      }
    }),
    get: vi.fn(async (id: number) => rows.find((entry) => entry.id === id)),
    delete: vi.fn(async (id: number) => {
      const index = rows.findIndex((entry) => entry.id === id)
      if (index !== -1) {
        rows.splice(index, 1)
      }
    }),
    count: vi.fn(async () => rows.length),
    where: vi.fn((field: string) => ({
      equals: vi.fn((value: unknown) => {
        const filteredRows = rows.filter((entry) => entry[field] === value)
        return createCollection(filteredRows, rows)
      })
    }))
  })

  return { mockTables, nextIdState, createTable }
})

vi.mock("dexie", () => {
  class Dexie {
    constructor(_name: string) {}

    version() {
      return {
        stores: (schema: Record<string, string>) => {
          for (const tableName of Object.keys(schema)) {
            ;(this as Record<string, unknown>)[tableName] =
              createTable(mockTables[tableName as keyof typeof mockTables])
          }

          return this
        }
      }
    }
  }

  return { default: Dexie }
})

import { getQuizHistory, saveQuizToHistory } from "../offlineQueue"

describe("offlineQueue", () => {
  beforeEach(() => {
    mockTables.pendingAnnotationQueue.length = 0
    mockTables.quizHistory.length = 0
    nextIdState.value = 1
    vi.clearAllMocks()
  })

  it("returns quiz history in createdAt descending order for a document", async () => {
    await saveQuizToHistory({
      documentId: 7,
      quiz: {
        quizId: "oldest",
        mediaId: 100,
        generatedAt: "2026-03-11T18:00:00.000Z",
        questions: []
      },
      answers: {},
      createdAt: 1_000
    })
    await saveQuizToHistory({
      documentId: 7,
      quiz: {
        quizId: "newest",
        mediaId: 100,
        generatedAt: "2026-03-11T18:05:00.000Z",
        questions: []
      },
      answers: {},
      createdAt: 3_000
    })
    await saveQuizToHistory({
      documentId: 7,
      quiz: {
        quizId: "middle",
        mediaId: 100,
        generatedAt: "2026-03-11T18:03:00.000Z",
        questions: []
      },
      answers: {},
      createdAt: 2_000
    })
    await saveQuizToHistory({
      documentId: 99,
      quiz: {
        quizId: "other-document",
        mediaId: 200,
        generatedAt: "2026-03-11T18:10:00.000Z",
        questions: []
      },
      answers: {},
      createdAt: 4_000
    })

    const history = await getQuizHistory(7)

    expect(history.map((entry) => entry.quiz.quizId)).toEqual([
      "newest",
      "middle",
      "oldest"
    ])
  })
})
