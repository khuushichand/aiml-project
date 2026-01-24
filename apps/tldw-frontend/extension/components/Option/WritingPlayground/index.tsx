import React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Alert,
  Button,
  Card,
  Collapse,
  Divider,
  Input,
  InputNumber,
  message,
  Modal,
  Select,
  Space,
  Switch,
  Tooltip,
  Typography
} from "antd"
import clsx from "clsx"
import {
  FileDown,
  FileUp,
  Palette,
  Play,
  Plus,
  RefreshCcw,
  Search,
  Settings,
  Square,
  Trash2,
  Undo2,
  Redo2,
  Wand2
} from "lucide-react"
import { useStorage } from "@plasmohq/storage/hook"

import { useServerOnline } from "@/hooks/useServerOnline"
import { MarkdownPreview } from "@/components/Common/MarkdownPreview"
import { bgRequest, bgStream } from "@/services/background-proxy"
import {
  countWritingTokens,
  createWritingSession,
  createWritingTemplate,
  createWritingTheme,
  deleteWritingSession,
  deleteWritingTemplate,
  deleteWritingTheme,
  getWritingCapabilities,
  getWritingSession,
  listWritingSessions,
  listWritingTemplates,
  listWritingThemes,
  cloneWritingSession,
  tokenizeWriting,
  updateWritingSession,
  updateWritingTemplate,
  updateWritingTheme,
  type WritingCapabilitiesResponse,
  type WritingSessionResponse,
  type WritingTemplateResponse,
  type WritingThemeResponse
} from "@/services/writing"
import {
  applyFimTemplate,
  assembleWorldInfo,
  buildAdditionalContext,
  convertChatToMessages,
  joinPrompt,
  normalizeSessionPayload,
  replaceNewlines,
  replacePlaceholders
} from "@/utils/writing"
import type {
  WritingPromptChunk,
  WritingSessionPayload,
  WritingTemplatePayload,
  WritingWorldInfoEntry,
  WritingLogitBiasState
} from "@/types/writing"
import { DEFAULT_SESSION, DEFAULT_TEMPLATES, DEFAULT_THEMES } from "./presets"

const { Text, Title } = Typography

const clamp = (value: number, min: number, max: number) =>
  Math.max(min, Math.min(max, value))

const buildSessionName = (index: number) => `Writing Playground #${index}`

const highlightOptions = [
  { label: "Show on hover", value: 0 },
  { label: "Only current token", value: 1 },
  { label: "Hide", value: -1 }
]

const colorModeOptions = [
  { label: "Default", value: 0 },
  { label: "Probability", value: 1 },
  { label: "Perplexity", value: 2 }
]

const probsModeOptions = [
  { label: "Show on hover", value: 0 },
  { label: "Show with Ctrl", value: 1 },
  { label: "Hide", value: -1 }
]

const samplerOptions = [
  { key: "temperature", label: "Temperature" },
  { key: "rep_pen", label: "Repeat penalty" },
  { key: "pres_pen", label: "Presence penalty" },
  { key: "freq_pen", label: "Frequency penalty" },
  { key: "top_k", label: "Top K" },
  { key: "top_p", label: "Top P" },
  { key: "min_p", label: "Min P" },
  { key: "typical_p", label: "Typical P" },
  { key: "tfs_z", label: "TFS Z" },
  { key: "mirostat", label: "Mirostat" },
  { key: "dynatemp", label: "Dynatemp" },
  { key: "xtc", label: "XTC" },
  { key: "dry", label: "DRY" },
  { key: "ban_tokens", label: "Ban tokens" }
]

