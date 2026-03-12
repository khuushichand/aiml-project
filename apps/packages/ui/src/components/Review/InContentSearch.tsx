import React from "react"
import { Input, Button } from "antd"
import { ChevronUp, ChevronDown, X } from "lucide-react"

interface InContentSearchProps {
  /** The full text content to search within */
  content: string
  /** Called when search query changes (for highlighting in ContentRenderer) */
  onQueryChange: (query: string) => void
  /** Whether the search bar is visible */
  visible: boolean
  /** Called to close the search bar */
  onClose: () => void
  /** Translation function */
  t: (key: string, fallback: string) => string
}

export interface InContentSearchMatch {
  index: number
  start: number
  end: number
}

function findMatches(content: string, query: string): InContentSearchMatch[] {
  if (!query || query.trim().length === 0) return []
  const needle = query.toLowerCase()
  const hay = content.toLowerCase()
  const results: InContentSearchMatch[] = []
  let pos = 0
  let idx = 0
  while (pos < hay.length) {
    const found = hay.indexOf(needle, pos)
    if (found === -1) break
    results.push({ index: idx, start: found, end: found + needle.length })
    pos = found + 1
    idx++
  }
  return results
}

/**
 * In-content search bar with match count, prev/next navigation.
 * Designed to sit at the top of the reading pane content area.
 */
export const InContentSearch: React.FC<InContentSearchProps> = ({
  content,
  onQueryChange,
  visible,
  onClose,
  t
}) => {
  const [query, setQuery] = React.useState("")
  const [currentMatch, setCurrentMatch] = React.useState(0)
  const inputRef = React.useRef<HTMLInputElement>(null)

  const matches = React.useMemo(() => findMatches(content, query), [content, query])

  React.useEffect(() => {
    if (visible && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [visible])

  React.useEffect(() => {
    onQueryChange(query)
  }, [query, onQueryChange])

  React.useEffect(() => {
    if (currentMatch >= matches.length && matches.length > 0) {
      setCurrentMatch(0)
    }
  }, [matches.length, currentMatch])

  const goNext = React.useCallback(() => {
    if (matches.length === 0) return
    setCurrentMatch((prev) => (prev + 1) % matches.length)
  }, [matches.length])

  const goPrev = React.useCallback(() => {
    if (matches.length === 0) return
    setCurrentMatch((prev) => (prev - 1 + matches.length) % matches.length)
  }, [matches.length])

  const handleClose = React.useCallback(() => {
    setQuery("")
    onQueryChange("")
    onClose()
  }, [onClose, onQueryChange])

  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault()
        handleClose()
      } else if (e.key === "Enter") {
        e.preventDefault()
        if (e.shiftKey) goPrev()
        else goNext()
      }
    },
    [handleClose, goNext, goPrev]
  )

  if (!visible) return null

  return (
    <div
      className="flex items-center gap-2 px-2 py-1 border-b border-border bg-surface2/50"
      data-testid="in-content-search"
    >
      <Input
        ref={inputRef as any}
        size="small"
        placeholder={t("mediaPage.searchInContent", "Search in content...")}
        aria-label={t("mediaPage.searchInContent", "Search in content...") as string}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        className="max-w-[20rem]"
      />
      <span className="text-xs text-text-muted whitespace-nowrap" data-testid="in-content-search-count">
        {query.trim().length > 0
          ? matches.length > 0
            ? `${currentMatch + 1}/${matches.length}`
            : t("mediaPage.noMatches", "No matches")
          : ""}
      </span>
      <Button
        size="small"
        type="text"
        icon={<ChevronUp className="w-3.5 h-3.5" />}
        onClick={goPrev}
        disabled={matches.length === 0}
        aria-label={t("mediaPage.prevMatch", "Previous match") as string}
      />
      <Button
        size="small"
        type="text"
        icon={<ChevronDown className="w-3.5 h-3.5" />}
        onClick={goNext}
        disabled={matches.length === 0}
        aria-label={t("mediaPage.nextMatch", "Next match") as string}
      />
      <Button
        size="small"
        type="text"
        icon={<X className="w-3.5 h-3.5" />}
        onClick={handleClose}
        aria-label={t("mediaPage.closeSearch", "Close search") as string}
      />
    </div>
  )
}

export { findMatches }
