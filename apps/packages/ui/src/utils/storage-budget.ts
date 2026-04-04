export const STORAGE_BUDGET_DEFAULT_MB = 5

const STORAGE_BUDGET_VITE_ENV = "VITE_WORKSPACE_STORAGE_PAYLOAD_BUDGET_MB"
const STORAGE_BUDGET_NEXT_ENV = "NEXT_PUBLIC_WORKSPACE_STORAGE_PAYLOAD_BUDGET_MB"

/** Estimate UTF-8 byte length of a string. */
export const estimateUtf8ByteLength = (str: string): number => {
  if (typeof TextEncoder !== "undefined") {
    return new TextEncoder().encode(str).length
  }
  return encodeURIComponent(str).replace(/%[A-F\d]{2}/g, "x").length
}

const parseStorageBudgetCandidateMb = (
  candidate: unknown
): number | null => {
  if (typeof candidate === "number" && Number.isFinite(candidate) && candidate > 0) {
    return candidate
  }
  if (typeof candidate !== "string") return null
  const parsed = Number(candidate.trim())
  if (!Number.isFinite(parsed) || parsed <= 0) return null
  return parsed
}

/** Estimate total localStorage bytes used by keys matching a prefix (default: all keys). */
export const estimateLocalStorageUsageBytes = (
  storage: Storage,
  prefix?: string
): number => {
  let totalBytes = 0
  for (let i = 0; i < storage.length; i++) {
    const key = storage.key(i)
    if (!key) continue
    if (prefix && !key.startsWith(prefix)) continue
    const value = storage.getItem(key)
    if (value == null) continue
    totalBytes += estimateUtf8ByteLength(key) + estimateUtf8ByteLength(value)
  }
  return totalBytes
}

/** Resolve the localStorage budget in bytes. Checks env vars, defaults to 5 MB. */
export const resolveStorageBudgetBytes = (): number => {
  const viteEnv = (import.meta as unknown as { env?: Record<string, unknown> }).env
  const viteBudgetMb = parseStorageBudgetCandidateMb(
    viteEnv?.[STORAGE_BUDGET_VITE_ENV]
  )
  if (viteBudgetMb != null) {
    return Math.round(viteBudgetMb * 1024 * 1024)
  }

  const nextProcess =
    typeof globalThis !== "undefined"
      ? (globalThis as { process?: { env?: Record<string, string | undefined> } })
          .process
      : undefined
  const nextBudgetMb = parseStorageBudgetCandidateMb(
    nextProcess?.env?.[STORAGE_BUDGET_NEXT_ENV]
  )
  if (nextBudgetMb != null) {
    return Math.round(nextBudgetMb * 1024 * 1024)
  }

  return STORAGE_BUDGET_DEFAULT_MB * 1024 * 1024
}