export const WritingPlayground: React.FC = () => {
  const online = useServerOnline()
  const queryClient = useQueryClient()

  const [selectedSessionId, setSelectedSessionId] = useStorage<string | null>(
    "writingPlayground:selectedSessionId",
    null
  )
  const [migrationDone, setMigrationDone] = useStorage<boolean>(
    "writingPlayground:migrated",
    false
  )

  const [session, setSession] = React.useState<WritingSessionPayload>(
    DEFAULT_SESSION
  )
  const [sessionMeta, setSessionMeta] = React.useState<WritingSessionResponse | null>(null)
  const [sessionNameDraft, setSessionNameDraft] = React.useState("")
  const [lastError, setLastError] = React.useState<string | null>(null)
  const [sessionError, setSessionError] = React.useState<string | null>(null)
  const [tokens, setTokens] = React.useState(0)
  const [tokensPerSec, setTokensPerSec] = React.useState(0)
  const [promptPreviewChunks, setPromptPreviewChunks] = React.useState<WritingPromptChunk[]>([])
  const [memoryTokenCount, setMemoryTokenCount] = React.useState(0)
  const [authorNoteTokenCount, setAuthorNoteTokenCount] = React.useState(0)
  const [worldInfoTokenCount, setWorldInfoTokenCount] = React.useState(0)
  const [logitBiasParam, setLogitBiasParam] = React.useState<Record<string, number>>({})
  const [currentPromptChunk, setCurrentPromptChunk] = React.useState<
    { index: number; top: number; left: number } | null
  >(null)
  const [showProbs, setShowProbs] = React.useState(false)
  const [stoppingStringsError, setStoppingStringsError] = React.useState<string | null>(null)
  const [drySequenceBreakersError, setDrySequenceBreakersError] = React.useState<string | null>(null)
  const [bannedTokensError, setBannedTokensError] = React.useState<string | null>(null)
  const [selectedText, setSelectedText] = React.useState("")
  const [instructContext, setInstructContext] = React.useState("")
  const [ttsAvailable, setTtsAvailable] = React.useState(false)
  const [ttsVoices, setTtsVoices] = React.useState<SpeechSynthesisVoice[]>([])

  const [modals, setModals] = React.useState({
    preferences: false,
    memory: false,
    authorNote: false,
    worldInfo: false,
    logitBias: false,
    context: false,
    templates: false,
    themes: false,
    searchReplace: false,
    grammar: false,
    instruct: false,
    renameSession: false
  })

  const promptAreaRef = React.useRef<HTMLTextAreaElement | null>(null)
  const promptOverlayRef = React.useRef<HTMLDivElement | null>(null)
  const promptPreviewRef = React.useRef<HTMLSpanElement | null>(null)
  const markdownPreviewRef = React.useRef<HTMLDivElement | null>(null)
  const themeStyleRef = React.useRef<HTMLStyleElement | null>(null)

  const abortControllerRef = React.useRef<AbortController | null>(null)
  const previewAbortRef = React.useRef<AbortController | null>(null)
  const saveTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const savingRef = React.useRef(false)
  const pendingSaveRef = React.useRef(false)
  const undoStackRef = React.useRef<number[]>([])
  const redoStackRef = React.useRef<WritingPromptChunk[][]>([])
  const keyStateRef = React.useRef<KeyboardEvent | null>(null)
  const probsDelayRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const isSyncingScrollRef = React.useRef(false)

  const ttsQueueRef = React.useRef<string[]>([])
  const ttsPausedRef = React.useRef(false)
  const ttsNewTextRef = React.useRef("")
  const ttsLastChunkRef = React.useRef("")

  const capabilitiesQuery = useQuery<WritingCapabilitiesResponse>({
    queryKey: ["writing", "capabilities"],
    queryFn: () => getWritingCapabilities(),
    enabled: online,
    staleTime: 60_000
  })

  const serverCapabilities = capabilitiesQuery.data?.server
  const sessionsSupported = serverCapabilities?.sessions !== false
  const templatesSupported = serverCapabilities?.templates !== false
  const themesSupported = serverCapabilities?.themes !== false
  const tokenizeSupported = serverCapabilities?.tokenize !== false
  const tokenCountSupported = serverCapabilities?.token_count !== false

  const sessionsQuery = useQuery({
    queryKey: ["writing", "sessions"],
    queryFn: () => listWritingSessions({ limit: 200 }),
    enabled: online && sessionsSupported
  })

  const templatesQuery = useQuery({
    queryKey: ["writing", "templates"],
    queryFn: () => listWritingTemplates({ limit: 300 }),
    enabled: online && templatesSupported
  })

  const themesQuery = useQuery({
    queryKey: ["writing", "themes"],
    queryFn: () => listWritingThemes({ limit: 300 }),
    enabled: online && themesSupported
  })

  const createSessionMutation = useMutation({
    mutationFn: createWritingSession,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["writing", "sessions"] })
      setSelectedSessionId(data.id)
    }
  })

  const updateSessionMutation = useMutation({
    mutationFn: ({
      sessionId,
      payload,
      name,
      expectedVersion
    }: {
      sessionId: string
      payload: WritingSessionPayload
      name: string
      expectedVersion: number
    }) =>
      updateWritingSession(
        sessionId,
        { payload: payload as Record<string, unknown>, name },
        expectedVersion
      )
  })

  const templateSeededRef = React.useRef(false)
  const themeSeededRef = React.useRef(false)

  const templateMap = React.useMemo(() => {
    const map = new Map<string, WritingTemplateResponse>()
    for (const template of templatesQuery.data?.templates ?? []) {
      map.set(template.name, template)
    }
    return map
  }, [templatesQuery.data])

  const themeMap = React.useMemo(() => {
    const map = new Map<string, WritingThemeResponse>()
    for (const theme of themesQuery.data?.themes ?? []) {
      map.set(theme.name, theme)
    }
    return map
  }, [themesQuery.data])

  const availableProviders = capabilitiesQuery.data?.providers ?? []
  const providerOptions = availableProviders.map((provider) => ({
    label: provider.name,
    value: provider.name
  }))

  const selectedProvider = session.provider || capabilitiesQuery.data?.default_provider || ""
  const providerCapabilities = availableProviders.find(
    (provider) => provider.name === selectedProvider
  )
  const supportedFields = new Set(providerCapabilities?.supported_fields ?? [])
  const tokenizerInfo = providerCapabilities?.tokenizers?.[session.model]
  const tokenizerAvailable = Boolean(tokenizeSupported && tokenizerInfo?.available)

  const modelOptions = (providerCapabilities?.models ?? []).map((model) => ({
    label: model,
    value: model
  }))

  const templateOptions = React.useMemo(() => {
    const names = new Set(Object.keys(DEFAULT_TEMPLATES))
    for (const name of templateMap.keys()) names.add(name)
    return Array.from(names)
      .sort((a, b) => a.localeCompare(b))
      .map((name) => ({ label: name, value: name }))
  }, [templateMap])

  const themeOptions = React.useMemo(() => {
    const names = new Set<string>(["Serif Light"])
    for (const name of themeMap.keys()) names.add(name)
    for (const name of Object.keys(DEFAULT_THEMES)) names.add(name)
    return Array.from(names)
      .sort((a, b) => a.localeCompare(b))
      .map((name) => ({ label: name, value: name }))
  }, [themeMap])

  const promptText = React.useMemo(() => joinPrompt(session.prompt), [session.prompt])

  const selectedTemplatePayload = React.useMemo<WritingTemplatePayload | undefined>(() => {
    if (templateMap.has(session.template)) {
      return templateMap.get(session.template)?.payload as WritingTemplatePayload
    }
    if (DEFAULT_TEMPLATES[session.template]) {
      return DEFAULT_TEMPLATES[session.template]
    }
    const fallback = templateOptions[0]?.value
    return fallback ? DEFAULT_TEMPLATES[fallback] : undefined
  }, [templateMap, session.template, templateOptions])

  const templateReplacements = React.useMemo(() => {
    const payload = selectedTemplatePayload
    if (!payload) return {}
    const values = replaceNewlines(payload)
    return {
      "{inst}": values.instPre || "",
      "{/inst}": values.instSuf || "",
      "{sys}": values.sysPre || "",
      "{/sys}": values.sysSuf || ""
    }
  }, [selectedTemplatePayload])

  const { modifiedPromptText, fimPromptInfo } = React.useMemo(
    () => applyFimTemplate(session.prompt, selectedTemplatePayload),
    [session.prompt, selectedTemplatePayload]
  )

  const assembledWorldInfo = React.useMemo(
    () => assembleWorldInfo(modifiedPromptText, session.worldInfo, session.tokenRatio),
    [modifiedPromptText, session.worldInfo, session.tokenRatio]
  )

  const additionalContextPrompt = React.useMemo(
    () =>
      buildAdditionalContext({
        promptText: modifiedPromptText,
        contextLength: session.contextLength,
        tokenRatio: session.tokenRatio,
        memoryTokens: session.memoryTokens,
        authorNoteTokens: session.authorNoteTokens,
        authorNoteDepth: session.authorNoteDepth,
        worldInfo: session.worldInfo,
        assembledWorldInfo,
        defaultContextOrder: DEFAULT_SESSION.memoryTokens.contextOrder
      }),
    [
      modifiedPromptText,
      session.contextLength,
      session.tokenRatio,
      session.memoryTokens,
      session.authorNoteTokens,
      session.authorNoteDepth,
      session.worldInfo,
      assembledWorldInfo
    ]
  )

  const finalPromptText = React.useMemo(
    () => replacePlaceholders(additionalContextPrompt, templateReplacements),
    [additionalContextPrompt, templateReplacements]
  )

  const promptPreviewText = React.useMemo(
    () => joinPrompt(promptPreviewChunks),
    [promptPreviewChunks]
  )

  const activeThemePayload = React.useMemo(() => {
    if (session.themeName === "Serif Light") {
      return null
    }
    if (themeMap.has(session.themeName)) {
      return themeMap.get(session.themeName) ?? null
    }
    return DEFAULT_THEMES[session.themeName] ?? null
  }, [session.themeName, themeMap])

  React.useEffect(() => {
    if (!themeStyleRef.current) return
    themeStyleRef.current.textContent = activeThemePayload?.css ?? ""
  }, [activeThemePayload])

  React.useEffect(() => {
    const voices = typeof speechSynthesis !== "undefined" ? speechSynthesis.getVoices() : []
    setTtsAvailable(voices.length > 0)
    setTtsVoices(voices)
    const handleVoices = () => {
      const next = speechSynthesis.getVoices()
      setTtsAvailable(next.length > 0)
      setTtsVoices(next)
    }
    if (typeof speechSynthesis !== "undefined") {
      speechSynthesis.addEventListener("voiceschanged", handleVoices)
      return () => speechSynthesis.removeEventListener("voiceschanged", handleVoices)
    }
    return
  }, [])

  React.useEffect(() => {
    if (!capabilitiesQuery.data) return
    if (!selectedProvider) {
      setSession((prev) => ({
        ...prev,
        provider: capabilitiesQuery.data?.default_provider || ""
      }))
      return
    }
    if (!providerCapabilities) {
      setSession((prev) => ({
        ...prev,
        provider: capabilitiesQuery.data?.default_provider || ""
      }))
      return
    }
    if (!session.model || !providerCapabilities.models.includes(session.model)) {
      const nextModel = providerCapabilities.models[0] || ""
      setSession((prev) => ({
        ...prev,
        model: nextModel
      }))
    }
  }, [capabilitiesQuery.data, providerCapabilities, selectedProvider, session.model])

  React.useEffect(() => {
    if (!templatesQuery.isSuccess || templateSeededRef.current || !online || !templatesSupported) return
    templateSeededRef.current = true
    const missing = Object.entries(DEFAULT_TEMPLATES).filter(
      ([name]) => !templateMap.has(name)
    )
    if (!missing.length) return
    Promise.all(
      missing.map(([name, payload]) =>
        createWritingTemplate({
          name,
          payload: payload as Record<string, unknown>,
          is_default: true
        }).catch(() => null)
      )
    ).finally(() => {
      queryClient.invalidateQueries({ queryKey: ["writing", "templates"] })
    })
  }, [templatesQuery.isSuccess, templateMap, online, templatesSupported, queryClient])

  React.useEffect(() => {
    if (!themesQuery.isSuccess || themeSeededRef.current || !online || !themesSupported) return
    themeSeededRef.current = true
    const missing = Object.entries(DEFAULT_THEMES).filter(
      ([name]) => !themeMap.has(name)
    )
    if (!missing.length) return
    Promise.all(
      missing.map(([name, theme]) =>
        createWritingTheme({
          name,
          class_name: theme.className ?? null,
          css: theme.css ?? null,
          order: theme.order ?? 0,
          is_default: theme.isDefault ?? false
        }).catch(() => null)
      )
    ).finally(() => {
      queryClient.invalidateQueries({ queryKey: ["writing", "themes"] })
    })
  }, [themesQuery.isSuccess, themeMap, online, themesSupported, queryClient])

  React.useEffect(() => {
    if (!sessionsQuery.isSuccess || !online || !sessionsSupported) return
    const sessions = sessionsQuery.data?.sessions ?? []
    if (sessions.length === 0 && !createSessionMutation.isPending) {
      const nextName = buildSessionName(1)
      createSessionMutation.mutate({
        name: nextName,
        payload: DEFAULT_SESSION as Record<string, unknown>,
        schema_version: DEFAULT_SESSION.schemaVersion
      })
      return
    }
    if (!selectedSessionId) {
      const fallbackId = sessions[0]?.id
      if (fallbackId) setSelectedSessionId(fallbackId)
    }
  }, [sessionsQuery.isSuccess, sessionsQuery.data, online, sessionsSupported, selectedSessionId, createSessionMutation, setSelectedSessionId])

  const sessionQuery = useQuery({
    queryKey: ["writing", "session", selectedSessionId],
    queryFn: () => (selectedSessionId ? getWritingSession(selectedSessionId) : null),
    enabled: online && sessionsSupported && !!selectedSessionId
  })

  React.useEffect(() => {
    if (!sessionQuery.data) return
    const normalized = normalizeSessionPayload(sessionQuery.data.payload)
    setSession(normalized)
    setSessionMeta(sessionQuery.data)
    setSessionNameDraft(sessionQuery.data.name)
    undoStackRef.current = []
    redoStackRef.current = []
    setPromptPreviewChunks([])
    setLastError(null)
  }, [sessionQuery.data])

  React.useEffect(() => {
    if (!sessionMeta || !online || !sessionsSupported) return
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current)
    }
    saveTimerRef.current = setTimeout(async () => {
      if (savingRef.current) {
        pendingSaveRef.current = true
        return
      }
      savingRef.current = true
      try {
        const updated = await updateSessionMutation.mutateAsync({
          sessionId: sessionMeta.id,
          payload: session,
          name: sessionNameDraft || sessionMeta.name,
          expectedVersion: sessionMeta.version
        })
        setSessionMeta(updated)
      } catch (error: any) {
        setSessionError(error?.message || "Failed to save session")
      } finally {
        savingRef.current = false
        if (pendingSaveRef.current) {
          pendingSaveRef.current = false
          queryClient.invalidateQueries({ queryKey: ["writing", "session", selectedSessionId] })
        }
      }
    }, 600)
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current)
      }
    }
  }, [session, sessionMeta, sessionNameDraft, online, updateSessionMutation, queryClient, selectedSessionId])

  React.useEffect(() => {
    if (!selectedSessionId || migrationDone || !online || !sessionsSupported) return
    if (!sessionsQuery.isSuccess) return
    if ((sessionsQuery.data?.sessions ?? []).length > 0) {
      setMigrationDone(true)
      return
    }
    const legacy = collectLegacySessions()
    if (!legacy.length) {
      setMigrationDone(true)
      return
    }
    Modal.confirm({
      title: "Import legacy sessions?",
      content:
        "We found Mikupad sessions in local storage. Import them into the Writing Playground?",
      okText: "Import",
      cancelText: "Skip",
      onOk: async () => {
        for (const entry of legacy) {
          const payload = normalizeSessionPayload(entry.payload)
          await createWritingSession({
            name: entry.name,
            payload: payload as Record<string, unknown>,
            schema_version: payload.schemaVersion
          })
        }
        queryClient.invalidateQueries({ queryKey: ["writing", "sessions"] })
        setMigrationDone(true)
      },
      onCancel: () => setMigrationDone(true)
    })
  }, [selectedSessionId, migrationDone, online, sessionsSupported, sessionsQuery.isSuccess, sessionsQuery.data, queryClient, setMigrationDone])

  React.useEffect(() => {
    const hasError = (value: string, setter: (value: string | null) => void) => {
      try {
        JSON.parse(value)
        setter(null)
      } catch (error: any) {
        setter(error?.message || "Invalid JSON")
      }
    }
    hasError(session.stoppingStrings, setStoppingStringsError)
    hasError(session.drySequenceBreakers, setDrySequenceBreakersError)
    hasError(session.bannedTokens, setBannedTokensError)
  }, [session.stoppingStrings, session.drySequenceBreakers, session.bannedTokens])

  React.useEffect(() => {
    const biasEntries = Object.values(session.logitBias.bias)
    if (!biasEntries.length) {
      setLogitBiasParam({})
      return
    }
    const param: Record<string, number> = {}
    for (const entry of biasEntries) {
      const id = entry.ids?.[0]
      if (typeof id === "number") {
        param[String(id)] = Number(clamp(entry.power, -100, 100).toFixed(1))
      }
    }
    setLogitBiasParam(param)
  }, [session.logitBias])

  React.useEffect(() => {
    if (!online || !tokenCountSupported || !tokenizerAvailable || !session.provider || !session.model) {
      setTokens(0)
      return
    }
    if (!finalPromptText) {
      setTokens(0)
      return
    }
    const abort = new AbortController()
    const timer = setTimeout(async () => {
      try {
        const response = await countWritingTokens({
          provider: session.provider,
          model: session.model,
          text: finalPromptText
        })
        setTokens(response.count)
      } catch (error: any) {
        if (error?.name !== "AbortError") {
          setTokens(0)
        }
      }
    }, 500)
    return () => {
      abort.abort()
      clearTimeout(timer)
    }
  }, [finalPromptText, session.provider, session.model, online, tokenCountSupported, tokenizerAvailable])

  React.useEffect(() => {
    if (!online || !tokenCountSupported || !tokenizerAvailable || !session.provider || !session.model) {
      setMemoryTokenCount(0)
      setAuthorNoteTokenCount(0)
      setWorldInfoTokenCount(0)
      return
    }
    const abort = new AbortController()
    const timer = setTimeout(async () => {
      try {
        const memoryText = session.memoryTokens.text
          ? [
              session.memoryTokens.prefix,
              session.memoryTokens.text,
              session.memoryTokens.suffix
            ].join("")
          : ""
        if (memoryText) {
          const response = await countWritingTokens({
            provider: session.provider,
            model: session.model,
            text: replacePlaceholders(memoryText, templateReplacements)
          })
          setMemoryTokenCount(response.count)
        } else {
          setMemoryTokenCount(0)
        }

        const authorNoteText = session.authorNoteTokens.text
          ? [
              session.authorNoteTokens.prefix,
              session.authorNoteTokens.text,
              session.authorNoteTokens.suffix
            ].join("")
          : ""
        if (authorNoteText) {
          const response = await countWritingTokens({
            provider: session.provider,
            model: session.model,
            text: replacePlaceholders(authorNoteText, templateReplacements)
          })
          setAuthorNoteTokenCount(response.count)
        } else {
          setAuthorNoteTokenCount(0)
        }

        if (assembledWorldInfo) {
          const response = await countWritingTokens({
            provider: session.provider,
            model: session.model,
            text: [session.worldInfo.prefix, assembledWorldInfo, session.worldInfo.suffix].join("")
          })
          setWorldInfoTokenCount(response.count)
        } else {
          setWorldInfoTokenCount(0)
        }
      } catch (error: any) {
        if (error?.name !== "AbortError") {
          setMemoryTokenCount(0)
          setAuthorNoteTokenCount(0)
          setWorldInfoTokenCount(0)
        }
      }
    }, 600)
    return () => {
      abort.abort()
      clearTimeout(timer)
    }
  }, [
    session.memoryTokens,
    session.authorNoteTokens,
    session.worldInfo,
    assembledWorldInfo,
    session.provider,
    session.model,
    online,
    tokenCountSupported,
    tokenizerAvailable,
    templateReplacements
  ])

  React.useEffect(() => {
    if (!promptPreviewRef.current || !promptAreaRef.current) return
    const previewElem = promptPreviewRef.current
    const textarea = promptAreaRef.current
    previewElem.textContent = promptPreviewText
    textarea.style.paddingBottom = previewElem.offsetHeight
      ? `${previewElem.offsetHeight}px`
      : "0px"
  }, [promptPreviewText])

  React.useLayoutEffect(() => {
    const textarea = promptAreaRef.current
    if (!textarea) return
    if (textarea.value === promptText) return
    const isTextSelected = textarea.selectionStart !== textarea.selectionEnd
    const oldHeight = textarea.scrollHeight
    const atBottom =
      (textarea.scrollTop || 0) + textarea.clientHeight + 1 > oldHeight
    if ((!isTextSelected && !session.preserveCursorPosition) || session.chatMode || session.chatAPI) {
      textarea.value = promptText
    } else {
      const oldLen = textarea.value.length
      textarea.setRangeText(promptText.slice(oldLen), oldLen, oldLen, "preserve")
    }
    const newHeight = textarea.scrollHeight
    if (atBottom && oldHeight !== newHeight) {
      textarea.scrollTop = newHeight - textarea.clientHeight
    }
  }, [promptText, session.preserveCursorPosition, session.chatMode, session.chatAPI])

  React.useLayoutEffect(() => {
    if (abortControllerRef.current || promptPreviewText) return
    if (!promptAreaRef.current || !promptOverlayRef.current) return
    promptAreaRef.current.scrollTop = session.scrollTop
    promptOverlayRef.current.scrollTop = session.scrollTop
  }, [session.scrollTop, promptPreviewText])

  React.useEffect(() => {
    if (!session.promptPreview || session.tokenHighlightMode === -1) return
    if (abortControllerRef.current) return
    if (previewAbortRef.current) {
      previewAbortRef.current.abort()
    }
    const abort = new AbortController()
    previewAbortRef.current = abort
    const timer = setTimeout(async () => {
      if (abort.signal.aborted) return
      setPromptPreviewChunks([])
      await predict({
        promptOverride: finalPromptText,
        chunkCount: session.prompt.length,
        onChunk: (chunk) => {
          setPromptPreviewChunks((prev) => [...prev, chunk])
          return true
        },
        abortController: abort,
        customParams: {
          max_tokens: session.promptPreviewTokens
        }
      })
    }, 500)
    abort.signal.addEventListener("abort", () => clearTimeout(timer))
    return () => abort.abort()
  }, [
    session.promptPreview,
    session.tokenHighlightMode,
    finalPromptText,
    session.prompt.length,
    session.promptPreviewTokens
  ])

  React.useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (Object.values(modals).some(Boolean)) return
      const key = `${event.altKey}:${event.ctrlKey}:${event.shiftKey}:${event.key}`
      let preventDefault = true
      switch (key) {
        case "false:false:true:Enter":
        case "false:true:false:Enter":
          void predict()
          break
        case "false:false:false:Escape":
          if (abortControllerRef.current) {
            abortControllerRef.current.abort()
          } else if (session.promptPreview && promptPreviewChunks.length) {
            setPromptPreviewChunks([])
          }
          break
        case "false:false:false:Tab":
          if (session.promptPreview && promptPreviewChunks.length) {
            setSession((prev) => ({
              ...prev,
              prompt: [...prev.prompt, ...promptPreviewChunks]
            }))
            setPromptPreviewChunks([])
          } else {
            preventDefault = false
          }
          break
        case "false:true:false:r":
        case "false:false:true:r":
          void undoAndPredict()
          break
        case "false:true:false:z":
        case "false:false:true:z":
          if (abortControllerRef.current) return
          if (!undo()) return
          break
        case "false:true:true:Z":
        case "false:true:false:y":
        case "false:false:true:y":
          if (abortControllerRef.current) return
          if (!redo()) return
          break
        case "false:true:false:e":
        case "false:false:true:e":
          ttsStop()
          break
        default:
          keyStateRef.current = event
          return
      }
      if (preventDefault) {
        event.preventDefault()
      }
    }

    const handleKeyUp = (event: KeyboardEvent) => {
      keyStateRef.current = event
    }

    window.addEventListener("keydown", handleKeyDown)
    window.addEventListener("keyup", handleKeyUp)
    return () => {
      window.removeEventListener("keydown", handleKeyDown)
      window.removeEventListener("keyup", handleKeyUp)
    }
  }, [modals, session.promptPreview, promptPreviewChunks])

  const onScroll = React.useCallback(
    (event: React.UIEvent<HTMLTextAreaElement>) => {
      const target = event.currentTarget
      if (!promptOverlayRef.current) return
      promptOverlayRef.current.scrollTop = target.scrollTop
      promptOverlayRef.current.scrollLeft = target.scrollLeft
      setSession((prev) => ({ ...prev, scrollTop: target.scrollTop }))

      if (session.showMarkdownPreview && markdownPreviewRef.current && !isSyncingScrollRef.current) {
        isSyncingScrollRef.current = true
        const preview = markdownPreviewRef.current
        if (target.scrollHeight > target.clientHeight) {
          const scrollPercentage =
            target.scrollTop / (target.scrollHeight - target.clientHeight)
          preview.scrollTop = scrollPercentage * (preview.scrollHeight - preview.clientHeight)
        }
        requestAnimationFrame(() => {
          isSyncingScrollRef.current = false
        })
      }
    },
    [session.showMarkdownPreview]
  )

  const onPromptMouseMove = React.useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      if (session.showProbsMode === -1 && session.tokenHighlightMode === -1) return
      if (!promptOverlayRef.current) return
      const overlay = promptOverlayRef.current
      overlay.style.pointerEvents = "auto"
      const element = document.elementFromPoint(event.clientX, event.clientY)
      const token = element?.closest?.("[data-promptchunk]") as HTMLElement | null
      const probsElement = element?.closest?.("[data-probs]")
      overlay.style.pointerEvents = "none"
      if (probsElement) return
      if (!token) {
        setCurrentPromptChunk(null)
        return
      }
      const rect = token.getClientRects().item(token.getClientRects().length - 1)
      const index = Number(token.dataset.promptchunk)
      const top = rect?.top ?? 0
      const left = rect ? rect.left + rect.width / 2 : 0
      setCurrentPromptChunk((prev) => {
        const isSame = prev && prev.index === index && prev.top === top && prev.left === left
        if (!isSame) {
          if (session.showProbsMode === 0) {
            setShowProbs(false)
            if (probsDelayRef.current) clearTimeout(probsDelayRef.current)
            probsDelayRef.current = setTimeout(() => setShowProbs(true), 300)
          }
          if (session.showProbsMode === 1) {
            setShowProbs(Boolean(keyStateRef.current?.ctrlKey))
          }
        }
        return isSame ? prev : { index, top, left }
      })
    },
    [session.showProbsMode, session.tokenHighlightMode]
  )

  const probs = React.useMemo(() => {
    if (!showProbs || currentPromptChunk == null) return null
    const raw = session.prompt[currentPromptChunk.index]?.completion_probabilities?.[0]?.probs
    if (!raw) return null
    return [...raw]
      .filter((prob) => prob.prob > 0)
      .sort((a, b) => b.prob - a.prob)
  }, [showProbs, currentPromptChunk, session.prompt])

  const updatePromptChunks = React.useCallback(
    (nextValue: string) => {
      if (session.promptPreview) {
        setPromptPreviewChunks([])
      }
      setSession((prev) => {
        const oldPrompt = prev.prompt
        const start: WritingPromptChunk[] = []
        const end: WritingPromptChunk[] = []
        let newValue = nextValue

        let i = 0
        for (; i < oldPrompt.length; i++) {
          const chunk = oldPrompt[i]
          if (!newValue.startsWith(chunk.content)) break
          start.push(chunk)
          newValue = newValue.slice(chunk.content.length)
        }

        for (let j = oldPrompt.length; j > i; j--) {
          const chunk = oldPrompt[j - 1]
          if (!newValue.endsWith(chunk.content)) break
          end.unshift(chunk)
          newValue = newValue.slice(0, -chunk.content.length)
        }

        const mergeUserChunks = (
          chunks: WritingPromptChunk[],
          content: string
        ) => {
          let lastChunk = chunks[chunks.length - 1]
          let mergedContent = content
          while (lastChunk && lastChunk.type === "user") {
            lastChunk.content += mergedContent
            if (chunks[chunks.length - 2]?.type === "user") {
              mergedContent = lastChunk.content
              lastChunk = chunks[chunks.length - 2]
              chunks.splice(chunks.length - 1, 1)
            } else {
              return chunks
            }
          }
          return [...chunks, { type: "user", content: mergedContent }]
        }

        let newPrompt = [...start]
        if (newValue) {
          newPrompt = mergeUserChunks(newPrompt, newValue)
        }
        if (end.length && end[0].type === "user") {
          newPrompt = mergeUserChunks(newPrompt, end.shift()?.content ?? "")
        }
        newPrompt.push(...end)

        const chunkDifference = oldPrompt.length - newPrompt.length
        undoStackRef.current = undoStackRef.current
          .filter((pos) => pos > start.length && pos < newPrompt.length)
          .map((pos) => (pos >= start.length ? pos - chunkDifference : pos))
        if (chunkDifference < 0 && !end.length) {
          redoStackRef.current = []
        }

        return {
          ...prev,
          prompt: newPrompt
        }
      })
    },
    [session.promptPreview]
  )

  const onPromptInput = React.useCallback(
    (event: React.FormEvent<HTMLTextAreaElement>) => {
      updatePromptChunks(event.currentTarget.value)
    },
    [updatePromptChunks]
  )

  const onPromptSelect = React.useCallback(() => {
    const textarea = promptAreaRef.current
    if (!textarea) return
    const selection = textarea.value.substring(textarea.selectionStart, textarea.selectionEnd)
    setSelectedText(selection)
    setInstructContext(finalPromptText)
  }, [finalPromptText])

  const insertTemplate = React.useCallback(
    (mode: "sys" | "inst") => {
      const template = selectedTemplatePayload
      if (!template || !promptAreaRef.current) return
      const { sysPre, sysSuf, instPre, instSuf } = replaceNewlines(template)
      const prefix = mode === "sys" ? sysPre ?? "" : instPre ?? ""
      const suffix = mode === "sys" ? sysSuf ?? "" : instSuf ?? ""
      if (!prefix && !suffix) return

      const elem = promptAreaRef.current
      const startPos = elem.selectionStart
      const endPos = elem.selectionEnd
      const textBefore = elem.value.substring(0, startPos)
      const textAfter =
        mode !== "sys" && endPos !== elem.value.length ? "{predict}" : ""
      const selected = elem.value.substring(startPos, endPos)
      const finalText = `${textBefore}${prefix}${selected}${suffix}${textAfter}${elem.value.substring(endPos)}`
      const scrollTop = elem.scrollTop
      elem.value = finalText
      const cursorPos =
        selected.length === 0
          ? startPos + prefix.length
          : startPos + prefix.length + selected.length + suffix.length
      elem.focus()
      elem.setSelectionRange(cursorPos, cursorPos)
      updatePromptChunks(finalText)
      elem.scrollTop = scrollTop
    },
    [selectedTemplatePayload, updatePromptChunks]
  )

  const computeStopParam = React.useCallback(() => {
    if (session.useBasicStoppingMode) {
      if (session.basicStoppingModeType === "new_line") {
        return ["\n"]
      }
      if (session.basicStoppingModeType === "fill_suffix" && fimPromptInfo) {
        const suffix = fimPromptInfo.fimRightChunks?.[0]?.content
        if (suffix) {
          return [suffix.trim().substring(0, 2)]
        }
      }
      return []
    }
    try {
      const parsed = JSON.parse(session.stoppingStrings)
      return Array.isArray(parsed) ? parsed : []
    } catch {
      return []
    }
  }, [session.useBasicStoppingMode, session.basicStoppingModeType, session.stoppingStrings, fimPromptInfo])

  const buildRequestBody = React.useCallback(
    (prompt: string, includeLogprobs: boolean, customParams?: Record<string, any>) => {
      const useChat = session.chatAPI || session.chatMode
      const messages = useChat
        ? convertChatToMessages(prompt, selectedTemplatePayload)
        : [{ role: "user", content: prompt }]
      const body: Record<string, any> = {
        model: session.model,
        messages,
        stream: session.tokenStreaming,
        ...(session.provider ? { api_provider: session.provider } : {})
      }

      const extraBody: Record<string, any> = {}
      const enabled = new Set(session.enabledSamplers)

      if (enabled.has("temperature") && supportedFields.has("temperature")) {
        body.temperature = session.temperature
      }
      if (enabled.has("top_p") && supportedFields.has("top_p")) {
        body.top_p = session.topP
      }
      if (enabled.has("top_k")) {
        if (supportedFields.has("top_k")) body.top_k = session.topK
        else extraBody.top_k = session.topK
      }
      if (enabled.has("min_p")) {
        if (supportedFields.has("min_p")) body.min_p = session.minP
        else extraBody.min_p = session.minP
      }
      if (enabled.has("pres_pen") && supportedFields.has("presence_penalty")) {
        body.presence_penalty = session.presencePenalty
      }
      if (enabled.has("freq_pen") && supportedFields.has("frequency_penalty")) {
        body.frequency_penalty = session.frequencyPenalty
      }
      if (supportedFields.has("seed") && session.seed !== -1) {
        body.seed = session.seed
      }
      if (session.maxPredictTokens > 0) {
        body.max_tokens = session.maxPredictTokens
      }
      if (includeLogprobs && supportedFields.has("logprobs")) {
        body.logprobs = true
        body.top_logprobs = 10
      }
      if (Object.keys(logitBiasParam).length > 0 && supportedFields.has("logit_bias")) {
        body.logit_bias = logitBiasParam
      }
      const stopParam = computeStopParam()
      if (stopParam.length && supportedFields.has("stop")) {
        body.stop = stopParam
      }

      if (enabled.has("rep_pen")) {
        extraBody.repeat_penalty = session.repeatPenalty
        extraBody.repeat_last_n = session.repeatLastN
      }
      if (enabled.has("dynatemp")) {
        extraBody.dynatemp_range = session.dynaTempRange
        extraBody.dynatemp_exponent = session.dynaTempExp
      }
      if (enabled.has("typical_p")) {
        extraBody.typical_p = session.typicalP
      }
      if (enabled.has("tfs_z")) {
        extraBody.tfs_z = session.tfsZ
      }
      if (enabled.has("mirostat")) {
        extraBody.mirostat = session.mirostat
        extraBody.mirostat_tau = session.mirostatTau
        extraBody.mirostat_eta = session.mirostatEta
      }
      if (enabled.has("xtc")) {
        extraBody.xtc_threshold = session.xtcThreshold
        extraBody.xtc_probability = session.xtcProbability
      }
      if (enabled.has("dry")) {
        extraBody.dry_multiplier = session.dryMultiplier
        extraBody.dry_base = session.dryBase
        extraBody.dry_allowed_length = session.dryAllowedLength
        extraBody.dry_penalty_last_n = session.dryPenaltyRange
        try {
          extraBody.dry_sequence_breakers = JSON.parse(session.drySequenceBreakers)
        } catch {
          extraBody.dry_sequence_breakers = session.drySequenceBreakers
        }
      }
      if (enabled.has("ban_tokens")) {
        try {
          extraBody.banned_tokens = JSON.parse(session.bannedTokens)
        } catch {
          extraBody.banned_tokens = session.bannedTokens
        }
      }
      if (session.grammar) {
        extraBody.grammar = session.grammar
      }
      if (session.penalizeNl) {
        extraBody.penalize_nl = session.penalizeNl
      }
      if (session.ignoreEos) {
        extraBody.ignore_eos = session.ignoreEos
      }
      if (Object.keys(extraBody).length) {
        body.extra_body = extraBody
      }

      return { ...body, ...(customParams ?? {}) }
    },
    [
      session,
      selectedTemplatePayload,
      supportedFields,
      logitBiasParam,
      computeStopParam
    ]
  )

  const streamCompletion = React.useCallback(async function* (
    body: Record<string, any>,
    signal: AbortSignal
  ): AsyncGenerator<WritingPromptChunk> {
    if (body.stream) {
      for await (const line of bgStream({
        path: "/api/v1/chat/completions",
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
        abortSignal: signal
      })) {
        let parsed: any
        try {
          parsed = JSON.parse(line)
        } catch {
          continue
        }
        const choice = parsed?.choices?.[0]
        if (!choice) continue
        const logprobContent = choice.logprobs?.content
        if (Array.isArray(logprobContent) && logprobContent.length) {
          for (const tokenInfo of logprobContent) {
            const token = tokenInfo.token
            if (!token) continue
            const topLogprobs = tokenInfo.top_logprobs ?? []
            const probs = Array.isArray(topLogprobs)
              ? topLogprobs.map((entry: any) => ({
                  tok_str: entry.token,
                  prob: Math.exp(entry.logprob)
                }))
              : []
            const prob = probs.find((p) => p.tok_str === token)?.prob
            yield {
              type: "assistant",
              content: token,
              ...(probs.length
                ? {
                    prob: prob ?? -1,
                    completion_probabilities: [
                      {
                        content: token,
                        probs
                      }
                    ]
                  }
                : {})
            }
          }
          continue
        }
        const delta = choice.delta?.content ?? choice.text ?? choice.message?.content
        if (!delta) continue
        const topLogprobs =
          choice.logprobs?.content?.[0]?.top_logprobs ??
          choice.logprobs?.top_logprobs?.[0]
        const probs = Array.isArray(topLogprobs)
          ? topLogprobs.map((entry: any) => ({
              tok_str: entry.token,
              prob: Math.exp(entry.logprob)
            }))
          : topLogprobs
            ? Object.entries(topLogprobs).map(([tok, logprob]) => ({
                tok_str: tok,
                prob: Math.exp(Number(logprob))
              }))
            : []
        const prob = probs.find((p) => p.tok_str === delta)?.prob
        yield {
          type: "assistant",
          content: delta,
          ...(probs.length
            ? {
                prob: prob ?? -1,
                completion_probabilities: [
                  {
                    content: delta,
                    probs
                  }
                ]
              }
            : {})
        }
      }
      return
    }

    const payload = await bgRequest<Record<string, any>>({
      path: "/api/v1/chat/completions",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      abortSignal: signal
    })
    const choice = payload?.choices?.[0]
    if (!choice) return
    const logprobContent = choice.logprobs?.content
    if (Array.isArray(logprobContent) && logprobContent.length) {
      for (const tokenInfo of logprobContent) {
        const token = tokenInfo.token
        if (!token) continue
        const topLogprobs = tokenInfo.top_logprobs ?? []
        const probs = Array.isArray(topLogprobs)
          ? topLogprobs.map((entry: any) => ({
              tok_str: entry.token,
              prob: Math.exp(entry.logprob)
            }))
          : []
        const prob = probs.find((p) => p.tok_str === token)?.prob
        yield {
          type: "assistant",
          content: token,
          ...(probs.length
            ? {
                prob: prob ?? -1,
                completion_probabilities: [
                  {
                    content: token,
                    probs
                  }
                ]
              }
            : {})
        }
      }
      return
    }
    const content = choice.message?.content ?? choice.text
    if (content) {
      yield { type: "assistant", content }
    }
  }, [])

  const predict = React.useCallback(async (options?: {
    promptOverride?: string
    chunkCount?: number
    onChunk?: (chunk: WritingPromptChunk) => boolean
    abortController?: AbortController
    invalidateUndo?: boolean
    customParams?: Record<string, any>
  }) => {
    if (!online) return false
    const promptOverride = options?.promptOverride ?? finalPromptText
    const chunkCount = options?.chunkCount ?? session.prompt.length
    const onChunk = options?.onChunk
    const invalidateUndo = options?.invalidateUndo ?? false

    if (!options?.abortController && abortControllerRef.current) {
      abortControllerRef.current.abort()
      await new Promise((resolve) => setTimeout(resolve, 250))
    }

    if (!onChunk && !options?.abortController && fimPromptInfo) {
      const didFill = await fillPredict()
      if (didFill) return true
    }

    const abortController = options?.abortController ?? new AbortController()
    if (!options?.abortController) {
      abortControllerRef.current = abortController
    }
    setLastError(null)
    if (session.promptPreview) {
      setPromptPreviewChunks([])
    }

    if (!onChunk) {
      undoStackRef.current.push(chunkCount)
      if (invalidateUndo) {
        undoStackRef.current = []
      }
      redoStackRef.current = []
    }

    const includeLogprobs = session.tokenHighlightMode !== -1 || session.showProbsMode !== -1
    const body = buildRequestBody(promptOverride, includeLogprobs, options?.customParams)
    body.stream = session.tokenStreaming

    let predictCount = 0
    let startTime = 0

    try {
      for await (const chunk of streamCompletion(body, abortController.signal)) {
        if (abortController.signal.aborted) break
        if (!chunk.content) continue
        if (!startTime) {
          startTime = performance.now()
        } else if (predictCount === 1) {
          startTime -= performance.now() - startTime
        }
        const elapsed = (performance.now() - startTime) / 1000
        if (elapsed > 0) {
          setTokensPerSec((predictCount + 1) / elapsed)
        }
        if (onChunk) {
          const shouldContinue = onChunk(chunk)
          if (!shouldContinue) break
        } else {
          setSession((prev) => ({
            ...prev,
            prompt: [...prev.prompt, chunk]
          }))
          setTokens((prev) => prev + 1)
        }
        predictCount += 1
        ttsAddChunk(chunk.content)
      }
    } catch (error: any) {
      if (error?.name !== "AbortError") {
        setLastError(error?.message || "Prediction failed")
      }
      return false
    } finally {
      if (!options?.abortController) {
        abortControllerRef.current = null
      }
      setTokensPerSec(0)
      if (!onChunk && predictCount === 0) {
        undoStackRef.current.pop()
      }
      if (session.chatMode || session.chatAPI) {
        const instPre = selectedTemplatePayload?.instPre?.replace(/\\n/g, "\n")
        if (instPre) {
          setSession((prev) => ({
            ...prev,
            prompt: [...prev.prompt, { type: "user", content: instPre }]
          }))
        }
      }
    }
    return true
  }, [
    online,
    finalPromptText,
    session.prompt.length,
    session.promptPreview,
    session.tokenHighlightMode,
    session.showProbsMode,
    session.tokenStreaming,
    session.chatMode,
    session.chatAPI,
    selectedTemplatePayload,
    buildRequestBody,
    streamCompletion
  ])

  const fillPredict = React.useCallback(async () => {
    if (!fimPromptInfo) return false
    const { fimLeftChunks, fimRightChunks } = fimPromptInfo
    await predict({
      promptOverride: finalPromptText,
      chunkCount: fimLeftChunks.length,
      onChunk: (chunk) => {
        fimLeftChunks.push(chunk)
        setSession((prev) => ({
          ...prev,
          prompt: [...fimLeftChunks, ...fimRightChunks]
        }))
        return true
      },
      invalidateUndo: true
    })
    return true
  }, [fimPromptInfo, predict, finalPromptText])

  const undo = React.useCallback(() => {
    if (!undoStackRef.current.length) return false
    const target = undoStackRef.current.pop() ?? 0
    redoStackRef.current.push(session.prompt.slice(target))
    setSession((prev) => ({
      ...prev,
      prompt: prev.prompt.slice(0, target)
    }))
    return true
  }, [session.prompt])

  const redo = React.useCallback(() => {
    if (!redoStackRef.current.length) return false
    const chunk = redoStackRef.current.pop()
    if (!chunk) return false
    undoStackRef.current.push(session.prompt.length)
    setSession((prev) => ({
      ...prev,
      prompt: [...prev.prompt, ...chunk]
    }))
    return true
  }, [session.prompt.length])

  const undoAndPredict = React.useCallback(async () => {
    const didUndo = undo()
    if (didUndo) {
      await predict()
    }
  }, [undo, predict])

  const switchCompletion = React.useCallback(
    async (index: number, tok: { tok_str: string; prob: number }) => {
      const remaining = session.prompt.slice(index)
      const instPre = selectedTemplatePayload?.instPre?.replace(/\\n/g, "\n")
      const lastChunk = session.prompt.at(-1)
      const hasRealUserTextAfter = remaining.some(
        (chunk) =>
          chunk.type === "user" &&
          !(chunk === lastChunk && (chunk.content === instPre || chunk.content.length <= 50))
      )
      if (hasRealUserTextAfter) return
      setSession((prev) => ({
        ...prev,
        prompt: [
          ...prev.prompt.slice(0, index),
          { ...prev.prompt[index], content: tok.tok_str, prob: tok.prob }
        ]
      }))
      await predict({
        promptOverride: finalPromptText,
        chunkCount: index,
        customParams: { stream: session.tokenStreaming }
      })
    },
    [session.prompt, selectedTemplatePayload, predict, finalPromptText, session.tokenStreaming]
  )

  const ttsProcessQueue = React.useCallback(() => {
    if (!session.ttsEnabled || !ttsVoices.length) return
    if (!ttsQueueRef.current.length) return
    if (ttsPausedRef.current) return
    const text = ttsQueueRef.current.shift()
    if (!text) return
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.voice = ttsVoices[session.ttsVoiceId]
    utterance.pitch = session.ttsPitch
    utterance.rate = session.ttsRate
    utterance.volume = session.ttsVolume
    utterance.addEventListener("end", () => ttsProcessQueue())
    speechSynthesis.speak(utterance)
  }, [session, ttsVoices])

  const ttsAddChunk = React.useCallback(
    (text: string) => {
      if (!session.ttsEnabled) return
      ttsNewTextRef.current += text
      const last = text.slice(-1)
      if (
        text.slice(-3) === "..." ||
        last === "." ||
        last === "!" ||
        last === "?" ||
        last === "\n"
      ) {
        if (/\w/.test(ttsNewTextRef.current)) {
          if (!ttsPausedRef.current) {
            ttsQueueRef.current.push(ttsNewTextRef.current)
          }
          ttsNewTextRef.current = ""
          ttsLastChunkRef.current = ""
          if (!speechSynthesis.speaking && !speechSynthesis.pending) {
            ttsProcessQueue()
          }
        }
      } else {
        ttsLastChunkRef.current = text
      }
    },
    [session.ttsEnabled, ttsProcessQueue]
  )

  const ttsStop = React.useCallback(() => {
    if (!session.ttsEnabled) return
    ttsPausedRef.current = true
    ttsQueueRef.current = []
    ttsNewTextRef.current = ""
    speechSynthesis.cancel()
  }, [session.ttsEnabled])

  const ttsPushUserInput = React.useCallback(() => {
    if (!session.ttsEnabled || !session.ttsSpeakInputs) return
    const lastChunk = session.prompt[session.prompt.length - 1]
    if (!lastChunk || lastChunk.type !== "user") return
    let text = lastChunk.content
    const words = text.split(/(?<=[ \n])/)
    if (words.length > session.ttsMaxUserInput) {
      text = words.slice(-session.ttsMaxUserInput).join("")
    }
    const strings = text.split(/(?<=[!\.\?\n])/)
    let textToRead = ""
    for (const part of strings) {
      if (/\w/.test(part)) {
        textToRead += part
      }
    }
    if (textToRead && !ttsPausedRef.current) {
      ttsQueueRef.current.push(textToRead)
      if (!speechSynthesis.speaking && !speechSynthesis.pending) {
        ttsProcessQueue()
      }
    }
  }, [session, ttsProcessQueue])

  const handleCreateSession = React.useCallback(() => {
    if (!sessionsSupported) {
      message.error("Writing sessions not supported by this server")
      return
    }
    const nextIndex = (sessionsQuery.data?.sessions?.length ?? 0) + 1
    const name = buildSessionName(nextIndex)
    createSessionMutation.mutate({
      name,
      payload: DEFAULT_SESSION as Record<string, unknown>,
      schema_version: DEFAULT_SESSION.schemaVersion
    })
  }, [createSessionMutation, sessionsQuery.data, sessionsSupported])

  const handleCloneSession = React.useCallback(async () => {
    if (!sessionsSupported) {
      message.error("Writing sessions not supported by this server")
      return
    }
    if (!sessionMeta) return
    try {
      const cloned = await cloneWritingSession(sessionMeta.id, {
        name: `Cloned ${sessionMeta.name}`
      })
      queryClient.invalidateQueries({ queryKey: ["writing", "sessions"] })
      setSelectedSessionId(cloned.id)
    } catch (error: any) {
      message.error(error?.message || "Failed to clone session")
    }
  }, [sessionMeta, queryClient, setSelectedSessionId, sessionsSupported])

  const handleDeleteSession = React.useCallback(async () => {
    if (!sessionsSupported) {
      message.error("Writing sessions not supported by this server")
      return
    }
    if (!sessionMeta) return
    Modal.confirm({
      title: "Delete session?",
      content: "This action cannot be undone.",
      okText: "Delete",
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await deleteWritingSession(sessionMeta.id, sessionMeta.version)
          queryClient.invalidateQueries({ queryKey: ["writing", "sessions"] })
          setSelectedSessionId(null)
        } catch (error: any) {
          message.error(error?.message || "Failed to delete session")
        }
      }
    })
  }, [sessionMeta, queryClient, setSelectedSessionId, sessionsSupported])

  const handleRenameSession = React.useCallback(async () => {
    if (!sessionsSupported) {
      message.error("Writing sessions not supported by this server")
      return
    }
    if (!sessionMeta) return
    try {
      const updated = await updateWritingSession(
        sessionMeta.id,
        { name: sessionNameDraft || sessionMeta.name },
        sessionMeta.version
      )
      setSessionMeta(updated)
      queryClient.invalidateQueries({ queryKey: ["writing", "sessions"] })
      setModals((prev) => ({ ...prev, renameSession: false }))
    } catch (error: any) {
      message.error(error?.message || "Failed to rename session")
    }
  }, [sessionMeta, sessionNameDraft, queryClient, sessionsSupported])

  const handleExportSession = React.useCallback(() => {
    const payload: Record<string, string> = {}
    Object.entries(session).forEach(([key, value]) => {
      payload[key] = JSON.stringify(value)
    })
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = `${sessionMeta?.name || "writing-session"}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }, [session, sessionMeta?.name])

  const handleImportSession = React.useCallback(() => {
    if (!sessionsSupported) {
      message.error("Writing sessions not supported by this server")
      return
    }
    const input = document.createElement("input")
    input.type = "file"
    input.accept = ".json"
    input.multiple = true
    input.onchange = async () => {
      const files = Array.from(input.files ?? [])
      if (!files.length) return
      for (const file of files) {
        const text = await file.text()
        try {
          const data = JSON.parse(text)
          const payload = normalizeSessionPayload(data)
          await createWritingSession({
            name: payload?.template ? `Imported ${payload.template}` : `Imported ${file.name}`,
            payload: payload as Record<string, unknown>,
            schema_version: payload.schemaVersion
          })
        } catch (error: any) {
          message.error(error?.message || "Failed to import session")
        }
      }
      queryClient.invalidateQueries({ queryKey: ["writing", "sessions"] })
    }
    input.click()
  }, [queryClient, sessionsSupported])

  const handleAddLogitBias = React.useCallback(
    async (biasPower: number, biasString: string) => {
      if (!biasString) return
      if (!tokenizeSupported) {
        message.error("Tokenization not supported by this server")
        return
      }
      if (!tokenizerAvailable || !session.provider || !session.model) {
        message.error("Tokenizer unavailable for this model")
        return
      }
      const isTokenIds = biasString.match(/^(?<!\\)\/(\s*\d+\s*,?\s*)+(?<!\\)\/$/)
      let tokenIds: number[] = []
      let tokenStrings: string[] = []
      if (isTokenIds) {
        tokenIds = biasString
          .replaceAll("/", "")
          .split(",")
          .map((entry) => Number(entry.trim()))
        tokenStrings = []
      } else {
        const tokens = await tokenizeWriting({
          provider: session.provider,
          model: session.model,
          text: `!==${biasString}`
        })
        const prefixTokens = await tokenizeWriting({
          provider: session.provider,
          model: session.model,
          text: "!=="
        })
        tokenIds = tokens.ids.slice(prefixTokens.ids.length)
        tokenStrings = (tokens.strings ?? []).slice(prefixTokens.ids.length)
      }
      setSession((prev) => {
        const bias = { ...prev.logitBias.bias }
        bias[biasString] = {
          ids: tokenIds,
          strings: tokenStrings,
          power: biasPower
        }
        return {
          ...prev,
          logitBias: {
            ...prev.logitBias,
            bias
          }
        }
      })
    },
    [session.provider, session.model, tokenizeSupported, tokenizerAvailable]
  )

  const sessionOptions = (sessionsQuery.data?.sessions ?? []).map((item) => ({
    label: item.name,
    value: item.id
  }))

  const themeClassName = activeThemePayload?.class_name ?? activeThemePayload?.className
  const tokenDisplay = tokenCountSupported ? tokens : "n/a"

  return (
    <div
      className={clsx(
        "writing-playground relative space-y-6",
        themeClassName,
        session.attachSidebar ? "lg:flex lg:gap-6" : ""
      )}
      style={{
        backgroundColor: "var(--writing-bg, transparent)",
        color: "var(--writing-fg, inherit)",
        fontFamily: "var(--writing-font, inherit)"
      }}>
      <style ref={themeStyleRef} />

      <div className={clsx("space-y-3", session.attachSidebar ? "lg:flex-1" : "")}
        onMouseMove={onPromptMouseMove}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <Title level={3} className="!mb-0">
              Writing Playground
            </Title>
            <Text type="secondary">
              Full-fidelity writing workspace backed by your tldw server.
            </Text>
          </div>
          <Space>
            <Button
              icon={<Settings className="h-4 w-4" />}
              onClick={() => setModals((prev) => ({ ...prev, preferences: true }))}>
              Preferences
            </Button>
            <Button
              icon={<Search className="h-4 w-4" />}
              onClick={() => setModals((prev) => ({ ...prev, searchReplace: true }))}>
              Search
            </Button>
          </Space>
        </div>

        {sessionError && (
          <Alert type="warning" message={sessionError} showIcon />
        )}
        {capabilitiesQuery.isSuccess && !sessionsSupported && (
          <Alert
            type="warning"
            message="Writing sessions are not supported by this server. Persistence is disabled."
            showIcon
          />
        )}

        <div
          className={clsx(
            "relative rounded-xl border border-border bg-surface",
            session.showMarkdownPreview ? "grid grid-cols-1 lg:grid-cols-2" : ""
          )}
          style={{
            backgroundColor: "var(--writing-panel, var(--surface))"
          }}>
          <div className="relative group">
            <textarea
              ref={promptAreaRef}
              id="writing-prompt"
              className="writing-editor h-[60vh] w-full resize-none bg-transparent px-6 py-6 text-base leading-relaxed text-text outline-none"
              style={{
                fontSize: `${16 * session.fontSizeMultiplier}px`,
                color: "var(--writing-fg, inherit)",
                fontFamily: "var(--writing-font, inherit)"
              }}
              spellCheck={session.spellCheck}
              onInput={onPromptInput}
              onScroll={onScroll}
              onSelect={onPromptSelect}
              defaultValue={promptText}
              readOnly={Boolean(abortControllerRef.current)}
            />
            <div
              ref={promptOverlayRef}
              className="writing-overlay absolute inset-0 pointer-events-none overflow-hidden whitespace-pre-wrap text-transparent"
              style={{
                fontSize: `${16 * session.fontSizeMultiplier}px`,
                padding: "1.5rem",
                fontFamily: "var(--writing-font, inherit)"
              }}>
              {session.tokenHighlightMode !== -1 &&
                session.prompt.map((chunk, index) => {
                  const chunkProb = chunk.prob ?? 1
                  const completionProbs =
                    chunk.completion_probabilities?.[0]?.probs ?? []
                  let bgColor = ""
                  if (session.tokenColorMode === 1 && chunkProb < 1) {
                    const ratio = clamp(chunkProb, 0, 1)
                    bgColor = ratio <= 0.5
                      ? `color-mix(in srgb, red ${100 - ratio * 200}%, yellow ${ratio * 200}%)`
                      : `color-mix(in srgb, yellow ${100 - (ratio - 0.5) * 200}%, var(--writing-accent, #14b8a6) ${(ratio - 0.5) * 200}%)`
                  }
                  if (session.tokenColorMode === 2 && completionProbs.length) {
                    const probs = completionProbs.map((entry) => entry.prob)
                    const min = Math.min(...probs)
                    const max = Math.max(...probs)
                    const ratio = max > min ? (chunkProb - min) / (max - min) : 0
                    bgColor = ratio <= 0.5
                      ? `color-mix(in srgb, red ${100 - ratio * 200}%, yellow ${ratio * 200}%)`
                      : `color-mix(in srgb, yellow ${100 - (ratio - 0.5) * 200}%, var(--writing-accent, #14b8a6) ${(ratio - 0.5) * 200}%)`
                  }
                  const isCurrent = currentPromptChunk?.index === index
                  const showHighlight =
                    (session.tokenHighlightMode === 0 && chunk.type === "assistant") ||
                    (session.tokenHighlightMode === 1 && isCurrent && chunk.type === "assistant")

                  return (
                    <span
                      key={`chunk-${index}`}
                      data-promptchunk={index}
                      className={clsx(
                        "inline-block",
                        chunk.type === "assistant" && "transition-opacity",
                        session.tokenHighlightMode === 0 && chunk.type === "assistant" && "opacity-0 group-hover:opacity-100",
                        session.tokenHighlightMode === 1 && chunk.type === "assistant" && !isCurrent && "opacity-0"
                      )}
                      style={{
                        backgroundColor: showHighlight ? bgColor || "color-mix(in srgb, var(--writing-accent, #14b8a6) 15%, transparent)" : "transparent",
                        outline: isCurrent ? "1px solid var(--writing-border, #d1d5db)" : undefined,
                        borderRadius: isCurrent ? "4px" : undefined
                      }}>
                      {chunk.content === "\n" ? " \n" : chunk.content}
                    </span>
                  )
                })}
              {session.promptPreview && promptPreviewChunks.length > 0 && (
                <>
                  <span ref={promptPreviewRef} className="text-text/40">
                    {promptPreviewText}
                  </span>
                  <span className="ml-2 rounded border border-border px-1.5 text-xs text-text/60">
                    Tab
                  </span>
                </>
              )}
            </div>
            {probs && currentPromptChunk && (
              <div
                data-probs
                className="fixed z-50 flex max-w-[90vw] translate-x-[-50%] translate-y-[-100%] gap-1 overflow-x-auto rounded-md border border-border bg-surface2 p-2 shadow"
                style={{
                  top: currentPromptChunk.top,
                  left: currentPromptChunk.left
                }}>
                {probs.map((prob, index) => (
                  <button
                    key={`prob-${index}`}
                    type="button"
                    className="rounded px-2 py-1 text-left text-xs text-text hover:bg-surface"
                    onClick={() => switchCompletion(currentPromptChunk.index, prob)}>
                    <div className="font-mono">{prob.tok_str.replace(/ /g, "<sp>")}</div>
                    <div className="text-[10px] text-text-muted">
                      {(prob.prob * 100).toFixed(2)}%
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
          {session.showMarkdownPreview && (
            <div
              ref={markdownPreviewRef}
              className="max-h-[60vh] overflow-y-auto border-l border-border bg-surface2/40 px-6 py-6">
              <MarkdownPreview content={promptText} size="sm" />
            </div>
          )}
        </div>

        <Card size="small" className="border-border">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="primary"
              icon={<Play className="h-4 w-4" />}
              onClick={() => {
                ttsPushUserInput()
                void predict()
              }}
              disabled={Boolean(abortControllerRef.current) || Boolean(stoppingStringsError || drySequenceBreakersError || bannedTokensError)}>
              Predict
            </Button>
            <Button
              icon={<Square className="h-4 w-4" />}
              onClick={() => abortControllerRef.current?.abort()}
              disabled={!abortControllerRef.current}>
              Cancel
            </Button>
            <Button
              icon={<RefreshCcw className="h-4 w-4" />}
              onClick={() => void undoAndPredict()}
              disabled={!undoStackRef.current.length}>
              Regenerate
            </Button>
            <Button
              icon={<Undo2 className="h-4 w-4" />}
              onClick={() => undo()}
              disabled={!undoStackRef.current.length}>
              Undo
            </Button>
            <Button
              icon={<Redo2 className="h-4 w-4" />}
              onClick={() => redo()}
              disabled={!redoStackRef.current.length}>
              Redo
            </Button>
            <Divider type="vertical" />
            <div className="text-xs text-text-muted">
              Tokens: {tokenDisplay}
              {tokensPerSec ? ` (${tokensPerSec.toFixed(2)} t/s)` : ""}
            </div>
            {lastError && (
              <div className="text-xs text-red-500">{lastError}</div>
            )}
          </div>
        </Card>
      </div>

      <div
        className={clsx(
          "space-y-4",
          session.attachSidebar ? "lg:w-[360px]" : ""
        )}
      >
        <Card size="small" className="border-border">
          <Space direction="vertical" className="w-full" size={8}>
            <div className="flex items-center justify-between gap-2">
              <Text strong>Theme</Text>
              <Button
                size="small"
                icon={<Palette className="h-4 w-4" />}
                onClick={() => setModals((prev) => ({ ...prev, themes: true }))}
                disabled={!themesSupported}>
                Manage
              </Button>
            </div>
            <Select
              value={session.themeName}
              options={themeOptions}
              onChange={(value) =>
                setSession((prev) => ({ ...prev, themeName: value }))
              }
            />
          </Space>
        </Card>

        <Card size="small" className="border-border">
          <Space direction="vertical" className="w-full" size={8}>
            <div className="flex items-center justify-between gap-2">
              <Text strong>Sessions</Text>
              <Button
                size="small"
                icon={<Plus className="h-4 w-4" />}
                onClick={handleCreateSession}
                disabled={!sessionsSupported}>
                New
              </Button>
            </div>
            <Select
              value={selectedSessionId ?? undefined}
              options={sessionOptions}
              onChange={(value) => setSelectedSessionId(value)}
              placeholder="Select session"
              disabled={!sessionsSupported}
            />
            <div className="flex flex-wrap gap-2">
              <Button
                size="small"
                icon={<Settings className="h-4 w-4" />}
                onClick={() => setModals((prev) => ({ ...prev, renameSession: true }))}
                disabled={!sessionMeta || !sessionsSupported}>
                Rename
              </Button>
              <Button
                size="small"
                onClick={() => void handleCloneSession()}
                disabled={!sessionMeta || !sessionsSupported}>
                Clone
              </Button>
              <Button
                size="small"
                icon={<FileDown className="h-4 w-4" />}
                onClick={handleExportSession}
                disabled={!sessionMeta || !sessionsSupported}>
                Export
              </Button>
              <Button
                size="small"
                icon={<FileUp className="h-4 w-4" />}
                onClick={handleImportSession}
                disabled={!sessionsSupported}>
                Import
              </Button>
              <Button
                size="small"
                danger
                icon={<Trash2 className="h-4 w-4" />}
                onClick={() => void handleDeleteSession()}
                disabled={!sessionMeta || !sessionsSupported}>
                Delete
              </Button>
            </div>
          </Space>
        </Card>

        <Collapse
          ghost
          items={[
            {
              key: "parameters",
              label: "Parameters",
              children: (
                <Space direction="vertical" size={10} className="w-full">
                  <div>
                    <Text strong>Provider</Text>
                    <Select
                      value={session.provider}
                      options={providerOptions}
                      onChange={(value) =>
                        setSession((prev) => ({ ...prev, provider: value }))
                      }
                      placeholder="Provider"
                    />
                  </div>
                  <div>
                    <Text strong>Model</Text>
                    <Select
                      value={session.model}
                      options={modelOptions}
                      onChange={(value) =>
                        setSession((prev) => ({ ...prev, model: value }))
                      }
                      placeholder="Model"
                    />
                  </div>
                  {!tokenizeSupported && (
                    <Alert type="info" message="Tokenization not supported by this server." showIcon />
                  )}
                  {tokenizeSupported && !tokenizerAvailable && (
                    <Alert type="info" message="Tokenizer unavailable for this model." showIcon />
                  )}
                  {!tokenCountSupported && (
                    <Alert type="info" message="Token counting not supported by this server." showIcon />
                  )}
                  <div>
                    <Text strong>Instruct Template</Text>
                    <div className="flex gap-2">
                      <Select
                        className="flex-1"
                        value={session.template}
                        options={templateOptions}
                        onChange={(value) =>
                          setSession((prev) => ({ ...prev, template: value }))
                        }
                      />
                      <Button
                        icon={<Settings className="h-4 w-4" />}
                        onClick={() => setModals((prev) => ({ ...prev, templates: true }))}
                        disabled={!templatesSupported}
                      />
                      <Tooltip title="Insert system template">
                        <Button onClick={() => insertTemplate("sys")}>SYS</Button>
                      </Tooltip>
                      <Tooltip title="Insert instruct template">
                        <Button onClick={() => insertTemplate("inst")}>INST</Button>
                      </Tooltip>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Text strong>Seed</Text>
                      <InputNumber
                        className="w-full"
                        value={session.seed}
                        onChange={(value) =>
                          setSession((prev) => ({ ...prev, seed: value ?? -1 }))
                        }
                      />
                    </div>
                    <div>
                      <Text strong>Context length</Text>
                      <InputNumber
                        className="w-full"
                        value={session.contextLength}
                        onChange={(value) =>
                          setSession((prev) => ({ ...prev, contextLength: value ?? prev.contextLength }))
                        }
                      />
                    </div>
                  </div>
                  <div>
                    <Text strong>Max predict tokens</Text>
                    <InputNumber
                      className="w-full"
                      value={session.maxPredictTokens}
                      onChange={(value) =>
                        setSession((prev) => ({ ...prev, maxPredictTokens: value ?? prev.maxPredictTokens }))
                      }
                    />
                  </div>
                  <div>
                    <Text strong>Stopping strings</Text>
                    <div className="flex gap-2">
                      <Input
                        value={session.stoppingStrings}
                        onChange={(event) =>
                          setSession((prev) => ({
                            ...prev,
                            stoppingStrings: event.target.value
                          }))
                        }
                        status={stoppingStringsError ? "error" : undefined}
                      />
                      <Button
                        onClick={() =>
                          setSession((prev) => ({
                            ...prev,
                            useBasicStoppingMode: !prev.useBasicStoppingMode
                          }))
                        }
                      >
                        {session.useBasicStoppingMode ? "Advanced" : "Basic"}
                      </Button>
                    </div>
                    {stoppingStringsError && (
                      <Text type="danger" className="text-xs">
                        {stoppingStringsError}
                      </Text>
                    )}
                  </div>
                  <div>
                    <Text strong>Prompt preview</Text>
                    <div className="flex items-center gap-3">
                      <Switch
                        checked={session.promptPreview}
                        onChange={(checked) =>
                          setSession((prev) => ({ ...prev, promptPreview: checked }))
                        }
                        disabled={session.tokenHighlightMode === -1}
                      />
                      <InputNumber
                        value={session.promptPreviewTokens}
                        min={1}
                        max={200}
                        onChange={(value) =>
                          setSession((prev) => ({
                            ...prev,
                            promptPreviewTokens: value ?? prev.promptPreviewTokens
                          }))
                        }
                      />
                    </div>
                  </div>
                </Space>
              )
            },
            {
              key: "sampling",
              label: "Sampling",
              children: (
                <Space direction="vertical" size={10} className="w-full">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Text strong>Temperature</Text>
                      <InputNumber
                        className="w-full"
                        value={session.temperature}
                        onChange={(value) =>
                          setSession((prev) => ({ ...prev, temperature: value ?? prev.temperature }))
                        }
                        disabled={!supportedFields.has("temperature")}
                      />
                    </div>
                    <div>
                      <Text strong>Top P</Text>
                      <InputNumber
                        className="w-full"
                        value={session.topP}
                        onChange={(value) =>
                          setSession((prev) => ({ ...prev, topP: value ?? prev.topP }))
                        }
                        disabled={!supportedFields.has("top_p")}
                      />
                    </div>
                    <div>
                      <Text strong>Top K</Text>
                      <InputNumber
                        className="w-full"
                        value={session.topK}
                        onChange={(value) =>
                          setSession((prev) => ({ ...prev, topK: value ?? prev.topK }))
                        }
                      />
                    </div>
                    <div>
                      <Text strong>Min P</Text>
                      <InputNumber
                        className="w-full"
                        value={session.minP}
                        onChange={(value) =>
                          setSession((prev) => ({ ...prev, minP: value ?? prev.minP }))
                        }
                      />
                    </div>
                    <div>
                      <Text strong>Presence penalty</Text>
                      <InputNumber
                        className="w-full"
                        value={session.presencePenalty}
                        onChange={(value) =>
                          setSession((prev) => ({ ...prev, presencePenalty: value ?? prev.presencePenalty }))
                        }
                        disabled={!supportedFields.has("presence_penalty")}
                      />
                    </div>
                    <div>
                      <Text strong>Frequency penalty</Text>
                      <InputNumber
                        className="w-full"
                        value={session.frequencyPenalty}
                        onChange={(value) =>
                          setSession((prev) => ({ ...prev, frequencyPenalty: value ?? prev.frequencyPenalty }))
                        }
                        disabled={!supportedFields.has("frequency_penalty")}
                      />
                    </div>
                  </div>
                  <Divider className="!my-2" />
                  <Text strong>Sampler toggles</Text>
                  <div className="grid grid-cols-2 gap-2">
                    {samplerOptions.map((option) => (
                      <label key={option.key} className="flex items-center gap-2 text-xs">
                        <Switch
                          size="small"
                          checked={session.enabledSamplers.includes(option.key)}
                          onChange={(checked) =>
                            setSession((prev) => ({
                              ...prev,
                              enabledSamplers: checked
                                ? [...prev.enabledSamplers, option.key]
                                : prev.enabledSamplers.filter((item) => item !== option.key)
                            }))
                          }
                        />
                        {option.label}
                      </label>
                    ))}
                  </div>
                  <Divider className="!my-2" />
                  <div>
                    <Text strong>Repeat penalty</Text>
                    <InputNumber
                      className="w-full"
                      value={session.repeatPenalty}
                      onChange={(value) =>
                        setSession((prev) => ({ ...prev, repeatPenalty: value ?? prev.repeatPenalty }))
                      }
                    />
                  </div>
                  <div>
                    <Text strong>Repeat last N</Text>
                    <InputNumber
                      className="w-full"
                      value={session.repeatLastN}
                      onChange={(value) =>
                        setSession((prev) => ({ ...prev, repeatLastN: value ?? prev.repeatLastN }))
                      }
                    />
                  </div>
                </Space>
              )
            },
            {
              key: "context",
              label: "Memory & Context",
              children: (
                <Space direction="vertical" size={10} className="w-full">
                  <div>
                    <Text strong>
                      Memory {memoryTokenCount ? `(${memoryTokenCount} tokens)` : ""}
                    </Text>
                    <Input.TextArea
                      value={session.memoryTokens.text}
                      onChange={(event) =>
                        setSession((prev) => ({
                          ...prev,
                          memoryTokens: {
                            ...prev.memoryTokens,
                            text: event.target.value
                          }
                        }))
                      }
                      rows={4}
                    />
                    <Button
                      size="small"
                      className="mt-2"
                      onClick={() => setModals((prev) => ({ ...prev, memory: true }))}
                    >
                      Memory settings
                    </Button>
                  </div>
                  <div>
                    <Text strong>
                      Author Note {authorNoteTokenCount ? `(${authorNoteTokenCount} tokens)` : ""}
                    </Text>
                    <Input.TextArea
                      value={session.authorNoteTokens.text}
                      onChange={(event) =>
                        setSession((prev) => ({
                          ...prev,
                          authorNoteTokens: {
                            ...prev.authorNoteTokens,
                            text: event.target.value
                          }
                        }))
                      }
                      rows={3}
                    />
                    <Button
                      size="small"
                      className="mt-2"
                      onClick={() => setModals((prev) => ({ ...prev, authorNote: true }))}
                    >
                      Author note settings
                    </Button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={() => setModals((prev) => ({ ...prev, worldInfo: true }))}>
                      World info
                    </Button>
                    <Button onClick={() => setModals((prev) => ({ ...prev, context: true }))}>
                      Show context
                    </Button>
                    <Button
                      onClick={() => setModals((prev) => ({ ...prev, logitBias: true }))}
                      disabled={!supportedFields.has("logit_bias") || !tokenizeSupported}
                    >
                      Logit bias
                    </Button>
                    <Button onClick={() => setModals((prev) => ({ ...prev, grammar: true }))}>
                      Grammar
                    </Button>
                    <Button onClick={() => setModals((prev) => ({ ...prev, instruct: true }))}>
                      Instruct
                    </Button>
                  </div>
                </Space>
              )
            }
          ]}
        />
      </div>

      <Modal
        title="Preferences"
        open={modals.preferences}
        onCancel={() => setModals((prev) => ({ ...prev, preferences: false }))}
        footer={null}
      >
        <Space direction="vertical" className="w-full" size={12}>
          <div>
            <Text strong>Font size</Text>
            <InputNumber
              className="w-full"
              min={0.5}
              max={5}
              step={0.05}
              value={session.fontSizeMultiplier}
              onChange={(value) =>
                setSession((prev) => ({ ...prev, fontSizeMultiplier: value ?? 1 }))
              }
            />
          </div>
          <div className="flex items-center justify-between">
            <Text strong>Spell check</Text>
            <Switch
              checked={session.spellCheck}
              onChange={(checked) =>
                setSession((prev) => ({ ...prev, spellCheck: checked }))
              }
            />
          </div>
          <div className="flex items-center justify-between">
            <Text strong>Attach sidebar</Text>
            <Switch
              checked={session.attachSidebar}
              onChange={(checked) =>
                setSession((prev) => ({ ...prev, attachSidebar: checked }))
              }
            />
          </div>
          <div className="flex items-center justify-between">
            <Text strong>Preserve cursor</Text>
            <Switch
              checked={session.preserveCursorPosition}
              onChange={(checked) =>
                setSession((prev) => ({ ...prev, preserveCursorPosition: checked }))
              }
            />
          </div>
          <div>
            <Text strong>Token highlight</Text>
            <Select
              value={session.tokenHighlightMode}
              options={highlightOptions}
              onChange={(value) =>
                setSession((prev) => ({ ...prev, tokenHighlightMode: value }))
              }
            />
          </div>
          {session.tokenHighlightMode !== -1 && (
            <>
              <div>
                <Text strong>Highlight color</Text>
                <Select
                  value={session.tokenColorMode}
                  options={colorModeOptions}
                  onChange={(value) =>
                    setSession((prev) => ({ ...prev, tokenColorMode: value }))
                  }
                />
              </div>
              <div>
                <Text strong>Token probabilities</Text>
                <Select
                  value={session.showProbsMode}
                  options={probsModeOptions}
                  onChange={(value) =>
                    setSession((prev) => ({ ...prev, showProbsMode: value }))
                  }
                />
              </div>
            </>
          )}
          <div className="flex items-center justify-between">
            <Text strong>Markdown preview</Text>
            <Switch
              checked={session.showMarkdownPreview}
              onChange={(checked) =>
                setSession((prev) => ({ ...prev, showMarkdownPreview: checked }))
              }
            />
          </div>
          <Divider className="!my-2" />
          <div className="flex items-center justify-between">
            <Text strong>TTS enabled</Text>
            <Switch
              checked={session.ttsEnabled}
              onChange={(checked) =>
                setSession((prev) => ({ ...prev, ttsEnabled: checked }))
              }
              disabled={!ttsAvailable}
            />
          </div>
          {session.ttsEnabled && (
            <>
              <div>
                <Text strong>Voice</Text>
                <Select
                  value={session.ttsVoiceId}
                  options={ttsVoices.map((voice, index) => ({
                    label: voice.name,
                    value: index
                  }))}
                  onChange={(value) =>
                    setSession((prev) => ({ ...prev, ttsVoiceId: value }))
                  }
                />
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <Text strong>Pitch</Text>
                  <InputNumber
                    className="w-full"
                    min={0}
                    max={2}
                    step={0.1}
                    value={session.ttsPitch}
                    onChange={(value) =>
                      setSession((prev) => ({ ...prev, ttsPitch: value ?? prev.ttsPitch }))
                    }
                  />
                </div>
                <div>
                  <Text strong>Rate</Text>
                  <InputNumber
                    className="w-full"
                    min={0.1}
                    max={10}
                    step={0.1}
                    value={session.ttsRate}
                    onChange={(value) =>
                      setSession((prev) => ({ ...prev, ttsRate: value ?? prev.ttsRate }))
                    }
                  />
                </div>
                <div>
                  <Text strong>Volume</Text>
                  <InputNumber
                    className="w-full"
                    min={0}
                    max={2}
                    step={0.1}
                    value={session.ttsVolume}
                    onChange={(value) =>
                      setSession((prev) => ({ ...prev, ttsVolume: value ?? prev.ttsVolume }))
                    }
                  />
                </div>
              </div>
              <div className="flex items-center justify-between">
                <Text strong>Speak inputs</Text>
                <Switch
                  checked={session.ttsSpeakInputs}
                  onChange={(checked) =>
                    setSession((prev) => ({ ...prev, ttsSpeakInputs: checked }))
                  }
                />
              </div>
            </>
          )}
        </Space>
      </Modal>

      <Modal
        title="Memory"
        open={modals.memory}
        onCancel={() => setModals((prev) => ({ ...prev, memory: false }))}
        footer={null}
      >
        <Space direction="vertical" className="w-full" size={10}>
          <Input
            placeholder="Prefix"
            value={session.memoryTokens.prefix}
            onChange={(event) =>
              setSession((prev) => ({
                ...prev,
                memoryTokens: { ...prev.memoryTokens, prefix: event.target.value }
              }))
            }
          />
          <Input.TextArea
            rows={6}
            placeholder="Memory text"
            value={session.memoryTokens.text}
            onChange={(event) =>
              setSession((prev) => ({
                ...prev,
                memoryTokens: { ...prev.memoryTokens, text: event.target.value }
              }))
            }
          />
          <Input
            placeholder="Suffix"
            value={session.memoryTokens.suffix}
            onChange={(event) =>
              setSession((prev) => ({
                ...prev,
                memoryTokens: { ...prev.memoryTokens, suffix: event.target.value }
              }))
            }
          />
          <Input.TextArea
            rows={3}
            placeholder="Context order"
            value={session.memoryTokens.contextOrder}
            onChange={(event) =>
              setSession((prev) => ({
                ...prev,
                memoryTokens: { ...prev.memoryTokens, contextOrder: event.target.value }
              }))
            }
          />
        </Space>
      </Modal>

      <Modal
        title="Author Note"
        open={modals.authorNote}
        onCancel={() => setModals((prev) => ({ ...prev, authorNote: false }))}
        footer={null}
      >
        <Space direction="vertical" className="w-full" size={10}>
          <Input
            placeholder="Prefix"
            value={session.authorNoteTokens.prefix}
            onChange={(event) =>
              setSession((prev) => ({
                ...prev,
                authorNoteTokens: { ...prev.authorNoteTokens, prefix: event.target.value }
              }))
            }
          />
          <Input.TextArea
            rows={4}
            placeholder="Author note"
            value={session.authorNoteTokens.text}
            onChange={(event) =>
              setSession((prev) => ({
                ...prev,
                authorNoteTokens: { ...prev.authorNoteTokens, text: event.target.value }
              }))
            }
          />
          <Input
            placeholder="Suffix"
            value={session.authorNoteTokens.suffix}
            onChange={(event) =>
              setSession((prev) => ({
                ...prev,
                authorNoteTokens: { ...prev.authorNoteTokens, suffix: event.target.value }
              }))
            }
          />
          <InputNumber
            className="w-full"
            value={session.authorNoteDepth}
            onChange={(value) =>
              setSession((prev) => ({
                ...prev,
                authorNoteDepth: value ?? prev.authorNoteDepth
              }))
            }
            min={1}
          />
        </Space>
      </Modal>

      <WorldInfoModal
        open={modals.worldInfo}
        onClose={() => setModals((prev) => ({ ...prev, worldInfo: false }))}
        worldInfo={session.worldInfo}
        onChange={(worldInfo) =>
          setSession((prev) => ({ ...prev, worldInfo }))
        }
      />

      <LogitBiasModal
        open={modals.logitBias && supportedFields.has("logit_bias") && tokenizeSupported}
        onClose={() => setModals((prev) => ({ ...prev, logitBias: false }))}
        logitBias={session.logitBias}
        onChange={(logitBias) => setSession((prev) => ({ ...prev, logitBias }))}
        onAdd={handleAddLogitBias}
      />

      <Modal
        title="Context"
        open={modals.context}
        onCancel={() => setModals((prev) => ({ ...prev, context: false }))}
        footer={null}
        width={720}
      >
        <Space direction="vertical" className="w-full" size={12}>
          <Alert
            type="info"
            showIcon
            message={`Memory: ${memoryTokenCount} tokens, Author Note: ${authorNoteTokenCount} tokens, World Info: ${worldInfoTokenCount} tokens`}
          />
          <Input.TextArea value={finalPromptText} rows={12} readOnly />
        </Space>
      </Modal>

      <TemplatesModal
        open={modals.templates && templatesSupported}
        onClose={() => setModals((prev) => ({ ...prev, templates: false }))}
        templates={templateMap}
        onRefresh={() => queryClient.invalidateQueries({ queryKey: ["writing", "templates"] })}
      />

      <ThemesModal
        open={modals.themes && themesSupported}
        onClose={() => setModals((prev) => ({ ...prev, themes: false }))}
        themes={themeMap}
        onRefresh={() => queryClient.invalidateQueries({ queryKey: ["writing", "themes"] })}
      />

      <SearchReplaceModal
        open={modals.searchReplace}
        onClose={() => setModals((prev) => ({ ...prev, searchReplace: false }))}
        promptRef={promptAreaRef}
        onUpdatePrompt={updatePromptChunks}
        promptText={promptText}
      />

      <Modal
        title="Grammar"
        open={modals.grammar}
        onCancel={() => setModals((prev) => ({ ...prev, grammar: false }))}
        footer={null}
      >
        <Input.TextArea
          rows={8}
          placeholder="EBNF grammar"
          value={session.grammar}
          onChange={(event) =>
            setSession((prev) => ({ ...prev, grammar: event.target.value }))
          }
        />
      </Modal>

      <InstructModal
        open={modals.instruct}
        onClose={() => setModals((prev) => ({ ...prev, instruct: false }))}
        selectedText={selectedText}
        context={instructContext}
        template={selectedTemplatePayload}
        onPredict={async (prompt) => {
          let result = ""
          await predict({
            promptOverride: prompt,
            onChunk: (chunk) => {
              result += chunk.content
              return true
            }
          })
          return result
        }}
        onInsert={(content, replaceSelected) => {
          const textarea = promptAreaRef.current
          if (!textarea) return
          const start = textarea.selectionStart
          const end = textarea.selectionEnd
          const before = textarea.value.substring(0, start)
          const selected = textarea.value.substring(start, end)
          const after = textarea.value.substring(end)
          const next = replaceSelected
            ? `${before}${content}${after}`
            : `${before}${selected}${content}${after}`
          textarea.value = next
          updatePromptChunks(next)
        }}
      />

      <Modal
        title="Rename Session"
        open={modals.renameSession}
        onCancel={() => setModals((prev) => ({ ...prev, renameSession: false }))}
        onOk={() => void handleRenameSession()}
      >
        <Input
          value={sessionNameDraft}
          onChange={(event) => setSessionNameDraft(event.target.value)}
        />
      </Modal>
    </div>
  )
}

type WorldInfoModalProps = {
  open: boolean
  onClose: () => void
  worldInfo: WritingSessionPayload["worldInfo"]
  onChange: (value: WritingSessionPayload["worldInfo"]) => void
}

const WorldInfoModal: React.FC<WorldInfoModalProps> = ({
  open,
  onClose,
  worldInfo,
  onChange
}) => {
  const [importBuffer, setImportBuffer] = React.useState<any | null>(null)
  const addEntry = () => {
    onChange({
      ...worldInfo,
      entries: [
        { displayName: "New Entry", text: "", keys: [], search: "" },
        ...worldInfo.entries
      ]
    })
  }
  const updateEntry = (index: number, patch: Partial<WritingWorldInfoEntry>) => {
    const entries = [...worldInfo.entries]
    entries[index] = { ...entries[index], ...patch }
    onChange({ ...worldInfo, entries })
  }
  const removeEntry = (index: number) => {
    const entries = worldInfo.entries.filter((_, i) => i !== index)
    onChange({ ...worldInfo, entries })
  }
  const moveEntry = (index: number, delta: number) => {
    const entries = [...worldInfo.entries]
    const next = index + delta
    if (next < 0 || next >= entries.length) return
    entries.splice(next, 0, entries.splice(index, 1)[0])
    onChange({ ...worldInfo, entries })
  }
  const importWorldInfo = async () => {
    const input = document.createElement("input")
    input.type = "file"
    input.accept = ".json"
    input.onchange = async () => {
      const file = input.files?.[0]
      if (!file) return
      const text = await file.text()
      const json = JSON.parse(text)
      if (worldInfo.entries.length) {
        setImportBuffer(json)
        return
      }
      const entries = importSillyTavernWorldInfo(json, worldInfo.entries)
      onChange({ ...worldInfo, entries })
    }
    input.click()
  }
  const exportWorldInfo = () => {
    const exported: any = { entries: {} }
    worldInfo.entries.forEach((entry, index) => {
      exported.entries[index] = {
        uid: index,
        key: [...entry.keys],
        keysecondary: [],
        comment: entry.displayName,
        content: entry.text,
        scanDepth: entry.search || null
      }
    })
    const blob = new Blob([JSON.stringify(exported, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = "Writing-WorldInfo.json"
    anchor.click()
    URL.revokeObjectURL(url)
  }
  const handleImport = (mode: "replace" | "append") => {
    if (!importBuffer) return
    const entries = importSillyTavernWorldInfo(
      importBuffer,
      mode === "append" ? worldInfo.entries : []
    )
    onChange({ ...worldInfo, entries })
    setImportBuffer(null)
  }

  return (
    <>
      <Modal
        title="World Info"
        open={open}
        onCancel={onClose}
        footer={null}
        width={860}
      >
        <Space direction="vertical" className="w-full" size={10}>
          <div className="flex flex-wrap gap-2">
            <Button icon={<FileUp className="h-4 w-4" />} onClick={() => void importWorldInfo()}>
              Import
            </Button>
            <Button icon={<FileDown className="h-4 w-4" />} onClick={exportWorldInfo}>
              Export
            </Button>
            <Button icon={<Plus className="h-4 w-4" />} onClick={addEntry}>
              New Entry
            </Button>
          </div>
          <div className="flex gap-2">
            <Input
              placeholder="Prefix"
              value={worldInfo.prefix}
              onChange={(event) => onChange({ ...worldInfo, prefix: event.target.value })}
            />
            <Input
              placeholder="Suffix"
              value={worldInfo.suffix}
              onChange={(event) => onChange({ ...worldInfo, suffix: event.target.value })}
            />
          </div>
          <div className="max-h-[50vh] overflow-y-auto space-y-3">
            {worldInfo.entries.map((entry, index) => (
              <Card key={`wi-${index}`} size="small">
                <Space direction="vertical" className="w-full" size={6}>
                  <div className="flex items-center justify-between gap-2">
                    <Input
                      value={entry.displayName}
                      onChange={(event) => updateEntry(index, { displayName: event.target.value })}
                    />
                    <div className="flex gap-1">
                      <Button size="small" onClick={() => moveEntry(index, -1)}>Up</Button>
                      <Button size="small" onClick={() => removeEntry(index)} danger>
                        Delete
                      </Button>
                      <Button size="small" onClick={() => moveEntry(index, 1)}>Down</Button>
                    </div>
                  </div>
                  <Input
                    placeholder="Comma-separated regex keys"
                    value={entry.keys.join(",")}
                    onChange={(event) =>
                      updateEntry(index, { keys: event.target.value.split(/(?<!\\),\s*/) })
                    }
                  />
                  <Input
                    placeholder="Search range"
                    value={String(entry.search)}
                    onChange={(event) => updateEntry(index, { search: event.target.value })}
                  />
                  <Input.TextArea
                    rows={3}
                    value={entry.text}
                    onChange={(event) => updateEntry(index, { text: event.target.value })}
                  />
                </Space>
              </Card>
            ))}
          </div>
        </Space>
      </Modal>
      <Modal
        title="World Info Import"
        open={Boolean(importBuffer)}
        onCancel={() => setImportBuffer(null)}
        footer={null}
      >
        <Space direction="vertical" className="w-full" size={10}>
          <Text>Existing entries found. How should we import?</Text>
          <div className="flex gap-2">
            <Button onClick={() => handleImport("replace")}>Replace</Button>
            <Button onClick={() => handleImport("append")}>Append</Button>
          </div>
        </Space>
      </Modal>
    </>
  )
}

type LogitBiasModalProps = {
  open: boolean
  onClose: () => void
  logitBias: WritingLogitBiasState
  onChange: (value: WritingLogitBiasState) => void
  onAdd: (power: number, text: string) => Promise<void>
}

const LogitBiasModal: React.FC<LogitBiasModalProps> = ({
  open,
  onClose,
  logitBias,
  onChange,
  onAdd
}) => {
  const [power, setPower] = React.useState(0)
  const [token, setToken] = React.useState("")

  const entries = Object.entries(logitBias.bias)

  return (
    <Modal title="Logit Bias" open={open} onCancel={onClose} footer={null} width={720}>
      <Space direction="vertical" className="w-full" size={10}>
        <div className="flex gap-2">
          <InputNumber value={power} onChange={(value) => setPower(value ?? 0)} />
          <Input value={token} onChange={(event) => setToken(event.target.value)} placeholder="Token" />
          <Button
            type="primary"
            onClick={async () => {
              await onAdd(power, token)
              setToken("")
            }}
          >
            Add
          </Button>
        </div>
        <div className="space-y-2">
          {entries.map(([key, entry]) => (
            <Card key={key} size="small">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <Text strong>{key}</Text>
                  <div className="text-xs text-text-muted">
                    Tokens: {entry.ids.join(", ")}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <InputNumber
                    value={entry.power}
                    onChange={(value) =>
                      onChange({
                        ...logitBias,
                        bias: {
                          ...logitBias.bias,
                          [key]: { ...entry, power: value ?? entry.power }
                        }
                      })
                    }
                  />
                  <Button
                    danger
                    onClick={() => {
                      const updated = { ...logitBias.bias }
                      delete updated[key]
                      onChange({ ...logitBias, bias: updated })
                    }}
                  >
                    Remove
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </Space>
    </Modal>
  )
}

type TemplatesModalProps = {
  open: boolean
  onClose: () => void
  templates: Map<string, WritingTemplateResponse>
  onRefresh: () => void
}

const TemplatesModal: React.FC<TemplatesModalProps> = ({
  open,
  onClose,
  templates,
  onRefresh
}) => {
  const [selectedName, setSelectedName] = React.useState<string | null>(null)
  const [draft, setDraft] = React.useState<WritingTemplatePayload>({})
  const [nameDraft, setNameDraft] = React.useState("")
  const [version, setVersion] = React.useState(0)

  React.useEffect(() => {
    const names = Array.from(templates.keys())
    const initial = names[0] ?? Object.keys(DEFAULT_TEMPLATES)[0] ?? null
    setSelectedName(initial)
  }, [templates, open])

  React.useEffect(() => {
    if (!selectedName) return
    if (templates.has(selectedName)) {
      const template = templates.get(selectedName)
      setDraft((template?.payload as WritingTemplatePayload) ?? {})
      setNameDraft(template?.name ?? selectedName)
      setVersion(template?.version ?? 0)
      return
    }
    setDraft(DEFAULT_TEMPLATES[selectedName] ?? {})
    setNameDraft(selectedName)
  }, [selectedName, templates])

  const handleSave = async () => {
    if (!selectedName) return
    if (templates.has(selectedName)) {
      await updateWritingTemplate(
        selectedName,
        { name: nameDraft, payload: draft as Record<string, unknown> },
        version
      )
    } else {
      await createWritingTemplate({
        name: nameDraft,
        payload: draft as Record<string, unknown>,
        is_default: false
      })
    }
    onRefresh()
  }

  const handleDelete = async () => {
    if (!selectedName || !templates.has(selectedName)) return
    const template = templates.get(selectedName)
    if (!template) return
    await deleteWritingTemplate(selectedName, template.version)
    onRefresh()
  }

  const handleCreateNew = () => {
    setSelectedName("New Template")
    setDraft({})
    setNameDraft("New Template")
    setVersion(0)
  }

  return (
    <Modal title="Instruct Templates" open={open} onCancel={onClose} footer={null} width={820}>
      <Space direction="vertical" className="w-full" size={12}>
        <div className="flex gap-2">
          <Select
            className="flex-1"
            value={selectedName ?? undefined}
            options={Array.from(new Set([...Object.keys(DEFAULT_TEMPLATES), ...templates.keys()])).map((name) => ({
              label: name,
              value: name
            }))}
            onChange={(value) => setSelectedName(value)}
          />
          <Button icon={<Plus className="h-4 w-4" />} onClick={handleCreateNew}>
            New
          </Button>
          <Button danger onClick={() => void handleDelete()} disabled={!templates.has(selectedName ?? "")}>Delete</Button>
        </div>
        <Input
          value={nameDraft}
          onChange={(event) => setNameDraft(event.target.value)}
          placeholder="Template name"
        />
        <Input.TextArea
          rows={2}
          value={draft.sysPre}
          onChange={(event) => setDraft((prev) => ({ ...prev, sysPre: event.target.value }))}
          placeholder="System prefix"
        />
        <Input.TextArea
          rows={2}
          value={draft.sysSuf}
          onChange={(event) => setDraft((prev) => ({ ...prev, sysSuf: event.target.value }))}
          placeholder="System suffix"
        />
        <Input.TextArea
          rows={2}
          value={draft.instPre}
          onChange={(event) => setDraft((prev) => ({ ...prev, instPre: event.target.value }))}
          placeholder="Instruction prefix"
        />
        <Input.TextArea
          rows={2}
          value={draft.instSuf}
          onChange={(event) => setDraft((prev) => ({ ...prev, instSuf: event.target.value }))}
          placeholder="Instruction suffix"
        />
        <Input.TextArea
          rows={2}
          value={draft.fimTemplate}
          onChange={(event) => setDraft((prev) => ({ ...prev, fimTemplate: event.target.value }))}
          placeholder="FIM template"
        />
        <div className="flex gap-2">
          <Button type="primary" onClick={() => void handleSave()}>Save</Button>
          <Button onClick={onClose}>Close</Button>
        </div>
      </Space>
    </Modal>
  )
}

type ThemesModalProps = {
  open: boolean
  onClose: () => void
  themes: Map<string, WritingThemeResponse>
  onRefresh: () => void
}

const ThemesModal: React.FC<ThemesModalProps> = ({ open, onClose, themes, onRefresh }) => {
  const [selectedName, setSelectedName] = React.useState<string | null>(null)
  const [nameDraft, setNameDraft] = React.useState("")
  const [classNameDraft, setClassNameDraft] = React.useState("")
  const [cssDraft, setCssDraft] = React.useState("")
  const [orderDraft, setOrderDraft] = React.useState(0)
  const [version, setVersion] = React.useState(0)

  React.useEffect(() => {
    const names = Array.from(themes.keys())
    const initial = names[0] ?? Object.keys(DEFAULT_THEMES)[0] ?? null
    setSelectedName(initial)
  }, [themes, open])

  React.useEffect(() => {
    if (!selectedName) return
    if (themes.has(selectedName)) {
      const theme = themes.get(selectedName)
      setNameDraft(theme?.name ?? selectedName)
      setClassNameDraft(theme?.class_name ?? "")
      setCssDraft(theme?.css ?? "")
      setOrderDraft(theme?.order ?? 0)
      setVersion(theme?.version ?? 0)
      return
    }
    const fallback = DEFAULT_THEMES[selectedName]
    setNameDraft(selectedName)
    setClassNameDraft(fallback?.className ?? "")
    setCssDraft(fallback?.css ?? "")
    setOrderDraft(fallback?.order ?? 0)
    setVersion(0)
  }, [selectedName, themes])

  const handleSave = async () => {
    if (!selectedName) return
    if (themes.has(selectedName)) {
      await updateWritingTheme(
        selectedName,
        {
          name: nameDraft,
          class_name: classNameDraft,
          css: cssDraft,
          order: orderDraft
        },
        version
      )
    } else {
      await createWritingTheme({
        name: nameDraft,
        class_name: classNameDraft,
        css: cssDraft,
        order: orderDraft,
        is_default: false
      })
    }
    onRefresh()
  }

  const handleDelete = async () => {
    if (!selectedName || !themes.has(selectedName)) return
    const theme = themes.get(selectedName)
    if (!theme) return
    await deleteWritingTheme(selectedName, theme.version)
    onRefresh()
  }

  const handleCreateNew = () => {
    setSelectedName("New Theme")
    setNameDraft("New Theme")
    setClassNameDraft("theme-new")
    setCssDraft("")
    setOrderDraft(0)
    setVersion(0)
  }

  return (
    <Modal title="Themes" open={open} onCancel={onClose} footer={null} width={820}>
      <Space direction="vertical" className="w-full" size={12}>
        <div className="flex gap-2">
          <Select
            className="flex-1"
            value={selectedName ?? undefined}
            options={Array.from(new Set([...Object.keys(DEFAULT_THEMES), ...themes.keys()])).map((name) => ({
              label: name,
              value: name
            }))}
            onChange={(value) => setSelectedName(value)}
          />
          <Button icon={<Plus className="h-4 w-4" />} onClick={handleCreateNew}>
            New
          </Button>
          <Button danger onClick={() => void handleDelete()} disabled={!themes.has(selectedName ?? "")}>Delete</Button>
        </div>
        <Input
          value={nameDraft}
          onChange={(event) => setNameDraft(event.target.value)}
          placeholder="Theme name"
        />
        <Input
          value={classNameDraft}
          onChange={(event) => setClassNameDraft(event.target.value)}
          placeholder="CSS class"
        />
        <InputNumber
          className="w-full"
          value={orderDraft}
          onChange={(value) => setOrderDraft(value ?? 0)}
          placeholder="Order"
        />
        <Input.TextArea
          rows={8}
          value={cssDraft}
          onChange={(event) => setCssDraft(event.target.value)}
          placeholder="Theme CSS"
        />
        <div className="flex gap-2">
          <Button type="primary" onClick={() => void handleSave()}>Save</Button>
          <Button onClick={onClose}>Close</Button>
        </div>
      </Space>
    </Modal>
  )
}

type SearchReplaceModalProps = {
  open: boolean
  onClose: () => void
  promptRef: React.RefObject<HTMLTextAreaElement>
  onUpdatePrompt: (value: string) => void
  promptText: string
}

const SearchReplaceModal: React.FC<SearchReplaceModalProps> = ({
  open,
  onClose,
  promptRef,
  onUpdatePrompt,
  promptText
}) => {
  const [mode, setMode] = React.useState(0)
  const [searchTerm, setSearchTerm] = React.useState("")
  const [replaceTerm, setReplaceTerm] = React.useState("")
  const [flags, setFlags] = React.useState("gi")
  const [matches, setMatches] = React.useState<{ start: number; end: number }[]>([])
  const [currentIndex, setCurrentIndex] = React.useState(-1)
  const [error, setError] = React.useState<string | null>(null)

  const findAllMatches = React.useCallback(() => {
    if (!promptRef.current) return []
    setError(null)
    const text = promptRef.current.value
    if (!searchTerm) return []
    if (mode === 0) {
      const positions: { start: number; end: number }[] = []
      let index = 0
      while ((index = text.indexOf(searchTerm, index)) > -1) {
        positions.push({ start: index, end: index + searchTerm.length })
        index += searchTerm.length
      }
      return positions
    }
    try {
      let regexFlags = flags
      if (!regexFlags.includes("g")) regexFlags += "g"
      const regex = new RegExp(searchTerm, regexFlags)
      const positions: { start: number; end: number }[] = []
      let match: RegExpExecArray | null
      while ((match = regex.exec(text)) !== null) {
        positions.push({ start: match.index, end: regex.lastIndex })
        if (match.index === regex.lastIndex) regex.lastIndex++
      }
      return positions
    } catch (err: any) {
      setError(err?.message || "Invalid regex")
      return []
    }
  }, [mode, searchTerm, flags, promptRef])

  const highlightIndex = (index: number) => {
    const textarea = promptRef.current
    if (!textarea) return
    const position = matches[index]
    if (!position) return
    textarea.focus()
    textarea.setSelectionRange(position.start, position.end)
  }

  const findNext = () => {
    const nextMatches = matches.length ? matches : findAllMatches()
    if (!nextMatches.length) {
      setMatches([])
      setCurrentIndex(-1)
      return
    }
    const nextIndex = (currentIndex + 1) % nextMatches.length
    setMatches(nextMatches)
    setCurrentIndex(nextIndex)
    highlightIndex(nextIndex)
  }

  const findPrev = () => {
    const nextMatches = matches.length ? matches : findAllMatches()
    if (!nextMatches.length) {
      setMatches([])
      setCurrentIndex(-1)
      return
    }
    const nextIndex = (currentIndex - 1 + nextMatches.length) % nextMatches.length
    setMatches(nextMatches)
    setCurrentIndex(nextIndex)
    highlightIndex(nextIndex)
  }

  const replaceAll = () => {
    const textarea = promptRef.current
    if (!textarea) return
    const text = textarea.value
    if (!searchTerm) return
    let next = text
    if (mode === 0) {
      next = text.split(searchTerm).join(replaceTerm)
    } else {
      try {
        const regex = new RegExp(searchTerm, flags)
        next = text.replace(regex, replaceTerm)
      } catch (err: any) {
        setError(err?.message || "Invalid regex")
        return
      }
    }
    textarea.value = next
    onUpdatePrompt(next)
    setMatches([])
    setCurrentIndex(-1)
  }

  React.useEffect(() => {
    if (!open) return
    const nextMatches = findAllMatches()
    setMatches(nextMatches)
    setCurrentIndex(nextMatches.length ? 0 : -1)
  }, [open, promptText, findAllMatches])

  return (
    <Modal title="Search & Replace" open={open} onCancel={onClose} footer={null}>
      <Space direction="vertical" className="w-full" size={10}>
        <Select
          value={mode}
          onChange={(value) => setMode(value)}
          options={[
            { label: "Plaintext", value: 0 },
            { label: "RegEx", value: 1 }
          ]}
        />
        <Input
          placeholder="Search"
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
        />
        {mode === 1 && (
          <Input
            placeholder="Flags"
            value={flags}
            onChange={(event) => setFlags(event.target.value)}
          />
        )}
        <Input
          placeholder="Replace"
          value={replaceTerm}
          onChange={(event) => setReplaceTerm(event.target.value)}
        />
        <div className="flex gap-2">
          <Button onClick={findPrev}>Prev</Button>
          <Button onClick={findNext}>Next</Button>
          <Button type="primary" onClick={replaceAll}>Replace all</Button>
        </div>
        {error && <Text type="danger">{error}</Text>}
        {matches.length > 0 && (
          <Text type="secondary">
            {currentIndex >= 0 ? `${currentIndex + 1} / ` : ""}
            {matches.length} matches
          </Text>
        )}
      </Space>
    </Modal>
  )
}

type InstructModalProps = {
  open: boolean
  onClose: () => void
  selectedText: string
  context: string
  template?: WritingTemplatePayload
  onPredict: (prompt: string) => Promise<string>
  onInsert: (content: string, replaceSelected: boolean) => void
}

const InstructModal: React.FC<InstructModalProps> = ({
  open,
  onClose,
  selectedText,
  context,
  template,
  onPredict,
  onInsert
}) => {
  const [prompt, setPrompt] = React.useState("")
  const [result, setResult] = React.useState("")
  const [includeContext, setIncludeContext] = React.useState(true)
  const [loading, setLoading] = React.useState(false)

  React.useEffect(() => {
    if (!open) return
    setPrompt("")
    setResult("")
  }, [open])

  const handlePredict = async () => {
    setLoading(true)
    let prefix = template?.instPre ?? ""
    let suffix = template?.instSuf ?? ""
    prefix = prefix.replace(/\\n/g, "\n")
    suffix = suffix.replace(/\\n/g, "\n")
    let instructPrompt = `${prefix}${prompt}${suffix}`
    instructPrompt = replacePlaceholders(instructPrompt, {
      "{selectedText}": selectedText.trim()
    })
    if (includeContext && context) {
      instructPrompt = `${context}${prefix}Wait a moment, I want to ask you something.${suffix}Understood.${instructPrompt}`
    }
    const output = await onPredict(instructPrompt)
    setResult(output)
    setLoading(false)
  }

  return (
    <Modal title="Instruct" open={open} onCancel={onClose} footer={null} width={720}>
      <Space direction="vertical" className="w-full" size={10}>
        <Input.TextArea
          rows={4}
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="Instruction prompt"
        />
        <div className="flex items-center gap-2">
          <Switch checked={includeContext} onChange={(checked) => setIncludeContext(checked)} />
          <Text>Include context</Text>
        </div>
        <Button type="primary" icon={<Wand2 className="h-4 w-4" />} loading={loading} onClick={() => void handlePredict()}>
          Predict
        </Button>
        <Input.TextArea rows={6} value={result} onChange={(event) => setResult(event.target.value)} />
        <div className="flex gap-2">
          <Button onClick={() => onInsert(result, false)} disabled={!result}>Insert</Button>
          <Button onClick={() => onInsert(result, true)} disabled={!result || !selectedText}>
            Replace selection
          </Button>
        </div>
      </Space>
    </Modal>
  )
}

const importSillyTavernWorldInfo = (
  json: any,
  existing: WritingWorldInfoEntry[]
): WritingWorldInfoEntry[] => {
  const entries = [...existing]
  Object.values(json.entries || {}).forEach((entry: any) => {
    entries.push({
      displayName: entry.comment,
      text: entry.content,
      keys: [...(entry.key || [])],
      search: entry.scanDepth || ""
    })
  })
  return entries
}

const collectLegacySessions = () => {
  try {
    const nextId = Number(localStorage.getItem("nextSessionId") || 0)
    if (!nextId) return []
    const sessions: Record<string, Record<string, unknown>> = {}
    for (const key of Object.keys(localStorage)) {
      const [sessionId, property] = key.split("/")
      if (!property) continue
      const rawValue = localStorage.getItem(key)
      if (!rawValue) continue
      try {
        const value = JSON.parse(rawValue)
        sessions[sessionId] = sessions[sessionId] || {}
        sessions[sessionId][property] = value
      } catch {
        continue
      }
    }
    return Object.entries(sessions).map(([id, payload]) => ({
      id,
      name: (payload as any).name || `Legacy ${id}`,
      payload
    }))
  } catch {
    return []
  }
}

export { InstructModal, SearchReplaceModal }
export default WritingPlayground
