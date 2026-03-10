import React from "react"
import type { Character } from "@/types/character"
import {
  assistantSelectionToCharacter,
  characterToAssistantSelection
} from "@/types/assistant-selection"
import { useSelectedAssistant } from "@/hooks/useSelectedAssistant"

type StoredCharacter = Character

export const useSelectedCharacter = <T = StoredCharacter>(
  initialValue: T | null = null
) => {
  const initialAssistantSelection = React.useMemo(
    () =>
      characterToAssistantSelection(
        initialValue as (StoredCharacter & Record<string, unknown>) | null
      ),
    [initialValue]
  )
  const [selectedAssistant, setSelectedAssistant, meta] = useSelectedAssistant(
    initialAssistantSelection
  )

  const selectedCharacter = React.useMemo(
    () => assistantSelectionToCharacter<T>(selectedAssistant),
    [selectedAssistant]
  )
  const setSelectedCharacterWithBroadcast = React.useCallback(
    async (next: T | null) => {
      await setSelectedAssistant(
        characterToAssistantSelection(
          next as (StoredCharacter & Record<string, unknown>) | null
        )
      )
    },
    [setSelectedAssistant]
  )

  return [selectedCharacter, setSelectedCharacterWithBroadcast, meta] as const
}
