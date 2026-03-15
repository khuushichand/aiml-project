import type { CompanionActivityCreate } from "@/services/companion"

export const COMPANION_PENDING_CAPTURE_STORAGE_KEY =
  "tldw:companion:pendingCapture"
export const COMPANION_PENDING_CAPTURE_EVENT = "tldw:companion-pending-capture"
export const COMPANION_CAPTURE_MESSAGE_TYPE = "save-to-companion"

export type PendingCompanionCapture = {
  id: string
  selectionText: string
  pageUrl?: string
  pageTitle?: string
  action?: string
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

export const normalizePendingCompanionCapture = (
  raw: unknown
): PendingCompanionCapture | null => {
  if (!isRecord(raw)) return null
  const id = String(raw.id || raw.captureId || "").trim()
  const selectionText = String(raw.selectionText || raw.text || "").trim()
  if (!id || !selectionText) return null

  const pageUrl = String(raw.pageUrl || "").trim()
  const pageTitle = String(raw.pageTitle || "").trim()
  const action = String(raw.action || "").trim()

  return {
    id,
    selectionText,
    pageUrl: pageUrl || undefined,
    pageTitle: pageTitle || undefined,
    action: action || undefined
  }
}

export const readPendingCompanionCapture = (): PendingCompanionCapture | null => {
  if (typeof window === "undefined") return null
  try {
    const raw = window.sessionStorage.getItem(COMPANION_PENDING_CAPTURE_STORAGE_KEY)
    if (!raw) return null
    return normalizePendingCompanionCapture(JSON.parse(raw))
  } catch {
    return null
  }
}

export const writePendingCompanionCapture = (
  capture: PendingCompanionCapture
): void => {
  if (typeof window === "undefined") return
  try {
    window.sessionStorage.setItem(
      COMPANION_PENDING_CAPTURE_STORAGE_KEY,
      JSON.stringify(capture)
    )
  } catch {
    // ignore storage failures
  }
  try {
    window.dispatchEvent(
      new CustomEvent<PendingCompanionCapture>(COMPANION_PENDING_CAPTURE_EVENT, {
        detail: capture
      })
    )
  } catch {
    // ignore event dispatch failures
  }
}

export const clearPendingCompanionCapture = (captureId?: string): void => {
  if (typeof window === "undefined") return
  if (captureId) {
    const current = readPendingCompanionCapture()
    if (current && current.id !== captureId) {
      return
    }
  }
  try {
    window.sessionStorage.removeItem(COMPANION_PENDING_CAPTURE_STORAGE_KEY)
  } catch {
    // ignore storage failures
  }
}

export const buildExplicitCompanionCapture = (
  capture: PendingCompanionCapture
): CompanionActivityCreate => ({
  event_type: "extension.selection_saved",
  source_type: "browser_selection",
  source_id: capture.id,
  surface: "extension.sidepanel",
  dedupe_key: `extension.selection_saved:${capture.id}`,
  tags: ["extension", "selection"],
  provenance: {
    capture_mode: "explicit",
    route: "extension.context_menu",
    action: capture.action || "save_selection"
  },
  metadata: {
    selection: capture.selectionText,
    page_url: capture.pageUrl,
    page_title: capture.pageTitle
  }
})
