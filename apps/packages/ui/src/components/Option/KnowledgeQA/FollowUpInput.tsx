/**
 * FollowUpInput - Input for asking follow-up questions
 */

import React, { useCallback, useState } from "react"
import { SendHorizontal, Plus, Loader2 } from "lucide-react"
import { useKnowledgeQA } from "./KnowledgeQAProvider"
import { cn } from "@/lib/utils"
import { useMobile } from "@/hooks/useMediaQuery"

type FollowUpInputProps = {
  className?: string
}

export function FollowUpInput({ className }: FollowUpInputProps) {
  const { askFollowUp, isSearching, createNewThread, results, answer } =
    useKnowledgeQA()
  const isMobile = useMobile()
  const [input, setInput] = useState("")
  const shouldShow = isSearching || results.length > 0 || Boolean(answer)
  const isQueuedState = isSearching && results.length === 0 && !answer
  const useStickyMobileLayout = isMobile

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      const trimmed = input.trim()
      if (!trimmed || isSearching) return

      await askFollowUp(trimmed)
      setInput("")
    },
    [input, isSearching, askFollowUp]
  )

  const handleNewTopic = useCallback(async () => {
    await createNewThread()
    setInput("")
  }, [createNewThread])

  if (!shouldShow) {
    return null
  }

  return (
    <>
      {useStickyMobileLayout && <div aria-hidden="true" className="h-28" />}
      <div
        data-testid={useStickyMobileLayout ? "knowledge-followup-sticky" : undefined}
        className={cn(
          useStickyMobileLayout
            ? "fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface/95 px-3 pt-2 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur supports-[backdrop-filter]:bg-surface/80"
            : "border-t border-border pt-4",
          className
        )}
      >
        <form
          onSubmit={handleSubmit}
          className={cn(
            "flex items-center gap-2",
            useStickyMobileLayout && "mx-auto max-w-4xl"
          )}
        >
          {/* New topic button */}
          <button
            type="button"
            onClick={handleNewTopic}
            aria-label="Start new topic"
            className="flex items-center gap-1.5 h-10 px-3 rounded-lg border border-border hover:border-primary/30 hover:bg-muted/50 transition-colors"
            title="Start new topic"
          >
            <Plus className="w-4 h-4 text-text-muted" />
            <span className="text-xs font-medium text-text-muted">New Topic</span>
          </button>

          {/* Input */}
          <div className="relative flex-1">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                isQueuedState
                  ? "Current search in progress..."
                  : "Ask a follow-up question..."
              }
              aria-label="Ask a follow-up question"
              disabled={isSearching}
              className={cn(
                "w-full pl-4 pr-12 py-3",
                "bg-surface border border-border rounded-lg",
                "focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent",
                "placeholder:text-text-subtle",
                "transition-all duration-200",
                isSearching && "opacity-75 cursor-not-allowed"
              )}
            />

            {/* Submit button */}
            <button
              type="submit"
              disabled={!input.trim() || isSearching}
              className={cn(
                "absolute right-2 top-1/2 -translate-y-1/2",
                "p-2 rounded-md",
                "bg-primary text-white",
                "transition-all duration-200",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                "hover:bg-primaryStrong"
              )}
            >
              {isSearching ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <SendHorizontal className="w-4 h-4" />
              )}
            </button>
          </div>
        </form>

        <p
          className={cn(
            "mt-2 text-xs text-text-muted text-center",
            useStickyMobileLayout && "mx-auto max-w-4xl"
          )}
        >
          {isQueuedState
            ? "Follow-up input unlocks when the current search completes."
            : "Follow-up questions maintain context. Click \"New Topic\" to start fresh."}
        </p>
      </div>
    </>
  )
}
