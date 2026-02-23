import { createWithEqualityFn } from "zustand/traditional"

const normalizeCount = (value: number) =>
  Number.isFinite(value) && value > 0 ? Math.floor(value) : 0

export type QuickIngestLastRunStatus =
  | "idle"
  | "success"
  | "error"
  | "cancelled"

export type QuickIngestLastRunSummary = {
  status: QuickIngestLastRunStatus
  attemptedAt: number | null
  completedAt: number | null
  totalCount: number
  successCount: number
  failedCount: number
  cancelledCount: number
  firstMediaId: string | null
  primarySourceLabel: string | null
  errorMessage: string | null
}

export const createInitialQuickIngestLastRunSummary =
  (): QuickIngestLastRunSummary => ({
    status: "idle",
    attemptedAt: null,
    completedAt: null,
    totalCount: 0,
    successCount: 0,
    failedCount: 0,
    cancelledCount: 0,
    firstMediaId: null,
    primarySourceLabel: null,
    errorMessage: null
  })

type QuickIngestStore = {
  /**
   * Number of items queued in Quick Ingest (used for UI badges).
   */
  queuedCount: number
  setQueuedCount: (count: number) => void
  clearQueued: () => void
  /**
   * Whether the most recent Quick Ingest processing attempt
   * failed due to a server or network error. Used to enrich
   * header/sidepanel tooltips and ARIA labels.
   */
  hadRecentFailure: boolean
  markFailure: () => void
  clearFailure: () => void
  /**
   * Summary of the most recent ingest run to support
   * onboarding next-step recommendations.
   */
  lastRunSummary: QuickIngestLastRunSummary
  recordRunSuccess: (payload: {
    totalCount: number
    successCount: number
    failedCount: number
    firstMediaId?: string | number | null
    primarySourceLabel?: string | null
  }) => void
  recordRunFailure: (payload?: {
    totalCount?: number
    failedCount?: number
    errorMessage?: string | null
  }) => void
  recordRunCancelled: (payload?: {
    totalCount?: number
    successCount?: number
    failedCount?: number
    cancelledCount?: number
    errorMessage?: string | null
  }) => void
  resetLastRunSummary: () => void
}

export const useQuickIngestStore = createWithEqualityFn<QuickIngestStore>((set) => ({
  queuedCount: 0,
  hadRecentFailure: false,
  lastRunSummary: createInitialQuickIngestLastRunSummary(),
  setQueuedCount: (count) =>
    set({
      queuedCount: count > 0 ? count : 0
    }),
  clearQueued: () =>
    set({
      queuedCount: 0
    }),
  markFailure: () =>
    set({
      hadRecentFailure: true
    }),
  clearFailure: () =>
    set({
      hadRecentFailure: false
    }),
  recordRunSuccess: ({
    totalCount,
    successCount,
    failedCount,
    firstMediaId,
    primarySourceLabel
  }) => {
    const now = Date.now()
    const nextTotal = normalizeCount(totalCount)
    const nextSuccess = normalizeCount(successCount)
    const nextFailed = normalizeCount(failedCount)
    set({
      lastRunSummary: {
        status: "success",
        attemptedAt: now,
        completedAt: now,
        totalCount: nextTotal,
        successCount: nextSuccess,
        failedCount: nextFailed,
        cancelledCount: 0,
        firstMediaId:
          firstMediaId === null || typeof firstMediaId === "undefined"
            ? null
            : String(firstMediaId),
        primarySourceLabel:
          typeof primarySourceLabel === "string" && primarySourceLabel.trim()
            ? primarySourceLabel.trim()
            : null,
        errorMessage: null
      }
    })
  },
  recordRunFailure: (payload) => {
    const now = Date.now()
    const totalCount = normalizeCount(payload?.totalCount ?? 0)
    const failedCount = normalizeCount(
      payload?.failedCount ?? (totalCount > 0 ? totalCount : 1)
    )
    set({
      lastRunSummary: {
        status: "error",
        attemptedAt: now,
        completedAt: now,
        totalCount,
        successCount: 0,
        failedCount,
        cancelledCount: 0,
        firstMediaId: null,
        primarySourceLabel: null,
        errorMessage: payload?.errorMessage?.trim() || null
      }
    })
  },
  recordRunCancelled: (payload) => {
    const now = Date.now()
    const totalCount = normalizeCount(payload?.totalCount ?? 0)
    const successCount = normalizeCount(payload?.successCount ?? 0)
    const failedCount = normalizeCount(payload?.failedCount ?? 0)
    const cancelledCount = normalizeCount(
      payload?.cancelledCount ??
        Math.max(totalCount - successCount - failedCount, 1)
    )
    set({
      lastRunSummary: {
        status: "cancelled",
        attemptedAt: now,
        completedAt: now,
        totalCount,
        successCount,
        failedCount,
        cancelledCount,
        firstMediaId: null,
        primarySourceLabel: null,
        errorMessage: payload?.errorMessage?.trim() || null
      }
    })
  },
  resetLastRunSummary: () =>
    set({
      lastRunSummary: createInitialQuickIngestLastRunSummary()
    })
}))

if (typeof window !== "undefined") {
  // Expose for Playwright tests and debugging only.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(window as any).__tldw_useQuickIngestStore = useQuickIngestStore
}
