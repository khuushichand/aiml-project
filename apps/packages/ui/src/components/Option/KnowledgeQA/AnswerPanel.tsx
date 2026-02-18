/**
 * AnswerPanel - Displays generated answer with inline citations
 */

import React, { useEffect, useMemo, useState } from "react"
import { Sparkles, AlertCircle, Loader2, ThumbsUp, ThumbsDown } from "lucide-react"
import { useKnowledgeQA } from "./KnowledgeQAProvider"
import { cn } from "@/lib/utils"
import { getFeedbackSessionId, submitExplicitFeedback } from "@/services/feedback"
import { useAntdMessage } from "@/hooks/useAntdMessage"
import { useNavigate } from "react-router-dom"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import {
  buildKnowledgeQaWorkspacePrefill,
  queueWorkspacePlaygroundPrefill,
} from "@/utils/workspace-playground-prefill"
import { trackKnowledgeQaSearchMetric } from "@/utils/knowledge-qa-search-metrics"
import { remarkCitationLinks } from "./answerMarkdown"

type AnswerPanelProps = {
  className?: string
}

const LONG_ANSWER_WORD_THRESHOLD = 1000

type ErrorPresentation = {
  title: string
  guidance: string
}

const classifyErrorMessage = (rawMessage: string): ErrorPresentation => {
  const message = rawMessage.trim()
  if (/timed out|timeout/i.test(message)) {
    return {
      title: "Search timed out",
      guidance: "Try the Fast preset or reduce the scope of your query.",
    }
  }
  if (/cannot reach server|network|offline|connection/i.test(message)) {
    return {
      title: "Cannot reach server",
      guidance: "Check your connection and server status, then try again.",
    }
  }
  if (/no relevant documents|no results/i.test(message)) {
    return {
      title: "No relevant documents found",
      guidance: "Try broader keywords or verify your sources are indexed.",
    }
  }
  return {
    title: "Search failed",
    guidance: "Try adjusting your query or settings and run the search again.",
  }
}

