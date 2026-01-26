import React from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"
import { Tooltip, Input, Dropdown, type MenuProps } from "antd"
import {
  FlaskConical,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Pencil,
  Check,
  X,
  ChevronDown,
  Plus,
  Trash2,
  MessageSquare,
  FolderOpen
} from "lucide-react"
import { useWorkspaceStore } from "@/store/workspace"

interface WorkspaceHeaderProps {
  leftPaneOpen: boolean
  rightPaneOpen: boolean
  onToggleLeftPane: () => void
  onToggleRightPane: () => void
  /** Hide pane toggle buttons (for mobile layout) */
  hideToggles?: boolean
}

export const WorkspaceHeader: React.FC<WorkspaceHeaderProps> = ({
  leftPaneOpen,
  rightPaneOpen,
  onToggleLeftPane,
  onToggleRightPane,
  hideToggles = false
}) => {
  const { t } = useTranslation(["playground", "option", "common"])
  const navigate = useNavigate()
  const [isEditing, setIsEditing] = React.useState(false)
  const [editName, setEditName] = React.useState("")

  const workspaceName = useWorkspaceStore((s) => s.workspaceName)
  const workspaceId = useWorkspaceStore((s) => s.workspaceId)
  const setWorkspaceName = useWorkspaceStore((s) => s.setWorkspaceName)
  const savedWorkspaces = useWorkspaceStore((s) => s.savedWorkspaces)
  const createNewWorkspace = useWorkspaceStore((s) => s.createNewWorkspace)
  const switchWorkspace = useWorkspaceStore((s) => s.switchWorkspace)
  const deleteWorkspace = useWorkspaceStore((s) => s.deleteWorkspace)
  const saveCurrentWorkspace = useWorkspaceStore((s) => s.saveCurrentWorkspace)

  const handleStartEdit = () => {
    setEditName(workspaceName || "New Research")
    setIsEditing(true)
  }

  const handleSaveEdit = () => {
    if (editName.trim()) {
      setWorkspaceName(editName.trim())
    }
    setIsEditing(false)
  }

  const handleCancelEdit = () => {
    setIsEditing(false)
    setEditName("")
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSaveEdit()
    } else if (e.key === "Escape") {
      handleCancelEdit()
    }
  }

  const handleGoToSimpleChat = () => {
    // Save current workspace before navigating
    saveCurrentWorkspace()
    navigate("/")
  }

  const handleCreateNewWorkspace = () => {
    createNewWorkspace()
  }

  const handleSwitchWorkspace = (id: string) => {
    switchWorkspace(id)
  }

  const handleDeleteWorkspace = (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    deleteWorkspace(id)
  }

  // Build dropdown menu items
  const workspaceMenuItems: MenuProps["items"] = [
    // Recent workspaces section
    ...(savedWorkspaces.length > 0
      ? [
          {
            key: "recent-header",
            type: "group" as const,
            label: t("playground:workspace.recentWorkspaces", "Recent Workspaces")
          },
          ...savedWorkspaces
            .filter((w) => w.id !== workspaceId) // Don't show current workspace
            .slice(0, 5) // Show max 5 recent
            .map((workspace) => ({
              key: workspace.id,
              label: (
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 flex-1 items-center gap-2">
                    <FolderOpen className="h-4 w-4 shrink-0 text-text-muted" />
                    <span className="truncate">{workspace.name}</span>
                    <span className="shrink-0 text-xs text-text-muted">
                      ({workspace.sourceCount} {workspace.sourceCount === 1 ? "source" : "sources"})
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => handleDeleteWorkspace(workspace.id, e)}
                    className="shrink-0 rounded p-1 text-text-muted opacity-0 transition hover:bg-error/10 hover:text-error group-hover:opacity-100 [.ant-dropdown-menu-item:hover_&]:opacity-100"
                    title={t("common:delete", "Delete")}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ),
              onClick: () => handleSwitchWorkspace(workspace.id)
            })),
          { type: "divider" as const, key: "divider-1" }
        ]
      : []),
    // New workspace option
    {
      key: "new",
      icon: <Plus className="h-4 w-4" />,
      label: t("playground:workspace.newWorkspace", "New Workspace"),
      onClick: handleCreateNewWorkspace
    },
    { type: "divider" as const, key: "divider-2" },
    // Simple chat option
    {
      key: "simple-chat",
      icon: <MessageSquare className="h-4 w-4" />,
      label: t("playground:workspace.goToSimpleChat", "Simple Chat"),
      onClick: handleGoToSimpleChat
    }
  ]

  return (
    <header className="flex items-center justify-between border-b border-border bg-surface px-4 py-3">
      <div className="flex items-center gap-3">
        <FlaskConical className="h-5 w-5 text-primary" />
        <div className="flex items-center gap-2">
          {isEditing ? (
            <div className="flex items-center gap-1">
              <Input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                onKeyDown={handleKeyDown}
                autoFocus
                size="small"
                className="w-48"
                placeholder={t(
                  "playground:workspace.namePlaceholder",
                  "Workspace name"
                )}
              />
              <button
                type="button"
                onClick={handleSaveEdit}
                className="rounded p-1 text-primary hover:bg-primary/10"
                aria-label={t("common:save", "Save")}
              >
                <Check className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={handleCancelEdit}
                className="rounded p-1 text-text-muted hover:bg-surface2 hover:text-text"
                aria-label={t("common:cancel", "Cancel")}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold text-text">
                {workspaceName || t("playground:workspace.title", "Research Workspace")}
              </h1>
              <Tooltip title={t("playground:workspace.rename", "Rename workspace")}>
                <button
                  type="button"
                  onClick={handleStartEdit}
                  className="rounded p-1 text-text-muted opacity-0 transition hover:bg-surface2 hover:text-text group-hover:opacity-100 [header:hover_&]:opacity-100"
                  aria-label={t("playground:workspace.rename", "Rename workspace")}
                >
                  <Pencil className="h-3.5 w-3.5" />
                </button>
              </Tooltip>
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        {/* Left pane expand button (only shown when collapsed) */}
        {!hideToggles && !leftPaneOpen && (
          <Tooltip title={t("playground:workspace.showSources", "Show sources")}>
            <button
              type="button"
              onClick={onToggleLeftPane}
              className="hidden rounded-lg bg-primary/10 p-2 text-primary transition-colors hover:bg-primary/20 lg:block"
              aria-label={t("playground:workspace.showSources", "Show sources")}
            >
              <PanelLeftOpen className="h-4 w-4" />
            </button>
          </Tooltip>
        )}

        {/* Right pane expand button (only shown when collapsed) */}
        {!hideToggles && !rightPaneOpen && (
          <Tooltip title={t("playground:workspace.showStudio", "Show studio")}>
            <button
              type="button"
              onClick={onToggleRightPane}
              className="hidden rounded-lg bg-primary/10 p-2 text-primary transition-colors hover:bg-primary/20 lg:block"
              aria-label={t("playground:workspace.showStudio", "Show studio")}
            >
              <PanelRightOpen className="h-4 w-4" />
            </button>
          </Tooltip>
        )}

        {/* Workspace Switcher Dropdown */}
        <Dropdown
          menu={{ items: workspaceMenuItems }}
          trigger={["click"]}
          placement="bottomRight"
        >
          <button
            type="button"
            className="ml-2 flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium text-text transition hover:bg-surface2"
          >
            <span>{t("playground:workspace.workspaces", "Workspaces")}</span>
            <ChevronDown className="h-4 w-4 text-text-muted" />
          </button>
        </Dropdown>
      </div>
    </header>
  )
}

export default WorkspaceHeader
