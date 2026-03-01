import React, { useEffect, useMemo, useRef, useState } from "react"
import { Loader2 } from "lucide-react"
import { cn } from "@/libs/utils"
import type { QueryStage } from "../types"
import { useKnowledgeQA } from "../KnowledgeQAProvider"
import { ConversationThread } from "../ConversationThread"
import { AnswerPanel } from "../AnswerPanel"
import { FollowUpInput } from "../FollowUpInput"

type AnswerWorkspaceProps = {
  queryStage: QueryStage
  className?: string
}

const STAGE_COPY: Record<QueryStage, string> = {
  idle: "Ready to search",
  searching: "Searching selected sources",
  ranking: "Ranking best evidence",
  generating: "Generating answer",
  verifying: "Verifying citations",
  complete: "Answer complete",
  error: "Search needs attention",
}

const LIVE_STAGE_COPY: Partial<Record<QueryStage, string>> = {
  searching: "Searching your selected sources.",
  ranking: "Ranking retrieved sources.",
  generating: "Generating answer.",
  verifying: "Verifying answer grounding.",
}

type TurnPreview = {
  turnNumber: number
  question: string
  answer: string | null
}

function truncatePreview(value: string, maxLength = 140): string {
  const normalized = value.trim()
  if (normalized.length <= maxLength) return normalized
  return `${normalized.slice(0, maxLength).trimEnd()}...`
}

export function AnswerWorkspace({ queryStage, className }: AnswerWorkspaceProps) {
  const { results = [], error = null, messages = [], currentThreadId = null } =
    useKnowledgeQA()
  const isActiveStage =
    queryStage !== "idle" && queryStage !== "complete" && queryStage !== "error"
  const [politeAnnouncement, setPoliteAnnouncement] = useState("")
  const [assertiveAnnouncement, setAssertiveAnnouncement] = useState("")
  const previousStageRef = useRef<QueryStage | null>(null)
  const turnPreviews = useMemo<TurnPreview[]>(
    () => {
      const previews: TurnPreview[] = []
      let turnNumber = 0

      for (let index = 0; index < messages.length; index += 1) {
        const message = messages[index]
        if (message?.role !== "user") continue

        turnNumber += 1
        const rawQuestion =
          typeof (message as { content?: unknown })?.content === "string"
            ? String((message as { content?: unknown }).content)
            : ""
        const question =
          rawQuestion.trim().length > 0
            ? truncatePreview(rawQuestion)
            : `Question ${turnNumber}`

        let answer: string | null = null
        for (let candidateIndex = index + 1; candidateIndex < messages.length; candidateIndex += 1) {
          const candidate = messages[candidateIndex]
          if (candidate?.role === "user") break
          if (candidate?.role !== "assistant") continue
          const rawAnswer =
            typeof (candidate as { content?: unknown })?.content === "string"
              ? String((candidate as { content?: unknown }).content)
              : ""
          answer = rawAnswer.trim().length > 0 ? truncatePreview(rawAnswer) : null
          break
        }

        previews.push({
          turnNumber,
          question,
          answer,
        })
      }

      return previews
    },
    [messages]
  )
  const displayedTurnCount = turnPreviews.length
  const priorTurnPreviews = useMemo(
    () => (turnPreviews.length > 1 ? turnPreviews.slice(0, -1) : []),
    [turnPreviews]
  )
  const hasThreadContext = Boolean(currentThreadId) || displayedTurnCount > 0
  const contextSummary = useMemo(() => {
    if (priorTurnPreviews.length === 0) {
      return "The next question starts from the current answer context."
    }
    if (priorTurnPreviews.length === 1) {
      return "Using context from turn 1."
    }
    return `Using context from turns 1-${priorTurnPreviews.length}.`
  }, [priorTurnPreviews.length])

  useEffect(() => {
    if (queryStage === previousStageRef.current) return
    previousStageRef.current = queryStage

    if (queryStage === "complete") {
      const count = results.length
      setPoliteAnnouncement(
        `Search complete. ${count} source${count === 1 ? "" : "s"} found.`
      )
      return
    }
    if (queryStage === "error") {
      return
    }
    const stageMessage = LIVE_STAGE_COPY[queryStage]
    if (stageMessage) {
      setPoliteAnnouncement(stageMessage)
    }
  }, [queryStage, results.length])

  useEffect(() => {
    if (!error) return
    setAssertiveAnnouncement(`Search error. ${error}`)
  }, [error])

  return (
    <div className={cn("space-y-6", className)}>
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {politeAnnouncement}
      </div>
      <div className="sr-only" aria-live="assertive" aria-atomic="true">
        {assertiveAnnouncement}
      </div>

      {isActiveStage ? (
        <div className="rounded-lg border border-border bg-muted/20 px-3 py-2 text-sm text-text-muted">
          <span className="inline-flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            {STAGE_COPY[queryStage]}
          </span>
        </div>
      ) : null}

      {hasThreadContext ? (
        <div className="rounded-lg border border-border bg-surface/70 px-3 py-2 text-xs text-text-muted">
          <p className="font-medium text-text">
            Conversation • {displayedTurnCount} turn
            {displayedTurnCount === 1 ? "" : "s"}
          </p>
          <p className="mt-1">{contextSummary}</p>
          {priorTurnPreviews.length > 0 ? (
            <details className="mt-2 rounded-md border border-border bg-muted/20 px-2 py-1.5">
              <summary className="cursor-pointer text-[11px] font-medium text-text">
                Context previews ({priorTurnPreviews.length})
              </summary>
              <div className="mt-2 space-y-2">
                {priorTurnPreviews.slice(-3).map((turn) => (
                  <article
                    key={`context-preview-${turn.turnNumber}`}
                    className="rounded bg-surface px-2 py-1.5"
                  >
                    <p className="text-[11px] font-medium text-text">
                      Turn {turn.turnNumber}
                    </p>
                    <p className="mt-1 text-[11px] leading-relaxed">
                      <span className="font-medium text-text">Q:</span>{" "}
                      {turn.question}
                    </p>
                    <p className="mt-1 text-[11px] leading-relaxed">
                      <span className="font-medium text-text">A:</span>{" "}
                      {turn.answer || "No answer recorded."}
                    </p>
                  </article>
                ))}
                {priorTurnPreviews.length > 3 ? (
                  <p className="text-[11px] text-text-muted">
                    Showing 3 of {priorTurnPreviews.length} prior turns.
                  </p>
                ) : null}
              </div>
            </details>
          ) : null}
        </div>
      ) : null}

      <ConversationThread />
      <AnswerPanel />
      <FollowUpInput />
    </div>
  )
}
