import React from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"
import { Tooltip, Input, Dropdown, Modal, type MenuProps } from "antd"
import {
  FlaskConical,
  PanelLeftOpen,
  PanelRightOpen,
  Pencil,
  Check,
  X,
  ChevronDown,
  Plus,
  Trash2,
  MessageSquare,
  FolderOpen,
  Copy,
  Archive,
  RotateCcw
} from "lucide-react"
import type { SavedWorkspace } from "@/types/workspace"
import { useWorkspaceStore } from "@/store/workspace"
import {
  filterSavedWorkspaces,
  formatWorkspaceLastAccessed
} from "./workspace-header.utils"

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
  const [workspaceBrowserOpen, setWorkspaceBrowserOpen] = React.useState(false)
  const [workspaceSearchQuery, setWorkspaceSearchQuery] = React.useState("")

  const workspaceName = useWorkspaceStore((s) => s.workspaceName)
  const workspaceId = useWorkspaceStore((s) => s.workspaceId)
  const setWorkspaceName = useWorkspaceStore((s) => s.setWorkspaceName)
  const savedWorkspaces = useWorkspaceStore((s) => s.savedWorkspaces)
  const archivedWorkspaces = useWorkspaceStore((s) => s.archivedWorkspaces)
  const createNewWorkspace = useWorkspaceStore((s) => s.createNewWorkspace)
  const switchWorkspace = useWorkspaceStore((s) => s.switchWorkspace)
  const duplicateWorkspace = useWorkspaceStore((s) => s.duplicateWorkspace)
  const archiveWorkspace = useWorkspaceStore((s) => s.archiveWorkspace)
  const restoreArchivedWorkspace = useWorkspaceStore(
    (s) => s.restoreArchivedWorkspace
  )
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

  const handleOpenWorkspaceBrowser = () => {
    setWorkspaceSearchQuery("")
    setWorkspaceBrowserOpen(true)
  }

  const handleCloseWorkspaceBrowser = () => {
    setWorkspaceBrowserOpen(false)
    setWorkspaceSearchQuery("")
  }

  const handleDeleteWorkspace = (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    Modal.confirm({
      title: t("playground:workspace.deleteTitle", "Delete workspace?"),
      content: t(
        "playground:workspace.deleteMessage",
        "This will permanently remove this workspace and its saved state."
      ),
      okText: t("common:delete", "Delete"),
      okButtonProps: { danger: true },
      cancelText: t("common:cancel", "Cancel"),
      onOk: () => {
        deleteWorkspace(id)
      },
      centered: true,
      maskClosable: false
    })
  }

  const handleDuplicateCurrentWorkspace = () => {
    if (!workspaceId) return
    duplicateWorkspace(workspaceId)
  }

  const handleArchiveCurrentWorkspace = () => {
    if (!workspaceId) return

    Modal.confirm({
      title: t("playground:workspace.archiveTitle", "Archive current workspace?"),
      content: t(
        "playground:workspace.archiveMessage",
        "You can restore archived workspaces later from this menu."
      ),
      okText: t("playground:workspace.archive", "Archive"),
      cancelText: t("common:cancel", "Cancel"),
      onOk: () => {
        archiveWorkspace(workspaceId)
      },
      centered: true,
      maskClosable: true
    })
  }

  const handleRestoreWorkspace = (id: string) => {
    restoreArchivedWorkspace(id)
    switchWorkspace(id)
  }

  const savedCountLabel = (workspace: SavedWorkspace) =>
    `${workspace.sourceCount} ${
      workspace.sourceCount === 1 ? "source" : "sources"
    }`

  const savedRelativeLabel = (workspace: SavedWorkspace) =>
    formatWorkspaceLastAccessed(new Date(workspace.lastAccessedAt))

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
                    <div className="min-w-0">
                      <div className="truncate">{workspace.name}</div>
                      <div className="text-xs text-text-muted">
                        {savedCountLabel(workspace)} • {savedRelativeLabel(workspace)}
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => handleDeleteWorkspace(workspace.id, e)}
                    className="shrink-0 rounded p-1 text-text-muted opacity-0 transition hover:bg-error/10 hover:text-error group-hover:opacity-100 [.ant-dropdown-menu-item:hover_&]:opacity-100"
                    title={t("common:delete", "Delete")}
                    aria-label={t("common:delete", "Delete")}
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
    ...(workspaceId
      ? [
          {
            key: "duplicate-current",
            icon: <Copy className="h-4 w-4" />,
            label: t(
              "playground:workspace.duplicateCurrent",
              "Duplicate Current Workspace"
            ),
            onClick: handleDuplicateCurrentWorkspace
          },
          {
            key: "archive-current",
            icon: <Archive className="h-4 w-4" />,
            label: t(
              "playground:workspace.archiveCurrent",
              "Archive Current Workspace"
            ),
            onClick: handleArchiveCurrentWorkspace
          },
          { type: "divider" as const, key: "divider-current-actions" }
        ]
      : []),
    ...(archivedWorkspaces.length > 0
      ? [
          {
            key: "archived-header",
            type: "group" as const,
            label: t("playground:workspace.archivedWorkspaces", "Archived Workspaces")
          },
          ...archivedWorkspaces.slice(0, 5).map((workspace) => ({
            key: `archived-${workspace.id}`,
            icon: <RotateCcw className="h-4 w-4" />,
            label: (
              <div className="flex min-w-0 items-center gap-2">
                <span className="truncate">{workspace.name}</span>
                <span className="shrink-0 text-xs text-text-muted">
                  ({workspace.sourceCount} {workspace.sourceCount === 1 ? "source" : "sources"})
                </span>
              </div>
            ),
            onClick: () => handleRestoreWorkspace(workspace.id)
          })),
          { type: "divider" as const, key: "divider-archived" }
        ]
      : []),
    ...(savedWorkspaces.length > 0
      ? [
          {
            key: "view-all-workspaces",
            icon: <FolderOpen className="h-4 w-4" />,
            label: t(
              "playground:workspace.viewAll",
              "View all workspaces"
            ),
            onClick: handleOpenWorkspaceBrowser
          },
          { type: "divider" as const, key: "divider-view-all" }
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
                  className="rounded p-1 text-text-muted opacity-40 transition hover:bg-surface2 hover:text-text hover:opacity-100"
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

      <Modal
        title={t("playground:workspace.allWorkspaces", "All Workspaces")}
        open={workspaceBrowserOpen}
        onCancel={handleCloseWorkspaceBrowser}
        footer={null}
        width={680}
        destroyOnHidden
      >
        <div className="space-y-3">
          <Input
            value={workspaceSearchQuery}
            onChange={(event) => setWorkspaceSearchQuery(event.target.value)}
            placeholder={t(
              "playground:workspace.searchPlaceholder",
              "Search workspaces by name or tag"
            )}
            allowClear
          />

          <div className="custom-scrollbar max-h-[360px] space-y-1 overflow-y-auto rounded-lg border border-border p-1">
            {filterSavedWorkspaces(savedWorkspaces, workspaceSearchQuery).map(
              (workspace) => {
                const isCurrent = workspace.id === workspaceId
                return (
                  <button
                    key={workspace.id}
                    type="button"
                    disabled={isCurrent}
                    onClick={() => {
                      switchWorkspace(workspace.id)
                      handleCloseWorkspaceBrowser()
                    }}
                    className={`w-full rounded-md border px-3 py-2 text-left transition ${
                      isCurrent
                        ? "cursor-default border-primary/30 bg-primary/10"
                        : "border-border hover:bg-surface2"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate font-medium text-text">
                          {workspace.name}
                        </div>
                        <div className="truncate text-xs text-text-muted">
                          {workspace.tag}
                        </div>
                      </div>
                      <div className="shrink-0 text-right text-xs text-text-muted">
                        <div>{savedCountLabel(workspace)}</div>
                        <div>
                          {t("playground:workspace.lastAccessed", "Last accessed")}{" "}
                          {savedRelativeLabel(workspace)}
                        </div>
                      </div>
                    </div>
                  </button>
                )
              }
            )}

            {filterSavedWorkspaces(savedWorkspaces, workspaceSearchQuery)
              .length === 0 && (
              <div className="px-3 py-6 text-center text-sm text-text-muted">
                {t(
                  "playground:workspace.noMatches",
                  "No workspaces match your search."
                )}
              </div>
            )}
          </div>
        </div>
      </Modal>
    </header>
  )
}

export default WorkspaceHeader
