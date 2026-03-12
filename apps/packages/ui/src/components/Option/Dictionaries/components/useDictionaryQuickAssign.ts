import { useQuery } from "@tanstack/react-query"
import React from "react"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import {
  type DictionaryChatState,
  formatDictionaryChatReferenceTitle,
  normalizeDictionaryChatState,
  resolveDictionaryChatReferenceId,
} from "../listUtils"

const DICTIONARY_SETTINGS_SINGLE_KEYS = new Set([
  "chatdictionaryid",
  "chat_dictionary_id",
  "dictionaryid",
  "dictionary_id",
])

const DICTIONARY_SETTINGS_LIST_KEYS = new Set([
  "chatdictionaryids",
  "chat_dictionary_ids",
  "chatdictionary",
  "chat_dictionary",
  "dictionaryids",
  "dictionary_ids",
  "chatdictionaries",
  "chat_dictionaries",
])

type UseDictionaryQuickAssignParams = {
  isOnline: boolean
  notification: {
    success: (config: { message: string; description?: string }) => void
    warning: (config: { message: string; description?: string }) => void
  }
  queryClient: {
    invalidateQueries: (input: { queryKey: readonly unknown[] }) => Promise<unknown>
  }
}

type UseDictionaryQuickAssignResult = {
  assignFor: any | null
  assignChatIds: string[]
  assignSearch: string
  setAssignSearch: React.Dispatch<React.SetStateAction<string>>
  assignSaving: boolean
  assignableChatsStatus: "pending" | "error" | "success"
  assignableChatsError: unknown
  refetchAssignableChats: () => Promise<unknown>
  quickAssignChatOptions: Array<{
    chat: any
    chatId: string
    title: string
    state: DictionaryChatState
  }>
  openQuickAssignModal: (dictionary: any) => void
  closeQuickAssignModal: () => void
  toggleAssignChatSelection: (chatId: string) => void
  handleConfirmQuickAssign: () => Promise<void>
}

function toPositiveDictionaryId(value: unknown): number | null {
  if (typeof value === "number" && Number.isInteger(value) && value > 0) {
    return value
  }
  if (typeof value === "string") {
    const trimmed = value.trim()
    if (!trimmed) return null
    const parsed = Number(trimmed)
    if (Number.isInteger(parsed) && parsed > 0) return parsed
  }
  return null
}

function collectDictionaryIdsFromSettingsValue(
  value: unknown,
  collector: Set<number>
) {
  const direct = toPositiveDictionaryId(value)
  if (direct != null) {
    collector.add(direct)
    return
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      collectDictionaryIdsFromSettingsValue(item, collector)
    }
    return
  }

  if (!value || typeof value !== "object") {
    return
  }

  for (const [rawKey, nested] of Object.entries(
    value as Record<string, unknown>
  )) {
    const normalizedKey = rawKey.trim().toLowerCase()
    if (
      normalizedKey === "id" ||
      DICTIONARY_SETTINGS_SINGLE_KEYS.has(normalizedKey) ||
      DICTIONARY_SETTINGS_LIST_KEYS.has(normalizedKey)
    ) {
      collectDictionaryIdsFromSettingsValue(nested, collector)
    }
  }
}

function collectDictionaryIdsFromChatSettings(settings: unknown): number[] {
  const collected = new Set<number>()
  const queue: unknown[] = [settings]

  while (queue.length > 0) {
    const current = queue.pop()
    if (!current || typeof current !== "object") continue

    if (Array.isArray(current)) {
      for (const item of current) {
        queue.push(item)
      }
      continue
    }

    for (const [rawKey, value] of Object.entries(
      current as Record<string, unknown>
    )) {
      const normalizedKey = rawKey.trim().toLowerCase()
      if (
        DICTIONARY_SETTINGS_SINGLE_KEYS.has(normalizedKey) ||
        DICTIONARY_SETTINGS_LIST_KEYS.has(normalizedKey)
      ) {
        collectDictionaryIdsFromSettingsValue(value, collected)
      }
      if (value && typeof value === "object") {
        queue.push(value)
      }
    }
  }

  return Array.from(collected).sort((a, b) => a - b)
}

function buildDictionaryChatAssignmentPatch(
  existingSettings: Record<string, unknown>,
  dictionaryId: number
): Record<string, unknown> {
  const merged = new Set(collectDictionaryIdsFromChatSettings(existingSettings))
  if (dictionaryId > 0) {
    merged.add(dictionaryId)
  }
  const ordered = Array.from(merged).sort((a, b) => a - b)
  const patch: Record<string, unknown> = {
    chat_dictionary_ids: ordered,
  }
  if (ordered.length === 1) {
    patch.chat_dictionary_id = ordered[0]
  }
  return patch
}

function isDictionaryChatSettingsNotFound(error: unknown): boolean {
  const message =
    error instanceof Error
      ? error.message.toLowerCase()
      : String(error || "").toLowerCase()
  if (!message) return false
  return message.includes("404") || message.includes("not found")
}

