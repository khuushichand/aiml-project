import { describe, expect, it } from "vitest"
import {
  createStartupTemplateBundle,
  parseStartupTemplateBundles,
  serializeStartupTemplateBundles,
  upsertStartupTemplateBundle,
  removeStartupTemplateBundle,
  sanitizeStartupTemplateName
} from "../startup-template-bundles"

describe("startup template bundles integration", () => {
  it("roundtrips saved bundles through serialized storage format", () => {
    const bundle = createStartupTemplateBundle(
      {
        name: "  Research kickoff template  ",
        selectedModel: "openai:gpt-4.1",
        systemPrompt: "You are a rigorous analyst.",
        selectedSystemPromptId: "prompt-1",
        promptStudioPromptId: 88,
        promptTitle: "Research kickoff",
        promptSource: "prompt-studio",
        presetKey: "balanced",
        character: {
          id: 12,
          name: "Archivist"
        } as any,
        ragPinnedResults: [
          {
            id: "source-1",
            snippet: "Pinned evidence",
            title: "Dataset",
            source: "docs"
          }
        ]
      },
      {
        id: "template-1",
        now: 1_700_000_000_000
      }
    )

    const raw = serializeStartupTemplateBundles([bundle])
    const parsed = parseStartupTemplateBundles(raw)

    expect(parsed).toEqual([bundle])
  })

  it("upserts and removes bundles while preserving newest-first order", () => {
    const older = createStartupTemplateBundle(
      {
        name: "Older",
        selectedModel: "gpt-4.1",
        systemPrompt: "A",
        presetKey: "balanced"
      },
      { id: "older", now: 1 }
    )
    const newer = createStartupTemplateBundle(
      {
        name: "Newer",
        selectedModel: "gpt-4.1-mini",
        systemPrompt: "B",
        presetKey: "precise"
      },
      { id: "newer", now: 2 }
    )

    const upserted = upsertStartupTemplateBundle([older], newer)
    expect(upserted.map((entry) => entry.id)).toEqual(["newer", "older"])

    const removed = removeStartupTemplateBundle(upserted, "newer")
    expect(removed.map((entry) => entry.id)).toEqual(["older"])
  })

  it("sanitizes names and discards malformed stored entries", () => {
    const invalidRaw = JSON.stringify([
      {
        id: "valid",
        name: "   ",
        selectedModel: "",
        systemPrompt: 123,
        presetKey: "unknown",
        ragPinnedResults: [
          { id: "ok", snippet: "keep" },
          { id: "bad" }
        ]
      },
      {
        name: "missing-id"
      }
    ])

    const parsed = parseStartupTemplateBundles(invalidRaw)
    expect(parsed).toHaveLength(1)
    expect(parsed[0]?.name).toBe("New startup template")
    expect(parsed[0]?.selectedModel).toBeNull()
    expect(parsed[0]?.presetKey).toBe("custom")
    expect(parsed[0]?.ragPinnedResults).toEqual([{ id: "ok", snippet: "keep" }])

    expect(
      sanitizeStartupTemplateName(
        "This is a very long startup template name that should be trimmed to fit the max length boundary in one shot"
      ).length
    ).toBeLessThanOrEqual(80)
  })
})
