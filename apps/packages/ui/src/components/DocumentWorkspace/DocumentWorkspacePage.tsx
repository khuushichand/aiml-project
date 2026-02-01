import React, { useState, useEffect, useCallback } from "react"
import { useTranslation } from "react-i18next"
import { useStorage } from "@plasmohq/storage/hook"
import { Drawer, Tabs, Empty, Tooltip } from "antd"
import {
  FileText,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Lightbulb,
  Image,
  List,
  Info,
  BookOpen,
  Highlighter,
  Quote,
  HelpCircle,
  Keyboard
} from "lucide-react"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"
import { useMobile } from "@/hooks/useMediaQuery"
import type { SidebarTab, RightPanelTab } from "./types"
import { DocumentViewer } from "./DocumentViewer"
import {
  DocumentInfoTab,
  TableOfContentsTab,
  QuickInsightsTab,
  ReferencesTab,
  FiguresTab,
} from "./LeftSidebar"
import { DocumentChat, AnnotationsPanel, CitationPanel, QuizPanel } from "./RightPanel"
import { DocumentWorkspaceErrorBoundary } from "./DocumentWorkspaceErrorBoundary"
import { DocumentShortcutsModal } from "./DocumentShortcutsModal"
import { DocumentTabBar } from "./DocumentTabBar"
import { SyncStatusIndicator } from "./SyncStatusIndicator"
import {
  useAnnotations,
  useAnnotationSync,
  useAnnotationSyncOnClose,
  useReadingProgress,
  useReadingProgressAutoSave,
  useReadingProgressSaveOnClose,
} from "@/hooks/document-workspace"

// Left sidebar content
const LeftSidebarContent: React.FC<{ onHide?: () => void }> = ({ onHide }) => {
  const { t } = useTranslation(["option", "common"])
  const activeSidebarTab = useDocumentWorkspaceStore((s) => s.activeSidebarTab)
  const setActiveSidebarTab = useDocumentWorkspaceStore(
    (s) => s.setActiveSidebarTab
  )

  const sidebarTabs: Array<{
    key: SidebarTab
    label: React.ReactNode
    icon: React.ReactNode
    children: React.ReactNode
  }> = [
    {
      key: "insights",
      label: t("option:documentWorkspace.insights", "Insights"),
      icon: <Lightbulb className="h-4 w-4" />,
      children: <QuickInsightsTab />
    },
    {
      key: "figures",
      label: t("option:documentWorkspace.figures", "Figures"),
      icon: <Image className="h-4 w-4" />,
      children: <FiguresTab />
    },
    {
      key: "toc",
      label: t("option:documentWorkspace.toc", "Contents"),
      icon: <List className="h-4 w-4" />,
      children: <TableOfContentsTab />
    },
    {
      key: "info",
      label: t("option:documentWorkspace.info", "Info"),
      icon: <Info className="h-4 w-4" />,
      children: <DocumentInfoTab />
    },
    {
      key: "references",
      label: t("option:documentWorkspace.references", "References"),
      icon: <BookOpen className="h-4 w-4" />,
      children: <ReferencesTab />
    }
  ]

  return (
    <div className="flex h-full flex-col">
      <Tabs
        activeKey={activeSidebarTab}
        onChange={(key) => setActiveSidebarTab(key as SidebarTab)}
        items={sidebarTabs.map((tab) => ({
          key: tab.key,
          label: (
            <span className="flex items-center gap-1.5">
              {tab.icon}
              <span className="hidden xl:inline">{tab.label}</span>
            </span>
          ),
          children: tab.children
        }))}
        size="small"
        className="flex-1 [&_.ant-tabs-content]:h-full [&_.ant-tabs-content-holder]:flex-1 [&_.ant-tabs-tabpane]:h-full"
        tabBarStyle={{ marginBottom: 0, paddingLeft: 8, paddingRight: 8 }}
      />
    </div>
  )
}

