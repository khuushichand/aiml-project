import type { ChatCompletionRequest } from "./TldwApiClient"

export type ChatRequestDebugMode = "stream" | "non-stream"

export type ChatRequestDebugSnapshot = {
  endpoint: string
  method: string
  mode: ChatRequestDebugMode
  sentAt: string
  body: unknown
}

type CaptureChatRequestDebugSnapshotInput = {
  endpoint: string
  method: string
  mode: ChatRequestDebugMode
  body: unknown
}

let lastChatRequestDebugSnapshot: ChatRequestDebugSnapshot | null = null

const clonePayload = (body: unknown): unknown => {
  try {
    return JSON.parse(JSON.stringify(body))
  } catch {
    return body
  }
}

export const captureChatRequestDebugSnapshot = ({
  endpoint,
  method,
  mode,
  body
}: CaptureChatRequestDebugSnapshotInput) => {
  lastChatRequestDebugSnapshot = {
    endpoint,
    method,
    mode,
    sentAt: new Date().toISOString(),
    body: clonePayload(body)
  }
}

export const getLastChatRequestDebugSnapshot = () =>
  lastChatRequestDebugSnapshot

// Backward-compatible helper for prior /chat/completions-only consumers.
export type ChatCompletionDebugSnapshot = {
  endpoint: "/api/v1/chat/completions"
  mode: ChatRequestDebugMode
  sentAt: string
  request: ChatCompletionRequest
}

export const getLastChatCompletionDebugSnapshot =
  (): ChatCompletionDebugSnapshot | null => {
    const snapshot = lastChatRequestDebugSnapshot
    if (!snapshot || snapshot.endpoint !== "/api/v1/chat/completions") {
      return null
    }
    return {
      endpoint: "/api/v1/chat/completions",
      mode: snapshot.mode,
      sentAt: snapshot.sentAt,
      request: (snapshot.body || {}) as ChatCompletionRequest
    }
  }
