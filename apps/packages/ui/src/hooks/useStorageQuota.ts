import { useState, useEffect, useCallback, useMemo } from "react"
import { estimateLocalStorageUsageBytes, resolveStorageBudgetBytes } from "@/utils/storage-budget"
import { STORAGE_QUOTA_REFRESH_EVENT } from "@/store/storage-quota-events"
import { WORKSPACE_STORAGE_QUOTA_EVENT } from "@/store/workspace-events"

export type StorageQuotaLevel = "ok" | "warning" | "exceeded"

export type StorageQuotaState = {
  usedBytes: number
  budgetBytes: number
  ratio: number
  level: StorageQuotaLevel
  availableBytes: number
  canWrite: (estimatedBytes: number) => boolean
  refresh: () => void
}

/** Workspace localStorage key prefix — the 5MB budget applies to these keys only. */
const WORKSPACE_KEY_PREFIX = "tldw-workspace"

const THRESHOLDS = {
  warning: 0.80,
  exceeded: 0.95
}

export const resolveLevel = (ratio: number): StorageQuotaLevel => {
  if (ratio >= THRESHOLDS.exceeded) return "exceeded"
  if (ratio >= THRESHOLDS.warning) return "warning"
  return "ok"
}

export function useStorageQuota(): StorageQuotaState {
  const budgetBytes = useMemo(() => resolveStorageBudgetBytes(), [])
  const [usedBytes, setUsedBytes] = useState(() => {
    try {
      return estimateLocalStorageUsageBytes(window.localStorage, WORKSPACE_KEY_PREFIX)
    } catch {
      return 0
    }
  })

  const refresh = useCallback(() => {
    try {
      setUsedBytes(estimateLocalStorageUsageBytes(window.localStorage, WORKSPACE_KEY_PREFIX))
    } catch { /* ignore */ }
  }, [])

  // Listen for storage events (cross-tab), quota refresh events, and workspace quota events
  useEffect(() => {
    const handleStorage = () => refresh()
    const handleRefresh = () => refresh()

    window.addEventListener("storage", handleStorage)
    window.addEventListener(STORAGE_QUOTA_REFRESH_EVENT, handleRefresh)
    window.addEventListener(WORKSPACE_STORAGE_QUOTA_EVENT, handleRefresh)

    return () => {
      window.removeEventListener("storage", handleStorage)
      window.removeEventListener(STORAGE_QUOTA_REFRESH_EVENT, handleRefresh)
      window.removeEventListener(WORKSPACE_STORAGE_QUOTA_EVENT, handleRefresh)
    }
  }, [refresh])

  const ratio = budgetBytes > 0 ? Math.min(usedBytes / budgetBytes, 1) : 0
  const level = resolveLevel(ratio)
  const availableBytes = Math.max(budgetBytes - usedBytes, 0)

  const canWrite = useCallback(
    (estimatedBytes: number) => usedBytes + estimatedBytes < budgetBytes * THRESHOLDS.exceeded,
    [usedBytes, budgetBytes]
  )

  return { usedBytes, budgetBytes, ratio, level, availableBytes, canWrite, refresh }
}
