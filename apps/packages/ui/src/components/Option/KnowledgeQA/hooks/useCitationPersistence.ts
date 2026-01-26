/**
 * useCitationPersistence - Hook for persisting citations with messages
 *
 * This hook provides functions to:
 * - Persist RAG context (citations, documents, settings) to a message
 * - Retrieve RAG context from a message
 * - Get all citations for a conversation
 */

import { useCallback, useState } from "react"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import type { RagContextData } from "../types"

export function useCitationPersistence() {
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  /**
   * Persist RAG context to a message
   */
  const persistRagContext = useCallback(
    async (messageId: string, ragContext: RagContextData): Promise<boolean> => {
      setIsSaving(true)
      setError(null)

      try {
        const response = await tldwClient.fetchWithAuth(
          `/api/v1/chat/messages/${messageId}/rag-context`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              message_id: messageId,
              rag_context: ragContext,
            }),
          }
        )

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || "Failed to persist RAG context")
        }

        const result = await response.json()
        return result?.success ?? false
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error"
        setError(message)
        console.error("Failed to persist RAG context:", err)
        return false
      } finally {
        setIsSaving(false)
      }
    },
    []
  )

  /**
   * Retrieve RAG context from a message
   */
  const getRagContext = useCallback(
    async (messageId: string): Promise<RagContextData | null> => {
      try {
        const response = await tldwClient.fetchWithAuth(
          `/api/v1/chat/messages/${messageId}/rag-context`
        )

        if (!response.ok) {
          return null
        }

        const data = await response.json()
        return data?.rag_context ?? null
      } catch (err) {
        console.error("Failed to get RAG context:", err)
        return null
      }
    },
    []
  )

  /**
   * Get all citations from a conversation
   */
  const getConversationCitations = useCallback(
    async (
      conversationId: string
    ): Promise<{
      citations: Array<{
        id?: string
        title?: string
        score?: number
        excerpt?: string
        message_ids: string[]
      }>
      totalCount: number
    }> => {
      try {
        const response = await tldwClient.fetchWithAuth(
          `/api/v1/chat/conversations/${conversationId}/citations`
        )

        if (!response.ok) {
          return { citations: [], totalCount: 0 }
        }

        const data = await response.json()
        return {
          citations: data?.citations ?? [],
          totalCount: data?.total_count ?? 0,
        }
      } catch (err) {
        console.error("Failed to get conversation citations:", err)
        return { citations: [], totalCount: 0 }
      }
    },
    []
  )

  /**
   * Get messages with RAG context for a conversation
   */
  const getMessagesWithContext = useCallback(
    async (
      conversationId: string,
      options: { limit?: number; offset?: number } = {}
    ): Promise<
      Array<{
        id: string
        role: string
        content: string
        timestamp?: string
        rag_context?: RagContextData
      }>
    > => {
      try {
        const params = new URLSearchParams({
          include_rag_context: "true",
          limit: String(options.limit ?? 100),
          offset: String(options.offset ?? 0),
        })

        const response = await tldwClient.fetchWithAuth(
          `/api/v1/chat/conversations/${conversationId}/messages-with-context?${params}`
        )

        if (!response.ok) {
          return []
        }

        return await response.json()
      } catch (err) {
        console.error("Failed to get messages with context:", err)
        return []
      }
    },
    []
  )

  return {
    persistRagContext,
    getRagContext,
    getConversationCitations,
    getMessagesWithContext,
    isSaving,
    error,
  }
}
