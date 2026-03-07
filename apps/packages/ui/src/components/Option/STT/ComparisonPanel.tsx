import React from "react"

export interface ComparisonPanelProps {
  blob: Blob | null
  availableModels: string[]
  selectedModels?: string[]
  sttOptions: Record<string, unknown>
  onSaveToNotes: (text: string, model: string) => void
}

/** Stub - replaced by Task 5 implementation */
export const ComparisonPanel: React.FC<ComparisonPanelProps> = () => {
  return <div>ComparisonPanel placeholder</div>
}
