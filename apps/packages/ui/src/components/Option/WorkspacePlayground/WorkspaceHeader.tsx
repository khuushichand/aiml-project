import React from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"
import { Tooltip, Input } from "antd"
import {
  FlaskConical,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Pencil,
  Check,
  X
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
  const setWorkspaceName = useWorkspaceStore((s) => s.setWorkspaceName)

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
    navigate("/")
  }

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
        {/* Left pane toggle (hidden on mobile) */}
        {!hideToggles && (
          <Tooltip
            title={
              leftPaneOpen
                ? t("playground:workspace.hideSources", "Hide sources")
                : t("playground:workspace.showSources", "Show sources")
            }
          >
            <button
              type="button"
              onClick={onToggleLeftPane}
              className={`hidden rounded-lg p-2 transition-colors lg:block ${
                leftPaneOpen
                  ? "text-text-muted hover:bg-surface2 hover:text-text"
                  : "bg-primary/10 text-primary"
              }`}
              aria-pressed={leftPaneOpen}
              aria-label={
                leftPaneOpen
                  ? t("playground:workspace.hideSources", "Hide sources")
                  : t("playground:workspace.showSources", "Show sources")
              }
            >
              {leftPaneOpen ? (
                <PanelLeftClose className="h-4 w-4" />
              ) : (
                <PanelLeftOpen className="h-4 w-4" />
              )}
            </button>
          </Tooltip>
        )}

        {/* Right pane toggle (hidden on mobile) */}
        {!hideToggles && (
          <Tooltip
            title={
              rightPaneOpen
                ? t("playground:workspace.hideStudio", "Hide studio")
                : t("playground:workspace.showStudio", "Show studio")
            }
          >
            <button
              type="button"
              onClick={onToggleRightPane}
              className={`hidden rounded-lg p-2 transition-colors lg:block ${
                rightPaneOpen
                  ? "text-text-muted hover:bg-surface2 hover:text-text"
                  : "bg-primary/10 text-primary"
              }`}
              aria-pressed={rightPaneOpen}
              aria-label={
                rightPaneOpen
                  ? t("playground:workspace.hideStudio", "Hide studio")
                  : t("playground:workspace.showStudio", "Show studio")
              }
            >
              {rightPaneOpen ? (
                <PanelRightClose className="h-4 w-4" />
              ) : (
                <PanelRightOpen className="h-4 w-4" />
              )}
            </button>
          </Tooltip>
        )}

        {/* Go to Simple Chat */}
        <button
          type="button"
          onClick={handleGoToSimpleChat}
          className="ml-2 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm font-medium text-text transition hover:bg-surface2"
        >
          {t("playground:workspace.goToSimpleChat", "Simple Chat")}
        </button>
      </div>
    </header>
  )
}

export default WorkspaceHeader
