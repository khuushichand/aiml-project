type BrowserListener = (...args: any[]) => void

const createEventTarget = () => {
  const listeners = new Set<BrowserListener>()
  return {
    addListener: (listener: BrowserListener) => listeners.add(listener),
    removeListener: (listener: BrowserListener) => listeners.delete(listener),
    hasListener: (listener: BrowserListener) => listeners.has(listener),
    trigger: (...args: any[]) => listeners.forEach((listener) => listener(...args))
  }
}

const noopAsync = async () => undefined

const runtime = {
  getURL: (path: string) => {
    if (typeof window === "undefined") return path
    try {
      return new URL(path, window.location.origin).toString()
    } catch {
      return path
    }
  },
  sendMessage: async () => undefined,
  connect: () => ({
    postMessage: () => {},
    onMessage: createEventTarget(),
    disconnect: () => {}
  }),
  openOptionsPage: () => {
    if (typeof window !== "undefined") {
      window.location.href = "/settings"
    }
  },
  onMessage: createEventTarget(),
  onConnect: createEventTarget()
}

const tabs = {
  query: async () => [],
  create: async ({ url }: { url: string }) => {
    if (typeof window !== "undefined") {
      window.open(url, "_blank", "noopener,noreferrer")
    }
  },
  captureVisibleTab: async () => null
}

const notifications = {
  create: async () => undefined
}

const storageArea = {
  clear: noopAsync
}

const storage = {
  local: storageArea,
  sync: storageArea,
  session: storageArea
}

const permissions = {
  request: async () => false
}

const i18n = {
  getMessage: () => ""
}

const action = {
  setTitle: noopAsync,
  setBadgeText: noopAsync,
  setBadgeBackgroundColor: noopAsync
}

const browserAction = action

const contextMenus = {
  create: noopAsync,
  remove: noopAsync,
  removeAll: noopAsync,
  onClicked: createEventTarget()
}

const commands = {
  onCommand: createEventTarget()
}

const alarms = {
  create: noopAsync,
  clear: noopAsync,
  onAlarm: createEventTarget()
}

export const browser = {
  runtime,
  tabs,
  notifications,
  storage,
  permissions,
  i18n,
  action,
  browserAction,
  contextMenus,
  commands,
  alarms
}

export type Browser = typeof browser
