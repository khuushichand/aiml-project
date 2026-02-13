const normalizePathname = (input: string): string => {
  const trimmed = String(input || "").trim()
  if (!trimmed) return "/"

  const pathOnly = trimmed.split(/[?#]/, 1)[0] || "/"
  const normalized = pathOnly.replace(/\/+$/, "")
  return normalized || "/"
}

export const isSidebarShortcutRouteActive = (
  shortcutPath: string,
  currentPathname: string
): boolean => {
  const target = normalizePathname(shortcutPath)
  const current = normalizePathname(currentPathname)

  if (target === "/") {
    return current === "/" || current === "/chat"
  }

  if (target === "/settings") {
    return current === "/settings" || current.startsWith("/settings/")
  }

  return current === target || current.startsWith(`${target}/`)
}

