import { trackWorkspacePlaygroundTelemetry } from "@/utils/workspace-playground-telemetry"

export const WORKSPACE_UNDO_WINDOW_MS = 10000

export interface WorkspaceUndoActionHandle {
  id: string
  expiresAt: number
}

interface PendingWorkspaceUndoAction {
  id: string
  expiresAt: number
  undo: () => void
  finalize: () => void
  timer: ReturnType<typeof setTimeout>
}

interface ScheduleWorkspaceUndoActionInput {
  apply: () => void
  undo: () => void
  finalize?: () => void
  timeoutMs?: number
}

const pendingWorkspaceUndoActions = new Map<string, PendingWorkspaceUndoAction>()

const createWorkspaceUndoActionId = (): string => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID()
  }
  return `workspace-undo-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

const clearPendingWorkspaceUndoAction = (
  id: string
): PendingWorkspaceUndoAction | null => {
  const action = pendingWorkspaceUndoActions.get(id)
  if (!action) return null
  clearTimeout(action.timer)
  pendingWorkspaceUndoActions.delete(id)
  return action
}

export const scheduleWorkspaceUndoAction = ({
  apply,
  undo,
  finalize,
  timeoutMs = WORKSPACE_UNDO_WINDOW_MS
}: ScheduleWorkspaceUndoActionInput): WorkspaceUndoActionHandle => {
  apply()

  const id = createWorkspaceUndoActionId()
  const expiresAt = Date.now() + timeoutMs

  const timer = setTimeout(() => {
    const action = clearPendingWorkspaceUndoAction(id)
    if (!action) return
    action.finalize()
  }, timeoutMs)

  pendingWorkspaceUndoActions.set(id, {
    id,
    expiresAt,
    undo,
    finalize: finalize || (() => {}),
    timer
  })

  return { id, expiresAt }
}

export const undoWorkspaceAction = (id: string): boolean => {
  const action = clearPendingWorkspaceUndoAction(id)
  if (!action) return false
  action.undo()
  void trackWorkspacePlaygroundTelemetry({
    type: "undo_triggered"
  })
  return true
}

export const getWorkspaceUndoPendingCount = (): number =>
  pendingWorkspaceUndoActions.size

export const clearWorkspaceUndoActionsForTests = (): void => {
  for (const action of pendingWorkspaceUndoActions.values()) {
    clearTimeout(action.timer)
  }
  pendingWorkspaceUndoActions.clear()
}
