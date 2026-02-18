import React, { useEffect } from "react"
import { useTranslation } from "react-i18next"
import { Drawer, Tabs } from "antd"
import { FileText, MessageSquare, Sparkles } from "lucide-react"
import { useWorkspaceStore } from "@/store/workspace"
import { useMobile } from "@/hooks/useMediaQuery"
import { WorkspaceHeader } from "./WorkspaceHeader"
import { SourcesPane } from "./SourcesPane"
import { ChatPane } from "./ChatPane"
import { StudioPane } from "./StudioPane"

/**
 * WorkspacePlayground - NotebookLM-style three-pane research interface
 *
 * Layout at different breakpoints:
 * - lg+ (1024px+): Full three-pane layout
 * - md (768-1023px): Chat main, Sources/Studio as slide-out drawers
 * - sm (<768px): Bottom tab navigation between panes
 *
 * Features:
 * - Sources Pane (left): Add and manage research sources
 * - Chat Pane (middle): RAG-powered conversation with selected sources
 * - Studio Pane (right): Generate outputs (summaries, quizzes, flashcards, etc.)
 */
export const WorkspacePlayground: React.FC = () => {
  const { t } = useTranslation(["playground", "option", "common"])
  const isMobile = useMobile()

  // Mobile drawer state
  const [leftDrawerOpen, setLeftDrawerOpen] = React.useState(false)
  const [rightDrawerOpen, setRightDrawerOpen] = React.useState(false)

  // Mobile tab state
  const [activeTab, setActiveTab] = React.useState<"sources" | "chat" | "studio">("chat")

  // Workspace store
  const workspaceId = useWorkspaceStore((s) => s.workspaceId)
  const initializeWorkspace = useWorkspaceStore((s) => s.initializeWorkspace)
  const selectedSourceIds = useWorkspaceStore((s) => s.selectedSourceIds)
  const generatedArtifacts = useWorkspaceStore((s) => s.generatedArtifacts)
  const leftPaneCollapsed = useWorkspaceStore((s) => s.leftPaneCollapsed)
  const rightPaneCollapsed = useWorkspaceStore((s) => s.rightPaneCollapsed)
  const setLeftPaneCollapsed = useWorkspaceStore((s) => s.setLeftPaneCollapsed)
  const setRightPaneCollapsed = useWorkspaceStore((s) => s.setRightPaneCollapsed)

  const leftPaneOpen = !leftPaneCollapsed
  const rightPaneOpen = !rightPaneCollapsed

  // Initialize workspace on mount if not already initialized — use ref to keep dep stable
  const initRef = React.useRef(initializeWorkspace)
  initRef.current = initializeWorkspace
  useEffect(() => {
    if (!workspaceId) {
      initRef.current()
    }
  }, [workspaceId])

  const handleToggleLeftPane = () => {
    if (isMobile) {
      setLeftDrawerOpen(!leftDrawerOpen)
    } else {
      setLeftPaneCollapsed(leftPaneOpen)
    }
  }

  const handleToggleRightPane = () => {
    if (isMobile) {
      setRightDrawerOpen(!rightDrawerOpen)
    } else {
      setRightPaneCollapsed(rightPaneOpen)
    }
  }

  // Mobile tab items with badges
  const mobileTabItems = [
    {
      key: "sources",
      label: (
        <span className="flex items-center gap-1.5">
          <FileText className="h-4 w-4" />
          <span>{t("playground:sources.title", "Sources")}</span>
          {selectedSourceIds.length > 0 && (
            <span className="ml-1 rounded-full bg-primary px-1.5 py-0.5 text-xs text-white">
              {selectedSourceIds.length}
            </span>
          )}
        </span>
      ),
      children: <SourcesPane />
    },
    {
      key: "chat",
      label: (
        <span className="flex items-center gap-1.5">
          <MessageSquare className="h-4 w-4" />
          <span>{t("playground:chat.title", "Chat")}</span>
        </span>
      ),
      children: <ChatPane />
    },
    {
      key: "studio",
      label: (
        <span className="flex items-center gap-1.5">
          <Sparkles className="h-4 w-4" />
          <span>{t("playground:studio.title", "Studio")}</span>
          {generatedArtifacts.length > 0 && (
            <span className="ml-1 rounded-full bg-success px-1.5 py-0.5 text-xs text-white">
              {generatedArtifacts.length}
            </span>
          )}
        </span>
      ),
      children: <StudioPane />
    }
  ]

  // Mobile layout (< 768px): Tab navigation
  if (isMobile) {
    return (
      <div className="flex h-full flex-col bg-bg text-text">
        {/* Mobile Header */}
        <WorkspaceHeader
          leftPaneOpen={false}
          rightPaneOpen={false}
          onToggleLeftPane={handleToggleLeftPane}
          onToggleRightPane={handleToggleRightPane}
          hideToggles
        />

        {/* Mobile Tabs */}
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as typeof activeTab)}
          items={mobileTabItems}
          centered
          className="flex-1 [&_.ant-tabs-content]:h-full [&_.ant-tabs-content-holder]:flex-1 [&_.ant-tabs-tabpane]:h-full"
          tabBarStyle={{ marginBottom: 0, borderBottom: "1px solid var(--border)" }}
        />
      </div>
    )
  }

  // Tablet/Desktop layout
  return (
    <div className="flex h-full flex-col bg-bg text-text">
      {/* Header */}
      <WorkspaceHeader
        leftPaneOpen={!!leftPaneOpen}
        rightPaneOpen={!!rightPaneOpen}
        onToggleLeftPane={handleToggleLeftPane}
        onToggleRightPane={handleToggleRightPane}
      />

      {/* Main three-pane layout */}
      <div className="flex min-h-0 flex-1">
        {/* Left pane - Sources (desktop) */}
        {leftPaneOpen && (
          <aside className="hidden w-72 shrink-0 border-r border-border bg-surface lg:flex lg:flex-col">
            <SourcesPane onHide={() => setLeftPaneCollapsed(true)} />
          </aside>
        )}

        {/* Left pane - Sources (tablet drawer) */}
        <Drawer
          title={
            <span className="flex items-center gap-2">
              <FileText className="h-4 w-4" />
              {t("playground:sources.title", "Sources")}
            </span>
          }
          placement="left"
          onClose={() => setLeftDrawerOpen(false)}
          open={leftDrawerOpen}
          className="lg:hidden"
          styles={{ wrapper: { width: 320 }, body: { padding: 0 } }}
        >
          <SourcesPane />
        </Drawer>

        {/* Center pane - Chat */}
        <main className="flex min-w-0 flex-1 flex-col">
          <ChatPane />
        </main>

        {/* Right pane - Studio (desktop) */}
        {rightPaneOpen && (
          <aside className="hidden w-80 shrink-0 border-l border-border bg-surface lg:flex lg:flex-col">
            <StudioPane onHide={() => setRightPaneCollapsed(true)} />
          </aside>
        )}

        {/* Right pane - Studio (tablet drawer) */}
        <Drawer
          title={
            <span className="flex items-center gap-2">
              <Sparkles className="h-4 w-4" />
              {t("playground:studio.title", "Studio")}
            </span>
          }
          placement="right"
          onClose={() => setRightDrawerOpen(false)}
          open={rightDrawerOpen}
          className="lg:hidden"
          styles={{ wrapper: { width: 360 }, body: { padding: 0 } }}
        >
          <StudioPane />
        </Drawer>
      </div>
    </div>
  )
}

export default WorkspacePlayground
