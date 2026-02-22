export type FlashcardsSurfaceState = "empty" | "active" | "success" | "error"
export type FlashcardsTabSurface = "review" | "manage" | "transfer"
export type FlashcardsPrimaryActionZone = "topbar" | "content" | "floating" | "panel"

export interface FlashcardsLayoutGuardrailRule {
  statePriority: readonly FlashcardsSurfaceState[]
  primaryActionPlacement: Record<FlashcardsSurfaceState, FlashcardsPrimaryActionZone>
  maxTopbarPrimaryCtas: Record<FlashcardsSurfaceState, number>
}

export const FLASHCARDS_LAYOUT_GUARDRAILS: Record<
  FlashcardsTabSurface,
  FlashcardsLayoutGuardrailRule
> = {
  review: {
    statePriority: ["error", "active", "success", "empty"],
    primaryActionPlacement: {
      error: "content",
      active: "content",
      success: "content",
      empty: "content"
    },
    maxTopbarPrimaryCtas: {
      error: 1,
      active: 0,
      success: 0,
      empty: 1
    }
  },
  manage: {
    statePriority: ["error", "active", "empty", "success"],
    primaryActionPlacement: {
      error: "content",
      active: "floating",
      success: "content",
      empty: "content"
    },
    maxTopbarPrimaryCtas: {
      error: 0,
      active: 0,
      success: 0,
      empty: 0
    }
  },
  transfer: {
    statePriority: ["error", "active", "success", "empty"],
    primaryActionPlacement: {
      error: "panel",
      active: "panel",
      success: "panel",
      empty: "panel"
    },
    maxTopbarPrimaryCtas: {
      error: 0,
      active: 0,
      success: 0,
      empty: 0
    }
  }
}
