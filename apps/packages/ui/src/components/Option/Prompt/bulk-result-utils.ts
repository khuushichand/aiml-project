export const collectFailedIds = <T>(
  ids: string[],
  results: PromiseSettledResult<T>[]
): string[] => {
  const failedIds: string[] = []
  for (let index = 0; index < results.length; index += 1) {
    if (results[index]?.status === "rejected") {
      failedIds.push(ids[index]!)
    }
  }
  return failedIds
}

export type BulkCountSummary = {
  total: number
  succeeded: number
  failed: number
}

export const buildBulkCountSummary = (
  total: number,
  failedCount: number
): BulkCountSummary => {
  const safeTotal = Math.max(0, total)
  const safeFailed = Math.max(0, failedCount)
  return {
    total: safeTotal,
    succeeded: Math.max(0, safeTotal - safeFailed),
    failed: safeFailed
  }
}
