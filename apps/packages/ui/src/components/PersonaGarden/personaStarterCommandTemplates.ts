export type PersonaStarterCommandTemplate = {
  key: string
  label: string
  description: string
  name: string
  commandDescription: string
  phrases: string[]
  toolName: string
  slotMap: Record<string, string>
  requiresConfirmation: boolean
}

const freezeTemplate = (
  template: PersonaStarterCommandTemplate
): Readonly<PersonaStarterCommandTemplate> =>
  Object.freeze({
    ...template,
    phrases: Object.freeze([...template.phrases]),
    slotMap: Object.freeze({ ...template.slotMap })
  })

export const PERSONA_STARTER_COMMAND_TEMPLATES: ReadonlyArray<
  Readonly<PersonaStarterCommandTemplate>
> = Object.freeze([
  freezeTemplate({
    key: "notes-search",
    label: "Search Notes",
    description: "Find notes by spoken topic",
    name: "Search Notes",
    commandDescription: "Find notes related to a spoken topic",
    phrases: ["search notes for {topic}", "find notes about {topic}"],
    toolName: "notes.search",
    slotMap: { query: "topic" },
    requiresConfirmation: false
  }),
  freezeTemplate({
    key: "note-create",
    label: "Create Note",
    description: "Save dictated notes quickly",
    name: "Create Note",
    commandDescription: "Create a new note from spoken content",
    phrases: ["create note {content}", "note this {content}"],
    toolName: "notes.create",
    slotMap: { content: "content" },
    requiresConfirmation: true
  }),
  freezeTemplate({
    key: "media-search",
    label: "Search Library",
    description: "Search ingested media by phrase",
    name: "Search Library",
    commandDescription: "Search media and research content",
    phrases: ["search library for {query}", "find media about {query}"],
    toolName: "media.search",
    slotMap: { query: "query" },
    requiresConfirmation: false
  })
])

export const getPersonaStarterCommandTemplate = (
  key: string
): PersonaStarterCommandTemplate | null => {
  const template =
    PERSONA_STARTER_COMMAND_TEMPLATES.find((candidate) => candidate.key === key) ||
    null

  if (!template) return null

  return {
    ...template,
    phrases: [...template.phrases],
    slotMap: { ...template.slotMap }
  }
}
