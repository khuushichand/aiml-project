import type { ReactNode } from "react"

export type InspectorTabKey = "generation" | "planning" | "diagnostics"

export interface WritingPlaygroundShellProps {
  children: ReactNode
}

export interface WritingPlaygroundPanelProps {
  title?: ReactNode
  extra?: ReactNode
  children: ReactNode
  testId?: string
}
