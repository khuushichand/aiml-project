import { notification as staticNotification } from "antd"

type NotificationMethod = "open" | "success" | "info" | "warning" | "error"

const METHOD_PATCH_MARKER = "__tldwTitleCompatPatched"

export const normalizeNotificationConfig = (config: unknown) => {
  if (!config || typeof config !== "object" || Array.isArray(config)) {
    return config
  }

  const typed = config as Record<string, unknown>
  if (!Object.prototype.hasOwnProperty.call(typed, "message")) {
    return config
  }

  const { message, ...rest } = typed
  if (Object.prototype.hasOwnProperty.call(rest, "title")) {
    return rest
  }

  return {
    ...rest,
    title: message
  }
}

const patchNotificationMethod = (api: any, method: NotificationMethod) => {
  const original = api?.[method]
  if (typeof original !== "function" || original[METHOD_PATCH_MARKER]) {
    return
  }
  const wrapped = (config: unknown) =>
    original.call(api, normalizeNotificationConfig(config))
  ;(wrapped as any)[METHOD_PATCH_MARKER] = true
  api[method] = wrapped
}

export const patchNotificationApi = (api: unknown) => {
  const target = api as any
  patchNotificationMethod(target, "open")
  patchNotificationMethod(target, "success")
  patchNotificationMethod(target, "info")
  patchNotificationMethod(target, "warning")
  patchNotificationMethod(target, "error")
}

let staticCompatPatched = false

export const patchStaticAntdNotificationCompat = () => {
  if (staticCompatPatched) return
  patchNotificationApi(staticNotification)
  staticCompatPatched = true
}