// Right panel content
const RightPanelContent: React.FC<{ onHide?: () => void }> = ({ onHide }) => {
  const { t } = useTranslation(["option", "common"])
  const activeRightTab = useDocumentWorkspaceStore((s) => s.activeRightTab)
  const setActiveRightTab = useDocumentWorkspaceStore(
    (s) => s.setActiveRightTab
  )

  const rightTabs: Array<{
    key: RightPanelTab
    label: React.ReactNode
    icon: React.ReactNode
    children: React.ReactNode
  }> = [
    {
      key: "chat",
      label: t("option:documentWorkspace.chat", "Chat"),
      icon: <MessageSquare className="h-4 w-4" />,
      children: <DocumentChat />
    },
    {
      key: "annotations",
      label: t("option:documentWorkspace.annotations", "Notes"),
      icon: <Highlighter className="h-4 w-4" />,
      children: <AnnotationsPanel />
    },
    {
      key: "citations",
      label: t("option:documentWorkspace.citations", "Cite"),
      icon: <Quote className="h-4 w-4" />,
      children: <CitationPanel />
    },
    {
      key: "quiz",
      label: t("option:documentWorkspace.quiz", "Quiz"),
      icon: <HelpCircle className="h-4 w-4" />,
      children: <QuizPanel />
    }
  ]

  return (
    <div className="flex h-full flex-col">
      <Tabs
        activeKey={activeRightTab}
        onChange={(key) => setActiveRightTab(key as RightPanelTab)}
        items={rightTabs.map((tab) => ({
          key: tab.key,
          label: (
            <span className="flex items-center gap-1.5">
              {tab.icon}
              {tab.label}
            </span>
          ),
          children: tab.children
        }))}
        size="small"
        className="flex-1 [&_.ant-tabs-content]:h-full [&_.ant-tabs-content-holder]:flex-1 [&_.ant-tabs-tabpane]:h-full"
        tabBarStyle={{ marginBottom: 0, paddingLeft: 8, paddingRight: 8 }}
      />
    </div>
  )
}

// Header component
const WorkspaceHeader: React.FC<{
  leftPaneOpen: boolean
  rightPaneOpen: boolean
  onToggleLeftPane: () => void
  onToggleRightPane: () => void
  onShowShortcuts: () => void
  onRetrySync?: () => void
  hideToggles?: boolean
}> = ({
  leftPaneOpen,
  rightPaneOpen,
  onToggleLeftPane,
  onToggleRightPane,
  onShowShortcuts,
  onRetrySync,
  hideToggles
}) => {
  const { t } = useTranslation(["option", "common"])
  const activeDocument = useDocumentWorkspaceStore((s) => {
    const doc = s.openDocuments.find((d) => d.id === s.activeDocumentId)
    return doc
  })

  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-surface px-4">
      <div className="flex items-center gap-3">
        {!hideToggles && (
          <button
            onClick={onToggleLeftPane}
            className="rounded p-1.5 hover:bg-hover"
            title={
              leftPaneOpen
                ? t("common:collapse", "Collapse")
                : t("common:expand", "Expand")
            }
          >
            {leftPaneOpen ? (
              <PanelLeftClose className="h-5 w-5" />
            ) : (
              <PanelLeftOpen className="h-5 w-5" />
            )}
          </button>
        )}
        <div className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-primary" />
          <h1 className="text-lg font-medium">
            {activeDocument?.title ||
              t("option:documentWorkspace.title", "Document Workspace")}
          </h1>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {/* Sync status indicator */}
        <SyncStatusIndicator onRetry={onRetrySync} />

        <Tooltip title={t("option:documentWorkspace.shortcuts", "Keyboard shortcuts (?)")}>
          <button
            onClick={onShowShortcuts}
            className="rounded p-1.5 hover:bg-hover text-text-subtle hover:text-text"
            aria-label={t("option:documentWorkspace.shortcuts", "Keyboard shortcuts")}
          >
            <Keyboard className="h-5 w-5" />
          </button>
        </Tooltip>
        {!hideToggles && (
          <button
            onClick={onToggleRightPane}
            className="rounded p-1.5 hover:bg-hover"
            title={
              rightPaneOpen
                ? t("common:collapse", "Collapse")
                : t("common:expand", "Expand")
            }
          >
            {rightPaneOpen ? (
              <PanelRightClose className="h-5 w-5" />
            ) : (
              <PanelRightOpen className="h-5 w-5" />
            )}
          </button>
        )}
      </div>
    </header>
  )
}

