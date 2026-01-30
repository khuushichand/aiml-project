import { useEffect, useRef, useCallback } from "react"
import { useStoreMessageOption } from "@/store/option"
import type { Knowledge, State } from "@/store/option"
import { useConnectionStore } from "@/store/connection"

type DocumentChatSession = Pick<
  State,
  | "messages"
  | "history"
  | "historyId"
  | "isFirstMessage"
  | "serverChatId"
  | "serverChatTitle"
  | "serverChatCharacterId"
  | "serverChatMetaLoaded"
  | "serverChatState"
  | "serverChatVersion"
  | "serverChatTopic"
  | "serverChatClusterId"
  | "serverChatSource"
  | "serverChatExternalRef"
  | "selectedKnowledge"
  | "replyTarget"
  | "actionInfo"
>

const createEmptySession = (): DocumentChatSession => ({
  messages: [],
  history: [],
  historyId: null,
  isFirstMessage: true,
  serverChatId: null,
  serverChatTitle: null,
  serverChatCharacterId: null,
  serverChatMetaLoaded: false,
  serverChatState: null,
  serverChatVersion: null,
  serverChatTopic: null,
  serverChatClusterId: null,
  serverChatSource: null,
  serverChatExternalRef: null,
  selectedKnowledge: null,
  replyTarget: null,
  actionInfo: null
})

const documentKnowledgeId = (mediaId: number) => `document:${mediaId}`

const buildDocumentKnowledge = (mediaId: number): Knowledge => ({
  id: documentKnowledgeId(mediaId),
  title: `Document ${mediaId}`
})

const isDocumentKnowledge = (
  knowledge: Knowledge | null,
  mediaId: number | null
) => {
  if (!knowledge || mediaId === null) return false
  return knowledge.id === documentKnowledgeId(mediaId)
}

const isMediaDbOnlySources = (sources: string[] | null | undefined) =>
  Array.isArray(sources) && sources.length === 1 && sources[0] === "media_db"

/**
 * Hook that manages document-scoped chat state by automatically setting
 * `ragMediaIds` based on the active document.
 *
 * When a mediaId is provided, this hook:
 * - Sets ragMediaIds to [mediaId] to scope RAG queries to this document
 * - Sets ragSources to ["media_db"] to ensure queries go to the media database
 * - Cleans up on unmount or when mediaId changes
 *
 * @param mediaId - The active document's media ID (null when no document is open)
 */
