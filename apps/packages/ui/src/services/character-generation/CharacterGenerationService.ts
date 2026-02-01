/**
 * Character generation service using LLM chat completions
 */

import { tldwChat, type TldwChatOptions } from "../tldw/TldwChat"
import type {
  CharacterField,
  GeneratedCharacter,
  GenerationOptions,
  GenerationResult
} from "./types"
import {
  FULL_CHARACTER_SYSTEM_PROMPT,
  FULL_CHARACTER_USER_PROMPT,
  getSingleFieldSystemPrompt,
  getSingleFieldUserPrompt,
  parseGenerationResponse
} from "./prompts"

const DEFAULT_TEMPERATURE = 0.8
const DEFAULT_MAX_TOKENS = 2000

/**
 * Strip the "tldw:" prefix from model IDs if present.
 * The UI uses "tldw:model_id" for display, but the API expects just "model_id".
 */
const stripModelPrefix = (model: string): string => {
  return model.startsWith("tldw:") ? model.slice(5) : model
}

export class CharacterGenerationService {
  /**
   * Generate a complete character from a concept
   */
  async generateFullCharacter(
    concept: string,
    options: GenerationOptions
  ): Promise<GenerationResult<GeneratedCharacter>> {
    if (!concept.trim()) {
      return {
        success: false,
        error: "Please provide a character concept"
      }
    }

    if (!options.model) {
      return {
        success: false,
        error: "Please select a model for generation"
      }
    }

    try {
      const chatOptions: TldwChatOptions = {
        model: stripModelPrefix(options.model),
        apiProvider: options.apiProvider,
        temperature: options.temperature ?? DEFAULT_TEMPERATURE,
        maxTokens: options.maxTokens ?? DEFAULT_MAX_TOKENS,
        systemPrompt: FULL_CHARACTER_SYSTEM_PROMPT,
        jsonMode: true,
        saveToDb: false
      }

      const response = await tldwChat.sendMessage(
        [{ role: "user", content: FULL_CHARACTER_USER_PROMPT(concept.trim()) }],
        chatOptions
      )

      const parsed = parseGenerationResponse<GeneratedCharacter>(response)

      if (!parsed) {
        return {
          success: false,
          error: "Failed to parse generation response. Please try again."
        }
      }

      return {
        success: true,
        data: parsed
      }
    } catch (error: any) {
      console.error("Character generation failed:", error)
      return {
        success: false,
        error: this.getErrorMessage(error)
      }
    }
  }

  /**
   * Generate a single field for a character
   */
  async generateField(
    field: CharacterField,
    existingFields: Partial<GeneratedCharacter>,
    options: GenerationOptions
  ): Promise<GenerationResult<string | string[]>> {
    if (field === "all") {
      const result = await this.generateFullCharacter(
        existingFields.description || existingFields.name || "",
        options
      )
      return result as GenerationResult<string | string[]>
    }

    if (!options.model) {
      return {
        success: false,
        error: "Please select a model for generation"
      }
    }

    try {
      const chatOptions: TldwChatOptions = {
        model: stripModelPrefix(options.model),
        apiProvider: options.apiProvider,
        temperature: options.temperature ?? DEFAULT_TEMPERATURE,
        maxTokens: options.maxTokens ?? 1000,
        systemPrompt: getSingleFieldSystemPrompt(field),
        jsonMode: true,
        saveToDb: false
      }

      const userPrompt = getSingleFieldUserPrompt(field, existingFields)

      const response = await tldwChat.sendMessage(
        [{ role: "user", content: userPrompt }],
        chatOptions
      )

      const parsed = parseGenerationResponse<Record<string, any>>(response)

      if (!parsed) {
        return {
          success: false,
          error: "Failed to parse generation response. Please try again."
        }
      }

      // Extract the field value from the response
      const value = parsed[field]

      if (value === undefined) {
        // Try to find any value in the response
        const keys = Object.keys(parsed)
        if (keys.length > 0) {
          const firstValue = parsed[keys[0]]
          return {
            success: true,
            data: firstValue
          }
        }
        return {
          success: false,
          error: "No valid response received. Please try again."
        }
      }

      return {
        success: true,
        data: value
      }
    } catch (error: any) {
      console.error(`Field generation failed for ${field}:`, error)
      return {
        success: false,
        error: this.getErrorMessage(error)
      }
    }
  }

  /**
   * Cancel any ongoing generation
   */
  cancel(): void {
    tldwChat.cancelStream()
  }

  /**
   * Get user-friendly error message
   */
  private getErrorMessage(error: any): string {
    const message = error?.message || String(error)
    const normalized = message.toLowerCase()

    if (normalized.includes("abort") || normalized.includes("cancel")) {
      return "Generation cancelled"
    }

    if (normalized.includes("timeout")) {
      return "Generation timed out. Please try again."
    }

    if (
      normalized.includes("network") ||
      normalized.includes("fetch") ||
      normalized.includes("connection")
    ) {
      return "Unable to connect to the server. Check your connection and try again."
    }

    if (normalized.includes("rate limit") || normalized.includes("429")) {
      return "Rate limit exceeded. Please wait a moment and try again."
    }

    if (normalized.includes("401") || normalized.includes("unauthorized")) {
      return "Authentication error. Please check your API settings."
    }

    if (normalized.includes("model") && normalized.includes("not found")) {
      return "Selected model not available. Please choose a different model."
    }

    // Return a generic message for unknown errors
    return "Generation failed. Please try again."
  }
}

// Singleton instance
export const characterGeneration = new CharacterGenerationService()
