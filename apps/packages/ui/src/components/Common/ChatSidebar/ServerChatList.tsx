import React from "react"
import { useTranslation } from "react-i18next"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Empty, Skeleton, Input, Modal, Select, message } from "antd"
import { useStorage } from "@plasmohq/storage/hook"
import { FolderPlus, Tag, Trash2 } from "lucide-react"
import { browser } from "wxt/browser"

import { useConfirmDanger } from "@/components/Common/confirm-danger"
import { useConnectionState } from "@/hooks/useConnectionState"
import { useServerChatHistory, type ServerChatHistoryItem } from "@/hooks/useServerChatHistory"
import { useSetting } from "@/hooks/useSetting"
import { useClearChat } from "@/hooks/chat/useClearChat"
import { useSelectServerChat } from "@/hooks/chat/useSelectServerChat"
import { useBulkChatOperations } from "@/hooks/useBulkChatOperations"
import { useStoreMessageOption } from "@/store/option"
import { useFolderStore } from "@/store/folder"
import { shallow } from "zustand/shallow"
import {
  tldwClient,
  type ConversationState,
  type ServerChatSummary
} from "@/services/tldw/TldwApiClient"
import { updatePageTitle } from "@/utils/update-page-title"
import { cn } from "@/libs/utils"
import { normalizeConversationState } from "@/utils/conversation-state"
import { useDataTablesStore } from "@/store/data-tables"
import { queueDataTablesPrefill } from "@/utils/data-tables-prefill"
import { startCreateTableFromChat } from "@/utils/data-tables-create-flow"
import {
  SIDEBAR_SERVER_CHAT_FILTER_SETTING,
  type SidebarServerChatFilterValue
} from "@/services/settings/ui-settings"
import { ServerChatRow } from "./ServerChatRow"

const BulkFolderPickerModal = React.lazy(
  () => import("@/components/Sidepanel/Chat/BulkFolderPickerModal")
)
const BulkTagPickerModal = React.lazy(
  () => import("@/components/Sidepanel/Chat/BulkTagPickerModal")
)

const CHAT_HISTORY_PAGE_SIZE = 25

interface ServerChatListProps {
  searchQuery: string
  className?: string
  selectionMode?: boolean
}

type UpdateChatRequestPayload = {
  chatId: string
  data:
    | { title?: string }
    | { topic_label?: string | null }
    | { state?: ConversationState }
  expectedVersion?: number | null
}

