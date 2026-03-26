import React from "react"
import { SearchBar } from "../SearchBar"

type KnowledgeComposerProps = {
  className?: string
  autoFocus?: boolean
  showWebToggle?: boolean
  widthMode?: "compact" | "wide"
}

export function KnowledgeComposer({
  className,
  autoFocus = true,
  showWebToggle = false,
  widthMode = "compact",
}: KnowledgeComposerProps) {
  return (
    <SearchBar
      className={className}
      autoFocus={autoFocus}
      showWebToggle={showWebToggle}
      widthMode={widthMode}
    />
  )
}
