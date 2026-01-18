type ChatBaseKeys =
  | "messages"
  | "setMessages"
  | "history"
  | "setHistory"
  | "streaming"
  | "setStreaming"
  | "isFirstMessage"
  | "setIsFirstMessage"
  | "historyId"
  | "setHistoryId"
  | "isLoading"
  | "setIsLoading"
  | "isProcessing"
  | "setIsProcessing"
  | "chatMode"
  | "setChatMode"
  | "isEmbedding"
  | "setIsEmbedding"
  | "selectedSystemPrompt"
  | "setSelectedSystemPrompt"
  | "selectedQuickPrompt"
  | "setSelectedQuickPrompt"
  | "useOCR"
  | "setUseOCR"

type ChatBaseShape = Record<ChatBaseKeys, unknown>

export type ChatBaseState<State extends ChatBaseShape> = Pick<State, ChatBaseKeys>

type StoreHook<State> = <T>(selector: (state: State) => T) => T

export const useChatBaseState = <State extends ChatBaseShape>(
  useStore: StoreHook<State>
): ChatBaseState<State> => ({
  messages: useStore((state) => state.messages),
  setMessages: useStore((state) => state.setMessages),
  history: useStore((state) => state.history),
  setHistory: useStore((state) => state.setHistory),
  streaming: useStore((state) => state.streaming),
  setStreaming: useStore((state) => state.setStreaming),
  isFirstMessage: useStore((state) => state.isFirstMessage),
  setIsFirstMessage: useStore((state) => state.setIsFirstMessage),
  historyId: useStore((state) => state.historyId),
  setHistoryId: useStore((state) => state.setHistoryId),
  isLoading: useStore((state) => state.isLoading),
  setIsLoading: useStore((state) => state.setIsLoading),
  isProcessing: useStore((state) => state.isProcessing),
  setIsProcessing: useStore((state) => state.setIsProcessing),
  chatMode: useStore((state) => state.chatMode),
  setChatMode: useStore((state) => state.setChatMode),
  isEmbedding: useStore((state) => state.isEmbedding),
  setIsEmbedding: useStore((state) => state.setIsEmbedding),
  selectedSystemPrompt: useStore((state) => state.selectedSystemPrompt),
  setSelectedSystemPrompt: useStore((state) => state.setSelectedSystemPrompt),
  selectedQuickPrompt: useStore((state) => state.selectedQuickPrompt),
  setSelectedQuickPrompt: useStore((state) => state.setSelectedQuickPrompt),
  useOCR: useStore((state) => state.useOCR),
  setUseOCR: useStore((state) => state.setUseOCR)
})
