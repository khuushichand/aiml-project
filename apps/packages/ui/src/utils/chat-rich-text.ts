import DOMPurify from "dompurify"
import { Marked } from "marked"
import markedKatexExtension from "./marked/katex"

import type { ChatRichTextMode } from "@/types/chat-settings"

export const CHAT_RICH_TEXT_MODE_VALUES: readonly ChatRichTextMode[] = [
  "safe_markdown",
  "st_compat"
] as const

const stCompatMarked = new Marked({
  gfm: true,
  breaks: true
})
stCompatMarked.use(markedKatexExtension({ throwOnError: false }))

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

const FORBID_ATTR = ["style", "srcset"]
const ALLOWED_PROTOCOLS = new Set(["http", "https", "mailto", "tel", "blob"])
const DATA_IMAGE_RE = /^data:image\/(png|jpeg|jpg|gif|webp|svg\+xml);base64,[a-z0-9+/=\s]+$/i
const FENCED_CODE_RE = /```[\s\S]*?```/g
const BLOCK_SPOILER_RE = /\[spoiler\]([\s\S]*?)\[\/spoiler\]/gi
const INLINE_SPOILER_RE = /\|\|([^|\n][\s\S]*?)\|\|/g

let hooksInstalled = false

const normalizeProtocol = (value: string): string | null => {
  const protocolMatch = value.match(/^([a-zA-Z][a-zA-Z0-9+.-]*):/)
  if (!protocolMatch) return null
  return String(protocolMatch[1] || "").toLowerCase()
}

const isExternalUrl = (value: string): boolean =>
  /^https?:\/\//i.test(value) || /^\/\/[^/]/.test(value)

const isAllowedUrlValue = (value: string, attrName: string): boolean => {
  const trimmed = String(value || "").trim()
  if (!trimmed) return true
  if (trimmed.startsWith("#")) return true
  if (/^(\/|\.\.?\/)/.test(trimmed)) return true
  if (trimmed.startsWith("//")) return false

  const protocol = normalizeProtocol(trimmed)
  if (!protocol) return false

  if (protocol === "data") {
    return attrName === "src" && DATA_IMAGE_RE.test(trimmed)
  }

  return ALLOWED_PROTOCOLS.has(protocol)
}

const installDomPurifyHooks = () => {
  if (hooksInstalled) return

  DOMPurify.addHook("uponSanitizeAttribute", (_node, data) => {
    const attrName = String(data.attrName || "").toLowerCase()
    if (!attrName) return

    if (attrName.startsWith("on")) {
      data.keepAttr = false
      return
    }

    if (attrName === "style" || attrName === "srcset") {
      data.keepAttr = false
      return
    }

    if ((attrName === "href" || attrName === "src") && !isAllowedUrlValue(String(data.attrValue || ""), attrName)) {
      data.keepAttr = false
      return
    }
  })

  hooksInstalled = true
}

const transformOutsideCodeBlocks = (
  input: string,
  transform: (value: string) => string
): string => {
  const text = String(input || "")
  let result = ""
  let lastIndex = 0

  for (const match of text.matchAll(FENCED_CODE_RE)) {
    const index = match.index ?? 0
    result += transform(text.slice(lastIndex, index))
    result += match[0]
    lastIndex = index + match[0].length
  }

  result += transform(text.slice(lastIndex))
  return result
}

const applySpoilerTransforms = (input: string): string => {
  const withBlockSpoilers = input.replace(
    BLOCK_SPOILER_RE,
    (_match, content: string) =>
      `<details class=\"st-spoiler\"><summary>Spoiler</summary>\n${content}\n</details>`
  )

  return withBlockSpoilers.replace(
    INLINE_SPOILER_RE,
    (_match, content: string) => `<span class=\"st-inline-spoiler\">${content}</span>`
  )
}

export const preprocessStCompatMarkdown = (markdown: string): string =>
  transformOutsideCodeBlocks(String(markdown || ""), applySpoilerTransforms)

export const normalizeChatRichTextMode = (
  value: unknown,
  fallback: ChatRichTextMode = "safe_markdown"
): ChatRichTextMode => {
  if (value === "safe_markdown" || value === "st_compat") {
    return value
  }
  return fallback
}

export const sanitizeChatRichHtml = (html: string): string => {
  installDomPurifyHooks()
  return DOMPurify.sanitize(String(html || ""), {
    FORBID_TAGS,
    FORBID_ATTR,
    ALLOW_UNKNOWN_PROTOCOLS: false,
    KEEP_CONTENT: true
  })
}

export const enforceChatRichHtmlImagePolicy = (
  html: string,
  allowExternalImages: boolean
): string => {
  const raw = String(html || "")
  if (typeof DOMParser === "undefined") return raw

  const doc = new DOMParser().parseFromString(raw, "text/html")

  for (const link of Array.from(doc.querySelectorAll("a"))) {
    const href = String(link.getAttribute("href") || "").trim()
    if (!href) continue
    if (isExternalUrl(href)) {
      link.setAttribute("target", "_blank")
      link.setAttribute("rel", "noopener noreferrer")
    }
  }

  for (const img of Array.from(doc.querySelectorAll("img"))) {
    const src = String(img.getAttribute("src") || "").trim()
    if (!src) {
      img.remove()
      continue
    }

    if (!allowExternalImages && isExternalUrl(src)) {
      const alt = String(img.getAttribute("alt") || "").trim()
      const wrapper = doc.createElement("span")
      wrapper.className = "st-external-image-blocked"
      wrapper.textContent = alt ? `Image: ${alt} (external image blocked)` : "External image blocked"

      const spacer = doc.createTextNode(" ")
      const openLink = doc.createElement("a")
      openLink.setAttribute("href", src)
      openLink.setAttribute("target", "_blank")
      openLink.setAttribute("rel", "noopener noreferrer")
      openLink.textContent = "Open"

      wrapper.appendChild(spacer)
      wrapper.appendChild(openLink)
      img.replaceWith(wrapper)
      continue
    }

    img.setAttribute("loading", "lazy")
    img.setAttribute("referrerpolicy", "no-referrer")
    img.classList.add("rounded-md", "border", "border-border")
  }

  return doc.body.innerHTML
}

export const renderStCompatMarkdownToHtml = (
  markdown: string,
  allowExternalImages: boolean
): string => {
  const preprocessed = preprocessStCompatMarkdown(String(markdown || ""))
  const rawRendered = stCompatMarked.parse(preprocessed)
  const renderedHtml =
    typeof rawRendered === "string" ? rawRendered : String(preprocessed)
  const safeHtml = sanitizeChatRichHtml(renderedHtml)
  return enforceChatRichHtmlImagePolicy(safeHtml, allowExternalImages)
}
