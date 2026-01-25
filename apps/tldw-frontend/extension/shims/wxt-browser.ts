type BrowserListener = (...args: unknown[]) => void
type BrowserTab = {
  id?: number
  title?: string
  url?: string
  favIconUrl?: string
  active?: boolean
  status?: string
}

const createEventTarget = () => {
  const listeners = new Set<BrowserListener>()
  return {
    addListener: (listener: BrowserListener) => listeners.add(listener),
    removeListener: (listener: BrowserListener) => listeners.delete(listener),
    hasListener: (listener: BrowserListener) => listeners.has(listener),
    trigger: (...args: unknown[]) =>
      listeners.forEach((listener) => listener(...args))
  }
}

const noopAsync = async (..._args: unknown[]) => undefined

const runtime = {
  id: undefined,
  getURL: (path: string) => {
    if (typeof window === "undefined") return path
    try {
      return new URL(path, window.location.origin).toString()
    } catch {
      return path
    }
  },
  getManifest: () => ({
    name: "tldw",
    version: "0.0.0"
  }),
  lastError: undefined,
  sendMessage: async (..._args: unknown[]) => undefined,
  sendNativeMessage: async (
    _host?: string,
    _message?: unknown
  ) => {
    throw new Error("Native messaging is not available in web mode.")
  },
  connect: (_info?: Record<string, unknown>) => ({
    postMessage: (_message?: unknown) => {},
    onMessage: createEventTarget(),
    onDisconnect: createEventTarget(),
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
  query: async (
    _query?: Record<string, unknown>,
    callback?: (tabs: BrowserTab[]) => void
  ): Promise<BrowserTab[]> => {
    const result: BrowserTab[] = []
    callback?.(result)
    return result
  },
  create: async ({ url }: { url: string }) => {
    if (typeof window !== "undefined") {
      window.open(url, "_blank", "noopener,noreferrer")
    }
  },
  captureVisibleTab: async (
    _windowId?: number | null,
    _options?: Record<string, unknown>,
    callback?: (dataUrl: string | null) => void
  ) => {
    const result = null
    callback?.(result)
    return result
  }
}

const notifications = {
  create: async (_options?: Record<string, unknown>) => undefined
}

const getStorageBackend = () => {
  if (typeof window !== "undefined" && window.localStorage) {
    return window.localStorage
  }
  return null
}

const storageArea = {
  get: (
    keys?: string | string[] | null,
    callback?: (items: Record<string, unknown>) => void
  ) => {
    const backend = getStorageBackend()
    const result: Record<string, unknown> = {}
    if (!backend) {
      callback?.(result)
      return Promise.resolve(result)
    }
    const parseValue = (raw: string | null): unknown => {
      if (raw == null) return raw
      try {
        return JSON.parse(raw)
      } catch {
        return raw
      }
    }
    if (!keys) {
      for (let i = 0; i < backend.length; i += 1) {
        const key = backend.key(i)
        if (key) {
          result[key] = parseValue(backend.getItem(key))
        }
      }
    } else {
      const keyList = Array.isArray(keys) ? keys : [keys]
      keyList.forEach((key) => {
        result[key] = parseValue(backend.getItem(key))
      })
    }
    callback?.(result)
    return Promise.resolve(result)
  },
  set: (items: Record<string, unknown>, callback?: () => void) => {
    const backend = getStorageBackend()
    if (backend) {
      Object.entries(items).forEach(([key, value]) => {
        backend.setItem(key, JSON.stringify(value))
      })
    }
    callback?.()
    return Promise.resolve()
  },
  remove: (keys: string | string[], callback?: () => void) => {
    const backend = getStorageBackend()
    if (backend) {
      const keyList = Array.isArray(keys) ? keys : [keys]
      keyList.forEach((key) => backend.removeItem(key))
    }
    callback?.()
    return Promise.resolve()
  },
  clear: (callback?: () => void) => {
    const backend = getStorageBackend()
    backend?.clear()
    callback?.()
    return Promise.resolve()
  }
}

const storage = {
  local: storageArea,
  sync: storageArea,
  session: storageArea,
  onChanged: createEventTarget()
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

type ScriptResult = { result?: unknown }

const scripting = {
  executeScript: async (
    _options?: Record<string, unknown>
  ): Promise<ScriptResult[]> => []
}

const tts = {
  speak: (_utterance: string, _options?: Record<string, unknown>) => {},
  stop: () => {},
  getVoices: async () => []
}

const extension = {
  inIncognitoContext: false
}

const sidePanel = {
  open: noopAsync,
  setOptions: noopAsync
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
  alarms,
  scripting,
  tts,
  extension,
  sidePanel
}

export type Browser = typeof browser
