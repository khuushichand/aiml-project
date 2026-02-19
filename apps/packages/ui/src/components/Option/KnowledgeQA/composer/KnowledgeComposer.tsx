import React from "react"
import { SearchBar } from "../SearchBar"

type KnowledgeComposerProps = {
  className?: string
  autoFocus?: boolean
  showWebToggle?: boolean
}

export function KnowledgeComposer({
  className,
  autoFocus = true,
  showWebToggle = false,
}: KnowledgeComposerProps) {
  return (
    <SearchBar
      className={className}
      autoFocus={autoFocus}
      showWebToggle={showWebToggle}
    />
  )
}
