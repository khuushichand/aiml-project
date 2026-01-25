import { App, notification as staticNotification } from "antd"
import type { NotificationInstance } from "antd/es/notification/interface"

export const useAntdNotification = (): NotificationInstance => {
  const { notification } = App.useApp()
  const base = (notification || staticNotification) as NotificationInstance
  const api: any = base
  if (typeof api?.open !== "function") {
    return staticNotification as NotificationInstance
  }
  const ensureMethod = (type: "success" | "info" | "warning" | "error") => {
    if (typeof api[type] !== "function") {
      api[type] = (config: any) => api.open({ ...config, type })
    }
  }
  ensureMethod("success")
  ensureMethod("info")
  ensureMethod("warning")
  ensureMethod("error")
  return api as NotificationInstance
}
