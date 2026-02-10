import { describe, expect, it } from "vitest"

import {
  sanitizeMediaRichHtml,
  sanitizeMediaRichHtmlWithStats
} from "@/utils/media-rich-html-sanitizer"

describe("media-rich-html-sanitizer", () => {
  it("removes forbidden tags but keeps safe surrounding content", () => {
    const html =
      '<div><script>alert(1)</script><style>p{color:red}</style><p>Safe</p></div>'
    const sanitized = sanitizeMediaRichHtml(html)

    expect(sanitized.includes("<script")).toBe(false)
    expect(sanitized.includes("<style")).toBe(false)
    expect(sanitized.includes("<p>Safe</p>")).toBe(true)
  })

  it("removes event handlers and inline styles", () => {
    const html =
      '<a href="https://example.com" onclick="alert(1)" style="color:red">Link</a>'
    const sanitized = sanitizeMediaRichHtml(html)

    expect(sanitized.includes("onclick")).toBe(false)
    expect(sanitized.includes("style=")).toBe(false)
    expect(sanitized.includes('href="https://example.com"')).toBe(true)
  })

  it("allows only approved protocols and same-document anchors", () => {
    const html = `
      <div>
        <a href="https://example.com">ok</a>
        <a href="mailto:test@example.com">mail</a>
        <a href="tel:+123456789">tel</a>
        <a href="#section-1">anchor</a>
        <a href="javascript:alert(1)">bad-js</a>
        <a href="data:text/html;base64,abc">bad-data</a>
        <a href="file:///tmp/test">bad-file</a>
        <a href="/relative/path">bad-relative</a>
      </div>
    `

    const sanitized = sanitizeMediaRichHtml(html)
    expect(sanitized.includes('href="https://example.com"')).toBe(true)
    expect(sanitized.includes('href="mailto:test@example.com"')).toBe(true)
    expect(sanitized.includes('href="tel:+123456789"')).toBe(true)
    expect(sanitized.includes('href="#section-1"')).toBe(true)

    expect(sanitized.includes("javascript:")).toBe(false)
    expect(sanitized.includes("data:text/html")).toBe(false)
    expect(sanitized.includes("file:///tmp/test")).toBe(false)
    expect(sanitized.includes('href="/relative/path"')).toBe(false)
  })

  it("reports sanitization stats for removed nodes/attributes and blocked schemes", () => {
    const html = `
      <div>
        <script>alert(1)</script>
        <a href="javascript:alert(1)" onclick="alert(1)" style="color:red">unsafe</a>
      </div>
    `

    const result = sanitizeMediaRichHtmlWithStats(html)
    expect(result.html.includes("<script")).toBe(false)
    expect(result.removed_node_count).toBeGreaterThan(0)
    expect(result.removed_attribute_count).toBeGreaterThan(0)
    expect(result.blocked_url_schemes).toContain("javascript")
  })
})
