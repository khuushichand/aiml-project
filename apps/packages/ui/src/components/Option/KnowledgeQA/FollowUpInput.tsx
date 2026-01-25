/**
 * FollowUpInput - Input for asking follow-up questions
 */

import React, { useCallback, useState } from "react"
import { SendHorizontal, Plus, Loader2 } from "lucide-react"
import { useKnowledgeQA } from "./KnowledgeQAProvider"
import { cn } from "@/lib/utils"

type FollowUpInputProps = {
  className?: string
}

export function FollowUpInput({ className }: FollowUpInputProps) {
  const { askFollowUp, isSearching, createNewThread, results, answer } =
    useKnowledgeQA()
  const [input, setInput] = useState("")

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

  // Only show if we have results or an answer
  if (results.length === 0 && !answer) {
    return null
  }

  return (
    <div className={cn("border-t border-border pt-4", className)}>
      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        {/* New topic button */}
        <button
          type="button"
          onClick={handleNewTopic}
          aria-label="Start new topic"
          className="flex items-center justify-center w-10 h-10 rounded-lg border border-border hover:border-primary/30 hover:bg-muted/50 transition-colors"
          title="Start new topic"
        >
          <Plus className="w-5 h-5 text-text-muted" />
        </button>

        {/* Input */}
        <div className="relative flex-1">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a follow-up question..."
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

      <p className="mt-2 text-xs text-text-muted text-center">
        Follow-up questions maintain context. Click &quot;New Topic&quot; to start fresh.
      </p>
    </div>
  )
}
