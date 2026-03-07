import type { FC, ReactNode } from "react"
import { Alert, Empty, Skeleton } from "antd"
import type { TranslateFn } from "./WritingPlaygroundDiagnostics.types"

type WritingPlaygroundActiveSessionGuardProps = {
  hasActiveSession: boolean
  isLoading: boolean
  hasError: boolean
  t: TranslateFn
  children: ReactNode
}

export const WritingPlaygroundActiveSessionGuard: FC<
  WritingPlaygroundActiveSessionGuardProps
> = ({ hasActiveSession, isLoading, hasError, t, children }) => {
  if (!hasActiveSession) {
    return (
      <Empty
        description={t(
          "option:writingPlayground.settingsEmpty",
          "Select a session to edit settings."
        )}
      />
    )
  }

  if (isLoading) {
    return <Skeleton active />
  }

  if (hasError) {
    return (
      <Alert
        type="error"
        showIcon
        title={t(
          "option:writingPlayground.settingsError",
          "Unable to load session settings."
        )}
      />
    )
  }

  return <>{children}</>
}
