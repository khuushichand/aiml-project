/**
 * WorkspaceSelector - Select and manage workspace directories
 */

import { FC, useState, useEffect, useRef, MouseEvent, useCallback } from "react"
import { useTranslation } from "react-i18next"
import { Dropdown, Modal, Input, message } from "antd"
import type { MenuProps } from "antd"
import {
  FolderOpen,
  ChevronDown,
  Plus,
  AlertCircle,
  Check,
  Trash2,
  Clock
} from "lucide-react"
import { useStorage } from "@plasmohq/storage/hook"
import * as nativeClient from "@/services/native/native-client"
import { useWorkspaceHistory, useAutoSelectWorkspace } from "@/hooks/useWorkspaceHistory"
import { formatRelativeTime } from "@/utils/dateFormatters"
import { isDuplicateWorkspacePath } from "./utils/workspace-paths"

export interface Workspace {
  id: string
  name: string
  path: string
}

interface WorkspaceSelectorProps {
  onWorkspaceChange?: (workspace: Workspace | null) => void
  className?: string
}

const generateWorkspaceId = () => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID()
  }
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    const bytes = new Uint8Array(16)
    crypto.getRandomValues(bytes)
    // RFC4122 version 4 and variant bits.
    bytes[6] = (bytes[6] & 0x0f) | 0x40
    bytes[8] = (bytes[8] & 0x3f) | 0x80
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("")
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

const MAX_RECENT_WORKSPACES = 3

