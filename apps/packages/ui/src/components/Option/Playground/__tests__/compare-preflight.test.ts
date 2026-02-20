import { describe, expect, it } from "vitest"
import {
  buildCompareModelMetaById,
  compareModelsSupportCapability,
  getCompareCapabilityIncompatibilities
} from "../compare-preflight"

const LABELS = {
  vision: "Mixed vision support",
  tools: "Mixed tool support",
  streaming: "Mixed streaming behavior",
  context: "Large context-window differences"
}

describe("compare-preflight", () => {
  it("normalizes model metadata from mixed payload shapes", () => {
    const meta = buildCompareModelMetaById([
      {
        model: "gpt-4o",
        capabilities: ["vision", "tools"],
        context_length: 128000
      },
      {
        model: "llama-3.1",
        details: {
          capabilities: ["streaming"],
          context_window: 8192
        }
      }
    ])

    expect(meta.get("gpt-4o")?.capabilities.has("vision")).toBe(true)
    expect(meta.get("llama-3.1")?.capabilities.has("streaming")).toBe(true)
    expect(meta.get("llama-3.1")?.contextLength).toBe(8192)
  })

  it("checks whether all selected models support a capability", () => {
    const meta = buildCompareModelMetaById([
      { model: "a", capabilities: ["vision", "tools"] },
      { model: "b", capabilities: ["vision"] }
    ])

    expect(compareModelsSupportCapability(["a", "b"], "vision", meta)).toBe(true)
    expect(compareModelsSupportCapability(["a", "b"], "tools", meta)).toBe(false)
  })

  it("flags mixed capability and large context mismatches", () => {
    const meta = buildCompareModelMetaById([
      {
        model: "vision-model",
        capabilities: ["vision", "tools", "streaming"],
        context_length: 131072
      },
      {
        model: "text-model",
        capabilities: ["streaming"],
        context_length: 8192
      }
    ])

    const warnings = getCompareCapabilityIncompatibilities({
      modelIds: ["vision-model", "text-model"],
      modelMetaById: meta,
      labels: LABELS
    })

    expect(warnings).toEqual([
      LABELS.vision,
      LABELS.tools,
      LABELS.context
    ])
  })
})
