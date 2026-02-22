import DOMPurify from "dompurify"

const FORBID_TAGS = [
  "script",
  "style",
  "iframe",
  "object",
  "embed",
  "link",
  "meta",
  "base",
  "form",
  "input",
  "button",
  "textarea",
  "select"
]

const FORBID_ATTR = ["style"]

const ALLOWED_PROTOCOLS = new Set(["http", "https", "mailto", "tel"])

type DomPurifyRemovedEntry = {
  element?: unknown
  attribute?: unknown
}

export type MediaRichSanitizationResult = {
  html: string
  removed_node_count: number
  removed_attribute_count: number
  blocked_url_schemes: string[]
}

const isAllowedUrlValue = (value: string): boolean => {
  const trimmed = String(value || "").trim()
  if (!trimmed) return true
  if (trimmed.startsWith("#")) return true
  if (trimmed.startsWith("//")) return false

  const protocolMatch = trimmed.match(/^([a-zA-Z][a-zA-Z0-9+.-]*):/)
  if (!protocolMatch) {
    // Only same-document anchors are allowed without protocol.
    return false
  }

  const protocol = String(protocolMatch[1] || "").toLowerCase()
  return ALLOWED_PROTOCOLS.has(protocol)
}

const classifyBlockedUrlScheme = (value: string): string | null => {
  const trimmed = String(value || "").trim()
  if (!trimmed) return null
  if (trimmed.startsWith("#")) return null
  if (trimmed.startsWith("//")) return "protocol-relative"

  const protocolMatch = trimmed.match(/^([a-zA-Z][a-zA-Z0-9+.-]*):/)
  if (!protocolMatch) return "relative"
  const protocol = String(protocolMatch[1] || "").toLowerCase()
  if (ALLOWED_PROTOCOLS.has(protocol)) return null
  return protocol
}

let hooksInstalled = false
let blockedUrlCollector: string[] | null = null

const installDomPurifyHooks = () => {
  if (hooksInstalled) return

  DOMPurify.addHook("uponSanitizeAttribute", (_node, data) => {
    const attrName = String(data.attrName || "").toLowerCase()
    if (!attrName) return

    if (attrName.startsWith("on")) {
      data.keepAttr = false
      return
    }

    if (attrName === "style") {
      data.keepAttr = false
      return
    }

    if (
      (attrName === "href" || attrName === "src") &&
      !isAllowedUrlValue(String(data.attrValue || ""))
    ) {
      const blockedScheme = classifyBlockedUrlScheme(String(data.attrValue || ""))
      if (blockedScheme && blockedUrlCollector) {
        blockedUrlCollector.push(blockedScheme)
      }
      data.keepAttr = false
    }
  })

  hooksInstalled = true
}

const countRemovedEntries = (): {
  removedNodeCount: number
  removedAttributeCount: number
} => {
  const removed = (DOMPurify as unknown as { removed?: DomPurifyRemovedEntry[] })
    .removed
  if (!Array.isArray(removed)) {
    return {
      removedNodeCount: 0,
      removedAttributeCount: 0
    }
  }

  let removedNodeCount = 0
  let removedAttributeCount = 0
  for (const entry of removed) {
    if (entry && typeof entry === "object") {
      if ("element" in entry && entry.element) removedNodeCount += 1
      if ("attribute" in entry && entry.attribute) removedAttributeCount += 1
    }
  }

  return {
    removedNodeCount,
    removedAttributeCount
  }
}

export const sanitizeMediaRichHtmlWithStats = (
  html: string
): MediaRichSanitizationResult => {
  installDomPurifyHooks()
  blockedUrlCollector = []
  try {
    const sanitizedHtml = DOMPurify.sanitize(String(html || ""), {
      FORBID_TAGS,
      FORBID_ATTR,
      ALLOW_UNKNOWN_PROTOCOLS: false,
      KEEP_CONTENT: true
    })
    const removedCounts = countRemovedEntries()
    const blockedSchemes = blockedUrlCollector || []

    return {
      html: sanitizedHtml,
      removed_node_count: removedCounts.removedNodeCount,
      removed_attribute_count: removedCounts.removedAttributeCount,
      blocked_url_schemes: [...blockedSchemes]
    }
  } finally {
    blockedUrlCollector = null
  }
}

export const sanitizeMediaRichHtml = (html: string): string => {
  const result = sanitizeMediaRichHtmlWithStats(html)
  return result.html
}

export const MEDIA_RICH_HTML_SANITIZER_CONFIG = {
  FORBID_TAGS,
  FORBID_ATTR
} as const
