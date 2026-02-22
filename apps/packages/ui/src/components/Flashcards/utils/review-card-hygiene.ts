import type { Flashcard } from "@/services/flashcards"

const STEP_PATTERN = /\bstep\s+\d+\s*:/gi
const OBJECTIVE_PATTERN = /\bobjective\s*:/gi
const ACTION_PATTERN = /\baction\s*:/gi

const TUTORIAL_PHRASES = [
  "here's a simple flow",
  "creating and using flashcards effectively",
  "tips for effective flashcard use",
  "end-to-end method"
]

const normalizeContent = (card: Pick<Flashcard, "front" | "back">): string =>
  `${card.front || ""}\n${card.back || ""}`
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase()

/**
 * Detects LLM-generated instructional residue cards that are not usable study prompts.
 * These cards typically contain multi-step how-to prose instead of a focused Q/A pair.
 */
export const isTutorialResidueCard = (
  card: Pick<Flashcard, "front" | "back">
): boolean => {
  const text = normalizeContent(card)
  if (!text) return false

  const hasTutorialPhrase = TUTORIAL_PHRASES.some((phrase) =>
    text.includes(phrase)
  )
  const stepCount = (text.match(STEP_PATTERN) || []).length
  const objectiveCount = (text.match(OBJECTIVE_PATTERN) || []).length
  const actionCount = (text.match(ACTION_PATTERN) || []).length

  if (text.includes("tips for effective flashcard use")) return true
  if (hasTutorialPhrase && stepCount >= 2) return true

  return stepCount >= 3 && objectiveCount >= 2 && actionCount >= 2
}

/**
 * Prefer the first reviewable card with concrete content. Falls back to the first
 * card if no better candidate exists so existing behavior remains stable.
 */
export const pickFirstReviewableCard = (
  cards: Flashcard[] | null | undefined
): Flashcard | null => {
  if (!cards?.length) return null
  return cards.find((card) => !isTutorialResidueCard(card)) || cards[0]
}

