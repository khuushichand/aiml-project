export const CHAT_PATH = "/chat"
export const WORKSPACE_PLAYGROUND_PATH = "/workspace-playground"
export const DOCUMENT_WORKSPACE_PATH = "/document-workspace"
export const REPO2TXT_PATH = "/repo2txt"

export const LOREBOOK_DEBUG_FOCUS = "lorebook-debug"

type BuildChatLorebookDebugPathOptions = {
  from?: string | null
}

export const buildChatLorebookDebugPath = (
  options: BuildChatLorebookDebugPathOptions = {}
): string => {
  const params = new URLSearchParams({
    focus: LOREBOOK_DEBUG_FOCUS
  })
  const from = options.from?.trim()
  if (from) {
    params.set("from", from)
  }
  return `${CHAT_PATH}?${params.toString()}`
}
