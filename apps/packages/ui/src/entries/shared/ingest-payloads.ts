import type { AllowedPath } from "@/services/tldw/openapi-guard"
import {
  getProcessPathForUrl,
  inferUploadMediaTypeFromUrl
} from "@/services/tldw/media-routing"

type ContextMenuInfoLike = {
  pageUrl?: string | null
  linkUrl?: string | null
}

type ContextMenuTabLike = {
  url?: string | null
} | null | undefined

const TRACKING_QUERY_KEYS = new Set([
  "fbclid",
  "gclid",
  "si",
  "utm_campaign",
  "utm_content",
  "utm_id",
  "utm_medium",
  "utm_source",
  "utm_term"
])

const normalizeHttpUrl = (value: unknown): string | null => {
  const url = typeof value === "string" ? value.trim() : ""
  if (!url) return null
  if (!/^https?:/i.test(url)) return null
  return url
}

const isSubdomainOf = (host: string, domain: string): boolean =>
  host === domain || host.endsWith(`.${domain}`)

const isYouTubeHost = (host: string): boolean =>
  isSubdomainOf(host, "youtube.com") ||
  isSubdomainOf(host, "youtube-nocookie.com") ||
  isSubdomainOf(host, "youtu.be")

const parseLooseDurationSeconds = (raw: string): number | null => {
  const value = String(raw || "").trim().toLowerCase()
  if (!value) return null
  if (/^\d+$/.test(value)) {
    const numeric = Number(value)
    return Number.isFinite(numeric) && numeric >= 0 ? Math.trunc(numeric) : null
  }
  const match = value.match(
    /^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/
  )
  if (!match) return null
  const hours = Number(match[1] || 0)
  const minutes = Number(match[2] || 0)
  const seconds = Number(match[3] || 0)
  const total = hours * 3600 + minutes * 60 + seconds
  return Number.isFinite(total) && total >= 0 ? Math.trunc(total) : null
}

const extractYouTubeVideoId = (parsed: URL): string | null => {
  const host = parsed.hostname.toLowerCase()
  const path = parsed.pathname
  if (isSubdomainOf(host, "youtu.be")) {
    const id = path.split("/").filter(Boolean)[0] || ""
    return id || null
  }
  if (
    !isSubdomainOf(host, "youtube.com") &&
    !isSubdomainOf(host, "youtube-nocookie.com")
  ) {
    return null
  }
  const watchId = parsed.searchParams.get("v")
  if (watchId) return watchId
  const prefixMatches = [
    "/shorts/",
    "/live/",
    "/embed/",
    "/v/",
    "/clip/"
  ]
  for (const prefix of prefixMatches) {
    if (path.startsWith(prefix)) {
      const id = path.slice(prefix.length).split("/")[0]
      return id || null
    }
  }
  return null
}

export const extractYouTubeTimestampSeconds = (
  rawUrl: string
): number | null => {
  try {
    const parsed = new URL(rawUrl)
    if (!isYouTubeHost(parsed.hostname.toLowerCase())) return null
    const direct =
      parsed.searchParams.get("t") ||
      parsed.searchParams.get("start") ||
      parsed.searchParams.get("time_continue")
    if (direct) {
      const seconds = parseLooseDurationSeconds(direct)
      if (seconds != null) return seconds
    }
    const hash = String(parsed.hash || "").replace(/^#/, "")
    if (!hash) return null
    const asParams = new URLSearchParams(hash)
    const hashDirect =
      asParams.get("t") ||
      asParams.get("start") ||
      asParams.get("time_continue")
    if (hashDirect) {
      const seconds = parseLooseDurationSeconds(hashDirect)
      if (seconds != null) return seconds
    }
    return parseLooseDurationSeconds(hash)
  } catch {
    return null
  }
}

export const normalizeUrlForDedupe = (rawUrl: string): string => {
  const source = String(rawUrl || "").trim()
  if (!source) return source
  try {
    const parsed = new URL(source)
    const host = parsed.hostname.toLowerCase()
    if (isYouTubeHost(host)) {
      const videoId = extractYouTubeVideoId(parsed)
      if (videoId) {
        return `https://www.youtube.com/watch?v=${encodeURIComponent(videoId)}`
      }
    }
    parsed.hash = ""
    for (const key of Array.from(parsed.searchParams.keys())) {
      if (TRACKING_QUERY_KEYS.has(key.toLowerCase())) {
        parsed.searchParams.delete(key)
      }
    }
    if (parsed.pathname.length > 1 && parsed.pathname.endsWith("/")) {
      parsed.pathname = parsed.pathname.slice(0, -1)
    }
    parsed.hostname = host
    return parsed.toString()
  } catch {
    return source
  }
}

export const resolveContextMenuTargetUrl = (
  info: ContextMenuInfoLike,
  tab?: ContextMenuTabLike
): string | null =>
  normalizeHttpUrl(info?.linkUrl) ||
  normalizeHttpUrl(info?.pageUrl) ||
  normalizeHttpUrl(tab?.url) ||
  null

export type ContextMenuAddPayload = {
  path: "/api/v1/media/add"
  method: "POST"
  fields: {
    media_type: string
    urls: string[]
  }
}

export const buildContextMenuAddPayload = (
  targetUrl: string
): ContextMenuAddPayload => ({
  path: "/api/v1/media/add",
  method: "POST",
  fields: {
    media_type: inferUploadMediaTypeFromUrl(targetUrl),
    urls: [targetUrl]
  }
})

export type ContextMenuProcessPayload = {
  path: AllowedPath
  method: "POST"
  headers: { "Content-Type": "application/json" }
  body: { url: string }
}

export const buildContextMenuProcessPayload = (
  targetUrl: string
): ContextMenuProcessPayload => ({
  path: getProcessPathForUrl(targetUrl),
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: { url: targetUrl }
})
