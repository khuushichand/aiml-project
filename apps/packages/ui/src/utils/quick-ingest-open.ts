export type QuickIngestPendingOpenMode = "normal" | "intro"

export type QuickIngestPendingOpenOptions = {
  autoProcessQueued?: boolean
  focusTrigger?: boolean
}

export type QuickIngestPendingOpenRequest = {
  mode: QuickIngestPendingOpenMode
  at: number
  detail?: unknown
  options?: QuickIngestPendingOpenOptions
}

type QuickIngestWindow = Window & {
  __tldwPendingQuickIngestOpen?: QuickIngestPendingOpenRequest
}

const getQuickIngestWindow = (): QuickIngestWindow | null => {
  if (typeof window === "undefined") {
    return null
  }
  return window as QuickIngestWindow
}

const buildPendingOpenRequest = (
  mode: QuickIngestPendingOpenMode,
  detail?: unknown,
  options?: QuickIngestPendingOpenOptions
): QuickIngestPendingOpenRequest => ({
  mode,
  at: Date.now(),
  detail,
  options,
})

const dispatchQuickIngestOpenEvent = (
  mode: QuickIngestPendingOpenMode,
  detail?: unknown
): void => {
  const scope = getQuickIngestWindow()
  if (!scope) return
  const eventName =
    mode === "intro"
      ? "tldw:open-quick-ingest-intro"
      : "tldw:open-quick-ingest"
  scope.dispatchEvent(new CustomEvent(eventName, { detail }))
}

export const rememberQuickIngestOpenRequest = (
  mode: QuickIngestPendingOpenMode,
  detail?: unknown,
  options?: QuickIngestPendingOpenOptions
): QuickIngestPendingOpenRequest | null => {
  const scope = getQuickIngestWindow()
  if (!scope) return null
  const request = buildPendingOpenRequest(mode, detail, options)
  scope.__tldwPendingQuickIngestOpen = request
  return request
}

export const requestQuickIngestOpen = (
  detail?: unknown,
  options?: QuickIngestPendingOpenOptions
): QuickIngestPendingOpenRequest | null => {
  const request = rememberQuickIngestOpenRequest("normal", detail, options)
  dispatchQuickIngestOpenEvent("normal", detail)
  return request
}

export const requestQuickIngestIntro = (
  detail?: unknown,
  options?: QuickIngestPendingOpenOptions
): QuickIngestPendingOpenRequest | null => {
  const request = rememberQuickIngestOpenRequest("intro", detail, options)
  dispatchQuickIngestOpenEvent("intro", detail)
  return request
}

export const consumePendingQuickIngestOpen = (): QuickIngestPendingOpenRequest | null => {
  const scope = getQuickIngestWindow()
  const request = scope?.__tldwPendingQuickIngestOpen || null
  if (scope) {
    delete scope.__tldwPendingQuickIngestOpen
  }
  return request
}
