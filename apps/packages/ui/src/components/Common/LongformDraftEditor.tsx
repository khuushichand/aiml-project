import React from "react"
import { Card, Input, Typography } from "antd"

const { Text } = Typography

type LongformDraftEditorProps = {
  outline: string
  transcript: string
  onOutlineChange: (value: string) => void
  onTranscriptChange: (value: string) => void
  outlineError?: string | null
  transcriptError?: string | null
  preview?: string
}

export const LongformDraftEditor: React.FC<LongformDraftEditorProps> = ({
  outline,
  transcript,
  onOutlineChange,
  onTranscriptChange,
  outlineError,
  transcriptError,
  preview
}) => {
  return (
    <Card size="small">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Text strong>Long-form draft</Text>
        <Text type="secondary" className="text-xs">
          Edit outline and transcript before synthesis.
        </Text>
      </div>
      <div className="mt-3 grid gap-4 lg:grid-cols-2">
        <div className="space-y-2">
          <label className="text-xs text-text">Outline</label>
          <Input.TextArea
            value={outline}
            onChange={(e) => onOutlineChange(e.target.value)}
            autoSize={{ minRows: 6, maxRows: 12 }}
            placeholder="Outline key points and sections"
          />
          {outlineError && (
            <Text type="danger" className="text-xs">
              {outlineError}
            </Text>
          )}
        </div>
        <div className="space-y-2">
          <label className="text-xs text-text">Transcript draft</label>
          <Input.TextArea
            value={transcript}
            onChange={(e) => onTranscriptChange(e.target.value)}
            autoSize={{ minRows: 6, maxRows: 12 }}
            placeholder="Write the full narration here"
          />
          {transcriptError && (
            <Text type="danger" className="text-xs">
              {transcriptError}
            </Text>
          )}
        </div>
      </div>
      {preview && (
        <div className="mt-4 rounded-md border border-border p-3">
          <Text className="text-xs text-text-subtle">Preview</Text>
          <div className="mt-1 text-sm whitespace-pre-wrap">{preview}</div>
        </div>
      )}
    </Card>
  )
}
