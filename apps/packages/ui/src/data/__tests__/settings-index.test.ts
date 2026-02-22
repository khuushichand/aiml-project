import { describe, expect, it } from "vitest"

import { searchSettings } from "@/data/settings-index"

const translate = (_key: string, defaultValue?: string) => defaultValue ?? ""

describe("settings index RAG discoverability", () => {
  it("finds the unified RAG defaults page by knowledge QA query", () => {
    const results = searchSettings("knowledge qa", translate)

    expect(
      results.some(
        (setting) =>
          setting.id === "setting-rag-default-profile" &&
          setting.route === "/settings/rag"
      )
    ).toBe(true)
  })

  it("finds chat context window controls", () => {
    const results = searchSettings("context window", translate)

    expect(
      results.some((setting) => setting.id === "setting-rag-chat-max-context")
    ).toBe(true)
  })
})