export function AnswerPanel({ className }: AnswerPanelProps) {
  const {
    answer,
    citations,
    isSearching,
    error,
    scrollToSource,
    results,
    searchDetails,
    query = "",
    currentThreadId = null,
    messages = [],
    setSettingsPanelOpen,
    preset,
    settings,
    rerunWithTokenLimit,
  } = useKnowledgeQA()
  const [isExpanded, setIsExpanded] = useState(false)
  const [answerFeedback, setAnswerFeedback] = useState<"up" | "down" | null>(null)
  const [answerFeedbackSubmitting, setAnswerFeedbackSubmitting] = useState(false)
  const [answerFeedbackError, setAnswerFeedbackError] = useState<string | null>(null)
  const [pendingFeedbackThumb, setPendingFeedbackThumb] = useState<"up" | "down" | null>(
    null
  )
  const [workspaceHandoffPending, setWorkspaceHandoffPending] = useState(false)
  const [answerLengthAction, setAnswerLengthAction] = useState<"shorter" | "longer" | null>(
    null
  )
  const [copiedAnswer, setCopiedAnswer] = useState(false)
  const [loadingElapsedSeconds, setLoadingElapsedSeconds] = useState(0)
  const messageApi = useAntdMessage()
  const navigate = useNavigate()

  // Get cited indices for highlighting
  const citedIndices = useMemo(() => citations.map((c) => c.index), [citations])
  const latestAssistantMessageId = useMemo(() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      if (messages[index]?.role === "assistant") {
        return messages[index].id
      }
    }
    return null
  }, [messages])
  const answerWordCount = useMemo(() => {
    if (!answer) return 0
    return answer.trim().split(/\s+/).filter(Boolean).length
  }, [answer])
  const isLongAnswer = answerWordCount > LONG_ANSWER_WORD_THRESHOLD

  useEffect(() => {
    setIsExpanded(false)
    setAnswerFeedback(null)
    setAnswerFeedbackError(null)
    setPendingFeedbackThumb(null)
  }, [answer])

  useEffect(() => {
    if (!isSearching) {
      setLoadingElapsedSeconds(0)
      return
    }

    setLoadingElapsedSeconds(0)
    const intervalId = window.setInterval(() => {
      setLoadingElapsedSeconds((prev) => prev + 1)
    }, 1000)

    return () => window.clearInterval(intervalId)
  }, [isSearching])

  useEffect(() => {
    if (!copiedAnswer) return
    const timeout = window.setTimeout(() => setCopiedAnswer(false), 2000)
    return () => window.clearTimeout(timeout)
  }, [copiedAnswer])

  const handleCitationClick = (index: number) => {
    scrollToSource(index - 1) // Convert from 1-based to 0-based
  }

  const handleSubmitAnswerFeedback = async (thumb: "up" | "down") => {
    setAnswerFeedbackSubmitting(true)
    setPendingFeedbackThumb(thumb)
    setAnswerFeedbackError(null)
    try {
      await submitExplicitFeedback({
        conversation_id: currentThreadId || undefined,
        message_id: latestAssistantMessageId || undefined,
        query: query?.trim() || undefined,
        feedback_type: "helpful",
        helpful: thumb === "up",
        feedback_id: searchDetails?.feedbackId || undefined,
        session_id: getFeedbackSessionId(),
      })
      void trackKnowledgeQaSearchMetric({
        type: "answer_feedback_submit",
        helpful: thumb === "up",
      })
      setAnswerFeedback(thumb)
      messageApi.open({
        type: "success",
        content: "Feedback submitted.",
        duration: 2,
      })
    } catch (submissionError) {
      const detail =
        submissionError instanceof Error && submissionError.message
          ? submissionError.message
          : "Unable to submit feedback right now."
      setAnswerFeedbackError(detail)
      messageApi.open({
        type: "error",
        content: "Feedback could not be sent. You can retry.",
        duration: 3,
      })
    } finally {
      setAnswerFeedbackSubmitting(false)
    }
  }

  const renderCitationButton = (citationNum: number) => {
    const isCited = citedIndices.includes(citationNum)
    return (
      <button
        onClick={() => handleCitationClick(citationNum)}
        aria-label={`Jump to source ${citationNum}`}
        className={cn(
          "inline-flex items-center justify-center",
          "min-w-8 h-8 px-2 mx-0.5 sm:min-w-[1.5rem] sm:h-5 sm:px-1.5",
          "text-sm sm:text-xs font-medium rounded",
          "transition-colors duration-200",
          isCited
            ? "bg-primary text-white dark:text-slate-900 hover:brightness-105"
            : "bg-surface2 text-text-muted border border-border hover:bg-muted hover:text-text"
        )}
        title={`Jump to source ${citationNum}`}
      >
        {citationNum}
      </button>
    )
  }

  const handleOpenInWorkspace = async () => {
    if (workspaceHandoffPending) return

    setWorkspaceHandoffPending(true)
    try {
      const payload = buildKnowledgeQaWorkspacePrefill({
        threadId: currentThreadId,
        query,
        answer,
        citations: citations.map((citation) => citation.index),
        results,
      })
      await queueWorkspacePlaygroundPrefill(payload)
      void trackKnowledgeQaSearchMetric({
        type: "workspace_handoff",
        source_count: results.length,
      })
      navigate("/workspace-playground")
    } catch (error) {
      console.error("Failed to open workspace with Knowledge QA context:", error)
      messageApi.open({
        type: "error",
        content: "Unable to open Workspace right now.",
        duration: 3,
      })
    } finally {
      setWorkspaceHandoffPending(false)
    }
  }

  const handleCopyAnswer = async () => {
    if (!answer) return
    try {
      await navigator.clipboard.writeText(answer)
      setCopiedAnswer(true)
      messageApi.open({
        type: "success",
        content: "Answer copied.",
        duration: 2,
      })
    } catch {
      messageApi.open({
        type: "error",
        content: "Unable to copy answer.",
        duration: 3,
      })
    }
  }

  const handleAdjustAnswerLength = async (action: "shorter" | "longer") => {
    if (!query?.trim() || isSearching) return
    const baseTokens =
      typeof settings?.max_generation_tokens === "number"
        ? settings.max_generation_tokens
        : 800
    const nextLimit =
      action === "shorter"
        ? Math.max(200, Math.round(baseTokens * 0.6))
        : Math.min(4000, Math.round(baseTokens * 1.5))

    setAnswerLengthAction(action)
    try {
      await rerunWithTokenLimit(nextLimit)
    } finally {
      setAnswerLengthAction(null)
    }
  }

  const loadingStageLabel = useMemo(() => {
    if (loadingElapsedSeconds < 5) return "Searching documents..."
    if (loadingElapsedSeconds < 10) return "Reranking results..."
    if (loadingElapsedSeconds < 20) return "Generating answer..."
    return "Verifying citations..."
  }, [loadingElapsedSeconds])

  const presetLatencyHint = useMemo(() => {
    if (preset === "fast") {
      return "Fast preset usually completes in a few seconds."
    }
    if (preset === "balanced") {
      return "Balanced preset typically completes within about 10 seconds."
    }
    if (preset === "thorough") {
      return "Thorough preset may take up to 30 seconds."
    }
    return "Custom preset timing varies with your settings."
  }, [preset])

  // Loading state
  if (isSearching && !answer) {
    return (
      <div className={cn("p-6 rounded-xl bg-muted/30 border border-border", className)}>
        <div className="flex items-center gap-3">
          <Loader2 className="w-5 h-5 animate-spin text-primary" />
          <div>
            <p className="font-medium">
              {loadingStageLabel}{" "}
              {loadingElapsedSeconds > 0 && (
                <span className="text-text-muted">({loadingElapsedSeconds}s)</span>
              )}
            </p>
            <p className="text-sm text-text-muted">
              {presetLatencyHint}
            </p>
          </div>
        </div>
      </div>
    )
  }

  // Error state
  if (error) {
    const errorPresentation = classifyErrorMessage(error)
    return (
      <div className={cn("p-6 rounded-xl bg-danger/10 border border-danger/20", className)}>
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-danger mt-0.5" />
          <div>
            <p className="font-medium text-danger">{errorPresentation.title}</p>
            <p className="text-sm text-text-muted mt-1">{error}</p>
            <p className="text-sm text-text-muted mt-1">{errorPresentation.guidance}</p>
          </div>
        </div>
      </div>
    )
  }

  // No answer yet
  if (!answer) {
    // Show empty state only if we have no results either
    if (results.length === 0) {
      return null
    }

    // Results but no generated answer
    return (
      <div className={cn("p-6 rounded-xl bg-muted/30 border border-border", className)}>
        <div className="flex items-start gap-3">
          <Sparkles className="w-5 h-5 text-text-muted mt-0.5" />
          <div>
            <p className="text-text-muted">
              Found {results.length} relevant source{results.length !== 1 ? "s" : ""}.
              Enable answer generation in settings to get a synthesized response.
            </p>
            <button
              type="button"
              onClick={() => setSettingsPanelOpen(true)}
              className="mt-2 inline-flex items-center rounded-md border border-primary/30 bg-primary/10 px-2 py-1 text-xs font-medium text-primary hover:bg-primary/15 transition-colors"
            >
              Enable in Settings
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Answer with citations
  return (
    <div className={cn("rounded-xl bg-gradient-to-br from-primary/5 to-primary/10 border border-primary/20", className)}>
      {/* Header */}
      <div className="flex items-center gap-2 px-6 py-3 border-b border-primary/10">
        <Sparkles className="w-4 h-4 text-primary" />
        <span className="font-medium text-sm">AI Answer</span>
        {isSearching && (
          <span className="text-xs text-text-muted">Streaming...</span>
        )}
        {searchDetails?.webFallbackTriggered && (
          <span className="inline-flex items-center rounded-md border border-primary/30 bg-primary/10 px-2 py-0.5 text-xs text-primary">
            Includes web sources
            {searchDetails.webFallbackEngine
              ? ` (${searchDetails.webFallbackEngine})`
              : ""}
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              void handleCopyAnswer()
            }}
            className="rounded-md border px-2 py-1 text-xs transition-colors border-border text-text-muted hover:bg-muted hover:text-text"
          >
            {copiedAnswer ? "Copied" : "Copy answer"}
          </button>
          <button
            type="button"
            onClick={() => {
              void handleOpenInWorkspace()
            }}
            disabled={workspaceHandoffPending}
            className={cn(
              "rounded-md border px-2 py-1 text-xs transition-colors",
              "border-border text-text-muted hover:bg-muted hover:text-text",
              workspaceHandoffPending && "opacity-60 cursor-not-allowed"
            )}
          >
            {workspaceHandoffPending ? "Opening..." : "Open in Workspace"}
          </button>
          {citations.length > 0 && (
            <span className="text-xs text-text-muted">
              {citations.length} citation{citations.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>
      </div>

      {/* Answer content */}
      <div className="p-6">
        {citations.length > 0 ? (
          <p id="knowledge-answer-citation-guidance" className="sr-only">
            This answer includes inline citation buttons. Press Tab to move between
            citation controls and source links.
          </p>
        ) : null}
        <div
          data-testid="knowledge-answer-content"
          aria-describedby={
            citations.length > 0 ? "knowledge-answer-citation-guidance" : undefined
          }
          className={cn(
            "prose prose-sm dark:prose-invert max-w-none",
            isLongAnswer && !isExpanded && "relative max-h-[28rem] overflow-hidden"
          )}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkCitationLinks]}
            components={{
              a({ href, children, ...props }) {
                const citationMatch =
                  typeof href === "string"
                    ? href.match(/^citation:\/\/(\d+)$/)
                    : null
                const childText =
                  typeof children === "string"
                    ? children
                    : Array.isArray(children) && children.length === 1
                      ? typeof children[0] === "string"
                        ? children[0]
                        : null
                      : null
                const childCitationMatch =
                  typeof childText === "string"
                    ? childText.match(/^\[(\d+)\]$/)
                    : null
                const citationNum = citationMatch
                  ? Number.parseInt(citationMatch[1], 10)
                  : childCitationMatch
                    ? Number.parseInt(childCitationMatch[1], 10)
                    : NaN
                if (Number.isFinite(citationNum)) {
                  return renderCitationButton(citationNum)
                }
                return (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                    {...props}
                  >
                    {children}
                  </a>
                )
              },
              code({ className: codeClassName, children, ...props }) {
                const isInline = !String(codeClassName || "").includes("language-")
                if (isInline) {
                  return (
                    <code
                      className="rounded bg-muted px-1 py-0.5 text-[0.9em]"
                      {...props}
                    >
                      {children}
                    </code>
                  )
                }
                return (
                  <code className={codeClassName} {...props}>
                    {children}
                  </code>
                )
              },
              pre({ children, ...props }) {
                return (
                  <pre
                    className="overflow-x-auto rounded-md border border-border bg-surface2/70 p-3"
                    {...props}
                  >
                    {children}
                  </pre>
                )
              },
              table({ children, ...props }) {
                return (
                  <table className="block overflow-x-auto text-sm" {...props}>
                    {children}
                  </table>
                )
              },
              p({ children, ...props }) {
                return (
                  <p className="leading-relaxed whitespace-pre-wrap" {...props}>
                    {children}
                  </p>
                )
              },
            }}
          >
            {answer}
          </ReactMarkdown>
          {isLongAnswer && !isExpanded && (
            <div className="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-primary/10 to-transparent" />
          )}
        </div>
        {isLongAnswer && (
          <button
            type="button"
            onClick={() => setIsExpanded((prev) => !prev)}
            className="mt-3 text-sm font-medium text-primary hover:text-primaryStrong transition-colors"
          >
            {isExpanded ? "Show less" : "Show full answer"}
          </button>
        )}
      </div>

      {/* Citation summary + feedback */}
      {
        <div className="px-6 py-3 bg-muted/20 border-t border-primary/10">
          {citations.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="text-text-muted">Sources:</span>
              {citations.map((citation) => (
                <button
                  key={citation.index}
                  onClick={() => handleCitationClick(citation.index)}
                  aria-label={`Jump to source ${citation.index}`}
                  className="inline-flex h-8 min-w-8 items-center justify-center rounded border border-border bg-surface px-2 text-sm text-text-muted transition-colors hover:bg-surface2 hover:text-text sm:h-6 sm:min-w-[1.5rem] sm:px-1.5 sm:text-xs"
                >
                  [{citation.index}]
                </button>
              ))}
            </div>
          )}
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
            {searchDetails?.tokensUsed != null && (
              <span className="text-text-muted">
                Used ~{Math.round(searchDetails.tokensUsed).toLocaleString()} tokens
              </span>
            )}
            {searchDetails?.estimatedCostUsd != null && (
              <span className="text-text-muted">
                Estimated cost ${searchDetails.estimatedCostUsd.toFixed(4)}
              </span>
            )}
            <span className="ml-auto text-text-muted">Was this answer helpful?</span>
            <button
              type="button"
              onClick={() => {
                void handleSubmitAnswerFeedback("up")
              }}
              disabled={answerFeedbackSubmitting}
              aria-pressed={answerFeedback === "up"}
              className={cn(
                "inline-flex items-center gap-1 rounded-md border px-2 py-1 transition-colors",
                answerFeedback === "up"
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border text-text-muted hover:text-text hover:bg-muted",
                answerFeedbackSubmitting && "opacity-60 cursor-not-allowed"
              )}
            >
              <ThumbsUp className="w-3.5 h-3.5" />
              Helpful
            </button>
            <button
              type="button"
              onClick={() => {
                void handleSubmitAnswerFeedback("down")
              }}
              disabled={answerFeedbackSubmitting}
              aria-pressed={answerFeedback === "down"}
              className={cn(
                "inline-flex items-center gap-1 rounded-md border px-2 py-1 transition-colors",
                answerFeedback === "down"
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border text-text-muted hover:text-text hover:bg-muted",
                answerFeedbackSubmitting && "opacity-60 cursor-not-allowed"
              )}
            >
              <ThumbsDown className="w-3.5 h-3.5" />
              Needs work
            </button>
            {answerFeedbackError && pendingFeedbackThumb && (
              <button
                type="button"
                onClick={() => {
                  void handleSubmitAnswerFeedback(pendingFeedbackThumb)
                }}
                className="text-primary underline hover:opacity-80"
              >
                Retry
              </button>
            )}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
            <span className="text-text-muted">Need a different answer length?</span>
            <button
              type="button"
              onClick={() => {
                void handleAdjustAnswerLength("shorter")
              }}
              disabled={isSearching || answerLengthAction !== null}
              className="rounded-md border border-border px-2 py-1 text-text-muted hover:bg-muted hover:text-text disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {answerLengthAction === "shorter" ? "Summarizing..." : "Summarize"}
            </button>
            <button
              type="button"
              onClick={() => {
                void handleAdjustAnswerLength("longer")
              }}
              disabled={isSearching || answerLengthAction !== null}
              className="rounded-md border border-border px-2 py-1 text-text-muted hover:bg-muted hover:text-text disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {answerLengthAction === "longer" ? "Expanding..." : "Show more"}
            </button>
          </div>
        </div>
      }
    </div>
  )
}
