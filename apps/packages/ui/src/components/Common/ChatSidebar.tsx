import React, { useState, useMemo } from "react"
import { useNavigate, useLocation } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { Input, Tooltip, Segmented } from "antd"
import {
  Plus,
  Search,
  Settings,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CheckSquare
} from "lucide-react"
import {
  SIDEBAR_ACTIVE_TAB_SETTING,
  SIDEBAR_SHORTCUTS_COLLAPSED_SETTING,
  SIDEBAR_SHORTCUT_SELECTION_SETTING
} from "@/services/settings/ui-settings"
import { useSetting } from "@/hooks/useSetting"

import { useDebounce } from "@/hooks/useDebounce"
import { useServerChatHistory } from "@/hooks/useServerChatHistory"
import { useClearChat } from "@/hooks/chat/useClearChat"
import { useStoreMessageOption } from "@/store/option"
import { useFolderStore } from "@/store/folder"
import { useRouteTransitionStore } from "@/store/route-transition"
import { cn } from "@/libs/utils"
import { ServerChatList } from "./ChatSidebar/ServerChatList"
import { FolderChatList } from "./ChatSidebar/FolderChatList"
import {
  normalizeSidebarShortcutSelection,
  type SidebarShortcutAction
} from "./ChatSidebar/shortcut-actions"
import { QuickChatHelperButton } from "@/components/Common/QuickChatHelper"
import { ModeToggle } from "@/components/Sidepanel/Chat/ModeToggle"

interface ChatSidebarProps {
  /** Whether sidebar is collapsed */
  collapsed?: boolean
  /** Toggle collapsed state */
  onToggleCollapse?: () => void
  /** Additional class names */
  className?: string
}

type SidebarTab = "server" | "folders"

