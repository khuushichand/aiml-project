import { DEFAULT_WRITING_WORKSPACE_MODE } from "./writing-workspace-mode-utils"
import type { WritingWorkspaceMode } from "./writing-workspace-mode-utils"

export const WRITING_WORKSPACE_MODE_STORAGE_KEY = "writing:workspace-mode"

export const normalizeWritingWorkspaceMode = (
  value: unknown
): WritingWorkspaceMode => {
  if (value === "draft" || value === "manage") return value
  return DEFAULT_WRITING_WORKSPACE_MODE
}

export const resolveInitialWorkspaceMode = (
  storedValue: unknown
): WritingWorkspaceMode => normalizeWritingWorkspaceMode(storedValue)
