export type WritingPromptChunk = {
  type: "user" | "assistant"
  content: string
  prob?: number
  completion_probabilities?: Array<{
    content: string
    probs: Array<{ tok_str: string; prob: number }>
  }>
}

export type WritingLogitBiasEntry = {
  ids: number[]
  strings: string[]
  power: number
}

export type WritingLogitBiasState = {
  bias: Record<string, WritingLogitBiasEntry>
  model: string
}

export type WritingMemoryTokens = {
  contextOrder: string
  prefix: string
  text: string
  suffix: string
  tokens?: number
  tokensWI?: number
  worldInfo?: string
}

export type WritingAuthorNoteTokens = {
  prefix: string
  text: string
  suffix: string
  tokens?: number
}

export type WritingWorldInfoEntry = {
  displayName: string
  text: string
  keys: string[]
  search: string | number
}

export type WritingWorldInfo = {
  mikuPediaVersion: number
  entries: WritingWorldInfoEntry[]
  prefix: string
  suffix: string
}

export type WritingTemplatePayload = {
  sysPre?: string
  sysSuf?: string
  instPre?: string
  instSuf?: string
  fimTemplate?: string
}

export type WritingThemePayload = {
  class_name?: string
  className?: string
  css?: string
  order?: number
  isDefault?: boolean
}

export type WritingSessionPayload = {
  schemaVersion: number
  prompt: WritingPromptChunk[]
  seed: number
  maxPredictTokens: number
  temperature: number
  dynaTempRange: number
  dynaTempExp: number
  repeatPenalty: number
  repeatLastN: number
  penalizeNl: boolean
  presencePenalty: number
  frequencyPenalty: number
  topK: number
  topP: number
  typicalP: number
  minP: number
  tfsZ: number
  mirostat: number
  mirostatTau: number
  mirostatEta: number
  xtcThreshold: number
  xtcProbability: number
  dryMultiplier: number
  dryBase: number
  dryAllowedLength: number
  dryPenaltyRange: number
  drySequenceBreakers: string
  bannedTokens: string
  stoppingStrings: string
  useBasicStoppingMode: boolean
  basicStoppingModeType: "max_tokens" | "new_line" | "fill_suffix"
  ignoreEos: boolean
  openaiPresets: boolean
  contextLength: number
  tokenRatio: number
  memoryTokens: WritingMemoryTokens
  authorNoteTokens: WritingAuthorNoteTokens
  authorNoteDepth: number
  worldInfo: WritingWorldInfo
  logitBias: WritingLogitBiasState
  template: string
  scrollTop: number
  enabledSamplers: string[]
  grammar: string
  chatMode: boolean
  chatAPI: boolean
  tokenStreaming: boolean
  promptPreview: boolean
  promptPreviewTokens: number
  themeName: string
  showMarkdownPreview: boolean
  fontSizeMultiplier: number
  spellCheck: boolean
  attachSidebar: boolean
  preserveCursorPosition: boolean
  tokenHighlightMode: number
  tokenColorMode: number
  showProbsMode: number
  promptAreaWidth?: string
  provider: string
  model: string
  ttsEnabled: boolean
  ttsVoiceId: number
  ttsPitch: number
  ttsRate: number
  ttsVolume: number
  ttsSpeakInputs: boolean
  ttsMaxUserInput: number
}
