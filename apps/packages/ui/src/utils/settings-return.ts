const SETTINGS_RETURN_TO_KEY = "tldw:settingsReturnTo"

const isSettingsPath = (path: string) => path.startsWith("/settings")

export const setSettingsReturnTo = (path: string) => {
  try {
    if (typeof sessionStorage === "undefined") return
    if (!path || isSettingsPath(path)) return
    sessionStorage.setItem(SETTINGS_RETURN_TO_KEY, path)
  } catch {
    // ignore storage errors
  }
}

export const getSettingsReturnTo = (): string | null => {
  try {
    if (typeof sessionStorage === "undefined") return null
    const raw = sessionStorage.getItem(SETTINGS_RETURN_TO_KEY)
    if (!raw || typeof raw !== "string") return null
    if (isSettingsPath(raw)) {
      sessionStorage.removeItem(SETTINGS_RETURN_TO_KEY)
      return null
    }
    return raw
  } catch {
    return null
  }
}

export const clearSettingsReturnTo = () => {
  try {
    if (typeof sessionStorage === "undefined") return
    sessionStorage.removeItem(SETTINGS_RETURN_TO_KEY)
  } catch {
    // ignore storage errors
  }
}
