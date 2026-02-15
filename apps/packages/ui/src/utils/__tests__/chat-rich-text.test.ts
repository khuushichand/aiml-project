import {
  enforceChatRichHtmlImagePolicy,
  normalizeChatRichTextMode,
  preprocessStCompatMarkdown,
  renderStCompatMarkdownToHtml,
  sanitizeChatRichHtml
} from "@/utils/chat-rich-text"
import { describe, expect, it } from "vitest"

describe("chat rich text utilities", () => {
  it("preprocesses spoiler syntax while preserving fenced code blocks", () => {
    const input = [
      "Hello ||secret||",
      "```txt",
      "literal ||keep-me||",
      "```",
      "[spoiler]block spoiler[/spoiler]"
    ].join("\n")

    const output = preprocessStCompatMarkdown(input)

    expect(output).toContain('<span class="st-inline-spoiler">secret</span>')
    expect(output).toContain("literal ||keep-me||")
    expect(output).toContain(
      '<details class="st-spoiler"><summary>Spoiler</summary>\nblock spoiler\n</details>'
    )
  })

  it("sanitizes unsafe tags, attributes, and URL schemes", () => {
    const dirty =
      '<p onclick="alert(1)">safe</p><a href="javascript:alert(1)">bad</a><script>alert(1)</script>'

    const clean = sanitizeChatRichHtml(dirty)

    expect(clean).toContain("<p>safe</p>")
    expect(clean).not.toContain("onclick")
    expect(clean).not.toContain("javascript:")
    expect(clean).not.toContain("<script")
  })

  it("blocks external images when the policy disallows them", () => {
    const html =
      '<p><img src="https://example.com/remote.png" alt="remote" /><img src="data:image/png;base64,AAAA" alt="inline" /></p>'

    const blocked = enforceChatRichHtmlImagePolicy(html, false)

    expect(blocked).toContain("external image blocked")
    expect(blocked).toContain('href="https://example.com/remote.png"')
    expect(blocked).toContain('src="data:image/png;base64,AAAA"')
  })

  it("renders st_compat markdown with sanitization and image policy", () => {
    const markdown = [
      "Hello",
      "world",
      "",
      "||spoiler||",
      "",
      "<script>alert(1)</script>",
      "",
      "![remote](https://example.com/remote.png)"
    ].join("\n")

    const html = renderStCompatMarkdownToHtml(markdown, false)

    expect(html).toContain("Hello")
    expect(html).toContain("world")
    expect(html).toContain("st-inline-spoiler")
    expect(html).toContain("external image blocked")
    expect(html).not.toContain("<script")
  })

  it("normalizes unknown rich text mode values to safe_markdown", () => {
    expect(normalizeChatRichTextMode("st_compat")).toBe("st_compat")
    expect(normalizeChatRichTextMode("safe_markdown")).toBe("safe_markdown")
    expect(normalizeChatRichTextMode("unknown")).toBe("safe_markdown")
    expect(normalizeChatRichTextMode(null)).toBe("safe_markdown")
  })
})
