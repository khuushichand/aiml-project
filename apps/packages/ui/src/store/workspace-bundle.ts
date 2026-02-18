import type { ChatHistory, Message } from "@/store/option"
import type {
  AudioGenerationSettings,
  GeneratedArtifact,
  WorkspaceNote,
  WorkspaceSource
} from "@/types/workspace"

export const WORKSPACE_EXPORT_BUNDLE_FORMAT = "tldw.workspace-playground.bundle"
export const WORKSPACE_EXPORT_BUNDLE_SCHEMA_VERSION = 1

type ExportDateValue = string | Date | null

export interface WorkspaceBundleSnapshot {
  workspaceName: string
  workspaceTag: string
  workspaceCreatedAt: ExportDateValue
  sources: WorkspaceSource[]
  selectedSourceIds: string[]
  generatedArtifacts: GeneratedArtifact[]
  notes: string
  currentNote: WorkspaceNote
  leftPaneCollapsed: boolean
  rightPaneCollapsed: boolean
  audioSettings: AudioGenerationSettings
}

export interface WorkspaceBundleChatSession {
  messages: Message[]
  history: ChatHistory
  historyId: string | null
  serverChatId: string | null
}

export interface WorkspaceExportBundle {
  format: typeof WORKSPACE_EXPORT_BUNDLE_FORMAT
  schemaVersion: typeof WORKSPACE_EXPORT_BUNDLE_SCHEMA_VERSION
  exportedAt: string
  workspace: {
    name: string
    tag: string
    createdAt: ExportDateValue
    snapshot: WorkspaceBundleSnapshot
    chatSession?: WorkspaceBundleChatSession
  }
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null

export const isWorkspaceExportBundle = (
  value: unknown
): value is WorkspaceExportBundle => {
  if (!isRecord(value)) return false
  if (value.format !== WORKSPACE_EXPORT_BUNDLE_FORMAT) return false
  if (value.schemaVersion !== WORKSPACE_EXPORT_BUNDLE_SCHEMA_VERSION) return false
  if (typeof value.exportedAt !== "string") return false
  if (!isRecord(value.workspace)) return false
  if (!isRecord(value.workspace.snapshot)) return false
  return true
}

const sanitizeFilenameToken = (value: string): string =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")

export const createWorkspaceExportFilename = (
  workspaceName: string,
  exportedAt: string
): string => {
  const safeName = sanitizeFilenameToken(workspaceName) || "workspace"
  const safeDate =
    sanitizeFilenameToken(exportedAt.replace(/[.:]/g, "-")) || "export"
  return `${safeName}-${safeDate}.workspace.json`
}
