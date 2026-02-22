import { describe, expect, it } from "vitest"
import type { Flashcard } from "@/services/flashcards"
import {
  isTutorialResidueCard,
  pickFirstReviewableCard
} from "../review-card-hygiene"

describe("review-card-hygiene", () => {
  const tutorialResidueCard: Flashcard = {
    uuid: "tutorial-card",
    front: `Sure! Here's a simple flow for creating and using flashcards effectively using the E2E (End-to-End) method:

Step 1: Identify Key Concepts
Objective: Determine the concepts you need to learn.
Action: Review your study material and highlight key terms.

Step 2: Create Flashcards
Objective: Develop a set of flashcards.
Action: Front Side: Write a question. Back Side: Write the answer.

Tips for Effective Flashcard Use`,
    back: "",
    is_cloze: false,
    ef: 2.5,
    interval_days: 0,
    repetitions: 0,
    lapses: 0,
    deleted: false,
    client_id: "test",
    version: 1,
    model_type: "basic" as const,
    reverse: false
  }

  const realCard: Flashcard = {
    ...tutorialResidueCard,
    uuid: "real-card",
    front: "What does CPU stand for?",
    back: "Central Processing Unit"
  }

  it("identifies instructional tutorial residue cards", () => {
    expect(isTutorialResidueCard(tutorialResidueCard)).toBe(true)
  })

  it("does not flag normal question-answer cards", () => {
    expect(isTutorialResidueCard(realCard)).toBe(false)
  })

  it("prefers the first reviewable card over tutorial residue", () => {
    const selected = pickFirstReviewableCard([tutorialResidueCard, realCard])
    expect(selected?.uuid).toBe("real-card")
  })

  it("falls back to the first card when no better candidate exists", () => {
    const selected = pickFirstReviewableCard([tutorialResidueCard])
    expect(selected?.uuid).toBe("tutorial-card")
  })
})
