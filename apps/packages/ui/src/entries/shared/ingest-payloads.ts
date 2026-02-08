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

const normalizeHttpUrl = (value: unknown): string | null => {
  const url = typeof value === "string" ? value.trim() : ""
  if (!url) return null
  if (!/^https?:/i.test(url)) return null
  return url
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

