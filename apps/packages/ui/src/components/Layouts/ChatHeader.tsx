import React from "react"
import type { TFunction } from "i18next"
import { Tooltip, Input } from "antd"
import { CogIcon, Menu, Search, SquarePen } from "lucide-react"
import { HeaderShortcuts } from "./HeaderShortcuts"
import logoImage from "~/assets/icon.png"

type ChatHeaderProps = {
  t: TFunction
  temporaryChat: boolean
  historyId?: string | null
  chatTitle: string
  isEditingTitle: boolean
  onTitleChange: (value: string) => void
  onTitleEditStart: () => void
  onTitleCommit: (value: string) => void | Promise<void>
  onToggleSidebar?: () => void
  sidebarCollapsed?: boolean
  onOpenCommandPalette: () => void
  onOpenShortcutsModal: () => void
  onOpenSettings: () => void
  onClearChat: () => void
  shortcutsExpanded: boolean
  onToggleShortcuts: (next?: boolean) => void
  commandKeyLabel: string
}

export function ChatHeader({
  t,
  temporaryChat,
  historyId,
  chatTitle,
  isEditingTitle,
  onTitleChange,
  onTitleEditStart,
  onTitleCommit,
  onToggleSidebar,
  sidebarCollapsed = false,
  onOpenCommandPalette,
  onOpenShortcutsModal,
  onOpenSettings,
  onClearChat,
  shortcutsExpanded,
  onToggleShortcuts,
  commandKeyLabel
}: ChatHeaderProps) {
  const logoSrc =
    typeof logoImage === "string"
      ? logoImage
      : (logoImage as { src?: string })?.src ?? ""
  const showSidebarToggle = Boolean(onToggleSidebar)
  const sidebarLabel = sidebarCollapsed
    ? t("common:chatSidebar.expand", "Expand sidebar")
    : t("common:chatSidebar.collapse", "Collapse sidebar")
  const shortcutsToggleLabel = shortcutsExpanded
    ? t("option:header.hideShortcuts", "Hide shortcuts")
    : t("option:header.showShortcuts", "Show shortcuts")
  const canEditTitle = !temporaryChat && historyId && historyId !== "temp"

  return (
    <header
      data-istemporary-chat={temporaryChat}
      data-ischat-route="true"
      className="z-30 flex w-full flex-col border-b border-border bg-surface/95 backdrop-blur data-[istemporary-chat='true']:bg-purple-900 data-[ischat-route='true']:bg-surface/95"
    >
      <div className="flex w-full items-center justify-between gap-3 px-4 py-2">
        <div className="flex min-w-0 items-center gap-2">
          {showSidebarToggle && (
            <Tooltip title={sidebarLabel} placement="bottom">
              <button
                type="button"
                onClick={onToggleSidebar}
                aria-label={sidebarLabel as string}
                className="rounded-md p-2 text-text-muted hover:bg-surface2 hover:text-text"
                title={sidebarLabel as string}
              >
                <Menu className="size-4" aria-hidden="true" />
              </button>
            </Tooltip>
          )}
          <div className="flex items-center gap-2 text-text">
            <img
              src={logoSrc}
              alt={t("common:pageAssist", "tldw Assistant")}
              className="h-5 w-auto"
            />
            <span className="text-sm font-medium">
              {t("common:pageAssist", "tldw Assistant")}
            </span>
          </div>
          {canEditTitle && (
            <div className="min-w-[140px] max-w-[220px] truncate">
              {isEditingTitle ? (
                <Input
                  size="small"
                  autoFocus
                  value={chatTitle}
                  onChange={(e) => onTitleChange(e.target.value)}
                  onPressEnter={() => {
                    void onTitleCommit(chatTitle)
                  }}
                  onBlur={() => {
                    void onTitleCommit(chatTitle)
                  }}
                />
              ) : (
                <button
                  type="button"
                  onClick={onTitleEditStart}
                  className="truncate text-left text-xs text-text-muted hover:text-text"
                  title={chatTitle || "Untitled"}
                >
                  {chatTitle || t("option:header.untitledChat", "Untitled")}
                </button>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onOpenCommandPalette}
            className="hidden items-center gap-2 rounded-md px-3 py-1.5 text-xs text-text-muted transition hover:bg-surface2 hover:text-text sm:inline-flex"
            title={t("common:search", "Search")}
          >
            <Search className="size-4" aria-hidden="true" />
            <span>{t("common:search", "Search")}</span>
            <span className="rounded border border-border px-1.5 py-0.5 text-xs text-text-subtle">
              {commandKeyLabel}K
            </span>
          </button>
          <Tooltip title={t("common:newChat", "New chat")}>
            <button
              type="button"
              onClick={onClearChat}
              aria-label={t("common:newChat", "New chat") as string}
              className="inline-flex items-center justify-center rounded-md p-2 text-text-muted hover:bg-surface2 hover:text-text"
              title={t("common:newChat", "New chat")}
            >
              <SquarePen className="size-4" aria-hidden="true" />
            </button>
          </Tooltip>
          <Tooltip title={t("sidepanel:header.settingsShortLabel", "Settings")}>
            <button
              type="button"
              onClick={onOpenSettings}
              aria-label={t("sidepanel:header.openSettingsAria", "Open settings") as string}
              className="inline-flex items-center justify-center rounded-md p-2 text-text-muted hover:bg-surface2 hover:text-text"
              title={t("sidepanel:header.settingsShortLabel", "Settings")}
            >
              <CogIcon className="size-4" aria-hidden="true" />
            </button>
          </Tooltip>
          <Tooltip title={t("option:header.keyboardShortcuts", "Keyboard shortcuts (?)")}>
            <button
              type="button"
              onClick={onOpenShortcutsModal}
              aria-label={t("option:header.keyboardShortcutsAria", "Show keyboard shortcuts") as string}
              className="inline-flex items-center justify-center rounded-md p-1.5 text-text-subtle hover:bg-surface2 hover:text-text"
              title={t("option:header.keyboardShortcuts", "Keyboard shortcuts")}
            >
              <kbd className="rounded border border-border px-1.5 py-0.5 text-xs font-medium text-text-subtle">?</kbd>
            </button>
          </Tooltip>
        </div>
      </div>
      <HeaderShortcuts
        className="px-4 pb-2 pt-1"
        showToggle={false}
        expanded={shortcutsExpanded}
        onExpandedChange={onToggleShortcuts}
      />
    </header>
  )
}
