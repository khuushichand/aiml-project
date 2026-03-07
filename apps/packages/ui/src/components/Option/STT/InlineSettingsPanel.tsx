import React from "react"

export interface SttLocalSettings {
  language?: string
  task?: string
  responseFormat?: string
  temperature?: number
  prompt?: string
  timestampGranularities?: string
  useSegmentation?: boolean
  segK?: number
  segMinSegmentSize?: number
  segLambdaBalance?: number
  segUtteranceExpansionWidth?: number
  segEmbeddingsProvider?: string
  segEmbeddingsModel?: string
}

export interface InlineSettingsPanelProps {
  onChange: (settings: SttLocalSettings | null) => void
}

/** Stub - replaced by Task 6 implementation */
export const InlineSettingsPanel: React.FC<InlineSettingsPanelProps> = () => {
  return <div>InlineSettingsPanel placeholder</div>
}
