import { App, message as staticMessage } from "antd"
import type { MessageInstance } from "antd/es/message/interface"

export const useAntdMessage = (): MessageInstance => {
  const app = App.useApp()
  const appMessage = app?.message as Partial<MessageInstance> | undefined

  if (
    appMessage &&
    typeof appMessage.open === "function" &&
    typeof appMessage.success === "function" &&
    typeof appMessage.error === "function"
  ) {
    return appMessage as MessageInstance
  }

  return staticMessage as MessageInstance
}
