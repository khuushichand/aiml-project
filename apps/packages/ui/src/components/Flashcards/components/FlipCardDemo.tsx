/**
 * FlipCardDemo — A standalone flip-card component for demo mode.
 *
 * Shows sample flashcards without requiring a server connection or SRS.
 * Users can flip cards and navigate between them to experience the
 * flashcard study flow before setting up a server.
 */

import React, { useState, useCallback } from "react"
import { Button, Space, Tag } from "antd"
import { ChevronLeft, ChevronRight, RotateCcw } from "lucide-react"

type DemoCard = {
  front: string
  back: string
  deck: string
}

const DEMO_CARDS: DemoCard[] = [
  {
    front: "What is spaced repetition?",
    back: "A learning technique that reviews material at increasing intervals based on how well you remember it. Cards you know well are shown less often; cards you struggle with are shown more frequently.",
    deck: "Study Techniques",
  },
  {
    front: "What does RAG stand for in AI?",
    back: "Retrieval-Augmented Generation — a technique that enhances LLM responses by retrieving relevant documents from a knowledge base before generating an answer.",
    deck: "AI Concepts",
  },
  {
    front: "What is the difference between a podcast and an audiobook?",
    back: "Podcasts are episodic audio series, often conversational, released on a schedule. Audiobooks are narrated versions of written books, typically consumed as a complete work.",
    deck: "Media Literacy",
  },
  {
    front: "What is an API key?",
    back: "A unique identifier used to authenticate requests to an API. Like a password for software — it proves your application is authorized to access the service.",
    deck: "Developer Basics",
  },
  {
    front: "What is the Feynman Technique?",
    back: "A learning method: (1) Choose a concept, (2) Explain it simply as if teaching a child, (3) Identify gaps in your explanation, (4) Review and simplify further.",
    deck: "Study Techniques",
  },
]

export const FlipCardDemo: React.FC = () => {
  const [cardIndex, setCardIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)

  const card = DEMO_CARDS[cardIndex]

  const handleFlip = useCallback(() => setFlipped((f) => !f), [])
  const handleNext = useCallback(() => {
    setCardIndex((i) => (i + 1) % DEMO_CARDS.length)
    setFlipped(false)
  }, [])
  const handlePrev = useCallback(() => {
    setCardIndex((i) => (i - 1 + DEMO_CARDS.length) % DEMO_CARDS.length)
    setFlipped(false)
  }, [])

  return (
    <div className="mx-auto max-w-md">
      <div className="mb-3 flex items-center justify-between text-xs text-text-muted">
        <Tag>{card.deck}</Tag>
        <span>
          {cardIndex + 1} / {DEMO_CARDS.length}
        </span>
      </div>

      <button
        type="button"
        onClick={handleFlip}
        className="w-full cursor-pointer rounded-xl border border-border bg-surface p-6 text-left shadow-sm transition-all hover:shadow-md focus:outline-none focus:ring-2 focus:ring-primary/40"
        aria-label={flipped ? "Show question" : "Show answer"}
      >
        <div className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-text-subtle">
          {flipped ? "Answer" : "Question"}
        </div>
        <div className="min-h-[80px] text-sm leading-relaxed text-text">
          {flipped ? card.back : card.front}
        </div>
        <div className="mt-4 text-center text-[10px] text-text-subtle">
          {flipped ? "Click to see question" : "Click to reveal answer"}
        </div>
      </button>

      <div className="mt-4 flex items-center justify-center">
        <Space>
          <Button
            size="small"
            icon={<ChevronLeft className="h-3.5 w-3.5" />}
            onClick={handlePrev}
            aria-label="Previous card"
          />
          <Button
            size="small"
            icon={<RotateCcw className="h-3.5 w-3.5" />}
            onClick={handleFlip}
            aria-label="Flip card"
          >
            Flip
          </Button>
          <Button
            size="small"
            icon={<ChevronRight className="h-3.5 w-3.5" />}
            onClick={handleNext}
            aria-label="Next card"
          />
        </Space>
      </div>

      <p className="mt-4 text-center text-[11px] text-text-muted">
        This is a preview. Connect a server to create your own decks with spaced repetition.
      </p>
    </div>
  )
}

export default FlipCardDemo
