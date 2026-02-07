import React from "react"
import { generateID } from "@/db/dexie/helpers"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import type { ChatHistory, Message } from "@/store/option/types"
import type { Character } from "@/types/character"
import {
  buildGreetingOptionsFromEntries,
  buildGreetingsChecksumFromOptions,
  collectGreetingEntries,
  type GreetingOption
} from "@/utils/character-greetings"
import { replaceUserDisplayNamePlaceholders } from "@/utils/chat-display-name"
import { useStorage } from "@plasmohq/storage/hook"
import { useChatSettingsRecord } from "@/hooks/chat/useChatSettingsRecord"
import {
  SELECTED_CHARACTER_STORAGE_KEY,
  selectedCharacterStorage,
  parseSelectedCharacterValue
} from "@/utils/selected-character-storage"

type UseCharacterGreetingOptions = {
  playgroundReady: boolean
  selectedCharacter: Character | null
  serverChatId: string | number | null
  historyId: string | null
  messagesLength: number
  setMessages: (
    messagesOrUpdater: Message[] | ((prev: Message[]) => Message[])
  ) => void
  setHistory: (
    historyOrUpdater: ChatHistory | ((prev: ChatHistory) => ChatHistory)
  ) => void
  setSelectedCharacter: (next: Character | null) => void
}

