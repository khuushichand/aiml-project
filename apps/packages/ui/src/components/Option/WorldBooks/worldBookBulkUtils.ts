export type BulkAddEntryInput = {
  keywords: string[]
  content: string
  sourceLine?: number
}

export type BulkAddProgress = {
  total: number
  completed: number
  succeeded: number
  failed: number
}

export type BulkAddFailure = {
  line: number
  keywords: string[]
  message: string
}

export type BulkAddResult = BulkAddProgress & {
  failures: BulkAddFailure[]
}

export const DEFAULT_BULK_ADD_CONCURRENCY = 5

const normalizeBulkAddError = (error: unknown): string => {
  if (typeof error === "object" && error && typeof (error as { message?: unknown }).message === "string") {
    const message = String((error as { message: string }).message).trim()
    if (message) return message
  }
  return "Unknown error"
}

export const runBulkAddEntries = async ({
  entries,
  addEntry,
  concurrency = DEFAULT_BULK_ADD_CONCURRENCY,
  onProgress
}: {
  entries: BulkAddEntryInput[]
  addEntry: (entry: { keywords: string[]; content: string }) => Promise<unknown>
  concurrency?: number
  onProgress?: (progress: BulkAddProgress) => void
}): Promise<BulkAddResult> => {
  const total = entries.length
  const progress: BulkAddProgress = {
    total,
    completed: 0,
    succeeded: 0,
    failed: 0
  }
  const failures: Array<BulkAddFailure & { index: number }> = []

  onProgress?.({ ...progress })
  if (total === 0) {
    return { ...progress, failures: [] }
  }

  const workerCount = Math.min(total, Math.max(1, Math.floor(concurrency)))
  let cursor = 0

  const runWorker = async () => {
    while (true) {
      const index = cursor
      cursor += 1
      if (index >= total) return

      const entry = entries[index]
      try {
        await addEntry({
          keywords: Array.isArray(entry?.keywords) ? entry.keywords : [],
          content: String(entry?.content || "")
        })
        progress.succeeded += 1
      } catch (error) {
        progress.failed += 1
        failures.push({
          index,
          line:
            typeof entry?.sourceLine === "number" && Number.isFinite(entry.sourceLine)
              ? entry.sourceLine
              : index + 1,
          keywords: Array.isArray(entry?.keywords) ? entry.keywords : [],
          message: normalizeBulkAddError(error)
        })
      } finally {
        progress.completed += 1
        onProgress?.({ ...progress })
      }
    }
  }

  await Promise.all(Array.from({ length: workerCount }, () => runWorker()))

  return {
    ...progress,
    failures: failures.sort((a, b) => a.index - b.index).map(({ index: _index, ...failure }) => failure)
  }
}
