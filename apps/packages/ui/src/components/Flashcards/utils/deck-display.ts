import type { Deck } from "@/services/flashcards"

type DeckLabelInput = Pick<Deck, "name" | "workspace_id"> | null | undefined

export const getDeckWorkspaceId = (deck: DeckLabelInput): string | null => {
  const workspaceId = deck?.workspace_id?.trim()
  return workspaceId ? workspaceId : null
}

export const formatDeckDisplayName = (
  deck: DeckLabelInput,
  fallbackName = "Untitled deck"
): string => {
  const baseName = deck?.name?.trim() || fallbackName
  const workspaceId = getDeckWorkspaceId(deck)
  return workspaceId ? `${baseName} · ${workspaceId}` : baseName
}
