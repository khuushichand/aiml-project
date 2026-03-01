export type WritingWorkspaceMode = "draft" | "manage"

export type WritingWorkspaceSectionId =
  | "sessions"
  | "draft-editor"
  | "draft-inspector"
  | "manage-styling"
  | "manage-generation"
  | "manage-context"
  | "manage-analysis"

type WritingWorkspaceSection = {
  id: WritingWorkspaceSectionId
  modes: WritingWorkspaceMode[]
}

export const DEFAULT_WRITING_WORKSPACE_MODE: WritingWorkspaceMode = "draft"

export const WRITING_WORKSPACE_SECTIONS: WritingWorkspaceSection[] = [
  { id: "sessions", modes: ["draft", "manage"] },
  { id: "draft-editor", modes: ["draft"] },
  { id: "draft-inspector", modes: ["draft"] },
  { id: "manage-styling", modes: ["manage"] },
  { id: "manage-generation", modes: ["manage"] },
  { id: "manage-context", modes: ["manage"] },
  { id: "manage-analysis", modes: ["manage"] }
]

export const getVisibleWritingWorkspaceSections = (
  mode: WritingWorkspaceMode
) => WRITING_WORKSPACE_SECTIONS.filter((section) => section.modes.includes(mode))