const STORAGE_KEY_LEFT_PANE = "document-workspace-left-pane"
const STORAGE_KEY_RIGHT_PANE = "document-workspace-right-pane"

/**
 * DocumentWorkspacePage - Three-panel document reader interface
 *
 * Layout at different breakpoints:
 * - lg+ (1024px+): Full three-pane layout
 * - md (768-1023px): Viewer main, sidebar/chat as slide-out drawers
 * - sm (<768px): Bottom tab navigation between panes
 */
export const DocumentWorkspacePage: React.FC = () => {
  const { t } = useTranslation(["option", "common"])
  const isMobile = useMobile()

  // Get active document for hooks
  const activeDocumentId = useDocumentWorkspaceStore((s) => s.activeDocumentId)

  // Initialize annotation fetching and sync
  useAnnotations(activeDocumentId)
  const { retrySync } = useAnnotationSync(activeDocumentId)
  useAnnotationSyncOnClose(activeDocumentId)

  // Initialize reading progress loading and auto-save
  useReadingProgress(activeDocumentId)
  useReadingProgressAutoSave(activeDocumentId, 5000) // Save every 5 seconds
  useReadingProgressSaveOnClose(activeDocumentId)

  // Pane state with persistence
  const [leftPaneOpen, setLeftPaneOpen] = useStorage(STORAGE_KEY_LEFT_PANE, true)
  const [rightPaneOpen, setRightPaneOpen] = useStorage(
    STORAGE_KEY_RIGHT_PANE,
    true
  )

  // Mobile drawer state
  const [leftDrawerOpen, setLeftDrawerOpen] = useState(false)
  const [rightDrawerOpen, setRightDrawerOpen] = useState(false)

  // Mobile tab state
  const [activeTab, setActiveTab] = useState<"sidebar" | "viewer" | "chat">(
    "viewer"
  )

  // Keyboard shortcuts modal state
  const [shortcutsModalOpen, setShortcutsModalOpen] = useState(false)

  const handleShowShortcuts = useCallback(() => {
    setShortcutsModalOpen(true)
  }, [])

  const handleCloseShortcuts = useCallback(() => {
    setShortcutsModalOpen(false)
  }, [])

  // Listen for "?" key to open shortcuts modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if typing in an input or if modal is already open
      const target = e.target as HTMLElement
      const isInputField =
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable

      if (isInputField) return

      // "?" key (Shift + /)
      if (e.key === "?" || (e.shiftKey && e.key === "/")) {
        e.preventDefault()
        setShortcutsModalOpen(true)
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [])

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

  // Mobile tab items
  const mobileTabItems = [
    {
      key: "sidebar",
      label: (
        <span className="flex items-center gap-1.5">
          <List className="h-4 w-4" />
          <span>{t("option:documentWorkspace.sidebar", "Sidebar")}</span>
        </span>
      ),
      children: <LeftSidebarContent />
    },
    {
      key: "viewer",
      label: (
        <span className="flex items-center gap-1.5">
          <FileText className="h-4 w-4" />
          <span>{t("option:documentWorkspace.document", "Document")}</span>
        </span>
      ),
      children: <DocumentViewer />
    },
    {
      key: "chat",
      label: (
        <span className="flex items-center gap-1.5">
          <MessageSquare className="h-4 w-4" />
          <span>{t("option:documentWorkspace.chat", "Chat")}</span>
        </span>
      ),
      children: <RightPanelContent />
    }
  ]

  // Mobile layout (< 768px): Tab navigation
  if (isMobile) {
    return (
      <DocumentWorkspaceErrorBoundary>
        <div className="flex h-full flex-col bg-bg text-text">
          <WorkspaceHeader
            leftPaneOpen={false}
            rightPaneOpen={false}
            onToggleLeftPane={handleToggleLeftPane}
            onToggleRightPane={handleToggleRightPane}
            onShowShortcuts={handleShowShortcuts}
            onRetrySync={retrySync}
            hideToggles
          />
          <DocumentShortcutsModal
            open={shortcutsModalOpen}
            onClose={handleCloseShortcuts}
          />

          <Tabs
            activeKey={activeTab}
            onChange={(key) =>
              setActiveTab(key as "sidebar" | "viewer" | "chat")
            }
            items={mobileTabItems}
            centered
            className="flex-1 [&_.ant-tabs-content]:h-full [&_.ant-tabs-content-holder]:flex-1 [&_.ant-tabs-tabpane]:h-full"
            tabBarStyle={{ marginBottom: 0, borderBottom: "1px solid var(--border)" }}
          />
        </div>
      </DocumentWorkspaceErrorBoundary>
    )
  }

  // Tablet/Desktop layout
  return (
    <DocumentWorkspaceErrorBoundary>
      <div className="flex h-full flex-col bg-bg text-text">
        <WorkspaceHeader
          leftPaneOpen={!!leftPaneOpen}
          rightPaneOpen={!!rightPaneOpen}
          onToggleLeftPane={handleToggleLeftPane}
          onToggleRightPane={handleToggleRightPane}
          onShowShortcuts={handleShowShortcuts}
          onRetrySync={retrySync}
        />
        <DocumentShortcutsModal
          open={shortcutsModalOpen}
          onClose={handleCloseShortcuts}
        />

        {/* Document tabs - shown when multiple documents are open */}
        <DocumentTabBar />

        <div className="flex min-h-0 flex-1">
          {/* Left pane - Sidebar (desktop) */}
          {leftPaneOpen && (
            <aside className="hidden w-72 shrink-0 border-r border-border bg-surface lg:flex lg:flex-col">
              <LeftSidebarContent onHide={() => setLeftPaneOpen(false)} />
            </aside>
          )}

          {/* Left pane - Sidebar (tablet drawer) */}
          <Drawer
            title={
              <span className="flex items-center gap-2">
                <List className="h-4 w-4" />
                {t("option:documentWorkspace.sidebar", "Sidebar")}
              </span>
            }
            placement="left"
            onClose={() => setLeftDrawerOpen(false)}
            open={leftDrawerOpen}
            width={320}
            className="lg:hidden"
            styles={{ body: { padding: 0 } }}
          >
            <LeftSidebarContent />
          </Drawer>

          {/* Center pane - Document Viewer */}
          <main className="flex min-w-0 flex-1 flex-col bg-bg">
            <DocumentViewer />
          </main>

          {/* Right pane - Chat/Annotations (desktop) */}
          {rightPaneOpen && (
            <aside className="hidden w-80 shrink-0 border-l border-border bg-surface lg:flex lg:flex-col">
              <RightPanelContent onHide={() => setRightPaneOpen(false)} />
            </aside>
          )}

          {/* Right pane - Chat/Annotations (tablet drawer) */}
          <Drawer
            title={
              <span className="flex items-center gap-2">
                <MessageSquare className="h-4 w-4" />
                {t("option:documentWorkspace.chat", "Chat")}
              </span>
            }
            placement="right"
            onClose={() => setRightDrawerOpen(false)}
            open={rightDrawerOpen}
            width={360}
            className="lg:hidden"
            styles={{ body: { padding: 0 } }}
          >
            <RightPanelContent />
          </Drawer>
        </div>
      </div>
    </DocumentWorkspaceErrorBoundary>
  )
}

export default DocumentWorkspacePage
