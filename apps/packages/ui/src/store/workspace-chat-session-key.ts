const WORKSPACE_CHAT_SESSION_KEY_SEPARATOR = "::"

const normalizeKeyPart = (value: string | null | undefined): string =>
  typeof value === "string" ? value.trim() : ""

export const buildWorkspaceChatSessionKey = (
  workspaceId: string,
  sessionReferenceId?: string | null
): string => {
  const normalizedWorkspaceId = normalizeKeyPart(workspaceId)
  const normalizedSessionReferenceId = normalizeKeyPart(sessionReferenceId)

  if (!normalizedWorkspaceId) {
    return normalizedSessionReferenceId
  }
  if (
    !normalizedSessionReferenceId ||
    normalizedSessionReferenceId === normalizedWorkspaceId
  ) {
    return normalizedWorkspaceId
  }

  return `${normalizedWorkspaceId}${WORKSPACE_CHAT_SESSION_KEY_SEPARATOR}${normalizedSessionReferenceId}`
}

export const isWorkspaceChatSessionKeyForWorkspace = (
  sessionKey: string,
  workspaceId: string
): boolean => {
  const normalizedSessionKey = normalizeKeyPart(sessionKey)
  const normalizedWorkspaceId = normalizeKeyPart(workspaceId)

  if (!normalizedSessionKey || !normalizedWorkspaceId) {
    return false
  }

  return (
    normalizedSessionKey === normalizedWorkspaceId ||
    normalizedSessionKey.startsWith(
      `${normalizedWorkspaceId}${WORKSPACE_CHAT_SESSION_KEY_SEPARATOR}`
    )
  )
}

export const extractWorkspaceIdFromChatSessionKey = (
  sessionKey: string
): string => {
  const normalizedSessionKey = normalizeKeyPart(sessionKey)
  if (!normalizedSessionKey) return ""

  const separatorIndex = normalizedSessionKey.indexOf(
    WORKSPACE_CHAT_SESSION_KEY_SEPARATOR
  )
  if (separatorIndex < 0) {
    return normalizedSessionKey
  }

  return normalizedSessionKey.slice(0, separatorIndex)
}
