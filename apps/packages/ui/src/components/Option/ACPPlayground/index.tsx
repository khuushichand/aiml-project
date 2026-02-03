import React, { useEffect } from "react"
import { useTranslation } from "react-i18next"
import { useStorage } from "@plasmohq/storage/hook"
import { Drawer, Tabs } from "antd"
import { Bot, MessageSquare, Wrench, Terminal } from "lucide-react"
import { useMobile } from "@/hooks/useMediaQuery"
import { useACPSessionsStore } from "@/store/acp-sessions"
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

  // Mobile drawer state
  const [leftDrawerOpen, setLeftDrawerOpen] = React.useState(false)
  const [rightDrawerOpen, setRightDrawerOpen] = React.useState(false)

  // Mobile tab state
  const [activeTab, setActiveTab] = React.useState<"sessions" | "chat" | "tools" | "workspace">("chat")
  const [rightTab, setRightTab] = React.useState<"tools" | "workspace">("tools")

  // Store
  const sessions = useACPSessionsStore((s) => s.getSessions())
  const activeSessionId = useACPSessionsStore((s) => s.activeSessionId)
  const activeSession = useACPSessionsStore((s) =>
    s.activeSessionId ? s.getSession(s.activeSessionId) : undefined
  )
  const cleanupExpiredSessions = useACPSessionsStore((s) => s.cleanupExpiredSessions)

  // Cleanup expired sessions on mount
  useEffect(() => {
    cleanupExpiredSessions()
  }, [cleanupExpiredSessions])

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

  // Check if there are pending permissions
  const hasPendingPermissions =
    activeSession && activeSession.pendingPermissions.length > 0

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
      children: <ACPSessionPanel />,
    },
    {
      key: "chat",
      label: (
        <span className="flex items-center gap-1.5">
          <MessageSquare className="h-4 w-4" />
          <span>{t("playground:acp.chat", "Chat")}</span>
        </span>
      ),
      children: <ACPChatPanel />,
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
          <span>{t("playground:acp.workspace", "Workspace")}</span>
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

        {hasPendingPermissions && <ACPPermissionModal />}
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
            <ACPSessionPanel onHide={() => setLeftPaneOpen(false)} />
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
          width={320}
          className="lg:hidden"
          styles={{ body: { padding: 0 } }}
        >
          <ACPSessionPanel />
        </Drawer>

        {/* Center pane - Chat */}
        <main className="flex min-w-0 flex-1 flex-col">
          <ACPChatPanel />
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
                  label: t("playground:acp.workspace", "Workspace"),
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
          width={320}
          className="lg:hidden"
          styles={{ body: { padding: 0 } }}
        >
          <ACPToolsPanel />
        </Drawer>
      </div>

      {/* Permission modal */}
      {hasPendingPermissions && <ACPPermissionModal />}
    </div>
  )
}

export default ACPPlayground
