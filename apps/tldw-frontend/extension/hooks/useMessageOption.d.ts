import type { ChatHistory, Message } from "@/store/option"
import type { ChatDocuments } from "@/models/ChatTypes"
import type { UploadedFile } from "@/db/dexie/types"

declare module "@/hooks/useMessageOption" {
  export type OnSubmitArgs = {
    message: string
    image: string
    isContinue?: boolean
    isRegenerate?: boolean
    messages?: Message[]
    memory?: ChatHistory
    controller?: AbortController
    messageType?: string
    regenerateFromMessage?: Message
    docs?: ChatDocuments
    uploadedFiles?: UploadedFile[]
  }

  export type UseMessageOptionReturn = {
    messages: Message[]
    setMessages: (
      messagesOrUpdater: Message[] | ((prev: Message[]) => Message[])
    ) => void
    history: ChatHistory
    setHistory: (
      historyOrUpdater: ChatHistory | ((prev: ChatHistory) => ChatHistory)
    ) => void
    compareSelectionByCluster: Record<string, string[]>
    compareSelectedModels: string[]
    onSubmit: (args: OnSubmitArgs) => Promise<void>
    [key: string]: unknown
  }

  export function useMessageOption(): UseMessageOptionReturn
}
