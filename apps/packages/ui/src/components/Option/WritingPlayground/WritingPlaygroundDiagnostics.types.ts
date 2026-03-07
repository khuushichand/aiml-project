export type TranslateFn = (
  key: string,
  defaultValue: string,
  options?: Record<string, unknown>
) => string

export type DiagnosticsWord = {
  text: string
  weight: number
}

export type ResponseInspectorCardProps = {
  t: TranslateFn
  responseInspectorRowsCount: number
  responseLogprobsCount: number
  settingsLogprobsEnabled: boolean
  settingsDisabled: boolean
  responseLogprobRowsCount: number
  responseLogprobTruncated: boolean
  onCopyResponseInspectorJson: () => void | Promise<void>
  onExportResponseInspectorCsv: () => void
  onClearResponseInspector: () => void
}

export type TokenInspectorCardProps = {
  t: TranslateFn
  tokenizerName: string | null
  serverSupportsTokenCount: boolean
  canCountTokens: boolean
  isCountingTokens: boolean
  onCountTokens: () => void | Promise<void>
  serverSupportsTokenize: boolean
  canTokenizePreview: boolean
  isTokenizingText: boolean
  onTokenizePreview: () => void | Promise<void>
  hasTokenCountResult: boolean
  tokenCountValue: number | null
  hasTokenizeResult: boolean
  tokenInspectorError: string | null
  tokenInspectorBusy: boolean
  tokenInspectorUnavailableReason: string | null
  onClearTokenInspector: () => void
  tokenPreviewRowsCount: number
  tokenPreviewTotal: number
}

export type WordcloudCardProps = {
  t: TranslateFn
  wordcloudStatus: string | null
  wordcloudStatusColor: string
  canGenerateWordcloud: boolean
  isGeneratingWordcloud: boolean
  onGenerateWordcloud: () => void | Promise<void>
  wordcloudError: string | null
  onClearWordcloud: () => void
  wordcloudWords: DiagnosticsWord[]
}

export type ResponseInspectorPanelState = {
  enabled: boolean
} & Omit<ResponseInspectorCardProps, "t">

export type TokenInspectorPanelState = {
  enabled: boolean
} & Omit<TokenInspectorCardProps, "t">

export type WordcloudPanelState = {
  enabled: boolean
} & Omit<WordcloudCardProps, "t">

export type WritingPlaygroundDiagnosticsPanelProps = {
  title?: string
  t: TranslateFn
  status: "warning" | "busy" | "ready"
  showOffline: boolean
  showUnsupported: boolean
  hasActiveSession: boolean
  response: ResponseInspectorPanelState
  token: TokenInspectorPanelState
  wordcloud: WordcloudPanelState
}
