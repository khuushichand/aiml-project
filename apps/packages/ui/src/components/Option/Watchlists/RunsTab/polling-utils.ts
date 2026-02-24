type RunLike = {
  status?: unknown
} | null | undefined

const normalizeStatus = (status: unknown): string =>
  String(status ?? "")
    .trim()
    .toLowerCase()

export const hasActiveWatchlistRuns = (runs: readonly RunLike[]): boolean =>
  runs.some((run) => {
    const status = normalizeStatus(run?.status)
    return status === "running" || status === "pending"
  })
