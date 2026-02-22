import React from "react"
import { useStoreMessageOption } from "@/store/option"
import { shallow } from "zustand/shallow"
import {
  formatDictionaryChatReferenceTitle,
  normalizeDictionaryChatState,
  resolveDictionaryChatReferenceId,
} from "../listUtils"

type UseDictionaryChatContextNavigationResult = {
  openChatContextFromDictionary: (chatRef: any) => void
}

export function useDictionaryChatContextNavigation(): UseDictionaryChatContextNavigationResult {
  const {
    setHistoryId,
    setServerChatId,
    setServerChatState,
    setServerChatTitle,
  } = useStoreMessageOption(
    (state) => ({
      setHistoryId: state.setHistoryId,
      setServerChatId: state.setServerChatId,
      setServerChatState: state.setServerChatState,
      setServerChatTitle: state.setServerChatTitle,
    }),
    shallow
  )

  const openChatContextFromDictionary = React.useCallback(
    (chatRef: any) => {
      const chatId = resolveDictionaryChatReferenceId(chatRef)
      if (!chatId) return

      const state = normalizeDictionaryChatState(chatRef?.state)
      const title = formatDictionaryChatReferenceTitle(chatRef)

      setHistoryId(null, { preserveServerChatId: true })
      setServerChatId(chatId)
      setServerChatState(state)
      setServerChatTitle(title)

      try {
        if (window.location.hash !== "#/") {
          if (window.history && typeof window.history.pushState === "function") {
            window.history.pushState(null, "", "#/")
          } else {
            window.location.hash = "#/"
          }
        }
      } catch {
        // best-effort navigation
      }
    },
    [setHistoryId, setServerChatId, setServerChatState, setServerChatTitle]
  )

  return { openChatContextFromDictionary }
}
