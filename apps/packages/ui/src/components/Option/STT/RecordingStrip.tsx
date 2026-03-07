import React from "react"

export interface RecordingStripProps {
  onBlobReady: (blob: Blob, durationMs: number) => void
  onSettingsToggle: () => void
}

/** Stub - replaced by Task 4 implementation */
export const RecordingStrip: React.FC<RecordingStripProps> = () => {
  return <div>RecordingStrip placeholder</div>
}