export function ChatSidebar({
  collapsed = false,
  onToggleCollapse,
  className
}: ChatSidebarProps) {
  const { t } = useTranslation(["common", "sidepanel", "option", "settings"])
  const navigate = useNavigate()
  const location = useLocation()
  const [searchQuery, setSearchQuery] = useState("")
  const debouncedSearchQuery = useDebounce(searchQuery, 300)
  const [selectionMode, setSelectionMode] = useState(false)

  // Tab state persisted in UI settings
  const [currentTab, setCurrentTab] = useSetting(SIDEBAR_ACTIVE_TAB_SETTING)
  const [shortcutsCollapsed, setShortcutsCollapsed] = useSetting(
    SIDEBAR_SHORTCUTS_COLLAPSED_SETTING
  )
  const showShortcuts = shortcutsCollapsed !== true
  const [shortcutSelection] = useSetting(SIDEBAR_SHORTCUT_SELECTION_SETTING)

  const clearChat = useClearChat()
  const temporaryChat = useStoreMessageOption((state) => state.temporaryChat)
  const startRouteTransition = useRouteTransitionStore((state) => state.start)

  // Folder conversation count for tab badge
  const conversationKeywordLinks = useFolderStore((s) => s.conversationKeywordLinks)
  const folderConversationCount = useMemo(
    () => new Set(conversationKeywordLinks.map((link) => link.conversation_id)).size,
    [conversationKeywordLinks]
  )

  // Server chat count for tab badge
  const { data: serverChatData } = useServerChatHistory(debouncedSearchQuery)
  const serverChats = serverChatData || []

  const sidebarShortcuts = useMemo(
    () => normalizeSidebarShortcutSelection(shortcutSelection),
    [shortcutSelection]
  )

  const handleShortcutAction = (item: SidebarShortcutAction) => {
    if (item.kind === "event") {
      if (item.eventName === "tldw:open-quick-ingest") {
        handleIngest()
        return
      }
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent(item.eventName))
      }
      return
    }
    navigateWithLoading(item.path)
  }

  const renderShortcutIcon = (item: SidebarShortcutAction) => (
    <Tooltip title={t(item.labelKey, item.labelDefault)} placement="right">
      <button
        aria-label={t(item.labelKey, item.labelDefault)}
        onClick={() => handleShortcutAction(item)}
        className="p-2 rounded-lg text-text-muted hover:bg-surface hover:text-text"
      >
        <item.icon className="size-4" />
      </button>
    </Tooltip>
  )

  const renderSidebarShortcut = (item: SidebarShortcutAction) => {
    return (
      <button
        key={item.id}
        onClick={() => handleShortcutAction(item)}
        className="flex items-center gap-2 w-full px-2 py-2 rounded text-sm text-text-muted hover:bg-surface hover:text-text"
      >
        <item.icon className="size-4" />
        <span>{t(item.labelKey, item.labelDefault)}</span>
      </button>
    )
  }

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value)
  }

  const handleNewChat = () => {
    clearChat()
  }

  const handleIngest = () => {
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("tldw:open-quick-ingest"))
    }
  }

  const navigateWithLoading = React.useCallback(
    (path: string) => {
      if (path === location.pathname) {
        return
      }
      void setShortcutsCollapsed(true)
      startRouteTransition(path)
      navigate(path)
    },
    [location.pathname, navigate, setShortcutsCollapsed, startRouteTransition]
  )

  React.useEffect(() => {
    if (currentTab !== "server" && selectionMode) {
      setSelectionMode(false)
    }
  }, [currentTab, selectionMode])

  const previousPathRef = React.useRef(location.pathname)
  React.useEffect(() => {
    if (previousPathRef.current !== location.pathname) {
      previousPathRef.current = location.pathname
      void setShortcutsCollapsed(true)
    }
  }, [location.pathname, setShortcutsCollapsed])

  // Build tab options with counts
  const tabOptions: Array<{ value: SidebarTab; label: string }> = [
    {
      value: "server",
      label: `${t("common:chatSidebar.tabs.server", "Server")}${serverChats.length > 0 ? ` (${serverChats.length})` : ""}`
    },
    {
      value: "folders",
      label: `${t("common:chatSidebar.tabs.folders", "Folders")}${folderConversationCount > 0 ? ` (${folderConversationCount})` : ""}`
    }
  ]

  // Collapsed view - just icons
  if (collapsed) {
    return (
      <div
        data-testid="chat-sidebar"
        className={cn(
          "flex flex-col h-screen items-center py-4 gap-2 w-12 border-r border-border bg-surface2",
          className
        )}
      >
        <Tooltip
          title={t("common:chatSidebar.expand", "Expand sidebar")}
          placement="right"
        >
          <button
            aria-label={t("common:chatSidebar.expand", "Expand sidebar")}
            data-testid="chat-sidebar-toggle"
            onClick={onToggleCollapse}
            className="p-2 rounded-lg text-text-muted hover:bg-surface hover:text-text"
          >
            <ChevronRight className="size-4" />
          </button>
        </Tooltip>

        <div className="h-px w-6 bg-border my-2" />

        <Tooltip
          title={t("common:chatSidebar.newChat", "New Chat")}
          placement="right"
        >
          <button
            aria-label={t("common:chatSidebar.newChat", "New Chat")}
            data-testid="chat-sidebar-new-chat"
            onClick={handleNewChat}
            className="p-2 rounded-lg text-text-muted hover:bg-surface hover:text-primary"
          >
            <Plus className="size-4" />
          </button>
        </Tooltip>

        <div className="h-px w-6 bg-border my-2" />

        {sidebarShortcuts.map((item) => (
          <React.Fragment key={item.id}>
            {renderShortcutIcon(item)}
          </React.Fragment>
        ))}

        <div className="flex-1" />

        <QuickChatHelperButton
          variant="inline"
          showToggle={false}
          appearance="ghost"
          tooltipPlacement="right"
          ariaLabel={t(
            "option:quickChatHelper.tooltipSidebar",
            "Open Quick Chat Helper (sidebar)"
          )}
        />

        <Tooltip
          title={t("common:chatSidebar.settings", "Settings")}
          placement="right"
        >
          <button
            aria-label={t("common:chatSidebar.settings", "Settings")}
            onClick={() => navigate("/settings")}
            className="p-2 rounded-lg text-text-muted hover:bg-surface hover:text-text"
          >
            <Settings className="size-4" />
          </button>
        </Tooltip>
      </div>
    )
  }

  // Expanded view
  return (
    <div
      data-testid="chat-sidebar"
      className={cn(
        "flex flex-col h-screen w-64 border-r border-border bg-surface2",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-3 border-b border-border">
        <h2 className="font-semibold text-text">
          {t("common:chatSidebar.title", "Chats")}
        </h2>
        <div className="flex items-center gap-1">
          <Tooltip title={t("common:chatSidebar.newChat", "New Chat")}>
            <button
              aria-label={t("common:chatSidebar.newChat", "New Chat")}
              data-testid="chat-sidebar-new-chat"
              onClick={handleNewChat}
              className="p-2 rounded text-text-muted hover:bg-surface hover:text-primary"
            >
              <Plus className="size-4" />
            </button>
          </Tooltip>
          {currentTab === "server" && (
            <Tooltip
              title={
                selectionMode
                  ? t("sidepanel:multiSelect.exit", "Exit selection")
                  : t("sidepanel:multiSelect.enter", "Select chats")
              }
            >
              <button
                type="button"
                onClick={() => setSelectionMode((prev) => !prev)}
                className={cn(
                  "rounded p-2",
                  selectionMode
                    ? "bg-surface text-text"
                    : "text-text-muted hover:bg-surface hover:text-text"
                )}
                aria-pressed={selectionMode}
                aria-label={
                  selectionMode
                    ? t("sidepanel:multiSelect.exit", "Exit selection")
                    : t("sidepanel:multiSelect.enter", "Select chats")
                }
              >
                <CheckSquare className="size-4" />
              </button>
            </Tooltip>
          )}
          <Tooltip
            title={t("common:chatSidebar.collapse", "Collapse sidebar")}
          >
            <button
              aria-label={t("common:chatSidebar.collapse", "Collapse sidebar")}
              data-testid="chat-sidebar-toggle"
              onClick={onToggleCollapse}
              className="p-2 rounded text-text-muted hover:bg-surface hover:text-text"
            >
              <ChevronLeft className="size-4" />
            </button>
          </Tooltip>
        </div>
      </div>

      {/* Search */}
      <div className="px-3 py-2 border-b border-border">
        <Input
          data-testid="chat-sidebar-search"
          prefix={<Search className="size-3.5 text-text-subtle" />}
          placeholder={t("common:chatSidebar.search", "Search chats...")}
          value={searchQuery}
          onChange={handleSearchChange}
          size="small"
          className="bg-surface"
          allowClear
        />
      </div>

      {/* Tabs */}
      <div className="px-3 py-2 border-b border-border">
        <Segmented<SidebarTab>
          value={currentTab}
          onChange={(value) => {
            void setCurrentTab(value)
          }}
          options={tabOptions}
          block
          size="small"
          className="w-full"
        />
      </div>

      {/* Quick Actions */}
      <button
        type="button"
        aria-expanded={showShortcuts}
        aria-controls="chat-sidebar-shortcuts"
        onClick={() => {
          void setShortcutsCollapsed(showShortcuts)
        }}
        className="group flex w-full items-center justify-between px-3 py-2 text-left hover:bg-surface"
        title={t("common:chatSidebar.shortcuts", "Shortcuts")}
      >
        <span className="text-xs font-semibold uppercase tracking-wide text-text-subtle">
          {t("common:chatSidebar.shortcuts", "Shortcuts")}
        </span>
        <ChevronDown
          className={cn(
            "size-4 text-text-muted transition-transform group-hover:text-text",
            showShortcuts ? "rotate-0" : "-rotate-90"
          )}
        />
      </button>
      {showShortcuts && (
        <div id="chat-sidebar-shortcuts" className="px-3 pb-2 space-y-1">
          {sidebarShortcuts.length > 0 ? (
            sidebarShortcuts.map((item) => renderSidebarShortcut(item))
          ) : (
            <div className="px-2 py-2 text-xs text-text-subtle">
              {t(
                "settings:uiCustomization.shortcuts.empty",
                "No shortcuts selected"
              )}
            </div>
          )}
        </div>
      )}

      <div className="h-px bg-border mx-3" />

      {/* Tab Content */}
      <div
        className={cn(
          "flex-1 overflow-y-auto",
          temporaryChat ? "pointer-events-none opacity-50" : ""
        )}
      >
        {currentTab === "server" && (
          <ServerChatList
            searchQuery={debouncedSearchQuery}
            selectionMode={selectionMode}
          />
        )}

        {currentTab === "folders" && (
          <FolderChatList />
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-border px-3 py-2">
        <button
          onClick={() => navigate("/settings")}
          className="flex items-center gap-2 w-full px-2 py-2 rounded text-sm text-text-muted hover:bg-surface hover:text-text"
        >
          <Settings className="size-4" />
          <span>{t("common:chatSidebar.settings", "Settings")}</span>
        </button>
        <div className="mt-2 border-t border-border pt-2">
          <div className="flex items-center gap-2">
            <div className="flex-1">
              <ModeToggle />
            </div>
            <QuickChatHelperButton
              variant="inline"
              showToggle={false}
              appearance="ghost"
              className="shrink-0"
              ariaLabel={t(
                "option:quickChatHelper.tooltipSidebar",
                "Open Quick Chat Helper (sidebar)"
              )}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

export default ChatSidebar
