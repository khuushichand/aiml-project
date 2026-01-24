import type { NotificationInstance } from "antd/es/notification/interface"
import type { TFunction } from "i18next"
import {
  saveMessageOnError as saveError,
  saveMessageOnSuccess as saveSuccess
} from "../chat-helper"
import type { ChatHistory } from "@/store/option"

type SaveSuccessPayload = Parameters<typeof saveSuccess>[0]
type SaveErrorPayload = Parameters<typeof saveError>[0]

export const focusTextArea = (
  textareaRef?: React.RefObject<HTMLTextAreaElement | null>
) => {
  try {
    if (textareaRef?.current) {
      textareaRef.current.focus()
    } else {
      const textareaElement = document.getElementById(
        "textarea-message"
      ) as HTMLTextAreaElement
      if (textareaElement) {
        textareaElement.focus()
      }
    }
  } catch {}
}

export const validateBeforeSubmit = (
  selectedModel: string,
  t: TFunction,
  notification: NotificationInstance
) => {
  if (!selectedModel || selectedModel?.trim()?.length === 0) {
    notification.error({
      message: t("error"),
      description: t("validationSelectModel")
    })
    return false
  }

  return true
}

export const createSaveMessageOnSuccess = (
  temporaryChat: boolean,
  setHistoryId: (id: string, options?: { preserveServerChatId?: boolean }) => void
) => {
  return async (payload: SaveSuccessPayload): Promise<string | null> => {
    if (!temporaryChat) {
      return await saveSuccess(payload)
    } else {
      setHistoryId("temp")
      return null
    }
  }
}

export const createSaveMessageOnError = (
  temporaryChat: boolean,
  history: ChatHistory,
  setHistory: (history: ChatHistory) => void,
  setHistoryId: (id: string, options?: { preserveServerChatId?: boolean }) => void
) => {
  return async (payload: SaveErrorPayload): Promise<string | null> => {
    if (!temporaryChat) {
      return await saveError(payload)
    } else {
      setHistory([
        ...history,
        {
          role: "user",
          content: payload.userMessage,
          image: payload.image
        },
        {
          role: "assistant",
          content: payload.botMessage
        }
      ])

      setHistoryId("temp")
      return null
    }
  }
}
