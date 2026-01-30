import React, { useState } from "react"
import { useTranslation } from "react-i18next"
import { Button, Empty, Popconfirm, Tooltip, Tag } from "antd"
import { Plus, Folder, Trash2, X, ChevronRight, Bot } from "lucide-react"
import { useACPSessionsStore } from "@/store/acp-sessions"
import { useStorage } from "@plasmohq/storage/hook"
import type { ACPSession, ACPAgentType } from "@/services/acp/types"
import { AGENT_TYPE_INFO } from "@/services/acp/constants"
import { ACPSessionCreateModal } from "./ACPSessionCreateModal"

interface ACPSessionPanelProps {
  onHide?: () => void
}

export const ACPSessionPanel: React.FC<ACPSessionPanelProps> = ({ onHide }) => {
  const { t } = useTranslation(["playground", "option", "common"])

  const [showCreateModal, setShowCreateModal] = useState(false)

  // Server config
  const [serverUrl] = useStorage("serverUrl", "http://localhost:8000")
  const [authMode] = useStorage("authMode", "single-user")
  const [apiKey] = useStorage("apiKey", "")
  const [accessToken] = useStorage("accessToken", "")

  // Store
  const sessions = useACPSessionsStore((s) => s.getSessions())
  const activeSessionId = useACPSessionsStore((s) => s.activeSessionId)
  const setActiveSession = useACPSessionsStore((s) => s.setActiveSession)
  const closeSession = useACPSessionsStore((s) => s.closeSession)

  const handleCreateSession = () => {
    setShowCreateModal(true)
  }

  const handleSessionCreated = (sessionId: string) => {
    // The modal handles everything, just close it
    setShowCreateModal(false)
  }

  const handleSelectSession = (sessionId: string) => {
    setActiveSession(sessionId)
  }

  const handleCloseSession = async (sessionId: string) => {
    try {
      // Call backend to close session
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      }
      if (authMode === "single-user" && apiKey) {
        headers["X-API-KEY"] = apiKey
      } else if (authMode === "multi-user" && accessToken) {
        headers["Authorization"] = `Bearer ${accessToken}`
      }

      await fetch(`${serverUrl}/api/v1/acp/sessions/close`, {
        method: "POST",
        headers,
        body: JSON.stringify({ session_id: sessionId }),
      }).catch(() => {
        // Ignore errors - session may already be closed
      })

      // Remove from local store
      closeSession(sessionId)
    } catch (error) {
      console.error("Failed to close session:", error)
    }
  }

  const getSessionStateColor = (state: string) => {
    switch (state) {
      case "connected":
        return "bg-success"
      case "running":
        return "bg-primary"
      case "waiting_permission":
        return "bg-warning"
      case "error":
        return "bg-error"
      case "connecting":
        return "bg-info"
      default:
        return "bg-text-muted"
    }
  }

  const formatDate = (date: Date) => {
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(minutes / 60)
    const days = Math.floor(hours / 24)

    if (minutes < 1) return t("playground:acp.justNow", "Just now")
    if (minutes < 60) return t("playground:acp.minutesAgo", "{{count}}m ago", { count: minutes })
    if (hours < 24) return t("playground:acp.hoursAgo", "{{count}}h ago", { count: hours })
    return t("playground:acp.daysAgo", "{{count}}d ago", { count: days })
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border p-3">
        <h2 className="text-sm font-semibold text-text">
          {t("playground:acp.sessions", "Sessions")}
        </h2>
        <div className="flex items-center gap-1">
          <Tooltip title={t("playground:acp.newSession", "New Session")}>
            <Button
              type="text"
              size="small"
              icon={<Plus className="h-4 w-4" />}
              onClick={handleCreateSession}
            />
          </Tooltip>
          {onHide && (
            <Tooltip title={t("common:close", "Close")}>
              <Button
                type="text"
                size="small"
                icon={<X className="h-4 w-4" />}
                onClick={onHide}
              />
            </Tooltip>
          )}
        </div>
      </div>

      {/* Sessions list */}
      <div className="flex-1 overflow-y-auto">
        {sessions.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={t("playground:acp.noSessions", "No active sessions")}
            className="py-8"
          >
            <Button
              type="primary"
              icon={<Plus className="h-4 w-4" />}
              onClick={handleCreateSession}
            >
              {t("playground:acp.createFirst", "Create Session")}
            </Button>
          </Empty>
        ) : (
          <div className="p-2">
            {sessions.map((session) => (
              <SessionItem
                key={session.id}
                session={session}
                isActive={session.id === activeSessionId}
                onSelect={() => handleSelectSession(session.id)}
                onClose={() => handleCloseSession(session.id)}
                getStateColor={getSessionStateColor}
                formatDate={formatDate}
              />
            ))}
          </div>
        )}
      </div>

      {/* Create Session Modal */}
      <ACPSessionCreateModal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSuccess={handleSessionCreated}
      />
    </div>
  )
}

interface SessionItemProps {
  session: ACPSession
  isActive: boolean
  onSelect: () => void
  onClose: () => void
  getStateColor: (state: string) => string
  formatDate: (date: Date) => string
}

const getAgentTypeColor = (agentType?: ACPAgentType): string => {
  if (!agentType) return "default"
  const info = AGENT_TYPE_INFO[agentType]
  return info?.color ?? "default"
}

const getAgentTypeName = (agentType?: ACPAgentType): string => {
  if (!agentType) return ""
  const info = AGENT_TYPE_INFO[agentType]
  return info?.name ?? agentType
}

const SessionItem: React.FC<SessionItemProps> = ({
  session,
  isActive,
  onSelect,
  onClose,
  getStateColor,
  formatDate,
}) => {
  const { t } = useTranslation(["playground", "common"])

  // Get the last part of the path for display
  const displayPath = session.cwd.split("/").filter(Boolean).slice(-2).join("/")
  const displayName = session.name || displayPath || session.cwd

  return (
    <div
      className={`group mb-1 flex cursor-pointer items-center gap-2 rounded-lg p-2 transition-colors ${
        isActive
          ? "bg-primary/10 text-primary"
          : "hover:bg-surface2"
      }`}
      onClick={onSelect}
    >
      <span className={`h-2 w-2 shrink-0 rounded-full ${getStateColor(session.state)}`} />

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium">
            {displayName}
          </span>
          {session.agentType && (
            <Tag
              className="shrink-0"
              color={getAgentTypeColor(session.agentType)}
              style={{ margin: 0, fontSize: "10px", lineHeight: "16px", padding: "0 4px" }}
            >
              <Bot className="mr-0.5 inline h-2.5 w-2.5" />
              {getAgentTypeName(session.agentType)}
            </Tag>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <Folder className="h-3 w-3 shrink-0" />
          <span className="truncate">{displayPath}</span>
          <span className="shrink-0">·</span>
          <span className="shrink-0">{formatDate(session.updatedAt)}</span>
        </div>
      </div>

      <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
        <Popconfirm
          title={t("playground:acp.closeSessionConfirm", "Close this session?")}
          onConfirm={(e) => {
            e?.stopPropagation()
            onClose()
          }}
          onCancel={(e) => e?.stopPropagation()}
          okText={t("common:yes", "Yes")}
          cancelText={t("common:no", "No")}
        >
          <Button
            type="text"
            size="small"
            icon={<Trash2 className="h-3 w-3" />}
            onClick={(e) => e.stopPropagation()}
            className="text-text-muted hover:text-error"
          />
        </Popconfirm>
      </div>

      {isActive && (
        <ChevronRight className="h-4 w-4 shrink-0 text-primary" />
      )}
    </div>
  )
}
