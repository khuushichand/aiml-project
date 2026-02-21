import { describe, expect, it } from "vitest"
import { buildCompareInteroperabilityNotices } from "../compare-interoperability"

const t = ((key: string, fallback?: string, options?: Record<string, unknown>) => {
  const template = fallback || key
  if (!options) return template
  return template.replace(/\{\{(\w+)\}\}/g, (_match, token) => {
    const value = options[token]
    return value == null ? "" : String(value)
  })
}) as any

describe("compare-interoperability", () => {
  it("returns warning+shared-context notices for stacked compare modes", () => {
    const notices = buildCompareInteroperabilityNotices({
      t,
      characterName: "Archivist",
      pinnedSourceCount: 3,
      webSearch: true,
      hasPromptContext: true,
      jsonMode: true,
      voiceChatEnabled: true
    })

    expect(notices.map((notice) => notice.id)).toEqual([
      "voice",
      "character",
      "pinned",
      "web-search",
      "prompt",
      "json"
    ])
    expect(notices[0]?.tone).toBe("warning")
    expect(notices[1]?.text).toContain("Archivist")
    expect(notices[2]?.text).toContain("3 pinned sources")
  })

  it("returns an empty list when no interoperability modifiers are active", () => {
    const notices = buildCompareInteroperabilityNotices({
      t,
      characterName: null,
      pinnedSourceCount: 0,
      webSearch: false,
      hasPromptContext: false,
      jsonMode: false,
      voiceChatEnabled: false
    })

    expect(notices).toEqual([])
  })
})
