import React from "react"
import type { ModerationScope } from "../moderation-utils"

export interface ModerationContextState {
  scope: ModerationScope
  setScope: (scope: ModerationScope) => void
  userIdDraft: string
  setUserIdDraft: (value: string) => void
  activeUserId: string | null
  setActiveUserId: (value: string | null) => void
  loadUser: () => void
  clearUser: () => void
}

export function useModerationContext(): ModerationContextState {
  const [scope, setScopeRaw] = React.useState<ModerationScope>("server")
  const [userIdDraft, setUserIdDraft] = React.useState("")
  const [activeUserId, setActiveUserId] = React.useState<string | null>(null)

  const setScope = React.useCallback((next: ModerationScope) => {
    setScopeRaw(next)
    if (next === "server") setActiveUserId(null)
  }, [])

  const loadUser = React.useCallback(() => {
    const trimmed = userIdDraft.trim()
    if (trimmed) setActiveUserId(trimmed)
  }, [userIdDraft])

  const clearUser = React.useCallback(() => {
    setActiveUserId(null)
    setUserIdDraft("")
  }, [])

  return { scope, setScope, userIdDraft, setUserIdDraft, activeUserId, setActiveUserId, loadUser, clearUser }
}
