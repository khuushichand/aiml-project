import React from "react"
import { HistorySidebar } from "../HistorySidebar"

type HistoryPaneProps = {
  className?: string
}

export function HistoryPane({ className }: HistoryPaneProps) {
  return <HistorySidebar className={className} />
}
