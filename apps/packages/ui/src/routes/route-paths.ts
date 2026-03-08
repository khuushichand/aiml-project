export const CHAT_PATH = "/chat"
export const RESEARCH_PATH = "/research"
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

type BuildResearchLaunchPathOptions = {
  query?: string | null
  sourcePolicy?: string | null
  autonomyMode?: string | null
  autorun?: boolean
  from?: string | null
  run?: string | null
}

const setTrimmedSearchParam = (
  params: URLSearchParams,
  key: string,
  value: string | null | undefined
) => {
  const trimmed = value?.trim()
  if (trimmed) {
    params.set(key, trimmed)
  }
}

export const buildResearchLaunchPath = (
  options: BuildResearchLaunchPathOptions = {}
): string => {
  const params = new URLSearchParams()
  setTrimmedSearchParam(params, "query", options.query)
  setTrimmedSearchParam(params, "source_policy", options.sourcePolicy)
  setTrimmedSearchParam(params, "autonomy_mode", options.autonomyMode)
  setTrimmedSearchParam(params, "from", options.from)
  setTrimmedSearchParam(params, "run", options.run)
  if (options.autorun) {
    params.set("autorun", "1")
  }
  const encoded = params.toString()
  return encoded ? `${RESEARCH_PATH}?${encoded}` : RESEARCH_PATH
}
