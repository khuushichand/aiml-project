import React from "react"

export interface SttHistoryResult {
  model: string
  text: string
  durationMs?: number
  error?: string
}

export interface SttHistoryEntry {
  id: string
  createdAt: string
  recordingId: string
  durationMs?: number
  results?: SttHistoryResult[]
}

export interface HistoryPanelProps {
  entries: SttHistoryEntry[]
  onRecompare: (entry: SttHistoryEntry) => void
  onExport: (entry: SttHistoryEntry) => void
  onDelete: (id: string) => void
  onClearAll: () => void
}

/** Stub - replaced by Task 7 implementation */
export const HistoryPanel: React.FC<HistoryPanelProps> = () => {
  return <div>HistoryPanel placeholder</div>
}