export function ServerChatList({
  searchQuery,
  className,
  selectionMode: selectionModeProp
}: ServerChatListProps) {
  const { t } = useTranslation([
    "common",
    "sidepanel",
    "option",
    "playground",
    "dataTables"
  ])
  const { isConnected } = useConnectionState()
  const queryClient = useQueryClient()
  const confirmDanger = useConfirmDanger()
  const [pinnedChatIds, setPinnedChatIds] = useStorage<string[]>(
    "tldw:server-chat-pins",
    []
  )
  const [chatTypeFilter, setChatTypeFilter] = useSetting(
    SIDEBAR_SERVER_CHAT_FILTER_SETTING
  )

  const {
    serverChatId,
    setServerChatTitle,
    setServerChatState,
    setServerChatVersion,
    setServerChatTopic
  } = useStoreMessageOption(
    (state) => ({
      serverChatId: state.serverChatId,
      setServerChatTitle: state.setServerChatTitle,
      setServerChatState: state.setServerChatState,
      setServerChatVersion: state.setServerChatVersion,
      setServerChatTopic: state.setServerChatTopic
    }),
    shallow
  )
  const selectServerChat = useSelectServerChat()
  const clearChat = useClearChat()
  const { resetWizard, addSource, setWizardStep } = useDataTablesStore(
    (state) => ({
      resetWizard: state.resetWizard,
      addSource: state.addSource,
      setWizardStep: state.setWizardStep
    }),
    shallow
  )
  const [openMenuFor, setOpenMenuFor] = React.useState<string | null>(null)
  const [renamingChat, setRenamingChat] =
    React.useState<ServerChatHistoryItem | null>(null)
  const [renameValue, setRenameValue] = React.useState("")
  const [renameError, setRenameError] = React.useState<string | null>(null)
  const [editingTopicChat, setEditingTopicChat] =
    React.useState<ServerChatHistoryItem | null>(null)
  const [topicValue, setTopicValue] = React.useState("")
  const selectionMode = selectionModeProp ?? false
  const [selectedChatIds, setSelectedChatIds] = React.useState<string[]>([])
  const [currentPage, setCurrentPage] = React.useState(1)
  const [pageJumpValue, setPageJumpValue] = React.useState("1")
  const selectedChatIdSet = React.useMemo(
    () => new Set(selectedChatIds),
    [selectedChatIds]
  )
  const [bulkFolderPickerOpen, setBulkFolderPickerOpen] = React.useState(false)
  const [bulkTagPickerOpen, setBulkTagPickerOpen] = React.useState(false)
  const [bulkDeleteConfirmOpen, setBulkDeleteConfirmOpen] = React.useState(false)
  const openSettingsTimeoutRef = React.useRef<number | null>(null)

  const openExtensionUrl = React.useCallback(
    (path: `/options.html${string}` | `/sidepanel.html${string}`) => {
      try {
        if (browser?.runtime?.getURL) {
          const url = browser.runtime.getURL(path)
          if (browser.tabs?.create) {
            browser.tabs.create({ url })
          } else {
            window.open(url, "_blank")
          }
          return
        }
      } catch (err) {
        console.debug("[ServerChatList] openExtensionUrl browser API unavailable:", err)
      }

      try {
        if (typeof chrome !== "undefined" && chrome.runtime?.getURL) {
          const url = chrome.runtime.getURL(path)
          window.open(url, "_blank")
          return
        }
        if (
          typeof chrome !== "undefined" &&
          chrome.runtime?.openOptionsPage &&
          path.includes("/options.html")
        ) {
          chrome.runtime.openOptionsPage()
          return
        }
      } catch (err) {
        console.debug("[ServerChatList] openExtensionUrl chrome API unavailable:", err)
      }

      let fallbackUrl: string = path
      try {
        fallbackUrl = new URL(path, window.location.origin).toString()
      } catch (err) {
        console.warn("[ServerChatList] openExtensionUrl failed to build fallback URL:", err)
      }
      console.warn(
        "[ServerChatList] openExtensionUrl runtime API unavailable; falling back to",
        fallbackUrl
      )
      window.open(fallbackUrl, "_blank")
    },
    []
  )

  const {
    folderApiAvailable,
    ensureKeyword,
    addKeywordToConversation
  } = useFolderStore(
    (state) => ({
      folderApiAvailable: state.folderApiAvailable,
      ensureKeyword: state.ensureKeyword,
      addKeywordToConversation: state.addKeywordToConversation
    }),
    shallow
  )

  const updateChatRequest = React.useCallback(
    async (payload: UpdateChatRequestPayload): Promise<ServerChatSummary> =>
      tldwClient.updateChat(
        payload.chatId,
        payload.data,
        payload.expectedVersion != null
          ? { expectedVersion: payload.expectedVersion }
          : undefined
      ),
    []
  )

  const invalidateServerChatHistory = React.useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["serverChatHistory"] })
  }, [queryClient])

  const { mutate: updateChatMetadata } = useMutation<
    ServerChatSummary,
    Error,
    UpdateChatRequestPayload
  >({
    mutationKey: ["updateChatMetadata"],
    mutationFn: updateChatRequest,
    onSettled: invalidateServerChatHistory
  })
  const { mutate: renameChat, isPending: renameLoading } = useMutation<
    ServerChatSummary,
    Error,
    UpdateChatRequestPayload
  >({
    mutationKey: ["renameChat"],
    mutationFn: updateChatRequest,
    onSettled: invalidateServerChatHistory
  })
  const { mutate: updateChatTopic, isPending: topicLoading } = useMutation<
    ServerChatSummary,
    Error,
    UpdateChatRequestPayload
  >({
    mutationKey: ["updateChatTopic"],
    mutationFn: updateChatRequest,
    onSettled: invalidateServerChatHistory
  })

  const {
    data: serverChatData,
    status,
    isLoading
  } = useServerChatHistory(searchQuery)
  const serverChats = serverChatData || []
  const filteredChatsByType = React.useMemo(() => {
    if (chatTypeFilter === "all") return serverChats
    const isCharacterChat = (chat: ServerChatHistoryItem) => {
      const characterId = chat.character_id
      if (characterId == null) return false
      if (typeof characterId === "string") return characterId.trim().length > 0
      return true
    }
    if (chatTypeFilter === "character") {
      return serverChats.filter((chat) => isCharacterChat(chat))
    }
    return serverChats.filter((chat) => !isCharacterChat(chat))
  }, [chatTypeFilter, serverChats])
  const pinnedChatSet = React.useMemo(
    () => new Set(pinnedChatIds || []),
    [pinnedChatIds]
  )
  const pinnedChats = filteredChatsByType.filter((chat) =>
    pinnedChatSet.has(chat.id)
  )
  const unpinnedChats = filteredChatsByType.filter(
    (chat) => !pinnedChatSet.has(chat.id)
  )
  const orderedChats = React.useMemo(
    () => [...pinnedChats, ...unpinnedChats],
    [pinnedChats, unpinnedChats]
  )
  const totalPages = Math.max(
    1,
    Math.ceil(orderedChats.length / CHAT_HISTORY_PAGE_SIZE)
  )
  const currentPageSafe = Math.min(currentPage, totalPages)
  const pageStartIndex = (currentPageSafe - 1) * CHAT_HISTORY_PAGE_SIZE
  const pagedChats = React.useMemo(
    () =>
      orderedChats.slice(
        pageStartIndex,
        pageStartIndex + CHAT_HISTORY_PAGE_SIZE
      ),
    [orderedChats, pageStartIndex]
  )
  const pagedPinnedChats = React.useMemo(
    () => pagedChats.filter((chat) => pinnedChatSet.has(chat.id)),
    [pagedChats, pinnedChatSet]
  )
  const pagedUnpinnedChats = React.useMemo(
    () => pagedChats.filter((chat) => !pinnedChatSet.has(chat.id)),
    [pagedChats, pinnedChatSet]
  )
  const pageStartNumber = orderedChats.length === 0 ? 0 : pageStartIndex + 1
  const pageEndNumber = pageStartIndex + pagedChats.length
  const hasMultiplePages = totalPages > 1
  const visibleChatIds = React.useMemo(
    () => Array.from(new Set(filteredChatsByType.map((chat) => chat.id))),
    [filteredChatsByType]
  )
  const visibleChatIdSet = React.useMemo(
    () => new Set(visibleChatIds),
    [visibleChatIds]
  )
  const chatById = React.useMemo(
    () => new Map(filteredChatsByType.map((chat) => [chat.id, chat])),
    [filteredChatsByType]
  )
  const selectedChats = React.useMemo(
    () =>
      selectedChatIds
        .map((id) => chatById.get(id))
        .filter(Boolean) as ServerChatHistoryItem[],
    [selectedChatIds, chatById]
  )
  const selectedConversationIds = React.useMemo(
    () => selectedChats.map((chat) => chat.id),
    [selectedChats]
  )
  const { openBulkFolderPicker, openBulkTagPicker, applyBulkTrash } =
    useBulkChatOperations({
      selectedConversationIds,
      folderApiAvailable,
      ensureKeyword,
      addKeywordToConversation,
      t,
      setBulkFolderPickerOpen,
      setBulkTagPickerOpen
    })

  React.useEffect(() => {
    setCurrentPage(1)
  }, [searchQuery, chatTypeFilter])

  React.useEffect(() => {
    if (currentPage !== currentPageSafe) {
      setCurrentPage(currentPageSafe)
    }
  }, [currentPage, currentPageSafe])

  React.useEffect(() => {
    setPageJumpValue(String(currentPageSafe))
  }, [currentPageSafe])

  const togglePinned = React.useCallback(
    (chatId: string) => {
      setPinnedChatIds((prev) => {
        const current = prev || []
        if (current.includes(chatId)) {
          return current.filter((id) => id !== chatId)
        }
        return [...current, chatId]
      })
    },
    [setPinnedChatIds]
  )

  React.useEffect(() => {
    if (!selectionMode) {
      setSelectedChatIds((prev) => (prev.length === 0 ? prev : []))
      return
    }
    setSelectedChatIds((prev) => {
      const next = prev.filter((id) => visibleChatIdSet.has(id))
      if (next.length === prev.length && next.every((id, idx) => id === prev[idx])) {
        return prev
      }
      return next
    })
  }, [selectionMode, visibleChatIdSet])

  const handleCreateTable = React.useCallback(
    async (chat: ServerChatHistoryItem) => {
      const isOptionsPage =
        typeof window !== "undefined" &&
        window.location.pathname.endsWith("options.html")
      const navigateFn = (window as Window & { __tldwNavigate?: (path: string) => void })
        .__tldwNavigate

      try {
        await startCreateTableFromChat(
          {
            id: chat.id,
            title: chat.title,
            topic_label: chat.topic_label
          },
          {
            isOptionsPage,
            navigate: navigateFn,
            resetWizard,
            addSource,
            setWizardStep,
            queuePrefill: queueDataTablesPrefill,
            openOptionsPage: () => openExtensionUrl("/options.html#/data-tables")
          }
        )
      } catch (error) {
        console.error("[ServerChatList] Failed to start table creation", {
          error,
          chatId: chat.id
        })
        resetWizard()
        message.error(
          t("dataTables:createFromChatError", {
            defaultValue: "Failed to start table creation."
          })
        )
      }
    },
    [
      addSource,
      openExtensionUrl,
      resetWizard,
      setWizardStep,
      t
    ]
  )

  React.useEffect(() => {
    if (selectionMode) {
      setOpenMenuFor(null)
      return
    }
    setBulkFolderPickerOpen(false)
    setBulkTagPickerOpen(false)
    setBulkDeleteConfirmOpen(false)
  }, [selectionMode])

  const toggleChatSelected = React.useCallback((chatId: string) => {
    setSelectedChatIds((prev) => {
      const next = new Set(prev)
      if (next.has(chatId)) {
        next.delete(chatId)
      } else {
        next.add(chatId)
      }
      return Array.from(next)
    })
  }, [])

  const handleSelectAllVisible = React.useCallback(() => {
    setSelectedChatIds(visibleChatIds)
  }, [visibleChatIds])

  const clearSelection = React.useCallback(() => {
    setSelectedChatIds([])
  }, [])

  const handlePreviousPage = React.useCallback(() => {
    setCurrentPage((prev) => Math.max(1, prev - 1))
  }, [])

  const handleNextPage = React.useCallback(() => {
    setCurrentPage((prev) => Math.min(totalPages, prev + 1))
  }, [totalPages])

  const handleJumpToPage = React.useCallback(() => {
    const nextPage = Number.parseInt(pageJumpValue, 10)
    if (!Number.isFinite(nextPage)) {
      setPageJumpValue(String(currentPageSafe))
      return
    }
    const clamped = Math.min(totalPages, Math.max(1, nextPage))
    setCurrentPage(clamped)
  }, [currentPageSafe, pageJumpValue, totalPages])

  const handleRenameSubmit = () => {
    if (renameLoading) return
    if (!renamingChat) return

    const newTitle = renameValue.trim()
    if (!newTitle) {
      setRenameError(
        t("common:renameChatEmptyError", {
          defaultValue: "Title cannot be empty."
        })
      )
      return
    }

    setRenameError(null)
    renameChat(
      {
        chatId: renamingChat.id,
        data: { title: newTitle },
        expectedVersion: renamingChat.version ?? null
      },
      {
        onSuccess: (updated) => {
          const resolvedTitle = updated?.title || newTitle
          if (serverChatId === renamingChat.id) {
            setServerChatTitle(resolvedTitle)
            setServerChatVersion(updated?.version ?? null)
            updatePageTitle(resolvedTitle)
          }
          setRenamingChat(null)
          setRenameValue("")
        },
        onError: () => {
          message.error(
            t("common:renameChatError", {
              defaultValue: "Failed to rename chat."
            })
          )
        }
      }
    )
  }

  const handleTopicSubmit = () => {
    if (topicLoading) return
    if (!editingTopicChat) return

    const nextTopic = topicValue.trim()
    updateChatTopic(
      {
        chatId: editingTopicChat.id,
        data: { topic_label: nextTopic || null },
        expectedVersion: editingTopicChat.version ?? null
      },
      {
        onSuccess: (updated) => {
          const resolvedTopic = updated?.topic_label ?? (nextTopic || null)
          if (serverChatId === editingTopicChat.id) {
            setServerChatTopic(resolvedTopic)
            setServerChatVersion(updated?.version ?? null)
          }
          setEditingTopicChat(null)
          setTopicValue("")
        },
        onError: () => {
          message.error(
            t("option:somethingWentWrong", {
              defaultValue: "Something went wrong"
            })
          )
        }
      }
    )
  }

  const handleUpdateState = React.useCallback(
    (chat: ServerChatHistoryItem, nextState: ConversationState) => {
      updateChatMetadata(
        {
          chatId: chat.id,
          data: { state: nextState },
          expectedVersion: chat.version ?? null
        },
        {
          onSuccess: (updated) => {
            const resolvedState = normalizeConversationState(
              updated?.state ?? nextState
            )
            if (serverChatId === chat.id) {
              setServerChatState(resolvedState)
              setServerChatVersion(updated?.version ?? null)
            }
          },
          onError: () => {
            message.error(
              t("option:somethingWentWrong", {
                defaultValue: "Something went wrong"
              })
            )
          }
        }
      )
    },
    [
      serverChatId,
      setServerChatState,
      setServerChatVersion,
      t,
      updateChatMetadata
    ]
  )

  const handleDeleteChat = React.useCallback(
    async (chat: ServerChatHistoryItem) => {
      const ok = await confirmDanger({
        title: t("common:confirmTitle", { defaultValue: "Please confirm" }),
        content: t("common:deleteHistoryConfirmation", {
          defaultValue: "Are you sure you want to delete this chat?"
        }),
        okText: t("common:delete", { defaultValue: "Delete" }),
        cancelText: t("common:cancel", { defaultValue: "Cancel" })
      })
      if (!ok) return

      try {
        await tldwClient.deleteChat(chat.id)
        setPinnedChatIds((prev) =>
          (prev || []).filter((id) => id !== chat.id)
        )
        queryClient.invalidateQueries({ queryKey: ["serverChatHistory"] })
        if (serverChatId === chat.id) {
          clearChat()
        }
      } catch (err) {
        console.error("[ServerChatList] Failed to delete chat", {
          error: err,
          chatId: chat.id
        })
        message.error(
          t("common:deleteChatError", {
            defaultValue: "Failed to delete chat."
          })
        )
      }
    },
    [clearChat, confirmDanger, queryClient, serverChatId, setPinnedChatIds, t]
  )

  const handleOpenSettings = React.useCallback(
    (chat: ServerChatHistoryItem) => {
      if (serverChatId !== chat.id) {
        selectServerChat(chat)
      }
      if (typeof window === "undefined") return
      if (openSettingsTimeoutRef.current !== null) {
        window.clearTimeout(openSettingsTimeoutRef.current)
      }
      openSettingsTimeoutRef.current = window.setTimeout(() => {
        window.dispatchEvent(new CustomEvent("tldw:open-model-settings"))
        openSettingsTimeoutRef.current = null
      }, 0)
    },
    [selectServerChat, serverChatId]
  )

  React.useEffect(() => {
    return () => {
      if (openSettingsTimeoutRef.current !== null) {
        window.clearTimeout(openSettingsTimeoutRef.current)
        openSettingsTimeoutRef.current = null
      }
    }
  }, [])

  const handleRenameChat = React.useCallback(
    (chat: ServerChatHistoryItem) => {
      setRenamingChat(chat)
      setRenameValue(chat.title || "")
      setRenameError(null)
    },
    []
  )

  const handleEditTopic = React.useCallback(
    (chat: ServerChatHistoryItem) => {
      setEditingTopicChat(chat)
      setTopicValue(chat.topic_label || "")
    },
    []
  )

  const handleRowClick = React.useCallback(
    (chat: ServerChatHistoryItem) => {
      if (selectionMode) {
        toggleChatSelected(chat.id)
        return
      }
      selectServerChat(chat)
    },
    [selectionMode, selectServerChat, toggleChatSelected]
  )

  const selectionPropsForChat = React.useCallback(
    (chatId: string) =>
      selectionMode
        ? {
            selectionMode: true as const,
            isSelected: selectedChatIdSet.has(chatId),
            onToggleSelected: toggleChatSelected
          }
        : { selectionMode: false as const },
    [selectionMode, selectedChatIdSet, toggleChatSelected]
  )

  const openBulkDeleteConfirm = React.useCallback(() => {
    setBulkDeleteConfirmOpen(true)
  }, [])

  const handleBulkFolderPickerClose = React.useCallback(() => {
    setBulkFolderPickerOpen(false)
  }, [])

  const handleBulkTagPickerClose = React.useCallback(() => {
    setBulkTagPickerOpen(false)
  }, [])

  const handleBulkDeleteConfirmClose = React.useCallback(() => {
    setBulkDeleteConfirmOpen(false)
  }, [])

  const handleBulkDelete = React.useCallback(async () => {
    try {
      const result = await applyBulkTrash()
      if (!result) return
      const { failedConversationIds } = result
      setPinnedChatIds((prev) =>
        (prev || []).filter(
          (id) =>
            !selectedConversationIds.includes(id) ||
            failedConversationIds.has(id)
        )
      )
      setSelectedChatIds(
        selectedConversationIds.filter((id) =>
          failedConversationIds.has(id)
        )
      )
      queryClient.invalidateQueries({ queryKey: ["serverChatHistory"] })
      setBulkDeleteConfirmOpen(false)
    } catch (error) {
      console.error("[ServerChatList] Failed to bulk delete chats", {
        error,
        selectedCount: selectedConversationIds.length
      })
      message.error(
        t("sidepanel:multiSelect.deleteFailed", {
          defaultValue: "Unable to move chats to trash."
        })
      )
    }
  }, [
    applyBulkTrash,
    queryClient,
    selectedConversationIds,
    setPinnedChatIds,
    t
  ])

  // Not connected state
  if (!isConnected) {
    return (
      <div className={cn("flex justify-center items-center py-8", className)}>
        <Empty
          description={t("common:serverChatsUnavailableNotConnected", {
            defaultValue:
              "Server chats are available once you connect to your tldw server."
          })}
        />
      </div>
    )
  }

  // Loading state
  if (isLoading) {
    return (
      <div className={cn("flex justify-center items-center py-8", className)}>
        <Skeleton active paragraph={{ rows: 4 }} />
      </div>
    )
  }

  // Error state
  if (status === "error") {
    return (
      <div className={cn("flex justify-center items-center py-8 px-2", className)}>
        <span className="text-xs text-text-subtle text-center">
          {t("common:serverChatsUnavailableServerError", {
            defaultValue:
              "Server chats unavailable right now. Check your server logs or try again."
          })}
        </span>
      </div>
    )
  }

  // Empty state
  if (serverChats.length === 0) {
    return (
      <div className={cn("flex justify-center items-center py-8", className)}>
        <Empty
          description={t("common:chatSidebar.noServerChats", {
            defaultValue: "No server chats yet"
          })}
        />
      </div>
    )
  }

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {renamingChat && (
        <Modal
          title={t("common:renameChat", { defaultValue: "Rename chat" })}
          open
          destroyOnHidden
          onCancel={() => {
            setRenamingChat(null)
            setRenameValue("")
            setRenameError(null)
          }}
          onOk={handleRenameSubmit}
          confirmLoading={renameLoading}
          okButtonProps={{
            disabled: renameLoading || !renameValue.trim()
          }}
        >
          <Input
            autoFocus
            value={renameValue}
            onChange={(e) => {
              setRenameValue(e.target.value)
              if (renameError) {
                setRenameError(null)
              }
            }}
            onPressEnter={handleRenameSubmit}
            status={renameError ? "error" : undefined}
            disabled={renameLoading}
          />
          {renameError && (
            <div className="mt-1 text-xs text-danger">{renameError}</div>
          )}
        </Modal>
      )}
      {editingTopicChat && (
        <Modal
          title={t("playground:composer.topicPlaceholder", {
            defaultValue: "Topic label (optional)"
          })}
          open
          destroyOnHidden
          onCancel={() => {
            setEditingTopicChat(null)
            setTopicValue("")
          }}
          onOk={handleTopicSubmit}
          confirmLoading={topicLoading}
          okButtonProps={{ disabled: topicLoading }}
        >
          <Input
            autoFocus
            value={topicValue}
            onChange={(e) => setTopicValue(e.target.value)}
            onPressEnter={handleTopicSubmit}
            placeholder={t("playground:composer.topicPlaceholder", {
              defaultValue: "Topic label (optional)"
            })}
            disabled={topicLoading}
          />
        </Modal>
      )}
      <div className="px-2 pt-1">
        <label id="chat-sidebar-type-filter-label" className="sr-only">
          {t("common:chatSidebar.filter.label", {
            defaultValue: "Chat type filter"
          })}
        </label>
        <Select<SidebarServerChatFilterValue>
          value={chatTypeFilter}
          onChange={(value) => {
            void setChatTypeFilter(value)
          }}
          size="small"
          className="w-full"
          aria-labelledby="chat-sidebar-type-filter-label"
          options={[
            {
              value: "all",
              label: t("common:chatSidebar.filter.allChats", {
                defaultValue: "All Chats"
              })
            },
            {
              value: "character",
              label: t("common:chatSidebar.filter.characterChats", {
                defaultValue: "Character Chats"
              })
            },
            {
              value: "non_character",
              label: t("common:chatSidebar.filter.nonCharacterChats", {
                defaultValue: "Non-Character Chats"
              })
            }
          ]}
        />
      </div>
      {selectionMode && (
        <div className="sticky top-0 z-10 border-b border-border bg-surface2 px-2 py-2">
          <div className="flex items-center justify-between text-xs text-text-subtle">
            <span>
              {t("sidepanel:multiSelect.count", {
                defaultValue: "{{count}} selected",
                count: selectedChatIds.length
              })}
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleSelectAllVisible}
                className="text-text-subtle hover:text-text"
                disabled={visibleChatIds.length === 0}
              >
                {t("sidepanel:multiSelect.selectAll", "Select all")}
              </button>
              <button
                type="button"
                onClick={clearSelection}
                className="text-text-subtle hover:text-text"
                disabled={selectedChatIds.length === 0}
              >
                {t("sidepanel:multiSelect.clear", "Clear")}
              </button>
            </div>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={openBulkFolderPicker}
              className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-text hover:bg-surface2"
              disabled={selectedChatIds.length === 0}
            >
              <FolderPlus className="size-3.5" />
              {t("sidepanel:multiSelect.addToFolder", "Add to folders")}
            </button>
            <button
              type="button"
              onClick={openBulkTagPicker}
              className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-text hover:bg-surface2"
              disabled={selectedChatIds.length === 0}
            >
              <Tag className="size-3.5" />
              {t("sidepanel:multiSelect.addTags", "Add tags")}
            </button>
            <button
              type="button"
              onClick={openBulkDeleteConfirm}
              className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-danger hover:bg-surface2"
              disabled={selectedChatIds.length === 0}
            >
              <Trash2 className="size-3.5" />
              {t("common:delete", "Delete")}
            </button>
          </div>
        </div>
      )}
      {orderedChats.length === 0 ? (
        <div className="px-2 py-8">
          <Empty
            description={t("common:chatSidebar.noChatsForFilter", {
              defaultValue:
                chatTypeFilter === "character"
                  ? "No character chats found."
                  : chatTypeFilter === "non_character"
                    ? "No non-character chats found."
                    : "No chats found."
            })}
          />
        </div>
      ) : (
        <>
          {pagedPinnedChats.length > 0 && (
            <div className="flex flex-col gap-2">
              <div className="px-2 text-[11px] font-medium text-text-subtle uppercase tracking-wide">
                {t("common:pinned", { defaultValue: "Pinned" })}
              </div>
              {pagedPinnedChats.map((chat) => (
                <ServerChatRow
                  key={chat.id}
                  chat={chat}
                  isPinned={pinnedChatSet.has(chat.id)}
                  isActive={serverChatId === chat.id}
                  openMenuFor={openMenuFor}
                  setOpenMenuFor={setOpenMenuFor}
                  onSelectChat={handleRowClick}
                  onTogglePinned={togglePinned}
                  onOpenSettings={handleOpenSettings}
                  onRenameChat={handleRenameChat}
                  onCreateTable={handleCreateTable}
                  onEditTopic={handleEditTopic}
                  onDeleteChat={handleDeleteChat}
                  onUpdateState={handleUpdateState}
                  {...selectionPropsForChat(chat.id)}
                  t={t}
                />
              ))}
            </div>
          )}
          {pagedUnpinnedChats.length > 0 && (
            <div
              className={cn(
                "flex flex-col gap-2",
                pagedPinnedChats.length > 0 && "mt-3"
              )}
            >
              {pagedUnpinnedChats.map((chat) => (
                <ServerChatRow
                  key={chat.id}
                  chat={chat}
                  isPinned={pinnedChatSet.has(chat.id)}
                  isActive={serverChatId === chat.id}
                  openMenuFor={openMenuFor}
                  setOpenMenuFor={setOpenMenuFor}
                  onSelectChat={handleRowClick}
                  onTogglePinned={togglePinned}
                  onOpenSettings={handleOpenSettings}
                  onRenameChat={handleRenameChat}
                  onCreateTable={handleCreateTable}
                  onEditTopic={handleEditTopic}
                  onDeleteChat={handleDeleteChat}
                  onUpdateState={handleUpdateState}
                  {...selectionPropsForChat(chat.id)}
                  t={t}
                />
              ))}
            </div>
          )}
          {hasMultiplePages && (
            <div className="mt-3 border-t border-border px-2 pt-3">
              <div className="mb-2 text-xs text-text-subtle">
                {t("common:chatSidebar.paginationRange", {
                  defaultValue: "Showing {{start}}-{{end}} of {{total}} chats",
                  start: pageStartNumber,
                  end: pageEndNumber,
                  total: orderedChats.length
                })}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={handlePreviousPage}
                  disabled={currentPageSafe <= 1}
                  className="rounded-md border border-border px-2 py-1 text-xs text-text hover:bg-surface2 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {t("common:previous", { defaultValue: "Previous" })}
                </button>
                <button
                  type="button"
                  onClick={handleNextPage}
                  disabled={currentPageSafe >= totalPages}
                  className="rounded-md border border-border px-2 py-1 text-xs text-text hover:bg-surface2 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {t("common:next", { defaultValue: "Next" })}
                </button>
                <span className="text-xs text-text-subtle">
                  {t("common:pageOf", {
                    defaultValue: "Page {{page}} of {{pages}}",
                    page: currentPageSafe,
                    pages: totalPages
                  })}
                </span>
                <Input
                  value={pageJumpValue}
                  onChange={(event) => setPageJumpValue(event.target.value)}
                  onPressEnter={handleJumpToPage}
                  size="small"
                  className="w-16"
                  inputMode="numeric"
                  aria-label={t("common:chatSidebar.pageNumber", {
                    defaultValue: "Page number"
                  })}
                />
                <button
                  type="button"
                  onClick={handleJumpToPage}
                  className="rounded-md border border-border px-2 py-1 text-xs text-text hover:bg-surface2"
                >
                  {t("common:go", { defaultValue: "Go" })}
                </button>
              </div>
            </div>
          )}
        </>
      )}
      <React.Suspense fallback={null}>
        {bulkFolderPickerOpen && (
          <BulkFolderPickerModal
            open={bulkFolderPickerOpen}
            conversationIds={selectedConversationIds}
            onClose={handleBulkFolderPickerClose}
            onSuccess={clearSelection}
          />
        )}
        {bulkTagPickerOpen && (
          <BulkTagPickerModal
            open={bulkTagPickerOpen}
            conversationIds={selectedConversationIds}
            onClose={handleBulkTagPickerClose}
            onSuccess={clearSelection}
          />
        )}
      </React.Suspense>
      <Modal
        open={bulkDeleteConfirmOpen}
        onCancel={handleBulkDeleteConfirmClose}
        onOk={handleBulkDelete}
        okText={t("sidepanel:multiSelect.deleteConfirmOk", "Move to trash")}
        cancelText={t("common:cancel", "Cancel")}
        okButtonProps={{ danger: true }}
        title={t(
          "sidepanel:multiSelect.deleteConfirmTitle",
          "Move chats to trash?"
        )}
        destroyOnHidden
      >
        <p>
          {t(
            "sidepanel:multiSelect.deleteConfirmBody",
            "This will hide the selected chats by tagging them as Trash."
          )}
        </p>
      </Modal>
    </div>
  )
}

export default ServerChatList
