import React from "react"
import { useTranslation } from "react-i18next"
import { useLocation, useNavigate } from "react-router-dom"
import { isMac } from "@/hooks/keyboard/useKeyboardShortcuts"
import { getTitleById, updateHistory } from "@/db"
import { useMessageOption } from "~/hooks/useMessageOption"
import { useSetting } from "@/hooks/useSetting"
import { HEADER_SHORTCUTS_EXPANDED_SETTING } from "@/services/settings/ui-settings"
import { ChatHeader } from "./ChatHeader"
import { TtsClipsDrawer } from "@/components/Sidepanel/Chat/TtsClipsDrawer"
import { useDarkMode } from "@/hooks/useDarkmode"
import { useSelectedCharacter } from "@/hooks/useSelectedCharacter"
import type { Character } from "@/types/character"

type Props = {
  onToggleSidebar?: () => void
  sidebarCollapsed?: boolean
}

export const Header: React.FC<Props> = ({
  onToggleSidebar,
  sidebarCollapsed = false
}) => {
  const { t } = useTranslation([
    "option",
    "common",
    "settings",
    "playground"
  ])
  const cmdKey = isMac ? "⌘" : "Ctrl+"
  const [headerShortcutsExpanded, setHeaderShortcutsExpanded] = useSetting(
    HEADER_SHORTCUTS_EXPANDED_SETTING
  )
  const { mode: themeMode, toggleDarkMode } = useDarkMode()
  const { clearChat, historyId, temporaryChat, setTemporaryChat } =
    useMessageOption()
  const [selectedCharacter, setSelectedCharacter] = useSelectedCharacter<Character | null>(
    null
  )
  const navigate = useNavigate()
  const location = useLocation()
  const [chatTitle, setChatTitle] = React.useState("")
  const [isEditingTitle, setIsEditingTitle] = React.useState(false)
  const [ttsClipsOpen, setTtsClipsOpen] = React.useState(false)
  const normalizedPath =
    location.pathname.length > 1 && location.pathname.endsWith("/")
      ? location.pathname.slice(0, -1)
      : location.pathname
  const isChatRoute = normalizedPath === "/chat"

  React.useEffect(() => {
    ;(async () => {
      try {
        if (historyId && historyId !== "temp" && !temporaryChat) {
          const title = await getTitleById(historyId)
          setChatTitle(title || "")
        } else {
          setChatTitle("")
        }
      } catch {}
    })()
  }, [historyId, temporaryChat])

  const saveTitle = async (value: string) => {
    try {
      if (historyId && historyId !== "temp" && !temporaryChat) {
        await updateHistory(historyId, value.trim() || "Untitled")
      }
    } catch (e) {
      console.error("Failed to update chat title", e)
    }
  }

  const openCommandPalette = React.useCallback(() => {
    if (typeof window === "undefined") return
    window.dispatchEvent(new CustomEvent("tldw:open-command-palette"))
  }, [])

  const openShortcutsModal = React.useCallback(() => {
    if (typeof window === "undefined") return
    window.dispatchEvent(new CustomEvent("tldw:open-shortcuts-modal"))
  }, [])

  const toggleHeaderShortcuts = React.useCallback((next?: boolean) => {
    void setHeaderShortcutsExpanded((prev) =>
      typeof next === "boolean" ? next : !prev
    ).catch(() => {
      // ignore storage write failures
    })
  }, [setHeaderShortcutsExpanded])

  const handleTitleEditStart = React.useCallback(() => {
    setIsEditingTitle(true)
  }, [])

  const handleTitleCommit = React.useCallback(
    async (value: string) => {
      setIsEditingTitle(false)
      await saveTitle(value)
    },
    [saveTitle]
  )

  const startSavedChat = React.useCallback(() => {
    setTemporaryChat(false)
    void setSelectedCharacter(null)
    clearChat()
  }, [clearChat, setSelectedCharacter, setTemporaryChat])

  const startTemporaryChat = React.useCallback(() => {
    setTemporaryChat(true)
    void setSelectedCharacter(null)
    clearChat()
  }, [clearChat, setSelectedCharacter, setTemporaryChat])

  const startCharacterChat = React.useCallback(() => {
    setTemporaryChat(false)
    clearChat()
    if (!selectedCharacter && typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("tldw:open-actor-settings"))
    }
  }, [clearChat, selectedCharacter, setTemporaryChat])

  return (
    <>
      <ChatHeader
        t={t}
        temporaryChat={temporaryChat}
        historyId={historyId}
        chatTitle={chatTitle}
        isEditingTitle={isEditingTitle}
        onTitleChange={setChatTitle}
        onTitleEditStart={handleTitleEditStart}
        onTitleCommit={handleTitleCommit}
        onToggleSidebar={onToggleSidebar}
        sidebarCollapsed={sidebarCollapsed}
        onOpenCommandPalette={openCommandPalette}
        onOpenShortcutsModal={openShortcutsModal}
        onOpenSettings={() => navigate("/settings/tldw")}
        onToggleTheme={toggleDarkMode}
        themeMode={themeMode}
        onClearChat={clearChat}
        onStartSavedChat={startSavedChat}
        onStartTemporaryChat={startTemporaryChat}
        onStartCharacterChat={startCharacterChat}
        activeCharacterName={selectedCharacter?.name || null}
        showChatTitle={isChatRoute}
        showSessionModeBadge={isChatRoute}
        shortcutsExpanded={headerShortcutsExpanded}
        onToggleShortcuts={toggleHeaderShortcuts}
        commandKeyLabel={cmdKey}
      />
      <TtsClipsDrawer
        open={ttsClipsOpen}
        onClose={() => setTtsClipsOpen(false)}
      />
    </>
  )
}
