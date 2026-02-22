export const WORKSPACE_STORAGE_KEY = "tldw-workspace"
export const WORKSPACE_STORAGE_QUOTA_EVENT =
  "tldw:workspace-storage-quota-error"
export const WORKSPACE_STORAGE_RECOVERY_EVENT =
  "tldw:workspace-storage-recovery"
export const WORKSPACE_STORAGE_CHANNEL_NAME = "tldw-workspace-sync"
export const WORKSPACE_BROADCAST_SYNC_FLAG = "tldw:workspace:broadcast-sync"
export const WORKSPACE_CONFLICT_NOTICE_THROTTLE_MS = 8000

type WorkspaceWindow = Window & {
  __TLDW_ENABLE_WORKSPACE_BROADCAST_SYNC__?: boolean
}

export interface WorkspaceStorageQuotaEventDetail {
  key: string
  reason: string
}

export type WorkspaceStorageRecoveryAction =
  | "archived_workspace_removed"
  | "chat_session_removed"
  | "artifact_removed"
  | "retry_success"
  | "retry_failed"
  | "retry_skipped"

export interface WorkspaceStorageRecoveryEventDetail {
  key: string
  action: WorkspaceStorageRecoveryAction
  beforeBytes: number
  afterBytes: number
  recoveredBytes: number
  workspaceId?: string
  reason?: string
}

export interface WorkspaceBroadcastUpdateMessage {
  type: "workspace-storage-updated"
  key: string
  updatedAt: number
}

export const isWorkspaceBroadcastSyncEnabled = (): boolean => {
  if (typeof window === "undefined") return false

  const typedWindow = window as WorkspaceWindow
  if (
    typeof typedWindow.__TLDW_ENABLE_WORKSPACE_BROADCAST_SYNC__ === "boolean"
  ) {
    return typedWindow.__TLDW_ENABLE_WORKSPACE_BROADCAST_SYNC__
  }

  try {
    return (
      window.localStorage.getItem(WORKSPACE_BROADCAST_SYNC_FLAG) === "1"
    )
  } catch {
    return false
  }
}

export const isWorkspaceBroadcastUpdateMessage = (
  value: unknown
): value is WorkspaceBroadcastUpdateMessage => {
  if (!value || typeof value !== "object") return false
  const candidate = value as Partial<WorkspaceBroadcastUpdateMessage>
  return (
    candidate.type === "workspace-storage-updated" &&
    typeof candidate.key === "string" &&
    typeof candidate.updatedAt === "number"
  )
}

export const shouldSurfaceWorkspaceConflictNotice = (
  lastShownAt: number,
  nextEventAt: number,
  throttleMs: number = WORKSPACE_CONFLICT_NOTICE_THROTTLE_MS
): boolean => {
  if (lastShownAt <= 0) return true
  return nextEventAt - lastShownAt >= throttleMs
}
