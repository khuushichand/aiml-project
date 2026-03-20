import { describe, expect, it } from "vitest"

import {
  PERSONA_STARTER_COMMAND_TEMPLATES,
  getPersonaStarterCommandTemplate
} from "../personaStarterCommandTemplates"

describe("personaStarterCommandTemplates", () => {
  it("exposes an immutable starter template catalog", () => {
    expect(Object.isFrozen(PERSONA_STARTER_COMMAND_TEMPLATES)).toBe(true)
    expect(Object.isFrozen(PERSONA_STARTER_COMMAND_TEMPLATES[0])).toBe(true)
    expect(Object.isFrozen(PERSONA_STARTER_COMMAND_TEMPLATES[0]?.phrases)).toBe(true)
    expect(Object.isFrozen(PERSONA_STARTER_COMMAND_TEMPLATES[0]?.slotMap)).toBe(true)
  })

  it("returns a defensive clone for each template lookup", () => {
    const template = getPersonaStarterCommandTemplate("notes-search")
    expect(template).not.toBeNull()

    const mutableTemplate = template as unknown as {
      name: string
      phrases: string[]
      slotMap: Record<string, string>
    }
    mutableTemplate.name = "Mutated"
    mutableTemplate.phrases.push("search notes by title {topic}")
    mutableTemplate.slotMap.query = "title"

    const freshTemplate = getPersonaStarterCommandTemplate("notes-search")
    expect(freshTemplate).toMatchObject({
      name: "Search Notes",
      phrases: ["search notes for {topic}", "find notes about {topic}"],
      slotMap: { query: "topic" }
    })
    expect(freshTemplate).not.toBe(template)
  })
})
