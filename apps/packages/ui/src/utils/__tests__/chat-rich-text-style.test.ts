import {
  CHAT_RICH_TEXT_STYLE_PRESETS,
  normalizeChatRichTextColor,
  normalizeChatRichTextFont,
  normalizeChatRichTextStylePreset,
  resolveChatRichTextStyleCssVars
} from "@/utils/chat-rich-text-style"
import { describe, expect, it } from "vitest"

describe("chat-rich-text-style", () => {
  it("normalizes invalid preset and style values", () => {
    expect(normalizeChatRichTextStylePreset("default")).toBe("default")
    expect(normalizeChatRichTextStylePreset("bogus")).toBe("default")
    expect(normalizeChatRichTextColor("primary")).toBe("primary")
    expect(normalizeChatRichTextColor("bogus")).toBe("default")
    expect(normalizeChatRichTextFont("mono")).toBe("mono")
    expect(normalizeChatRichTextFont("bogus")).toBe("default")
  })

  it("resolves expected CSS vars from default preset", () => {
    const vars = resolveChatRichTextStyleCssVars(
      CHAT_RICH_TEXT_STYLE_PRESETS.default
    )

    expect(vars["--rt-italic-color"]).toBe("inherit")
    expect(vars["--rt-bold-color"]).toBe("inherit")
    expect(vars["--rt-quote-border-color"]).toContain("--color-border")
    expect(vars["--rt-quote-bg-color"]).toContain("--color-surface-2")
  })

  it("resolves expected CSS vars from high_contrast preset", () => {
    const vars = resolveChatRichTextStyleCssVars(
      CHAT_RICH_TEXT_STYLE_PRESETS.high_contrast
    )

    expect(vars["--rt-italic-color"]).toContain("--color-warn")
    expect(vars["--rt-bold-color"]).toContain("--color-primary")
    expect(vars["--rt-quote-border-color"]).toContain("--color-danger")
    expect(vars["--rt-quote-bg-color"]).toContain("--color-primary")
  })
})
