/**
 * React hook for character generation
 */

import React from "react"
import {
  characterGeneration,
  type CharacterField,
  type GeneratedCharacter,
  type GenerationOptions
} from "@/services/character-generation"

export interface UseCharacterGenerationReturn {
  /** Whether any generation is in progress */
  isGenerating: boolean
  /** Which field is currently being generated (null if none) */
  generatingField: CharacterField | null
  /** Error message if generation failed */
  error: string | null
  /** Generate a complete character from a concept */
  generateFullCharacter: (
    concept: string,
    options: GenerationOptions
  ) => Promise<GeneratedCharacter | null>
  /** Generate a single field based on existing character data */
  generateField: (
    field: CharacterField,
    existingFields: Partial<GeneratedCharacter>,
    options: GenerationOptions
  ) => Promise<string | string[] | null>
  /** Cancel any ongoing generation */
  cancel: () => void
  /** Clear the current error */
  clearError: () => void
}

export function useCharacterGeneration(): UseCharacterGenerationReturn {
  const [isGenerating, setIsGenerating] = React.useState(false)
  const [generatingField, setGeneratingField] =
    React.useState<CharacterField | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const isMountedRef = React.useRef(true)

  React.useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
      characterGeneration.cancel()
    }
  }, [])

  const generateFullCharacter = React.useCallback(
    async (
      concept: string,
      options: GenerationOptions
    ): Promise<GeneratedCharacter | null> => {
      setIsGenerating(true)
      setGeneratingField("all")
      setError(null)

      try {
        const result = await characterGeneration.generateFullCharacter(
          concept,
          options
        )

        if (!isMountedRef.current) return null

        if (!result.success) {
          setError(result.error || "Generation failed")
          return null
        }

        return result.data || null
      } catch (err: any) {
        if (!isMountedRef.current) return null
        const message = err?.message || "Generation failed"
        setError(message)
        return null
      } finally {
        if (isMountedRef.current) {
          setIsGenerating(false)
          setGeneratingField(null)
        }
      }
    },
    []
  )

  const generateField = React.useCallback(
    async (
      field: CharacterField,
      existingFields: Partial<GeneratedCharacter>,
      options: GenerationOptions
    ): Promise<string | string[] | null> => {
      setIsGenerating(true)
      setGeneratingField(field)
      setError(null)

      try {
        const result = await characterGeneration.generateField(
          field,
          existingFields,
          options
        )

        if (!isMountedRef.current) return null

        if (!result.success) {
          setError(result.error || "Generation failed")
          return null
        }

        return result.data ?? null
      } catch (err: any) {
        if (!isMountedRef.current) return null
        const message = err?.message || "Generation failed"
        setError(message)
        return null
      } finally {
        if (isMountedRef.current) {
          setIsGenerating(false)
          setGeneratingField(null)
        }
      }
    },
    []
  )

  const cancel = React.useCallback(() => {
    characterGeneration.cancel()
    setIsGenerating(false)
    setGeneratingField(null)
  }, [])

  const clearError = React.useCallback(() => {
    setError(null)
  }, [])

  return {
    isGenerating,
    generatingField,
    error,
    generateFullCharacter,
    generateField,
    cancel,
    clearError
  }
}
