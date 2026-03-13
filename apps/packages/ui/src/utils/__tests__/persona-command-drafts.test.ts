import { describe, expect, it } from "vitest"

import { buildDraftAssistSuggestions } from "../persona-command-drafts"

describe("buildDraftAssistSuggestions", () => {
  it("suggests a topic placeholder for phrases that use for-topic phrasing", () => {
    expect(
      buildDraftAssistSuggestions("search notes for model context protocol")
    ).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          label: "Use {topic}",
          suggestedPhrase: "search notes for {topic}",
          suggestedSlotMap: { query: "topic" }
        })
      ])
    )
  })

  it("suggests content placeholders for with-content phrasing", () => {
    expect(
      buildDraftAssistSuggestions("create note with remember to review tests")
    ).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          label: "Use {content}",
          suggestedPhrase: "create note with {content}",
          suggestedSlotMap: { content: "content" }
        })
      ])
    )
  })

  it("captures numeric duration phrases deterministically", () => {
    expect(buildDraftAssistSuggestions("start a focus sprint for 10 minutes")).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          label: "Use {duration}",
          suggestedPhrase: "start a focus sprint for {duration}",
          suggestedSlotMap: { duration: "duration" }
        })
      ])
    )
  })
})
