import React from "react"
import { Tag } from "antd"

import type { Flashcard } from "@/services/flashcards"

const QUEUE_STATE_META: Record<
  Flashcard["queue_state"],
  {
    label: string
    color: string
  }
> = {
  new: {
    label: "New",
    color: "blue"
  },
  learning: {
    label: "Learning",
    color: "gold"
  },
  review: {
    label: "Review",
    color: "green"
  },
  relearning: {
    label: "Relearning",
    color: "orange"
  },
  suspended: {
    label: "Suspended",
    color: "red"
  }
}

const coerceQueueState = (
  queueState: Flashcard["queue_state"] | null | undefined
): Flashcard["queue_state"] => {
  if (queueState && queueState in QUEUE_STATE_META) {
    return queueState
  }
  return "review"
}

export const formatFlashcardQueueStateLabel = (
  queueState: Flashcard["queue_state"] | null | undefined,
  suspendedReason?: Flashcard["suspended_reason"] | null
): string => {
  const normalizedQueueState = coerceQueueState(queueState)

  if (normalizedQueueState !== "suspended") {
    return QUEUE_STATE_META[normalizedQueueState].label
  }

  if (suspendedReason === "leech") {
    return "Suspended (Leech)"
  }

  if (suspendedReason === "manual") {
    return "Suspended (Manual)"
  }

  return QUEUE_STATE_META[queueState].label
}

export interface FlashcardQueueStateBadgeProps {
  card: Pick<Flashcard, "queue_state" | "suspended_reason">
  testId?: string
}

export const FlashcardQueueStateBadge: React.FC<FlashcardQueueStateBadgeProps> = ({
  card,
  testId
}) => {
  const normalizedQueueState = coerceQueueState(card.queue_state)

  return (
    <Tag color={QUEUE_STATE_META[normalizedQueueState].color} data-testid={testId}>
      {formatFlashcardQueueStateLabel(normalizedQueueState, card.suspended_reason)}
    </Tag>
  )
}

export default FlashcardQueueStateBadge
