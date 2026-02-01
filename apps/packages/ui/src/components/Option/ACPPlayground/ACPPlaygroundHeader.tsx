import React from "react"
import { useTranslation } from "react-i18next"
import { Tooltip } from "antd"
import {
  Bot,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Settings,
} from "lucide-react"
import { useACPSessionsStore } from "@/store/acp-sessions"

interface ACPPlaygroundHeaderProps {
  leftPaneOpen: boolean
  rightPaneOpen: boolean
  onToggleLeftPane: () => void
  onToggleRightPane: () => void
  hideToggles?: boolean
}

export const ACPPlaygroundHeader: React.FC<ACPPlaygroundHeaderProps> = ({
  leftPaneOpen,
  rightPaneOpen,
  onToggleLeftPane,
  onToggleRightPane,
  hideToggles = false,
}) => {
  const { t } = useTranslation(["playground", "option", "common"])

  const activeSession = useACPSessionsStore((s) =>
    s.activeSessionId ? s.getSession(s.activeSessionId) : undefined
  )

  const getStateColor = (state: string | undefined) => {
    switch (state) {
      case "connected":
        return "bg-success"
      case "running":
        return "bg-primary animate-pulse"
      case "waiting_permission":
        return "bg-warning animate-pulse"
      case "error":
        return "bg-error"
      case "connecting":
        return "bg-info animate-pulse"
      default:
        return "bg-text-muted"
    }
  }

  const getStateLabel = (state: string | undefined) => {
    switch (state) {
      case "connected":
        return t("playground:acp.state.connected", "Connected")
      case "running":
        return t("playground:acp.state.running", "Running")
      case "waiting_permission":
        return t("playground:acp.state.waitingPermission", "Awaiting Permission")
      case "error":
        return t("playground:acp.state.error", "Error")
      case "connecting":
        return t("playground:acp.state.connecting", "Connecting...")
      default:
        return t("playground:acp.state.disconnected", "Disconnected")
    }
  }

  return (
    <header className="flex items-center justify-between border-b border-border bg-surface px-4 py-3">
      <div className="flex items-center gap-3">
        {!hideToggles && (
          <Tooltip
            title={
              leftPaneOpen
                ? t("playground:acp.hideSessions", "Hide sessions")
                : t("playground:acp.showSessions", "Show sessions")
            }
          >
            <button
              type="button"
              onClick={onToggleLeftPane}
              className="hidden rounded-lg p-2 text-text-muted transition-colors hover:bg-surface2 hover:text-text lg:block"
              aria-pressed={leftPaneOpen}
            >
              {leftPaneOpen ? (
                <PanelLeftClose className="h-4 w-4" />
              ) : (
                <PanelLeftOpen className="h-4 w-4" />
              )}
            </button>
          </Tooltip>
        )}

        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-primary" />
          <div>
            <h1 className="text-lg font-semibold text-text">
              {t("playground:acp.title", "Agent Playground")}
            </h1>
            <p className="text-xs text-text-muted">
              {t("playground:acp.subtitle", "Interact with AI coding agents via ACP")}
            </p>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Session status indicator */}
        {activeSession && (
          <div className="flex items-center gap-2 rounded-lg bg-surface2 px-3 py-1.5">
            <span
              className={`h-2 w-2 rounded-full ${getStateColor(activeSession.state)}`}
            />
            <span className="text-sm text-text-muted">
              {getStateLabel(activeSession.state)}
            </span>
          </div>
        )}

        {!hideToggles && (
          <Tooltip
            title={
              rightPaneOpen
                ? t("playground:acp.hideTools", "Hide tools")
                : t("playground:acp.showTools", "Show tools")
            }
          >
            <button
              type="button"
              onClick={onToggleRightPane}
              className="hidden rounded-lg p-2 text-text-muted transition-colors hover:bg-surface2 hover:text-text lg:block"
              aria-pressed={rightPaneOpen}
            >
              {rightPaneOpen ? (
                <PanelRightClose className="h-4 w-4" />
              ) : (
                <PanelRightOpen className="h-4 w-4" />
              )}
            </button>
          </Tooltip>
        )}
      </div>
    </header>
  )
}
