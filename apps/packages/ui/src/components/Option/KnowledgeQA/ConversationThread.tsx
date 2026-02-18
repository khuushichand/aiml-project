/**
 * ConversationThread - Inline history of prior Q&A turns
 */

import React, { useMemo } from "react"
import { MessageSquare, Sparkles } from "lucide-react"
import { useKnowledgeQA } from "./KnowledgeQAProvider"
import { cn } from "@/lib/utils"
import type { KnowledgeQAMessage } from "./types"
import { useKnowledgeQaBranching } from "@/hooks/useFeatureFlags"

type ConversationThreadProps = {
  className?: string
}

type ConversationTurn = {
  id: string
  question: string
  answer: string | null
  sourceCount: number
  citationCount: number
  timestamp: string
}

function countInlineCitationMarkers(content: string | null | undefined): number {
  if (typeof content !== "string" || content.length === 0) return 0
  const matches = content.match(/\[(\d+)\]/g) || []
  return new Set(matches).size
}

function buildConversationTurns(messages: KnowledgeQAMessage[]): ConversationTurn[] {
  const turns: ConversationTurn[] = []

  for (let index = 0; index < messages.length; index += 1) {
    const message = messages[index]
    if (message.role !== "user") continue

    const assistantMessage = messages
      .slice(index + 1)
      .find((candidate) => candidate.role === "assistant")

    turns.push({
      id: message.id,
      question: message.content,
      answer: assistantMessage?.content || null,
      sourceCount: assistantMessage?.ragContext?.retrieved_documents?.length || 0,
      citationCount:
        assistantMessage?.ragContext?.citations?.length ||
        countInlineCitationMarkers(assistantMessage?.content),
      timestamp: message.timestamp,
    })
  }

  return turns
}

function formatTurnTimestamp(timestamp: string): string {
  const value = new Date(timestamp)
  if (Number.isNaN(value.getTime())) return ""
  return value.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
}

export function ConversationThread({ className }: ConversationThreadProps) {
  const { messages, setQuery } = useKnowledgeQA()
  const [branchingEnabled] = useKnowledgeQaBranching()

  const historicalTurns = useMemo(() => {
    const turns = buildConversationTurns(messages)
    if (turns.length <= 1) return []
    return turns.slice(0, -1)
  }, [messages])

  if (historicalTurns.length === 0) {
    return null
  }

  const handleReuseQuestion = (question: string) => {
    setQuery(question)
    const searchInput = document.getElementById("knowledge-search-input")
    if (searchInput instanceof HTMLInputElement || searchInput instanceof HTMLTextAreaElement) {
      searchInput.focus()
      searchInput.setSelectionRange(searchInput.value.length, searchInput.value.length)
    }
  }

  return (
    <section
      className={cn("rounded-xl border border-border bg-muted/20", className)}
      aria-label="Conversation thread"
    >
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
        <MessageSquare className="w-4 h-4 text-text-muted" />
        <h2 className="text-sm font-semibold">
          Conversation Thread ({historicalTurns.length} prior turn
          {historicalTurns.length === 1 ? "" : "s"})
        </h2>
      </div>

      <div className="divide-y divide-border">
        {historicalTurns.map((turn, turnIndex) => (
          <article key={turn.id} className="px-4 py-3" role="article">
            <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
              <span>Question {turnIndex + 1}</span>
              {turn.timestamp ? <span>{formatTurnTimestamp(turn.timestamp)}</span> : null}
              <span className="inline-flex items-center gap-1 rounded bg-surface px-2 py-0.5">
                <Sparkles className="w-3 h-3" />
                {turn.sourceCount} source{turn.sourceCount === 1 ? "" : "s"}
              </span>
              {turn.citationCount > 0 ? (
                <span className="inline-flex items-center gap-1 rounded bg-surface px-2 py-0.5">
                  {turn.citationCount} citation{turn.citationCount === 1 ? "" : "s"}
                </span>
              ) : null}
            </div>

            <p className="mt-2 text-sm font-medium">{turn.question}</p>

            <div className="mt-2 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => handleReuseQuestion(turn.question)}
                className="rounded-md border border-border px-2 py-1 text-xs font-medium hover:bg-muted transition-colors"
              >
                Reuse Question
              </button>
              {branchingEnabled ? (
                <button
                  type="button"
                  disabled
                  title="Branching is staged behind this feature flag and is not yet enabled in this build."
                  className="rounded-md border border-border px-2 py-1 text-xs font-medium text-text-muted opacity-60 cursor-not-allowed"
                >
                  Start Branch (Soon)
                </button>
              ) : null}
            </div>

            <details className="mt-2 group">
              <summary className="cursor-pointer text-xs text-primary hover:text-primaryStrong transition-colors">
                {turn.answer ? "Show answer" : "No answer recorded"}
              </summary>
              {turn.answer ? (
                <p className="mt-2 text-sm whitespace-pre-wrap leading-relaxed">
                  {turn.answer}
                </p>
              ) : null}
            </details>
          </article>
        ))}
      </div>
    </section>
  )
}
