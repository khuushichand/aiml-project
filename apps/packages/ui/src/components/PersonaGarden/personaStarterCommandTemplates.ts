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

export const PERSONA_STARTER_COMMAND_TEMPLATES: PersonaStarterCommandTemplate[] = [
  {
    key: "notes-search",
    label: "Search Notes",
    description: "Find notes by spoken topic",
    name: "Search Notes",
    commandDescription: "Find notes related to a spoken topic",
    phrases: ["search notes for {topic}", "find notes about {topic}"],
    toolName: "notes.search",
    slotMap: { query: "topic" },
    requiresConfirmation: false
  },
  {
    key: "note-create",
    label: "Create Note",
    description: "Save dictated notes quickly",
    name: "Create Note",
    commandDescription: "Create a new note from spoken content",
    phrases: ["create note {content}", "note this {content}"],
    toolName: "notes.create",
    slotMap: { content: "content" },
    requiresConfirmation: true
  },
  {
    key: "media-search",
    label: "Search Library",
    description: "Search ingested media by phrase",
    name: "Search Library",
    commandDescription: "Search media and research content",
    phrases: ["search library for {query}", "find media about {query}"],
    toolName: "media.search",
    slotMap: { query: "query" },
    requiresConfirmation: false
  }
]

export const getPersonaStarterCommandTemplate = (
  key: string
): PersonaStarterCommandTemplate | null =>
  PERSONA_STARTER_COMMAND_TEMPLATES.find((template) => template.key === key) || null
