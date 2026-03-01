import type { FC } from "react"
import { Card } from "antd"
import type { WritingPlaygroundPanelProps } from "./WritingPlayground.types"

export const WritingPlaygroundEditorPanel: FC<WritingPlaygroundPanelProps> = ({
  title,
  extra,
  children,
  testId = "writing-playground-editor-panel"
}) => {
  return (
    <Card data-testid={testId} title={title} extra={extra}>
      {children}
    </Card>
  )
}
