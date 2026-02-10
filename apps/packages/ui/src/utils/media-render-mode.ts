import type { MediaNavigationFormat } from "@/utils/media-navigation-scope"

type ResolveMediaRenderModeInput = {
  requestedMode: MediaNavigationFormat
  resolvedContentFormat?: MediaNavigationFormat | null
  allowRichRendering?: boolean
}

const MARKDOWN_FALLBACK: MediaNavigationFormat = "markdown"

const normalizeRichAvailability = (
  mode: MediaNavigationFormat,
  allowRichRendering: boolean
): MediaNavigationFormat =>
  mode === "html" && !allowRichRendering ? MARKDOWN_FALLBACK : mode

export const resolveMediaRenderMode = ({
  requestedMode,
  resolvedContentFormat,
  allowRichRendering = true
}: ResolveMediaRenderModeInput): MediaNavigationFormat => {
  if (requestedMode !== "auto") {
    return normalizeRichAvailability(requestedMode, allowRichRendering)
  }

  if (resolvedContentFormat && resolvedContentFormat !== "auto") {
    return normalizeRichAvailability(resolvedContentFormat, allowRichRendering)
  }

  return MARKDOWN_FALLBACK
}

export const normalizeRequestedMediaRenderMode = (
  requestedMode: MediaNavigationFormat,
  allowRichRendering: boolean
): MediaNavigationFormat =>
  requestedMode === "html" && !allowRichRendering ? "auto" : requestedMode

