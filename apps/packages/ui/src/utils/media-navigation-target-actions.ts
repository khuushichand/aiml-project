import type { MediaNavigationTargetLike } from "@/utils/media-navigation-target"

export const MEDIA_NAVIGATION_TARGET_EVENT = "tldw:media-navigation:target"

export type MediaNavigationTargetEventDetail = {
  media_id: string | null
  target: MediaNavigationTargetLike
}

type ApplyMediaNavigationTargetOptions = {
  root?: ParentNode | null
  mediaId?: string | number | null
  smoothScroll?: boolean
}

const toFiniteNumber = (value: unknown): number | null => {
  if (typeof value !== "number" || !Number.isFinite(value)) return null
  return value
}

const normalizeAnchorId = (href: string | null): string | null => {
  const raw = String(href || "").trim()
  if (!raw || !raw.startsWith("#")) return null
  const encodedId = raw.slice(1).trim()
  if (!encodedId) return null
  try {
    return decodeURIComponent(encodedId)
  } catch {
    return encodedId
  }
}

const escapeForCssAttribute = (value: string): string => {
  return value.replace(/["\\]/g, "\\$&")
}

const querySelectorSafe = (
  scope: ParentNode | null,
  selector: string
): Element | null => {
  if (!scope || typeof (scope as Element).querySelector !== "function") return null
  try {
    return (scope as Element).querySelector(selector)
  } catch {
    return null
  }
}

const findAnchorElement = (
  scope: ParentNode | null,
  anchorId: string
): HTMLElement | null => {
  if (!scope || !anchorId) return null

  if (
    typeof (scope as Document).getElementById === "function" &&
    (scope as Document).getElementById(anchorId) instanceof HTMLElement
  ) {
    return (scope as Document).getElementById(anchorId) as HTMLElement
  }

  const escaped = escapeForCssAttribute(anchorId)
  const byQuery = querySelectorSafe(scope, `[id="${escaped}"], a[name="${escaped}"]`)
  if (byQuery instanceof HTMLElement) return byQuery
  return null
}

const findPageElement = (
  scope: ParentNode | null,
  pageNumber: number
): HTMLElement | null => {
  if (!scope || !Number.isFinite(pageNumber) || pageNumber < 1) return null
  const page = String(Math.trunc(pageNumber))
  const escaped = escapeForCssAttribute(page)
  const match = querySelectorSafe(
    scope,
    `[data-page-number="${escaped}"], #page-${escaped}, #page_${escaped}`
  )
  if (match instanceof HTMLElement) return match
  return null
}

const findMediaElement = (scope: ParentNode | null): HTMLMediaElement | null => {
  if (!scope) return null
  const match = querySelectorSafe(scope, "audio,video")
  if (match instanceof HTMLMediaElement) return match
  return null
}

const scrollElementIntoView = (
  node: HTMLElement,
  smoothScroll: boolean
): boolean => {
  if (typeof node.scrollIntoView !== "function") return false
  node.scrollIntoView({
    behavior: smoothScroll ? "smooth" : "auto",
    block: "start",
    inline: "nearest"
  })
  return true
}

const dispatchMediaNavigationTargetEvent = (
  detail: MediaNavigationTargetEventDetail
): boolean => {
  if (typeof window === "undefined" || typeof window.dispatchEvent !== "function") {
    return false
  }
  window.dispatchEvent(
    new CustomEvent<MediaNavigationTargetEventDetail>(
      MEDIA_NAVIGATION_TARGET_EVENT,
      { detail }
    )
  )
  return true
}

export const applyMediaNavigationTarget = (
  target: MediaNavigationTargetLike | null | undefined,
  options: ApplyMediaNavigationTargetOptions = {}
): boolean => {
  if (!target) return false

  const documentRoot =
    typeof document !== "undefined" ? (document as ParentNode) : null
  const root =
    options.root ??
    documentRoot
  const smoothScroll = options.smoothScroll !== false
  const mediaId =
    options.mediaId === null || options.mediaId === undefined
      ? null
      : String(options.mediaId)

  const eventDetail: MediaNavigationTargetEventDetail = {
    media_id: mediaId,
    target
  }

  if (target.target_type === "href") {
    const anchorId = normalizeAnchorId(target.target_href)
    if (!anchorId) return false

    const anchorNode =
      findAnchorElement(root, anchorId) || findAnchorElement(documentRoot, anchorId)
    const scrolled = anchorNode
      ? scrollElementIntoView(anchorNode, smoothScroll)
      : false
    const dispatched = dispatchMediaNavigationTargetEvent(eventDetail)
    return scrolled || dispatched
  }

  if (target.target_type === "page") {
    const pageNumber = toFiniteNumber(target.target_start)
    if (pageNumber == null || pageNumber < 1) return false

    const pageNode =
      findPageElement(root, pageNumber) || findPageElement(documentRoot, pageNumber)
    const scrolled = pageNode ? scrollElementIntoView(pageNode, smoothScroll) : false
    const dispatched = dispatchMediaNavigationTargetEvent(eventDetail)
    return scrolled || dispatched
  }

  if (target.target_type === "time_range") {
    const startSeconds = toFiniteNumber(target.target_start)
    if (startSeconds == null || startSeconds < 0) return false

    const mediaNode =
      findMediaElement(root) || findMediaElement(documentRoot)
    let sought = false
    if (mediaNode) {
      try {
        mediaNode.currentTime = startSeconds
        sought = true
      } catch {
        sought = false
      }
    }
    const dispatched = dispatchMediaNavigationTargetEvent(eventDetail)
    return sought || dispatched
  }

  if (target.target_type === "char_range") {
    return dispatchMediaNavigationTargetEvent(eventDetail)
  }

  return false
}
