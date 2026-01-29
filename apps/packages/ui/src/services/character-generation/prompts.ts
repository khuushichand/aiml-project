/**
 * Prompt templates for character generation
 */

import type { GeneratedCharacter, CharacterField } from "./types"

/**
 * System prompt for full character generation
 */
export const FULL_CHARACTER_SYSTEM_PROMPT = `You are an expert character designer for roleplay and AI assistants.
Your task is to create detailed, engaging characters based on user concepts.

Guidelines:
- Create characters that are interesting, nuanced, and suitable for conversation
- System prompts should be clear instructions for how the AI should behave as this character
- First messages should be engaging and set the tone for the character
- Tags should be relevant keywords for categorization
- Keep descriptions concise but evocative
- Personality should capture key traits and quirks
- Scenarios should set up interesting contexts for interaction

You MUST respond with valid JSON only, no additional text.`

/**
 * User prompt template for full character generation
 */
export const FULL_CHARACTER_USER_PROMPT = (concept: string): string => `Create a detailed character based on this concept: "${concept}"

Respond with a JSON object containing these fields:
{
  "name": "Character's name",
  "description": "Brief physical/narrative description (1-2 sentences)",
  "personality": "Personality traits and characteristics (2-3 sentences)",
  "scenario": "The context or setting where this character exists (1-2 sentences)",
  "system_prompt": "Instructions for how an AI should roleplay as this character, including tone, style, knowledge, and behaviors (3-5 sentences)",
  "first_message": "An engaging opening message this character would send to start a conversation",
  "message_example": "An example exchange showing how this character typically responds",
  "creator_notes": "Optional notes about the character design or tips for interacting with them",
  "tags": ["array", "of", "relevant", "tags"],
  "alternate_greetings": ["one or two alternative opening messages"]
}

IMPORTANT: Respond ONLY with the JSON object, no other text.`

/**
 * Get system prompt for single field generation
 */
export const getSingleFieldSystemPrompt = (field: CharacterField): string => {
  const basePrompt = `You are an expert character designer. Generate only the requested field for a character.
You MUST respond with valid JSON only, no additional text.`
  return basePrompt
}

/**
 * Get user prompt for generating a single field
 */
export const getSingleFieldUserPrompt = (
  field: CharacterField,
  existingFields: Partial<GeneratedCharacter>
): string => {
  const context = buildContextString(existingFields)

  switch (field) {
    case "name":
      return `${context}

Generate a fitting name for this character. Respond with JSON: {"name": "the character's name"}`

    case "description":
      return `${context}

Generate a brief description (1-2 sentences) of this character's appearance and demeanor. Respond with JSON: {"description": "the description"}`

    case "personality":
      return `${context}

Generate personality traits for this character (2-3 sentences covering key traits, quirks, and behavioral patterns). Respond with JSON: {"personality": "the personality description"}`

    case "scenario":
      return `${context}

Generate a scenario or context where this character would typically be encountered (1-2 sentences). Respond with JSON: {"scenario": "the scenario"}`

    case "system_prompt":
      return `${context}

Generate a system prompt that instructs an AI how to roleplay as this character. Include tone, style, knowledge areas, and behavioral guidelines (3-5 sentences). Respond with JSON: {"system_prompt": "the system prompt"}`

    case "first_message":
      return `${context}

Generate an engaging first message this character would send to start a conversation. It should establish their personality and invite interaction. Respond with JSON: {"first_message": "the greeting message"}`

    case "message_example":
      return `${context}

Generate an example message exchange that demonstrates how this character typically communicates. Format as a brief dialogue. Respond with JSON: {"message_example": "the example exchange"}`

    case "creator_notes":
      return `${context}

Generate creator notes with tips for interacting with this character and notes about their design (2-3 sentences). Respond with JSON: {"creator_notes": "the notes"}`

    case "tags":
      return `${context}

Generate 3-6 relevant tags for categorizing this character. Respond with JSON: {"tags": ["tag1", "tag2", "tag3"]}`

    case "alternate_greetings":
      return `${context}

Generate 2-3 alternative greeting messages this character could use. Each should have a different tone or approach. Respond with JSON: {"alternate_greetings": ["greeting1", "greeting2"]}`

    default:
      return `${context}

Generate appropriate content for the "${field}" field of this character. Respond with valid JSON.`
  }
}

/**
 * Build a context string from existing character fields
 */
function buildContextString(fields: Partial<GeneratedCharacter>): string {
  const parts: string[] = ["Here is the current character information:"]

  if (fields.name) {
    parts.push(`Name: ${fields.name}`)
  }
  if (fields.description) {
    parts.push(`Description: ${fields.description}`)
  }
  if (fields.personality) {
    parts.push(`Personality: ${fields.personality}`)
  }
  if (fields.scenario) {
    parts.push(`Scenario: ${fields.scenario}`)
  }
  if (fields.system_prompt) {
    parts.push(`System prompt: ${fields.system_prompt}`)
  }
  if (fields.first_message) {
    parts.push(`First message: ${fields.first_message}`)
  }
  if (fields.tags && fields.tags.length > 0) {
    parts.push(`Tags: ${fields.tags.join(", ")}`)
  }

  if (parts.length === 1) {
    return "No existing character information provided."
  }

  return parts.join("\n")
}

/**
 * Parse JSON response, handling potential issues
 */
export function parseGenerationResponse<T>(response: string): T | null {
  // Try to extract JSON from the response
  let jsonStr = response.trim()

  // Handle markdown code blocks
  const codeBlockMatch = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/)
  if (codeBlockMatch) {
    jsonStr = codeBlockMatch[1].trim()
  }

  // Try to find JSON object in the response
  const jsonMatch = jsonStr.match(/\{[\s\S]*\}/)
  if (jsonMatch) {
    jsonStr = jsonMatch[0]
  }

  try {
    return JSON.parse(jsonStr) as T
  } catch (error) {
    console.error("Failed to parse generation response:", error, response)
    return null
  }
}
