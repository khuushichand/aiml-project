import React from "react"
import { Alert } from "antd"
import { ChunkCardView } from "./ChunkCardView"
import type { Chunk } from "@/services/chunking"

interface SplitViewProps {
  pdfUrl: string | null
  chunks: Chunk[]
  highlightedIndex: number | null
  onChunkHover?: (index: number | null) => void
}

export const SplitView: React.FC<SplitViewProps> = ({
  pdfUrl,
  chunks,
  highlightedIndex,
  onChunkHover
}) => {
  if (!pdfUrl) {
    return (
      <Alert
        type="error"
        title="PDF preview is required to use split view."
        showIcon
      />
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div className="border border-surface2 rounded-md overflow-hidden min-h-[500px]">
        <iframe
          src={pdfUrl}
          title="PDF Preview"
          className="w-full h-full min-h-[500px]"
        />
      </div>
      <div className="max-h-[600px] overflow-y-auto custom-scrollbar">
        <ChunkCardView
          chunks={chunks}
          highlightedIndex={highlightedIndex}
          onChunkHover={onChunkHover}
        />
      </div>
    </div>
  )
}

export default SplitView
