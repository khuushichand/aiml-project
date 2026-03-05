import type {
  ChatLoopEventsResponse,
  ChatLoopStartRequest,
  ChatLoopStartResponse,
} from "@/services/chat-loop/types"

async function requestJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init)
  if (!response.ok) {
    throw new Error(`Chat loop request failed (${response.status})`)
  }
  return (await response.json()) as T
}

export async function startChatLoop(
  body: ChatLoopStartRequest,
  init?: RequestInit,
): Promise<ChatLoopStartResponse> {
  return requestJson<ChatLoopStartResponse>("/api/v1/chat/loop/start", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    body: JSON.stringify(body),
    ...init,
  })
}

export async function getChatLoopEvents(
  runId: string,
  afterSeq = 0,
  init?: RequestInit,
): Promise<ChatLoopEventsResponse> {
  const query = new URLSearchParams({ after_seq: String(afterSeq) }).toString()
  return requestJson<ChatLoopEventsResponse>(`/api/v1/chat/loop/${encodeURIComponent(runId)}/events?${query}`, init)
}