export function useDocumentChat(mediaId: number | null) {
  const previousMediaIdRef = useRef<number | null>(null)
  const activeMediaIdRef = useRef<number | null>(mediaId)
  const sessionsRef = useRef<Map<number, DocumentChatSession>>(new Map())
  const baselineSessionRef = useRef<DocumentChatSession | null>(null)
  const baselineRagSettingsRef = useRef<{
    ragMediaIds: number[] | null
    ragSources: string[]
  } | null>(null)
  const previousRagSourcesRef = useRef<string[] | null>(null)

  // RAG state from the store
  const setRagMediaIds = useStoreMessageOption((s) => s.setRagMediaIds)
  const setRagSources = useStoreMessageOption((s) => s.setRagSources)
  const ragMediaIds = useStoreMessageOption((s) => s.ragMediaIds)
  const ragSources = useStoreMessageOption((s) => s.ragSources)
  const ragSearchMode = useStoreMessageOption((s) => s.ragSearchMode)
  const ragTopK = useStoreMessageOption((s) => s.ragTopK)

  // Chat state
  const messages = useStoreMessageOption((s) => s.messages)
  const setMessages = useStoreMessageOption((s) => s.setMessages)
  const streaming = useStoreMessageOption((s) => s.streaming)
  const isProcessing = useStoreMessageOption((s) => s.isProcessing)
  const selectedKnowledge = useStoreMessageOption((s) => s.selectedKnowledge)
  const setSelectedKnowledge = useStoreMessageOption(
    (s) => s.setSelectedKnowledge
  )

  // Connection state
  const isConnected = useConnectionStore((s) => s.state.isConnected)
  const mode = useConnectionStore((s) => s.state.mode)
  const isServerAvailable = isConnected && mode !== "demo"

  const snapshotSession = useCallback((): DocumentChatSession => {
    const state = useStoreMessageOption.getState()
    return {
      messages: state.messages,
      history: state.history,
      historyId: state.historyId,
      isFirstMessage: state.isFirstMessage,
      serverChatId: state.serverChatId,
      serverChatTitle: state.serverChatTitle,
      serverChatCharacterId: state.serverChatCharacterId,
      serverChatMetaLoaded: state.serverChatMetaLoaded,
      serverChatState: state.serverChatState,
      serverChatVersion: state.serverChatVersion,
      serverChatTopic: state.serverChatTopic,
      serverChatClusterId: state.serverChatClusterId,
      serverChatSource: state.serverChatSource,
      serverChatExternalRef: state.serverChatExternalRef,
      selectedKnowledge: state.selectedKnowledge,
      replyTarget: state.replyTarget,
      actionInfo: state.actionInfo
    }
  }, [])

  const applySession = useCallback((session: DocumentChatSession) => {
    useStoreMessageOption.setState({
      messages: session.messages,
      history: session.history,
      historyId: session.historyId,
      isFirstMessage: session.isFirstMessage,
      serverChatId: session.serverChatId,
      serverChatTitle: session.serverChatTitle,
      serverChatCharacterId: session.serverChatCharacterId,
      serverChatMetaLoaded: session.serverChatMetaLoaded,
      serverChatState: session.serverChatState,
      serverChatVersion: session.serverChatVersion,
      serverChatTopic: session.serverChatTopic,
      serverChatClusterId: session.serverChatClusterId,
      serverChatSource: session.serverChatSource,
      serverChatExternalRef: session.serverChatExternalRef,
      selectedKnowledge: session.selectedKnowledge,
      replyTarget: session.replyTarget,
      actionInfo: session.actionInfo
    })
  }, [])

  const ensureDocumentSources = useCallback(() => {
    if (isMediaDbOnlySources(ragSources)) {
      return
    }
    if (!previousRagSourcesRef.current) {
      previousRagSourcesRef.current = ragSources
    }
    setRagSources(["media_db"])
  }, [ragSources, setRagSources])

  const restoreRagSources = useCallback(() => {
    const previous = previousRagSourcesRef.current
    if (!previous) return
    const current = useStoreMessageOption.getState().ragSources
    if (isMediaDbOnlySources(current)) {
      setRagSources(previous)
    }
    previousRagSourcesRef.current = null
  }, [setRagSources])

  const ragEnabled = isDocumentKnowledge(selectedKnowledge, mediaId)

  const setRagEnabled = useCallback(
    (enabled: boolean) => {
      if (mediaId === null) return
      if (enabled) {
        setSelectedKnowledge(buildDocumentKnowledge(mediaId))
        ensureDocumentSources()
      } else {
        setSelectedKnowledge(null)
        restoreRagSources()
      }
    },
    [ensureDocumentSources, mediaId, restoreRagSources, setSelectedKnowledge]
  )

  useEffect(() => {
    activeMediaIdRef.current = mediaId
  }, [mediaId])

  useEffect(() => {
    if (!baselineSessionRef.current) {
      baselineSessionRef.current = snapshotSession()
      const state = useStoreMessageOption.getState()
      baselineRagSettingsRef.current = {
        ragMediaIds: state.ragMediaIds,
        ragSources: state.ragSources
      }
    }
  }, [snapshotSession])

  // Update RAG scope when mediaId changes
  useEffect(() => {
    if (mediaId === previousMediaIdRef.current) {
      return
    }

    const previousMediaId = previousMediaIdRef.current
    if (previousMediaId !== null) {
      sessionsRef.current.set(previousMediaId, snapshotSession())
    }

    previousMediaIdRef.current = mediaId

    if (mediaId !== null) {
      const session = sessionsRef.current.get(mediaId) ?? createEmptySession()
      applySession(session)
      // Scope RAG to this specific document
      setRagMediaIds([mediaId])
      if (isDocumentKnowledge(session.selectedKnowledge, mediaId)) {
        ensureDocumentSources()
      } else {
        restoreRagSources()
      }
    } else {
      // Clear document-specific RAG scope
      applySession(createEmptySession())
      setRagMediaIds(null)
      restoreRagSources()
    }
  }, [
    applySession,
    ensureDocumentSources,
    mediaId,
    restoreRagSources,
    setRagMediaIds,
    snapshotSession
  ])

  // Clean up on unmount
  useEffect(() => {
    return () => {
      const currentMediaId = activeMediaIdRef.current
      if (currentMediaId !== null) {
        sessionsRef.current.set(currentMediaId, snapshotSession())
      }
      if (baselineSessionRef.current) {
        applySession(baselineSessionRef.current)
      }
      const baselineRag = baselineRagSettingsRef.current
      if (baselineRag) {
        setRagMediaIds(baselineRag.ragMediaIds)
        setRagSources(baselineRag.ragSources)
      } else {
        // Reset RAG scope when leaving document workspace
        setRagMediaIds(null)
        restoreRagSources()
      }
      previousRagSourcesRef.current = null
    }
  }, [
    applySession,
    restoreRagSources,
    setRagMediaIds,
    setRagSources,
    snapshotSession
  ])

  // Clear messages for new document session
  const clearDocumentChat = useCallback(() => {
    const currentMediaId = activeMediaIdRef.current
    const existingSession = snapshotSession()
    const clearedSession: DocumentChatSession = {
      ...existingSession,
      messages: [],
      history: [],
      historyId: null,
      isFirstMessage: true,
      serverChatId: null,
      serverChatTitle: null,
      serverChatCharacterId: null,
      serverChatMetaLoaded: false,
      serverChatState: null,
      serverChatVersion: null,
      serverChatTopic: null,
      serverChatClusterId: null,
      serverChatSource: null,
      serverChatExternalRef: null,
      replyTarget: null,
      actionInfo: null
    }
    if (currentMediaId !== null) {
      sessionsRef.current.set(currentMediaId, clearedSession)
    }
    applySession(clearedSession)
  }, [applySession, snapshotSession])

  // Check if chat is ready for use
  const isChatReady = isServerAvailable && mediaId !== null

  // Check if document is currently scoped for RAG
  const isDocumentScoped =
    ragMediaIds !== null &&
    ragMediaIds.length === 1 &&
    ragMediaIds[0] === mediaId

  return {
    // Current state
    messages,
    streaming,
    isProcessing,
    isDocumentScoped,
    isChatReady,
    isServerAvailable,
    ragEnabled,

    // RAG configuration
    ragMediaIds,
    ragSources,
    ragSearchMode,
    ragTopK,

    // Actions
    clearDocumentChat,
    setRagEnabled,
    setMessages
  }
}

export type UseDocumentChatReturn = ReturnType<typeof useDocumentChat>
