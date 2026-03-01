import type { FC } from "react"
import { Card } from "antd"
import type { WritingPlaygroundPanelProps } from "./WritingPlayground.types"

export const WritingPlaygroundLibraryPanel: FC<WritingPlaygroundPanelProps> = ({
  title,
  extra,
  children,
  testId = "writing-playground-library-panel"
}) => {
  return (
    <Card data-testid={testId} title={title} extra={extra}>
      {children}
    </Card>
  )
}
