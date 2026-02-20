import { describe, expect, it } from "vitest"
import {
  createStartupTemplateBundle,
  describeStartupTemplatePrompt,
  resolveStartupTemplatePrompt
} from "../startup-template-bundles"
import type { Prompt } from "@/db/dexie/types"

const studioPrompt: Prompt = {
  id: "studio-prompt",
  title: "Studio analysis",
  content: "Use evidence-first analysis.",
  is_system: true,
  createdAt: 1,
  updatedAt: 1,
  sourceSystem: "studio",
  studioPromptId: 900,
  serverId: 900,
  syncStatus: "synced"
}

const localPrompt: Prompt = {
  id: "local-prompt",
  title: "Local helper",
  content: "Be concise.",
  is_system: true,
  createdAt: 1,
  updatedAt: 1,
  sourceSystem: "workspace"
}

describe("startup template prompt mapping contract", () => {
  it("maps selected prompt id directly to prompt library entries", () => {
    const template = createStartupTemplateBundle(
      {
        name: "Local prompt template",
        selectedModel: "openai:gpt-4.1",
        selectedSystemPromptId: "local-prompt",
        systemPrompt: "",
        promptSource: "prompt-library"
      },
      { id: "template-local", now: 1 }
    )

    const resolution = resolveStartupTemplatePrompt(template, [studioPrompt, localPrompt])
    expect(resolution.prompt?.id).toBe("local-prompt")
    expect(resolution.source).toBe("prompt-library")
    expect(describeStartupTemplatePrompt(template, [studioPrompt, localPrompt])).toContain(
      "Prompt library"
    )
  })

  it("falls back to Prompt Studio id matching when local id is unavailable", () => {
    const template = createStartupTemplateBundle(
      {
        name: "Studio prompt template",
        selectedModel: "openai:gpt-4.1",
        selectedSystemPromptId: "missing-local",
        promptStudioPromptId: 900,
        promptTitle: "Studio analysis",
        promptSource: "prompt-studio",
        systemPrompt: ""
      },
      { id: "template-studio", now: 1 }
    )

    const resolution = resolveStartupTemplatePrompt(template, [localPrompt, studioPrompt])
    expect(resolution.prompt?.id).toBe("studio-prompt")
    expect(resolution.source).toBe("prompt-studio")
    expect(resolution.promptStudioPromptId).toBe(900)
    expect(describeStartupTemplatePrompt(template, [localPrompt, studioPrompt])).toContain(
      "Prompt Studio"
    )
  })

  it("returns template fallback metadata when no prompt records are available", () => {
    const template = createStartupTemplateBundle(
      {
        name: "Manual template",
        selectedModel: "openai:gpt-4.1",
        systemPrompt: "Respond with strict JSON.",
        promptSource: "system-template"
      },
      { id: "template-manual", now: 1 }
    )

    const resolution = resolveStartupTemplatePrompt(template, [])
    expect(resolution.prompt).toBeNull()
    expect(resolution.source).toBe("system-template")
    expect(describeStartupTemplatePrompt(template, [])).toBe("Custom system prompt")
  })
})
