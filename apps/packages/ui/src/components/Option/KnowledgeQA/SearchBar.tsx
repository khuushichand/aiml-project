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

  // Rotate placeholder examples
  useEffect(() => {
    const interval = setInterval(() => {
      setPlaceholderIndex((prev) => (prev + 1) % EXAMPLE_QUERIES.length)
    }, 4000)
    return () => clearInterval(interval)
  }, [])

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
            <Search className="w-5 h-5 text-muted-foreground group-focus-within:text-primary transition-colors" />
          )}
        </div>

        {/* Input */}
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={EXAMPLE_QUERIES[placeholderIndex]}
          disabled={isSearching}
          className={cn(
            "w-full pl-12 pr-20 py-4 text-lg",
            "bg-background border border-border rounded-xl",
            "focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent",
            "placeholder:text-muted-foreground/60",
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
            className="absolute right-14 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-foreground transition-colors"
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
            "bg-primary text-primary-foreground",
            "font-medium text-sm",
            "transition-all duration-200",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            "hover:bg-primary/90"
          )}
        >
          {isSearching ? "..." : "Ask"}
        </button>
      </div>

      {/* Keyboard hint */}
      <div className="flex justify-center mt-2 text-xs text-muted-foreground">
        <span>
          Press <kbd className="px-1.5 py-0.5 bg-muted rounded font-mono">/</kbd> to focus,{" "}
          <kbd className="px-1.5 py-0.5 bg-muted rounded font-mono">Cmd+K</kbd> for new search
        </span>
      </div>
    </form>
  )
}
