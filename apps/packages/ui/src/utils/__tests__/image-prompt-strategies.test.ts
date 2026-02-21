import { describe, expect, it } from "vitest"
import {
  createImagePromptDraftFromStrategy,
  extractWeightedImagePromptContext,
  getImagePromptStrategy,
  getImagePromptStrategies
} from "@/utils/image-prompt-strategies"

describe("image prompt strategy registry", () => {
  it("falls back to scene strategy when id is unknown", () => {
    const strategy = getImagePromptStrategy("does-not-exist")
    expect(strategy.id).toBe("scene")
  })

  it("extracts weighted context entries in deterministic score order", () => {
    const weighted = extractWeightedImagePromptContext(
      {
        conversationSummary: "alpha beta gamma delta",
        characterName: "Lana Reed",
        moodLabel: "curious and attentive",
        assistantFocus: "neon hallway with mirror reflections",
        userIntent: "focus on hands and face composition"
      },
      {
        user_intent: 0.8,
        conversation: 0.05,
        character: 0.05,
        mood: 0.05,
        assistant_focus: 0.05
      }
    )

    expect(weighted.entries.length).toBeGreaterThan(0)
    expect(weighted.entries[0]?.id).toBe("user_intent")
    expect(weighted.summary.length).toBeGreaterThan(0)
  })

  it("produces non-empty prompt drafts for all default strategies with minimal and full context", () => {
    const strategies = getImagePromptStrategies()
    expect(strategies.length).toBeGreaterThanOrEqual(5)

    for (const strategy of strategies) {
      const minimalDraft = createImagePromptDraftFromStrategy({
        strategyId: strategy.id,
        rawContext: {}
      })
      expect(minimalDraft.prompt.trim().length).toBeGreaterThan(0)

      const fullDraft = createImagePromptDraftFromStrategy({
        strategyId: strategy.id,
        rawContext: {
          conversationSummary:
            "They are planning a rooftop meetup under city lights.",
          characterName: "Lana",
          moodLabel: "excited",
          assistantFocus: "camera near eye level with soft rim light",
          userIntent: "emphasize expression and clothing details"
        }
      })
      expect(fullDraft.prompt.trim().length).toBeGreaterThan(0)
    }
  })
})

