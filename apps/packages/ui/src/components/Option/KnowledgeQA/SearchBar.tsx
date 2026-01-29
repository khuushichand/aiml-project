/**
 * SearchBar - Prominent search input for Knowledge QA
 */

import React, { useCallback, useEffect, useRef, useState } from "react"
import { Search, Sparkles, X } from "lucide-react"
import { useKnowledgeQA } from "./KnowledgeQAProvider"
import { cn } from "@/lib/utils"

const EXAMPLE_QUERIES = [
  "What are the key findings from the research?",
  "Summarize the main arguments in this document",
  "What are the pros and cons discussed?",
  "Explain the methodology used in this study",
]

type SearchBarProps = {
  className?: string
  autoFocus?: boolean
}

export function SearchBar({ className, autoFocus = true }: SearchBarProps) {
  const { query, setQuery, search, isSearching, clearResults } = useKnowledgeQA()
  const inputRef = useRef<HTMLInputElement>(null)
  const [placeholderIndex, setPlaceholderIndex] = useState(0)
  const [isFocused, setIsFocused] = useState(false)
  const [cycleCount, setCycleCount] = useState(0)
  const MAX_CYCLES = 3 // Stop rotating after 3 full cycles

  // Rotate placeholder examples - slower interval, pause on focus, stop after cycles
  useEffect(() => {
    // Stop rotation if focused, has query, or exceeded max cycles
    if (isFocused || query || cycleCount >= MAX_CYCLES) return

    const interval = setInterval(() => {
      setPlaceholderIndex((prev) => {
        const next = (prev + 1) % EXAMPLE_QUERIES.length
        // Increment cycle count when we loop back to start
        if (next === 0) {
          setCycleCount((c) => c + 1)
        }
        return next
      })
    }, 8000) // 8 seconds instead of 4 for better readability

    return () => clearInterval(interval)
  }, [isFocused, query, cycleCount])

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Focus search bar on "/" key
      if (e.key === "/" && !e.metaKey && !e.ctrlKey) {
        const target = e.target as HTMLElement
        if (target.tagName !== "INPUT" && target.tagName !== "TEXTAREA") {
          e.preventDefault()
          inputRef.current?.focus()
        }
      }
      // Cmd+K for new search
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        clearResults()
        setQuery("")
        inputRef.current?.focus()
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [clearResults, setQuery])

  // Auto focus on mount
  useEffect(() => {
    if (autoFocus) {
      inputRef.current?.focus()
    }
  }, [autoFocus])

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()
      if (query.trim() && !isSearching) {
        search()
      }
    },
    [query, isSearching, search]
  )

  const handleClear = useCallback(() => {
    setQuery("")
    clearResults()
    inputRef.current?.focus()
  }, [setQuery, clearResults])

  return (
    <form onSubmit={handleSubmit} className={cn("w-full max-w-3xl mx-auto", className)}>
      <div className="relative group">
        {/* Search icon */}
        <div className="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none">
          {isSearching ? (
            <div className="animate-spin">
              <Sparkles className="w-5 h-5 text-primary" />
            </div>
          ) : (
            <Search className="w-5 h-5 text-text-muted group-focus-within:text-primary transition-colors" />
          )}
        </div>

        {/* Input */}
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder={EXAMPLE_QUERIES[placeholderIndex]}
          disabled={isSearching}
          className={cn(
            "w-full pl-12 pr-20 py-4 text-lg",
            "bg-surface border border-border rounded-xl",
            "focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent",
            "placeholder:text-text-subtle",
            "transition-all duration-200",
            "shadow-sm hover:shadow-md focus:shadow-md",
            isSearching && "opacity-75 cursor-not-allowed"
          )}
          aria-label="Search your knowledge base"
        />

        {/* Clear button */}
        {query && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute right-14 top-1/2 -translate-y-1/2 p-1 text-text-muted hover:text-text transition-colors"
            aria-label="Clear search"
          >
            <X className="w-4 h-4" />
          </button>
        )}

        {/* Submit button */}
        <button
          type="submit"
          disabled={!query.trim() || isSearching}
          className={cn(
            "absolute right-2 top-1/2 -translate-y-1/2",
            "px-4 py-2 rounded-lg",
            "bg-primary text-white",
            "font-medium text-sm",
            "transition-all duration-200",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            "hover:bg-primaryStrong"
          )}
        >
          {isSearching ? "..." : "Ask"}
        </button>
      </div>

      {/* Keyboard hint */}
      <div className="flex justify-center mt-2 text-xs text-text-muted">
        <span>
          Press <kbd className="px-1.5 py-0.5 bg-muted rounded font-mono">/</kbd> to focus,{" "}
          <kbd className="px-1.5 py-0.5 bg-muted rounded font-mono">Cmd+K</kbd> for new search
        </span>
      </div>
    </form>
  )
}
