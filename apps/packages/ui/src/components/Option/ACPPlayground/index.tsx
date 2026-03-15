import React, { useEffect } from "react"
import { useTranslation } from "react-i18next"
import { useStorage } from "@plasmohq/storage/hook"
import { Drawer, Tabs } from "antd"
import { Bot, MessageSquare, Wrench, Terminal } from "lucide-react"
import { useMobile } from "@/hooks/useMediaQuery"
import { useACPSession } from "@/hooks/useACPSession"
import { ACPRestClient } from "@/services/acp/client"
import { useACPSessionsStore } from "@/store/acp-sessions"
import type { ACPPermissionTier } from "@/services/acp/types"
import { ACPPlaygroundHeader } from "./ACPPlaygroundHeader"
import { ACPSessionPanel } from "./ACPSessionPanel"
import { ACPChatPanel } from "./ACPChatPanel"
import { ACPToolsPanel } from "./ACPToolsPanel"
import { ACPPermissionModal } from "./ACPPermissionModal"
import { ACPWorkspacePanel } from "./ACPWorkspacePanel"

const ACP_LEFT_PANE_KEY = "acp-playground-left-pane"
const ACP_RIGHT_PANE_KEY = "acp-playground-right-pane"

/**
 * ACPPlayground - Agent Client Protocol interface
 *
 * Enables interaction with downstream agents like Claude Code through ACP.
 *
 * Layout:
 * - Left pane: Session list and creation
 * - Center: Agent chat/conversation view
 * - Right pane: Tools and capabilities display
 */
