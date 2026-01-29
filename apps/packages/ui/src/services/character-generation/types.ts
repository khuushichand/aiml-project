/**
 * Types for character generation service
 */

/**
 * Fields that can be generated for a character
 */
export type CharacterField =
  | "all"
  | "name"
  | "description"
  | "personality"
  | "scenario"
  | "system_prompt"
  | "first_message"
  | "message_example"
  | "creator_notes"
  | "alternate_greetings"
  | "tags"

/**
 * Generated character data structure
 */
export interface GeneratedCharacter {
  name?: string
  description?: string
  personality?: string
  scenario?: string
  system_prompt?: string
  first_message?: string
  message_example?: string
  creator_notes?: string
  alternate_greetings?: string[]
  tags?: string[]
}

/**
 * Input for character generation
 */
export interface CharacterGenerationInput {
  /** For full generation: a brief concept like "a grumpy medieval blacksmith" */
  concept?: string
  /** Existing character fields to use as context for single-field generation */
  existingFields?: Partial<GeneratedCharacter>
  /** Which field to generate ('all' for full character) */
  targetField?: CharacterField
}

/**
 * Options for generation
 */
export interface GenerationOptions {
  /** Model ID to use for generation */
  model: string
  /** API provider (optional, will be inferred from model if not provided) */
  apiProvider?: string
  /** Temperature for generation (default 0.8) */
  temperature?: number
  /** Maximum tokens to generate */
  maxTokens?: number
}

/**
 * Result of a generation operation
 */
export interface GenerationResult<T> {
  success: boolean
  data?: T
  error?: string
}
