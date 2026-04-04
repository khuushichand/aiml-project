import { estimateLocalStorageUsageBytes, estimateUtf8ByteLength, resolveStorageBudgetBytes } from "./storage-budget"
import { STORAGE_QUOTA_REFRESH_EVENT } from "@/store/storage-quota-events"

const WORKSPACE_KEY_PREFIX = "tldw-workspace"
const EXCEEDED_THRESHOLD = 0.95

export type StorageGuardResult = {
  canWrite: boolean
  currentRatio: number
  wouldExceed: boolean
  recommendation: string | null
}

/**
 * Advisory pre-write check. Does NOT block writes — callers decide.
 * Dispatches a refresh event so the quota hook updates.
 */
export function checkStorageBeforeWrite(estimatedBytes: number): StorageGuardResult {
  try {
    const usedBytes = estimateLocalStorageUsageBytes(window.localStorage, WORKSPACE_KEY_PREFIX)
    const budgetBytes = resolveStorageBudgetBytes()
    const currentRatio = budgetBytes > 0 ? usedBytes / budgetBytes : 0
    const wouldExceed = (usedBytes + estimatedBytes) >= budgetBytes * EXCEEDED_THRESHOLD

    let recommendation: string | null = null
    if (wouldExceed) {
      recommendation = "Storage is nearly full. Consider archiving old workspaces before saving."
    } else if (currentRatio >= 0.80) {
      recommendation = "Storage is getting full. Consider cleaning up old data soon."
    }

    return {
      canWrite: !wouldExceed,
      currentRatio: Math.min(currentRatio, 1),
      wouldExceed,
      recommendation
    }
  } catch {
    // If we can't check, assume it's fine
    return { canWrite: true, currentRatio: 0, wouldExceed: false, recommendation: null }
  }
}

/**
 * Dispatch a refresh event to update any mounted StorageQuotaBanner.
 * Call this after a successful localStorage write.
 */
export function notifyStorageWrite(): void {
  try {
    window.dispatchEvent(new CustomEvent(STORAGE_QUOTA_REFRESH_EVENT))
  } catch { /* ignore */ }
}

export { estimateUtf8ByteLength }
