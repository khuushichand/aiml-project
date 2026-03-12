import { describe, expect, it, vi } from "vitest"

import { validateSelectedChatModelAvailability } from "@/utils/chat-model-validation"

describe("validateSelectedChatModelAvailability", () => {
  it("treats cached model matches as valid without forcing a refresh", async () => {
    const fetchModels = vi.fn(async () => [
      { model: "tldw:gpt-4o-mini", name: "gpt-4o-mini" }
    ])

    const result = await validateSelectedChatModelAvailability("gpt-4o-mini", {
      fetchModels
    })

    expect(result).toEqual({ status: "valid" })
    expect(fetchModels).toHaveBeenCalledWith({
      returnEmpty: true,
      allowNetwork: false
    })
  })

  it("returns an advisory result when the selected model is missing from the cached catalog", async () => {
    const fetchModels = vi.fn(async () => [
      { model: "tldw:gpt-4o-mini", name: "gpt-4o-mini" }
    ])

    const result = await validateSelectedChatModelAvailability("claude-3-7-sonnet", {
      fetchModels
    })

    expect(result).toEqual({
      status: "unknown",
      reason: "model-unavailable-in-cache"
    })
    expect(fetchModels).toHaveBeenCalledWith({
      returnEmpty: true,
      allowNetwork: false
    })
  })

  it("returns an advisory result when no cached models are loaded", async () => {
    const fetchModels = vi.fn(async () => [])

    const result = await validateSelectedChatModelAvailability("gpt-4o-mini", {
      fetchModels
    })

    expect(result).toEqual({
      status: "unknown",
      reason: "catalog-empty"
    })
    expect(fetchModels).toHaveBeenCalledWith({
      returnEmpty: true,
      allowNetwork: false
    })
  })
})
