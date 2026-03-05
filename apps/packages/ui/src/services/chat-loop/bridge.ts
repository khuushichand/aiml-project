import type { ChatLoopEvent } from "@/services/chat-loop/types"

type ChatLoopEventListener = (event: ChatLoopEvent) => void

const listeners = new Set<ChatLoopEventListener>()

export function publishChatLoopEvent(event: ChatLoopEvent): void {
  listeners.forEach((listener) => {
    try {
      listener(event)
    } catch {
      // Best-effort fan-out; one listener must not break others.
    }
  })
}

export function subscribeChatLoopEvents(
  listener: ChatLoopEventListener,
): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}