export const useCharacterGreeting = ({
  playgroundReady,
  selectedCharacter,
  serverChatId,
  historyId,
  messagesLength,
  setMessages,
  setHistory,
  setSelectedCharacter
}: UseCharacterGreetingOptions) => {
  const [userDisplayName] = useStorage("chatUserDisplayName", "")
  const resolvedServerChatId =
    serverChatId != null ? String(serverChatId) : null
  const { settings, updateSettings } = useChatSettingsRecord({
    historyId,
    serverChatId: resolvedServerChatId
  })
  const greetingEnabled = settings?.greetingEnabled ?? true
  const greetingInjectedRef = React.useRef<string | null>(null)
  const greetingFetchRef = React.useRef<string | null>(null)
  const greetingTemplateRef = React.useRef<{
    characterId: string
    greeting: string
    selectionId: string | null
    checksum: string | null
  } | null>(null)
  const chatWasEmptyRef = React.useRef(false)
  const selectedCharacterIdRef = React.useRef<string | null>(null)
  const lastCharacterIdRef = React.useRef<string | null>(null)

  React.useEffect(() => {
    if (!playgroundReady) return
    let cancelled = false
    const syncSelection = async () => {
      try {
        const storedRaw = await selectedCharacterStorage.get(
          SELECTED_CHARACTER_STORAGE_KEY
        )
        const stored = parseSelectedCharacterValue<Character>(storedRaw)
        if (!stored?.id || cancelled) return
        const storedId = String(stored.id)
        const currentId = selectedCharacter?.id
          ? String(selectedCharacter.id)
          : null
        if (storedId !== currentId) {
          setSelectedCharacter(stored)
        }
      } catch {
        // ignore
      }
    }
    void syncSelection()
    return () => {
      cancelled = true
    }
  }, [playgroundReady, selectedCharacter?.id, setSelectedCharacter])

  React.useEffect(() => {
    const isEmpty = messagesLength === 0
    if (isEmpty && !chatWasEmptyRef.current) {
      greetingInjectedRef.current = null
      greetingTemplateRef.current = null
    }
    chatWasEmptyRef.current = isEmpty
  }, [messagesLength])

  React.useEffect(() => {
    greetingFetchRef.current = null
    greetingTemplateRef.current = null
  }, [selectedCharacter?.id])

  React.useEffect(() => {
    if (!playgroundReady) return
    if (!selectedCharacter?.id) {
      selectedCharacterIdRef.current = null
      return
    }

    const characterId = String(selectedCharacter.id)
    selectedCharacterIdRef.current = characterId
    if (
      lastCharacterIdRef.current &&
      lastCharacterIdRef.current !== characterId
    ) {
      void updateSettings({
        greetingSelectionId: null,
        greetingsChecksum: null,
        useCharacterDefault: false
      })
      greetingTemplateRef.current = null
      greetingInjectedRef.current = null
    }
    lastCharacterIdRef.current = characterId
    const characterName = selectedCharacter.name || "Assistant"
    const characterAvatarUrl = selectedCharacter.avatar_url ?? null
    const isCurrentSelection = () =>
      selectedCharacterIdRef.current === characterId

    const upsertGreeting = (
      greetingValue: string,
      avatarUrl?: string | null,
      meta?: { selectionId?: string | null; checksum?: string | null }
    ) => {
      if (!isCurrentSelection()) return
      const rendered = replaceUserDisplayNamePlaceholders(
        greetingValue,
        userDisplayName
      )
      const trimmed = rendered.trim()
      if (!trimmed) return

      const createdAt = Date.now()
      const messageId = generateID()
      let updated = false

      setMessages((prev) => {
        if (!isCurrentSelection()) return prev
        const onlyGreetings =
          prev.length > 0 &&
          prev.every((message) => message.messageType === "character:greeting")
        const singleAssistant = prev.length === 1 && prev[0]?.isBot
        const canReplace =
          prev.length === 0 || onlyGreetings || singleAssistant
        if (!canReplace) return prev
        updated = true
        if (prev.length === 1 && prev[0]?.messageType === "character:greeting") {
          return [
            {
              ...prev[0],
              name: characterName,
              role: "assistant",
              message: trimmed,
              modelName: characterName,
              modelImage: avatarUrl ?? prev[0]?.modelImage
            }
          ]
        }
        return [
          {
            isBot: true,
            name: characterName,
            role: "assistant",
            message: trimmed,
            messageType: "character:greeting",
            sources: [],
            createdAt,
            id: messageId,
            modelName: characterName,
            modelImage: avatarUrl ?? undefined
          }
        ]
      })

      if (!updated) return
      greetingInjectedRef.current = characterId
      greetingTemplateRef.current = {
        characterId,
        greeting: greetingValue,
        selectionId: meta?.selectionId ?? null,
        checksum: meta?.checksum ?? null
      }

      if (greetingEnabled) {
        setHistory((prev) => {
          if (!isCurrentSelection()) return prev
          const onlyGreetings =
            prev.length > 0 &&
            prev.every((entry) => entry.messageType === "character:greeting")
          const singleAssistant =
            prev.length === 1 && prev[0]?.role === "assistant"
          const canReplace =
            prev.length === 0 || onlyGreetings || singleAssistant
          if (!canReplace) return prev
          if (
            prev.length === 1 &&
            prev[0]?.messageType === "character:greeting"
          ) {
            return [
              {
                ...prev[0],
                content: trimmed
              }
            ]
          }
          return [
            {
              role: "assistant",
              content: trimmed,
              messageType: "character:greeting"
            }
          ]
        })
      }
    }

    const resolveAndPersistGreeting = (
      options: GreetingOption[],
      avatarUrl: string | null
    ) => {
      const checksum =
        options.length > 0 ? buildGreetingsChecksumFromOptions(options) : null
      const storedSelectionId =
        typeof settings?.greetingSelectionId === "string"
          ? settings.greetingSelectionId
          : null
      const storedChecksum =
        typeof settings?.greetingsChecksum === "string"
          ? settings.greetingsChecksum
          : null
      const useCharacterDefault = Boolean(settings?.useCharacterDefault)
      const isStale =
        Boolean(storedChecksum) && checksum ? storedChecksum !== checksum : false
      let selectedOption =
        !isStale && storedSelectionId
          ? options.find((option) => option.id === storedSelectionId)
          : undefined

      if (!selectedOption) {
        if (useCharacterDefault) {
          selectedOption = options[0]
        } else if (options.length > 0) {
          selectedOption =
            options[Math.floor(Math.random() * options.length)]
        }
      }

      if (!selectedOption) {
        if (storedSelectionId || storedChecksum) {
          void updateSettings({
            greetingSelectionId: null,
            greetingsChecksum: null
          })
        }
        return
      }

      const cached = greetingTemplateRef.current
      if (
        cached?.characterId === characterId &&
        cached.selectionId === selectedOption.id &&
        cached.checksum === checksum
      ) {
        upsertGreeting(cached.greeting, avatarUrl, {
          selectionId: cached.selectionId,
          checksum: cached.checksum
        })
        return
      }

      if (
        storedSelectionId !== selectedOption.id ||
        storedChecksum !== checksum
      ) {
        void updateSettings({
          greetingSelectionId: selectedOption.id,
          greetingsChecksum: checksum
        })
      }

      upsertGreeting(selectedOption.text, avatarUrl, {
        selectionId: selectedOption.id,
        checksum
      })
    }

    const greetingEntries = collectGreetingEntries(selectedCharacter)
    const greetingOptions = buildGreetingOptionsFromEntries(greetingEntries)
    if (greetingOptions.length > 0) {
      resolveAndPersistGreeting(greetingOptions, characterAvatarUrl)
      if (greetingOptions.length > 1) {
        return
      }
    }

    const fallbackGreeting = greetingOptions[0]?.text?.trim() || ""
    if (greetingFetchRef.current !== characterId) {
      greetingFetchRef.current = characterId
      void (async () => {
        try {
          await tldwClient.initialize().catch(() => null)
          if (
            !isCurrentSelection() ||
            greetingFetchRef.current !== characterId
          ) {
            return
          }
          const full = await tldwClient.getCharacter(characterId)
          if (
            !isCurrentSelection() ||
            greetingFetchRef.current !== characterId
          ) {
            return
          }
          const fetchedEntries = collectGreetingEntries(full)
          const resolvedEntries =
            fetchedEntries.length > 0 ? fetchedEntries : greetingEntries
          const resolvedOptions = buildGreetingOptionsFromEntries(
            resolvedEntries
          )
          if (resolvedOptions.length > 0) {
            resolveAndPersistGreeting(resolvedOptions, characterAvatarUrl)
          } else if (
            settings?.greetingSelectionId ||
            settings?.greetingsChecksum
          ) {
            void updateSettings({
              greetingSelectionId: null,
              greetingsChecksum: null
            })
          }
          const nextAvatar =
            full?.avatar_url ?? selectedCharacter.avatar_url ?? null
          const mergedCharacter = full
            ? {
                ...selectedCharacter,
                ...full,
                avatar_url: nextAvatar
              }
            : {
                ...selectedCharacter,
                avatar_url: nextAvatar
              }
          setSelectedCharacter(mergedCharacter)
        } catch {
          if (fallbackGreeting) {
            resolveAndPersistGreeting(
              buildGreetingOptionsFromEntries([
                {
                  text: fallbackGreeting,
                  sourceKey: "greeting",
                  sourceLabel: "Greeting"
                }
              ]),
              characterAvatarUrl
            )
          }
        } finally {
          if (greetingFetchRef.current === characterId) {
            greetingFetchRef.current = null
          }
        }
      })()
    }
  }, [
    playgroundReady,
    selectedCharacter,
    serverChatId,
    historyId,
    setHistory,
    setMessages,
    setSelectedCharacter,
    userDisplayName,
    settings?.greetingSelectionId,
    settings?.greetingsChecksum,
    settings?.useCharacterDefault,
    settings?.greetingEnabled,
    updateSettings
  ])
}
