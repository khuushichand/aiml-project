export type CharacterPromptPresetId = "default" | "st_default"

export const DEFAULT_CHARACTER_PROMPT_PRESET: CharacterPromptPresetId = "default"

export const CHARACTER_PROMPT_PRESETS: Array<{
  id: CharacterPromptPresetId
  label: string
  description: string
}> = [
  {
    id: "default",
    label: "Default (legacy)",
    description: "Use the existing character prompt formatting."
  },
  {
    id: "st_default",
    label: "SillyTavern default",
    description: "Format character context with ST-style sections."
  }
]

export const isCharacterPromptPresetId = (
  value: unknown
): value is CharacterPromptPresetId =>
  value === "default" || value === "st_default"