export const ACPPlayground: React.FC = () => {
  const { t } = useTranslation(["playground", "option", "common"])
  const isMobile = useMobile()

  // Pane state with persistence
  const [leftPaneOpen, setLeftPaneOpen] = useStorage(ACP_LEFT_PANE_KEY, true)
  const [rightPaneOpen, setRightPaneOpen] = useStorage(ACP_RIGHT_PANE_KEY, true)
  const [serverUrl] = useStorage("serverUrl", "http://localhost:8000")
  const [authMode] = useStorage("authMode", "single-user")
  const [apiKey] = useStorage("apiKey", "")
  const [accessToken] = useStorage("accessToken", "")

  // Mobile drawer state
  const [leftDrawerOpen, setLeftDrawerOpen] = React.useState(false)
  const [rightDrawerOpen, setRightDrawerOpen] = React.useState(false)

  // Mobile tab state
  const [activeTab, setActiveTab] = React.useState<"sessions" | "chat" | "tools" | "workspace">("chat")
  const [rightTab, setRightTab] = React.useState<"tools" | "workspace">("tools")

  // Store
  const sessionsById = useACPSessionsStore((s) => s.sessions)
  const activeSessionId = useACPSessionsStore((s) => s.activeSessionId)
  const sessions = React.useMemo(
    () =>
      Object.values(sessionsById).sort(
        (a, b) => b.updatedAt.getTime() - a.updatedAt.getTime()
      ),
    [sessionsById]
  )
  const activeSession = React.useMemo(
    () => (activeSessionId ? sessionsById[activeSessionId] : undefined),
    [activeSessionId, sessionsById]
  )
  const updateSessionState = useACPSessionsStore((s) => s.updateSessionState)
  const setSessionCapabilities = useACPSessionsStore((s) => s.setSessionCapabilities)
  const addUpdate = useACPSessionsStore((s) => s.addUpdate)
  const addPendingPermission = useACPSessionsStore((s) => s.addPendingPermission)
  const removePendingPermission = useACPSessionsStore((s) => s.removePendingPermission)
  const clearPendingPermissions = useACPSessionsStore((s) => s.clearPendingPermissions)
  const upsertSessionsFromServerList = useACPSessionsStore((s) => s.upsertSessionsFromServerList)
  const applySessionDetail = useACPSessionsStore((s) => s.applySessionDetail)
  const applySessionUsage = useACPSessionsStore((s) => s.applySessionUsage)
  const globalError = useACPSessionsStore((s) => s.globalError)
  const setGlobalError = useACPSessionsStore((s) => s.setGlobalError)
  const cleanupExpiredSessions = useACPSessionsStore((s) => s.cleanupExpiredSessions)
  const workspaceTabLabel = t("playground:acp.workspace.title", "Workspace")
  const [isHydratingSessions, setIsHydratingSessions] = React.useState(false)

  const restClient = React.useMemo(
    () =>
      new ACPRestClient({
        serverUrl,
        getAuthHeaders: async () => {
          const headers: Record<string, string> = {}
          if (authMode === "single-user" && apiKey) {
            headers["X-API-KEY"] = apiKey
          } else if (authMode === "multi-user" && accessToken) {
            headers.Authorization = `Bearer ${accessToken}`
          }
          return headers
        },
        getAuthParams: async () => ({
          token: authMode === "multi-user" && accessToken ? accessToken : undefined,
          api_key: authMode === "single-user" && apiKey ? apiKey : undefined,
        }),
      }),
    [serverUrl, authMode, apiKey, accessToken]
  )

  const refreshSessionsFromServer = React.useCallback(async () => {
    setIsHydratingSessions(true)
    try {
      const response = await restClient.listSessions({ limit: 200, offset: 0 })
      upsertSessionsFromServerList(response.sessions ?? [])
    } catch (error) {
      console.warn("Failed to hydrate ACP sessions from backend:", error)
    } finally {
      setIsHydratingSessions(false)
    }
  }, [restClient, upsertSessionsFromServerList])

  // Single ACP connection shared across chat + modal actions.
  const {
    state,
    isConnected,
    error: websocketError,
    connect,
    sendPrompt,
    cancel,
    approvePermission,
    denyPermission,
  } = useACPSession({
    sessionId: activeSessionId ?? undefined,
    autoConnect: !!activeSessionId,
    onConnected: (message) => {
      updateSessionState(message.session_id, "connected")
      setGlobalError(null)
      if (message.agent_capabilities) {
        setSessionCapabilities(message.session_id, message.agent_capabilities)
      }
    },
    onUpdate: (message) => {
      addUpdate(message.session_id, {
        type: message.update_type,
        data: message.data,
      })
    },
    onPermissionRequest: (message) => {
      addPendingPermission(message.session_id, {
        request_id: message.request_id,
        tool_name: message.tool_name,
        tool_arguments: message.tool_arguments,
        tier: message.tier,
        approval_requirement: message.approval_requirement,
        governance_reason: message.governance_reason,
        deny_reason: message.deny_reason,
        provenance_summary: message.provenance_summary,
        runtime_narrowing_reason: message.runtime_narrowing_reason,
        policy_snapshot_fingerprint: message.policy_snapshot_fingerprint,
        timeout_seconds: message.timeout_seconds,
        requestedAt: new Date(),
      })
    },
    onPromptComplete: (message) => {
      clearPendingPermissions(message.session_id)
      updateSessionState(message.session_id, "connected")
    },
    onError: (message) => {
      if (message.session_id) {
        updateSessionState(message.session_id, "error")
      }
      setGlobalError(message.message)
    },
  })

  // Cleanup expired sessions on mount
  useEffect(() => {
    cleanupExpiredSessions()
  }, [cleanupExpiredSessions])

  // Hydrate persisted ACP sessions from backend when the page loads.
  useEffect(() => {
    void refreshSessionsFromServer()
  }, [refreshSessionsFromServer])

  // Keep the active session state in sync with the shared ACP hook.
  useEffect(() => {
    if (!activeSessionId) return
    updateSessionState(activeSessionId, state)
    if (state === "disconnected") {
      clearPendingPermissions(activeSessionId)
    }
  }, [activeSessionId, state, updateSessionState, clearPendingPermissions])

  const previousActiveSessionIdRef = React.useRef<string | null>(null)

  // Mark the previous active session disconnected when switching sessions.
  useEffect(() => {
    const previousSessionId = previousActiveSessionIdRef.current
    if (previousSessionId && previousSessionId !== activeSessionId) {
      updateSessionState(previousSessionId, "disconnected")
      clearPendingPermissions(previousSessionId)
    }
    previousActiveSessionIdRef.current = activeSessionId
  }, [activeSessionId, updateSessionState, clearPendingPermissions])

  useEffect(() => {
    setGlobalError(null)
  }, [activeSessionId, setGlobalError])

  // When switching sessions, refresh detail + usage if the session exists server-side.
  useEffect(() => {
    if (!activeSessionId) return

    let cancelled = false
    const loadSessionMetadata = async () => {
      try {
        const [detailResult, usageResult] = await Promise.allSettled([
          restClient.getSessionDetail(activeSessionId),
          restClient.getSessionUsage(activeSessionId),
        ])

        if (cancelled) return

        if (detailResult.status === "fulfilled") {
          applySessionDetail(detailResult.value)
        }
        if (usageResult.status === "fulfilled") {
          applySessionUsage(usageResult.value)
        }
      } catch {
        // Ignore metadata refresh failures for local-only sessions.
      }
    }

    void loadSessionMetadata()

    return () => {
      cancelled = true
    }
  }, [activeSessionId, restClient, applySessionDetail, applySessionUsage])

  const handleToggleLeftPane = () => {
    if (isMobile) {
      setLeftDrawerOpen(!leftDrawerOpen)
    } else {
      setLeftPaneOpen(!leftPaneOpen)
    }
  }

  const handleToggleRightPane = () => {
    if (isMobile) {
      setRightDrawerOpen(!rightDrawerOpen)
    } else {
      setRightPaneOpen(!rightPaneOpen)
    }
  }

  const pendingPermissions = activeSession?.pendingPermissions ?? []
  const hasPendingPermissions = pendingPermissions.length > 0

  const handleApprovePermission = React.useCallback((requestId: string, batchApproveTier?: ACPPermissionTier) => {
    try {
      approvePermission(requestId, batchApproveTier)
      if (activeSessionId) {
        removePendingPermission(activeSessionId, requestId)
      }
    } catch (error) {
      setGlobalError(error instanceof Error ? error.message : "Failed to approve permission")
    }
  }, [approvePermission, activeSessionId, removePendingPermission, setGlobalError])

  const handleDenyPermission = React.useCallback((requestId: string) => {
    try {
      denyPermission(requestId)
      if (activeSessionId) {
        removePendingPermission(activeSessionId, requestId)
      }
    } catch (error) {
      setGlobalError(error instanceof Error ? error.message : "Failed to deny permission")
    }
  }, [denyPermission, activeSessionId, removePendingPermission, setGlobalError])

  // Mobile tab items
  const mobileTabItems = [
    {
      key: "sessions",
      label: (
        <span className="flex items-center gap-1.5">
          <Bot className="h-4 w-4" />
          <span>{t("playground:acp.sessions", "Sessions")}</span>
          {sessions.length > 0 && (
            <span className="ml-1 rounded-full bg-primary px-1.5 py-0.5 text-xs text-white">
              {sessions.length}
            </span>
          )}
        </span>
      ),
      children: (
        <ACPSessionPanel
          onRefreshSessions={refreshSessionsFromServer}
          isRefreshing={isHydratingSessions}
        />
      ),
    },
    {
      key: "chat",
      label: (
        <span className="flex items-center gap-1.5">
          <MessageSquare className="h-4 w-4" />
          <span>{t("playground:acp.chat", "Chat")}</span>
        </span>
      ),
      children: (
        <ACPChatPanel
          state={state}
          isConnected={isConnected}
          updates={activeSession?.updates ?? []}
          connect={connect}
          error={globalError ?? websocketError}
          sendPrompt={sendPrompt}
          cancel={cancel}
        />
      ),
    },
    {
      key: "tools",
      label: (
        <span className="flex items-center gap-1.5">
          <Wrench className="h-4 w-4" />
          <span>{t("playground:acp.tools", "Tools")}</span>
        </span>
      ),
      children: <ACPToolsPanel />,
    },
    {
      key: "workspace",
      label: (
        <span className="flex items-center gap-1.5">
          <Terminal className="h-4 w-4" />
          <span>{workspaceTabLabel}</span>
        </span>
      ),
      children: <ACPWorkspacePanel />,
    },
  ]

  // Mobile layout
  if (isMobile) {
    return (
      <div className="flex h-full flex-col bg-bg text-text">
        <ACPPlaygroundHeader
          leftPaneOpen={false}
          rightPaneOpen={false}
          onToggleLeftPane={handleToggleLeftPane}
          onToggleRightPane={handleToggleRightPane}
          hideToggles
        />

        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as typeof activeTab)}
          items={mobileTabItems}
          centered
          className="flex-1 [&_.ant-tabs-content]:h-full [&_.ant-tabs-content-holder]:flex-1 [&_.ant-tabs-tabpane]:h-full"
          tabBarStyle={{ marginBottom: 0, borderBottom: "1px solid var(--border)" }}
        />

        {hasPendingPermissions && (
          <ACPPermissionModal
            pendingPermissions={pendingPermissions}
            approvePermission={handleApprovePermission}
            denyPermission={handleDenyPermission}
          />
        )}
      </div>
    )
  }

  // Desktop layout
  return (
    <div className="flex h-full flex-col bg-bg text-text">
      <ACPPlaygroundHeader
        leftPaneOpen={!!leftPaneOpen}
        rightPaneOpen={!!rightPaneOpen}
        onToggleLeftPane={handleToggleLeftPane}
        onToggleRightPane={handleToggleRightPane}
      />

      <div className="flex min-h-0 flex-1">
        {/* Left pane - Sessions (desktop) */}
        {leftPaneOpen && (
          <aside className="hidden w-72 shrink-0 border-r border-border bg-surface lg:flex lg:flex-col">
            <ACPSessionPanel
              onHide={() => setLeftPaneOpen(false)}
              onRefreshSessions={refreshSessionsFromServer}
              isRefreshing={isHydratingSessions}
            />
          </aside>
        )}

        {/* Left pane - Sessions (tablet drawer) */}
        <Drawer
          title={
            <span className="flex items-center gap-2">
              <Bot className="h-4 w-4" />
              {t("playground:acp.sessions", "Sessions")}
            </span>
          }
          placement="left"
          onClose={() => setLeftDrawerOpen(false)}
          open={leftDrawerOpen}
          size={320}
          className="lg:hidden"
          styles={{ body: { padding: 0 } }}
        >
          <ACPSessionPanel
            onRefreshSessions={refreshSessionsFromServer}
            isRefreshing={isHydratingSessions}
          />
        </Drawer>

        {/* Center pane - Chat */}
        <main className="flex min-w-0 flex-1 flex-col">
          <ACPChatPanel
            state={state}
            isConnected={isConnected}
            updates={activeSession?.updates ?? []}
            connect={connect}
            error={globalError ?? websocketError}
            sendPrompt={sendPrompt}
            cancel={cancel}
          />
        </main>

        {/* Right pane - Tools (desktop) */}
        {rightPaneOpen && (
          <aside className="hidden w-80 shrink-0 border-l border-border bg-surface lg:flex lg:flex-col">
            <Tabs
              activeKey={rightTab}
              onChange={(key) => setRightTab(key as typeof rightTab)}
              items={[
                {
                  key: "tools",
                  label: t("playground:acp.tools", "Tools"),
                  children: <ACPToolsPanel onHide={() => setRightPaneOpen(false)} />,
                },
                {
                  key: "workspace",
                  label: workspaceTabLabel,
                  children: <ACPWorkspacePanel />,
                },
              ]}
              className="h-full [&_.ant-tabs-content]:h-full [&_.ant-tabs-content-holder]:flex-1 [&_.ant-tabs-tabpane]:h-full"
            />
          </aside>
        )}

        {/* Right pane - Tools (tablet drawer) */}
        <Drawer
          title={
            <span className="flex items-center gap-2">
              <Wrench className="h-4 w-4" />
              {t("playground:acp.tools", "Tools")}
            </span>
          }
          placement="right"
          onClose={() => setRightDrawerOpen(false)}
          open={rightDrawerOpen}
          size={320}
          className="lg:hidden"
          styles={{ body: { padding: 0 } }}
        >
          <Tabs
            activeKey={rightTab}
            onChange={(key) => setRightTab(key as typeof rightTab)}
            items={[
              {
                key: "tools",
                label: t("playground:acp.tools", "Tools"),
                children: (
                  <ACPToolsPanel
                    onHide={() => {
                      setRightPaneOpen(false)
                      setRightDrawerOpen(false)
                    }}
                  />
                ),
              },
              {
                key: "workspace",
                label: workspaceTabLabel,
                children: <ACPWorkspacePanel />,
              },
            ]}
            className="h-full [&_.ant-tabs-content]:h-full [&_.ant-tabs-content-holder]:flex-1 [&_.ant-tabs-tabpane]:h-full"
          />
        </Drawer>
      </div>

      {/* Permission modal */}
      {hasPendingPermissions && (
        <ACPPermissionModal
          pendingPermissions={pendingPermissions}
          approvePermission={handleApprovePermission}
          denyPermission={handleDenyPermission}
        />
      )}
    </div>
  )
}

export default ACPPlayground
