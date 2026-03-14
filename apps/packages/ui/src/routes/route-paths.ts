export const CHAT_PATH = "/chat"
export const WORKSPACE_PLAYGROUND_PATH = "/workspace-playground"
export const DOCUMENT_WORKSPACE_PATH = "/document-workspace"
export const PRESENTATION_STUDIO_PATH = "/presentation-studio"
export const PRESENTATION_STUDIO_NEW_PATH = "/presentation-studio/new"
export const PRESENTATION_STUDIO_DETAIL_PATH = "/presentation-studio/:projectId"
export const PRESENTATION_STUDIO_START_PATH = "/presentation-studio/start"
export const REPO2TXT_PATH = "/repo2txt"
export const SOURCES_PATH = "/sources"
export const SOURCES_NEW_PATH = "/sources/new"
export const SOURCES_DETAIL_PATH = "/sources/:sourceId"
export const ADMIN_SOURCES_PATH = "/admin/sources"

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
