export const normalizeWorkspacePath = (rawPath: string): string => {
  const trimmed = rawPath.trim()
  if (!trimmed) {
    return ""
  }

  let normalized = trimmed.replace(/\\/g, "/")
  const isWindowsRoot = /^[a-zA-Z]:\/$/.test(normalized)

  if (normalized.length > 1 && !isWindowsRoot) {
    normalized = normalized.replace(/\/+$/, "")
  }

  const isWindowsPath = /^[a-zA-Z]:\//.test(normalized) || normalized.startsWith("//")
  if (isWindowsPath) {
    normalized = normalized.toLowerCase()
  }

  return normalized
}

export const isDuplicateWorkspacePath = (
  candidatePath: string,
  workspaces: Array<{ path: string }>
): boolean => {
  const normalizedCandidate = normalizeWorkspacePath(candidatePath)
  if (!normalizedCandidate) {
    return false
  }

  return workspaces.some(
    (workspace) => normalizeWorkspacePath(workspace.path) === normalizedCandidate
  )
}