export function useDictionaryQuickAssign({
  isOnline,
  notification,
  queryClient,
}: UseDictionaryQuickAssignParams): UseDictionaryQuickAssignResult {
  const [assignFor, setAssignFor] = React.useState<any | null>(null)
  const [assignChatIds, setAssignChatIds] = React.useState<string[]>([])
  const [assignSearch, setAssignSearch] = React.useState("")
  const [assignSaving, setAssignSaving] = React.useState(false)

  const {
    data: assignableChatsData,
    status: assignableChatsStatus,
    error: assignableChatsError,
    refetch: refetchAssignableChats,
  } = useQuery({
    queryKey: ["tldw:listChatsForDictionaryAssign", assignFor?.id ?? null],
    queryFn: async () => {
      await tldwClient.initialize()
      return await tldwClient.listChats({
        limit: 100,
        offset: 0,
        include_deleted: false,
      })
    },
    enabled: Boolean(assignFor?.id && isOnline),
  })

  const openQuickAssignModal = React.useCallback((dictionary: any) => {
    const refs = Array.isArray(dictionary?.used_by_chat_refs)
      ? dictionary.used_by_chat_refs
      : []
    const preselectedIds = refs
      .map((chat: any) => resolveDictionaryChatReferenceId(chat))
      .filter((chatId: string) => chatId.length > 0)

    setAssignFor(dictionary)
    setAssignChatIds(Array.from(new Set(preselectedIds)))
    setAssignSearch("")
  }, [])

  const closeQuickAssignModal = React.useCallback(() => {
    if (assignSaving) return
    setAssignFor(null)
    setAssignChatIds([])
    setAssignSearch("")
  }, [assignSaving])

  const assignableChats = React.useMemo(() => {
    if (!Array.isArray(assignableChatsData)) return []
    return assignableChatsData
  }, [assignableChatsData])

  const filteredAssignableChats = React.useMemo(() => {
    if (!assignSearch.trim()) return assignableChats
    const normalized = assignSearch.trim().toLowerCase()
    return assignableChats.filter((chat: any) => {
      const id = resolveDictionaryChatReferenceId(chat).toLowerCase()
      const title = formatDictionaryChatReferenceTitle(chat).toLowerCase()
      return id.includes(normalized) || title.includes(normalized)
    })
  }, [assignSearch, assignableChats])

  const quickAssignChatOptions = React.useMemo(
    () =>
      filteredAssignableChats
        .map((chat: any) => {
          const chatId = resolveDictionaryChatReferenceId(chat)
          if (!chatId) return null
          return {
            chat,
            chatId,
            title: formatDictionaryChatReferenceTitle(chat),
            state: normalizeDictionaryChatState(chat?.state),
          }
        })
        .filter((value): value is {
          chat: any
          chatId: string
          title: string
          state: DictionaryChatState
        } => value != null),
    [filteredAssignableChats]
  )

  const toggleAssignChatSelection = React.useCallback((chatId: string) => {
    if (!chatId) return
    setAssignChatIds((prev) => {
      const exists = prev.includes(chatId)
      if (exists) {
        return prev.filter((value) => value !== chatId)
      }
      return [...prev, chatId]
    })
  }, [])

  const handleConfirmQuickAssign = React.useCallback(async () => {
    const dictionaryId = Number(assignFor?.id)
    if (!Number.isFinite(dictionaryId) || dictionaryId <= 0) return

    const selectedChatIds = Array.from(
      new Set(
        assignChatIds
          .map((value) => value.trim())
          .filter((value) => value.length > 0)
      )
    )

    if (selectedChatIds.length === 0) {
      notification.warning({
        message: "No chats selected",
        description: "Select at least one chat session before assigning.",
      })
      return
    }

    setAssignSaving(true)
    try {
      const assignmentResults = await Promise.all(
        selectedChatIds.map(async (chatId) => {
          try {
            let existingSettings: Record<string, unknown> = {}
            try {
              const settingsResponse = await tldwClient.getChatSettings(chatId)
              const rawSettings = settingsResponse?.settings
              if (rawSettings && typeof rawSettings === "object") {
                existingSettings = rawSettings as Record<string, unknown>
              }
            } catch (settingsError) {
              if (!isDictionaryChatSettingsNotFound(settingsError)) {
                throw settingsError
              }
            }

            const patch = buildDictionaryChatAssignmentPatch(
              existingSettings,
              dictionaryId
            )
            await tldwClient.updateChatSettings(chatId, patch)
            return { chatId, ok: true }
          } catch (chatError) {
            return { chatId, ok: false, error: chatError }
          }
        })
      )

      const successCount = assignmentResults.filter((item) => item.ok).length
      const failureCount = assignmentResults.length - successCount

      if (successCount > 0) {
        notification.success({
          message: "Dictionary assigned",
          description:
            successCount === 1
              ? "Dictionary assigned to 1 chat session."
              : `Dictionary assigned to ${successCount} chat sessions.`,
        })
        await queryClient.invalidateQueries({ queryKey: ["tldw:listDictionaries"] })
      }
      if (failureCount > 0) {
        notification.warning({
          message: "Some assignments failed",
          description:
            failureCount === 1
              ? "1 chat session could not be updated. Retry and check server logs."
              : `${failureCount} chat sessions could not be updated. Retry and check server logs.`,
        })
      }

      if (failureCount === 0) {
        setAssignFor(null)
        setAssignChatIds([])
        setAssignSearch("")
      }
    } finally {
      setAssignSaving(false)
    }
  }, [assignChatIds, assignFor, notification, queryClient])

  return {
    assignFor,
    assignChatIds,
    assignSearch,
    setAssignSearch,
    assignSaving,
    assignableChatsStatus,
    assignableChatsError,
    refetchAssignableChats,
    quickAssignChatOptions,
    openQuickAssignModal,
    closeQuickAssignModal,
    toggleAssignChatSelection,
    handleConfirmQuickAssign,
  }
}