export const WorkspaceSelector: FC<WorkspaceSelectorProps> = ({
  onWorkspaceChange,
  className = ""
}) => {
  const { t } = useTranslation("common")
  const [workspaces, setWorkspaces] = useStorage<Workspace[]>("agent:workspaces", [])
  const [selectedId, setSelectedId] = useStorage<string | null>("agent:selectedWorkspace", null)
  const [isHostInstalled, setIsHostInstalled] = useState<boolean | null>(null)
  const [showAddModal, setShowAddModal] = useState(false)
  const [newPath, setNewPath] = useState("")
  const [newName, setNewName] = useState("")
  const [isValidating, setIsValidating] = useState(false)
  const [isSelecting, setIsSelecting] = useState(false)

  // Workspace history
  const {
    recentWorkspaces,
    recordUsage,
    removeWorkspace: removeFromHistory,
  } = useWorkspaceHistory(workspaces || [])

  // Check if native host is installed
  useEffect(() => {
    let cancelled = false

    const checkHost = async () => {
      try {
        const installed = await nativeClient.isHostInstalled()
        if (!cancelled) {
          setIsHostInstalled(installed)
        }
      } catch (error) {
        // If detection fails, treat host as not installed so the UI doesn't stay stuck
        console.warn(
          "[WorkspaceSelector] Failed to detect native host installation:",
          error
        )
        if (!cancelled) {
          setIsHostInstalled(false)
        }
      }
    }

    void checkHost()

    return () => {
      cancelled = true
    }
  }, [])

  const resolvedSelectedId = selectedId ?? null

  // Get currently selected workspace
  const selectedWorkspace = workspaces?.find(w => w.id === resolvedSelectedId) || null

  const callbackRef = useRef(onWorkspaceChange)
  const lastNotifiedWorkspaceId = useRef<string | null>(null)
  useEffect(() => {
    callbackRef.current = onWorkspaceChange
  }, [onWorkspaceChange])

  // Notify parent of workspace change
  useEffect(() => {
    const nextId = selectedWorkspace?.id ?? null
    if (lastNotifiedWorkspaceId.current === nextId) {
      return
    }
    lastNotifiedWorkspaceId.current = nextId
    callbackRef.current?.(selectedWorkspace)
  }, [selectedWorkspace])

  // Handle workspace selection
  const handleSelect = useCallback(async (workspace: Workspace) => {
    setIsSelecting(true)
    try {
      // Set workspace in native agent
      const result = await nativeClient.setWorkspace(workspace.path)
      if (!result.ok) {
        message.error(result.error || t("failedToSetWorkspace", "Failed to set workspace"))
        return
      }
      setSelectedId(workspace.id)

      // Record usage in history
      try {
        await recordUsage(workspace)
      } catch (e: unknown) {
        console.error("[WorkspaceSelector] Failed to record workspace usage:", e)
      }
    } catch (e: unknown) {
      const err =
        e && typeof e === "object" && "message" in e
          ? String((e as { message?: unknown }).message)
          : t("failedToSetWorkspace", "Failed to set workspace")
      message.error(err)
    } finally {
      setIsSelecting(false)
    }
  }, [recordUsage, setSelectedId, t])

  const handleAutoSelect = useCallback(
    (workspace: Workspace) => {
      void handleSelect(workspace)
    },
    [handleSelect]
  )

  // Auto-select last used workspace on mount
  const canAutoSelectWorkspace = isHostInstalled === true
  useAutoSelectWorkspace(
    workspaces || [],
    resolvedSelectedId,
    handleAutoSelect,
    canAutoSelectWorkspace
  )

  // Handle adding new workspace
  const handleAddWorkspace = async () => {
    const trimmedPath = newPath.trim()
    if (!trimmedPath) {
      message.error(t("pleaseEnterPath", "Please enter a path"))
      return
    }
    if (isDuplicateWorkspacePath(trimmedPath, workspaces || [])) {
      message.error(t("workspaceAlreadyAdded", "Workspace already added"))
      return
    }

    setIsValidating(true)
    try {
      // Validate path via native agent
      const result = await nativeClient.setWorkspace(trimmedPath)
      if (!result.ok) {
        message.error(result.error || t("invalidPath", "Invalid path"))
        return
      }

      const pathForName = trimmedPath.replace(/[/\\]+$/, "") || trimmedPath
      const derivedName = pathForName.split(/[/\\]/).pop() || t("workspace", "Workspace")

      // Add to list
      const workspace: Workspace = {
        id: generateWorkspaceId(),
        name: newName.trim() || derivedName,
        path: trimmedPath
      }

      setWorkspaces(prev => [...(prev || []), workspace])
      setSelectedId(workspace.id)
      void recordUsage(workspace).catch((error) => {
        console.warn("[WorkspaceSelector] Failed to record workspace usage:", error)
      })
      setShowAddModal(false)
      setNewPath("")
      setNewName("")
      message.success(t("workspaceAdded", "Workspace added"))
    } catch (e: unknown) {
      const err =
        e && typeof e === "object" && "message" in e
          ? String((e as { message?: unknown }).message)
          : t("failedToAddWorkspace", "Failed to add workspace")
      message.error(err)
    } finally {
      setIsValidating(false)
    }
  }

  // Handle removing workspace
  const handleRemove = (id: string, e: MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation()
    setWorkspaces(prev => (prev || []).filter(w => w.id !== id))
    if (selectedId === id) {
      setSelectedId(null)
    }
    void removeFromHistory(id).catch((error) => {
      console.warn(
        "[WorkspaceSelector] Failed to remove workspace from history:",
        error
      )
    })
  }

  // If host not installed, show setup prompt
  if (isHostInstalled === false) {
    return (
      <div className={`flex items-center gap-2 rounded-lg border border-warn/30 bg-warn/10 px-3 py-2 ${className}`}>
        <AlertCircle className="size-4 text-warn" />
        <span className="text-sm text-warn">
          {t("agentNotInstalled", "tldw-agent not installed")}
        </span>
        <a
          href="https://github.com/rmusser01/tldw_browser_assistant/blob/HEAD/docs/agent/user-guide.md#installation"
          target="_blank"
          rel="noopener noreferrer"
          className="ml-auto text-sm text-primary hover:underline"
        >
          {t("setup", "Setup")}
        </a>
      </div>
    )
  }

  // Loading state
  if (isHostInstalled === null) {
    return (
      <div className={`flex items-center gap-2 rounded-lg bg-surface2 px-3 py-2 ${className}`}>
        <div
          className="size-4 rounded-full border-2 border-border-strong border-t-transparent animate-spin"
          role="status"
          aria-label={t("checkingAgent", "Checking agent...")}
        />
        <span className="text-sm text-text-subtle">
          {t("checkingAgent", "Checking agent...")}
        </span>
      </div>
    )
  }

  // Build menu items with recent workspaces section
  const menuItems: MenuProps["items"] = []

  // Recent workspaces section (if any)
  const recentItems = recentWorkspaces
    .slice(0, MAX_RECENT_WORKSPACES)
    .flatMap(recent => {
      const ws = workspaces?.find(w => w.id === recent.workspaceId)
      if (!ws) return []
      return [
        {
          key: `recent-${ws.id}`,
          label: (
            <div className="flex items-center justify-between gap-3 py-1">
              <div className="flex flex-col min-w-0">
                <span className="font-medium truncate">{ws.name}</span>
                <span className="text-xs text-text-subtle">
                  {formatRelativeTime(recent.lastUsedAt, t, { compact: true })}
                </span>
              </div>
              {ws.id === selectedId && (
                <Check className="size-4 flex-shrink-0 text-success" />
              )}
            </div>
          ),
          onClick: () => {
            void handleSelect(ws)
          }
        }
      ]
    })

  if (recentItems.length > 0) {
    menuItems.push({
      key: "recent-header",
      type: "group" as const,
      label: (
        <div className="flex items-center gap-1.5 text-xs text-text-subtle uppercase tracking-wider">
          <Clock className="size-3" />
          {t("recent", "Recent")}
        </div>
      ),
      children: recentItems
    })

    menuItems.push({ type: "divider" as const, key: "recent-divider" })
  }

  // All workspaces section
  menuItems.push({
    key: "all-header",
    type: "group" as const,
    label: (
      <span className="text-xs text-text-subtle uppercase tracking-wider">
        {t("allWorkspaces", "All Workspaces")}
      </span>
    ),
    children: (workspaces || []).map(ws => ({
      key: ws.id,
      label: (
        <div className="flex items-center justify-between gap-3 py-1">
          <div className="flex flex-col min-w-0">
            <span className="font-medium truncate">{ws.name}</span>
            <span className="text-xs text-text-subtle truncate">
              {ws.path}
            </span>
          </div>
          <div className="flex items-center gap-1">
            {ws.id === selectedId && (
              <Check className="size-4 text-success" />
            )}
            <button
              onClick={(e) => handleRemove(ws.id, e)}
              className="rounded p-1 hover:bg-surface2 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              aria-label={t("removeWorkspace", "Remove workspace")}
            >
              <Trash2 className="size-3 text-text-subtle hover:text-danger" />
            </button>
          </div>
        </div>
      ),
      onClick: () => {
        void handleSelect(ws)
      }
    }))
  })

  menuItems.push({ type: "divider" as const, key: "add-divider" })

  // Add workspace option
  menuItems.push({
    key: "add",
    label: (
      <div className="flex items-center gap-2 text-primary">
        <Plus className="size-4" />
        <span>{t("addWorkspace", "Add Workspace")}</span>
      </div>
    ),
    onClick: () => setShowAddModal(true)
  })

  return (
    <>
      <Dropdown
        menu={{ items: menuItems }}
        trigger={["click"]}
        placement="bottomLeft"
      >
        <button
          type="button"
          data-testid="agent-workspace-selector"
          className={`flex items-center gap-2 rounded-lg bg-surface2 px-3 py-2 transition-colors hover:bg-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 ${className} ${isSelecting ? "opacity-70 cursor-wait" : ""}`}
          aria-label={selectedWorkspace?.name || t("selectWorkspace", "Select Workspace")}
          aria-haspopup="menu"
          aria-busy={isSelecting}
          disabled={isSelecting}
        >
          {isSelecting ? (
            <div
              className="size-4 rounded-full border-2 border-border-strong border-t-transparent animate-spin"
              role="status"
              aria-label={t("selectingWorkspace", "Selecting workspace...")}
            />
          ) : (
            <FolderOpen className="size-4 text-text-subtle" />
          )}
          <span className="text-sm font-medium truncate max-w-[200px]">
            {isSelecting
              ? t("selectingWorkspace", "Selecting...")
              : selectedWorkspace?.name || t("selectWorkspace", "Select Workspace")}
          </span>
          <ChevronDown className="size-4 text-text-subtle" />
        </button>
      </Dropdown>

      <Modal
        title={t("addWorkspace", "Add Workspace")}
        open={showAddModal}
        onOk={() => {
          void handleAddWorkspace()
        }}
        onCancel={() => {
          setShowAddModal(false)
          setNewPath("")
          setNewName("")
        }}
        confirmLoading={isValidating}
        okText={t("add", "Add")}
        cancelText={t("cancel", "Cancel")}
      >
        <div className="space-y-4 py-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              {t("workspacePath", "Workspace Path")}
            </label>
            <Input
              placeholder="/Users/you/projects/myapp"
              value={newPath}
              onChange={(e) => setNewPath(e.target.value)}
              onPressEnter={() => {
                void handleAddWorkspace()
              }}
            />
            <p className="mt-1 text-xs text-text-subtle">
              {t("workspacePathHelp", "Enter the full path to your project directory")}
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              {t("workspaceName", "Display Name")} ({t("optional", "optional")})
            </label>
            <Input
              placeholder="My Project"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onPressEnter={() => {
                void handleAddWorkspace()
              }}
            />
          </div>
        </div>
      </Modal>
    </>
  )
}

export default WorkspaceSelector
