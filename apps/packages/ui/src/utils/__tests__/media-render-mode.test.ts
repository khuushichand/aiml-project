import { describe, expect, it } from "vitest"

import {
  normalizeRequestedMediaRenderMode,
  resolveMediaRenderMode
} from "@/utils/media-render-mode"

describe("media-render-mode", () => {
  it("prefers explicit requested mode over resolved format", () => {
    const mode = resolveMediaRenderMode({
      requestedMode: "plain",
      resolvedContentFormat: "html",
      allowRichRendering: true
    })
    expect(mode).toBe("plain")
  })

  it("uses resolved format when requested mode is auto", () => {
    expect(
      resolveMediaRenderMode({
        requestedMode: "auto",
        resolvedContentFormat: "html",
        allowRichRendering: true
      })
    ).toBe("html")

    expect(
      resolveMediaRenderMode({
        requestedMode: "auto",
        resolvedContentFormat: "plain",
        allowRichRendering: true
      })
    ).toBe("plain")
  })

  it("falls back to markdown when no resolved format exists", () => {
    expect(
      resolveMediaRenderMode({
        requestedMode: "auto",
        resolvedContentFormat: null,
        allowRichRendering: true
      })
    ).toBe("markdown")
  })

  it("downgrades html mode when rich rendering is disabled", () => {
    expect(
      resolveMediaRenderMode({
        requestedMode: "html",
        resolvedContentFormat: "html",
        allowRichRendering: false
      })
    ).toBe("markdown")

    expect(normalizeRequestedMediaRenderMode("html", false)).toBe("auto")
    expect(normalizeRequestedMediaRenderMode("markdown", false)).toBe("markdown")
  })
})

