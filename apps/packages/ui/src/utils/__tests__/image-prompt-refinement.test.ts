import { describe, expect, it } from "vitest"
import {
  buildImagePromptRefineMessages,
  extractImagePromptRefineCandidate
} from "@/utils/image-prompt-refinement"

describe("image prompt refinement utilities", () => {
  it("builds deterministic refinement messages with context blend entries", () => {
    const messages = buildImagePromptRefineMessages({
      originalPrompt: "Portrait of Lana in neon rain.",
      strategyLabel: "Expression",
      backend: "local-sd",
      contextEntries: [
        {
          id: "character",
          label: "Character",
          text: "Lana Reed",
          weight: 0.3,
          quality: 0.9,
          score: 0.27
        },
        {
          id: "mood",
          label: "Mood",
          text: "focused and intense",
          weight: 0.2,
          quality: 0.8,
          score: 0.16
        }
      ]
    })

    expect(messages).toHaveLength(2)
    expect(messages[0]).toMatchObject({ role: "system" })
    expect(messages[1]).toMatchObject({ role: "user" })
    const userContent = String(messages[1].content || "")
    expect(userContent).toContain("Prompt mode: Expression")
    expect(userContent).toContain("Backend: local-sd")
    expect(userContent).toContain("Character (27%): Lana Reed")
    expect(userContent).toContain("Mood (16%): focused and intense")
  })

  it("extracts refined prompt text from fenced completion payloads", () => {
    const candidate = extractImagePromptRefineCandidate({
      choices: [
        {
          message: {
            content:
              "```text\nPrompt: cinematic portrait of Lana, rain-soaked neon alley, shallow depth of field\n```"
          }
        }
      ]
    })

    expect(candidate).toBe(
      "cinematic portrait of Lana, rain-soaked neon alley, shallow depth of field"
    )
  })

  it("returns null when completion payload has no usable text", () => {
    expect(extractImagePromptRefineCandidate({ choices: [] })).toBeNull()
    expect(extractImagePromptRefineCandidate({})).toBeNull()
  })
})
