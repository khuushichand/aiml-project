import React, { useEffect } from "react"
import { useTranslation } from "react-i18next"
import { Drawer, Tabs, Modal, Input, Empty, Skeleton } from "antd"
import type { InputRef } from "antd"
import {
  FileText,
  MessageSquare,
  Sparkles,
  Search,
  Command
} from "lucide-react"
import { useWorkspaceStore } from "@/store/workspace"
import {
  WORKSPACE_CONFLICT_NOTICE_THROTTLE_MS,
  WORKSPACE_STORAGE_CHANNEL_NAME,
  WORKSPACE_STORAGE_KEY,
  WORKSPACE_STORAGE_QUOTA_EVENT,
  isWorkspaceBroadcastSyncEnabled,
  isWorkspaceBroadcastUpdateMessage,
  shouldSurfaceWorkspaceConflictNotice,
  type WorkspaceStorageQuotaEventDetail
} from "@/store/workspace-events"
import { useMobile } from "@/hooks/useMediaQuery"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import {
  buildKnowledgeQaSeedNote,
  consumeWorkspacePlaygroundPrefill
} from "@/utils/workspace-playground-prefill"
import { WorkspaceHeader } from "./WorkspaceHeader"
import { SourcesPane } from "./SourcesPane"
import { ChatPane } from "./ChatPane"
import { StudioPane } from "./StudioPane"
import {
  buildWorkspaceGlobalSearchResults,
  type WorkspaceGlobalSearchResult
} from "./workspace-global-search"

const WORKSPACE_SWITCH_TRANSITION_MS = 420
const WORKSPACE_SOURCE_STATUS_POLL_INTERVAL_MS = 5000

type WorkspaceTabKey = "sources" | "chat" | "studio"

const isDesktopLayout = (): boolean => {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return true
  }
  return window.matchMedia("(min-width: 1024px)").matches
}

const isMediaLikelyReadyForRag = (detail: unknown): boolean => {
  if (!detail || typeof detail !== "object") {
    return false
  }

  const candidate = detail as Record<string, unknown>
  const content = candidate.content as Record<string, unknown> | undefined
  const processing = candidate.processing as Record<string, unknown> | undefined

  const contentText =
    typeof content?.text === "string" ? content.text.trim() : ""
  if (contentText.length > 0) {
    return true
  }

  const analysis =
    typeof processing?.analysis === "string" ? processing.analysis.trim() : ""
  if (analysis.length > 0) {
    return true
  }

  const safeMetadata = processing?.safe_metadata
  if (
    safeMetadata &&
    typeof safeMetadata === "object" &&
    Object.keys(safeMetadata as Record<string, unknown>).length > 0
  ) {
    return true
  }

  return false
}

const isTransientSourceStatusError = (
  error: unknown
): { transient: boolean; message: string } => {
  const status = (error as { status?: number } | null)?.status
  const message =
    error instanceof Error ? error.message : String(error ?? "Unknown error")
  const transient =
    status === 0 ||
    status === 404 ||
    status === 408 ||
    status === 429 ||
    status === 502 ||
    status === 503 ||
    status === 504 ||
    /network|timeout|abort/i.test(message)

  return { transient, message }
}

const WorkspacePlaygroundSkeleton: React.FC<{ isMobile: boolean }> = ({
  isMobile
}) => (
  <div
    data-testid="workspace-playground-skeleton"
    className="flex h-full flex-col bg-bg px-3 py-3"
  >
    <div className="border-b border-border pb-3">
      <Skeleton.Input active size="small" className="w-[220px] max-w-full" />
    </div>
    {isMobile ? (
      <div className="flex min-h-0 flex-1 flex-col gap-3 pt-3">
        <div className="grid grid-cols-3 gap-2">
          <Skeleton.Button active size="small" block />
          <Skeleton.Button active size="small" block />
          <Skeleton.Button active size="small" block />
        </div>
        <Skeleton active paragraph={{ rows: 8 }} title={false} />
      </div>
    ) : (
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 pt-3 lg:grid-cols-[280px_1fr_320px]">
        <Skeleton active paragraph={{ rows: 9 }} title={false} />
        <Skeleton active paragraph={{ rows: 10 }} title={false} />
        <Skeleton active paragraph={{ rows: 8 }} title={false} />
      </div>
    )}
  </div>
)

type WorkspacePlaygroundErrorBoundaryState = {
  hasError: boolean
}

class WorkspacePlaygroundErrorBoundary extends React.Component<
  React.PropsWithChildren,
  WorkspacePlaygroundErrorBoundaryState
> {
  state: WorkspacePlaygroundErrorBoundaryState = { hasError: false }

  static getDerivedStateFromError(): WorkspacePlaygroundErrorBoundaryState {
    return { hasError: true }
  }

  componentDidCatch(error: unknown): void {
    // Surface in console for debugging while showing a recoverable fallback UI.
    console.error("WorkspacePlayground render error", error)
  }

  handleReload = () => {
    if (typeof window !== "undefined") {
      window.location.reload()
    }
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children
    }

    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="w-full max-w-md rounded-lg border border-border bg-surface p-5 text-center shadow-card">
          <h2 className="text-base font-semibold text-text">
            Something went wrong
          </h2>
          <p className="mt-2 text-sm text-text-muted">
            The workspace hit an unexpected error. Reload to recover.
          </p>
          <button
            type="button"
            onClick={this.handleReload}
            className="mt-4 rounded bg-primary px-3 py-1.5 text-sm font-medium text-white transition hover:opacity-90"
            data-testid="workspace-reload-button"
          >
            Reload workspace
          </button>
        </div>
      </div>
    )
  }
}

/**
 * WorkspacePlayground - NotebookLM-style three-pane research interface
 *
 * Layout at different breakpoints:
 * - lg+ (1024px+): Full three-pane layout
 * - md (768-1023px): Chat main, Sources/Studio as slide-out drawers
 * - sm (<768px): Bottom tab navigation between panes
 *
 * Features:
 * - Sources Pane (left): Add and manage research sources
 * - Chat Pane (middle): RAG-powered conversation with selected sources
 * - Studio Pane (right): Generate outputs (summaries, quizzes, flashcards, etc.)
 */
const WorkspacePlaygroundBody: React.FC = () => {
  const { t } = useTranslation(["playground", "option", "common"])
  const isMobile = useMobile()

  // Mobile drawer state
  const [leftDrawerOpen, setLeftDrawerOpen] = React.useState(false)
  const [rightDrawerOpen, setRightDrawerOpen] = React.useState(false)

  // Mobile tab state
  const [activeTab, setActiveTab] = React.useState<WorkspaceTabKey>("chat")

  // Global search state
  const [globalSearchOpen, setGlobalSearchOpen] = React.useState(false)
  const [globalSearchQuery, setGlobalSearchQuery] = React.useState("")
  const [activeSearchResultIndex, setActiveSearchResultIndex] = React.useState(0)
  const globalSearchInputRef = React.useRef<InputRef | null>(null)

  // Workspace switch transition cue state
  const [showWorkspaceTransitionCue, setShowWorkspaceTransitionCue] =
    React.useState(false)
  const previousWorkspaceIdRef = React.useRef<string | null>(null)
  const workspaceTransitionTimerRef = React.useRef<number | null>(null)
  const [showStorageQuotaWarning, setShowStorageQuotaWarning] =
    React.useState(false)
  const [showCrossTabSyncWarning, setShowCrossTabSyncWarning] =
    React.useState(false)
  const lastCrossTabSyncWarningRef = React.useRef(0)

  // Workspace store
  const workspaceId = useWorkspaceStore((s) => s.workspaceId)
  const initializeWorkspace = useWorkspaceStore((s) => s.initializeWorkspace)
  const createNewWorkspace = useWorkspaceStore((s) => s.createNewWorkspace)
  const addSources = useWorkspaceStore((s) => s.addSources)
  const setSelectedSourceIds = useWorkspaceStore((s) => s.setSelectedSourceIds)
  const captureToCurrentNote = useWorkspaceStore((s) => s.captureToCurrentNote)
  const clearCurrentNote = useWorkspaceStore((s) => s.clearCurrentNote)
  const selectedSourceIds = useWorkspaceStore((s) => s.selectedSourceIds)
  const generatedArtifacts = useWorkspaceStore((s) => s.generatedArtifacts)
  const leftPaneCollapsed = useWorkspaceStore((s) => s.leftPaneCollapsed)
  const rightPaneCollapsed = useWorkspaceStore((s) => s.rightPaneCollapsed)
  const setLeftPaneCollapsed = useWorkspaceStore((s) => s.setLeftPaneCollapsed)
  const setRightPaneCollapsed = useWorkspaceStore((s) => s.setRightPaneCollapsed)
  const sources = useWorkspaceStore((s) => s.sources)
  const currentNote = useWorkspaceStore((s) => s.currentNote)
  const workspaceChatSessions = useWorkspaceStore((s) => s.workspaceChatSessions)
  const focusSourceById = useWorkspaceStore((s) => s.focusSourceById)
  const focusChatMessageById = useWorkspaceStore((s) => s.focusChatMessageById)
  const focusWorkspaceNote = useWorkspaceStore((s) => s.focusWorkspaceNote)
  const setSourceStatusByMediaId = useWorkspaceStore(
    (s) => s.setSourceStatusByMediaId
  )
  const storeHydrated = useWorkspaceStore((s) => s.storeHydrated)
  const isStoreHydrated = storeHydrated !== false
  const sourceStatusFailureRef = React.useRef<Record<number, number>>({})

  const leftPaneOpen = !leftPaneCollapsed
  const rightPaneOpen = !rightPaneCollapsed

  const workspaceChatMessages = React.useMemo(
    () => (workspaceId ? workspaceChatSessions[workspaceId]?.messages || [] : []),
    [workspaceChatSessions, workspaceId]
  )

  const globalSearchResults = React.useMemo(
    () =>
      buildWorkspaceGlobalSearchResults({
        query: globalSearchQuery,
        sources,
        chatMessages: workspaceChatMessages,
        currentNote
      }),
    [currentNote, globalSearchQuery, sources, workspaceChatMessages]
  )

  const processingMediaIds = React.useMemo(
    () =>
      sources
        .filter((source) => (source.status || "ready") === "processing")
        .map((source) => source.mediaId),
    [sources]
  )

  const closeGlobalSearch = React.useCallback(() => {
    setGlobalSearchOpen(false)
    setGlobalSearchQuery("")
    setActiveSearchResultIndex(0)
  }, [])

  const focusWorkspacePane = React.useCallback(
    (pane: WorkspaceTabKey) => {
      if (pane === "sources") {
        if (isMobile) {
          setActiveTab("sources")
        } else if (isDesktopLayout()) {
          setLeftPaneCollapsed(false)
        } else {
          setLeftDrawerOpen(true)
        }

        window.setTimeout(() => {
          const panel = document.getElementById("workspace-sources-panel")
          const firstFocusable = panel?.querySelector<HTMLElement>(
            "button, input, textarea, [tabindex]:not([tabindex='-1'])"
          )
          firstFocusable?.focus()
        }, 0)
        return
      }

      if (pane === "studio") {
        if (isMobile) {
          setActiveTab("studio")
        } else if (isDesktopLayout()) {
          setRightPaneCollapsed(false)
        } else {
          setRightDrawerOpen(true)
        }

        window.setTimeout(() => {
          const panel = document.getElementById("workspace-studio-panel")
          const firstFocusable = panel?.querySelector<HTMLElement>(
            "button, input, textarea, [tabindex]:not([tabindex='-1'])"
          )
          firstFocusable?.focus()
        }, 0)
        return
      }

      if (isMobile) {
        setActiveTab("chat")
      }
      window.setTimeout(() => {
        const chatInput = document.querySelector<HTMLElement>(
          "#workspace-main-content textarea"
        )
        if (chatInput) {
          chatInput.focus()
          return
        }
        const main = document.getElementById("workspace-main-content")
        const firstFocusable = main?.querySelector<HTMLElement>(
          "button, input, textarea, [tabindex]:not([tabindex='-1'])"
        )
        firstFocusable?.focus()
      }, 0)
    },
    [isMobile, setLeftPaneCollapsed, setRightPaneCollapsed]
  )

  const focusSearchResult = React.useCallback(
    (result: WorkspaceGlobalSearchResult) => {
      closeGlobalSearch()

      if (result.domain === "source" && result.sourceId) {
        if (isMobile) {
          setActiveTab("sources")
        } else if (isDesktopLayout()) {
          setLeftPaneCollapsed(false)
        } else {
          setLeftDrawerOpen(true)
        }

        window.setTimeout(() => {
          focusSourceById(result.sourceId!)
        }, 0)
        return
      }

      if (result.domain === "chat" && result.chatMessageId) {
        if (isMobile) {
          setActiveTab("chat")
        }
        window.setTimeout(() => {
          focusChatMessageById(result.chatMessageId!)
        }, 0)
        return
      }

      if (result.domain === "note") {
        if (isMobile) {
          setActiveTab("studio")
        } else if (isDesktopLayout()) {
          setRightPaneCollapsed(false)
        } else {
          setRightDrawerOpen(true)
        }

        window.setTimeout(() => {
          focusWorkspaceNote(result.noteField || "content")
        }, 0)
      }
    },
    [
      closeGlobalSearch,
      focusChatMessageById,
      focusSourceById,
      focusWorkspaceNote,
      isMobile,
      setLeftPaneCollapsed,
      setRightPaneCollapsed
    ]
  )

  const handleSearchInputKeyDown = (
    event: React.KeyboardEvent<HTMLInputElement>
  ) => {
    if (event.key === "ArrowDown") {
      event.preventDefault()
      if (globalSearchResults.length === 0) return
      setActiveSearchResultIndex((prev) =>
        prev + 1 >= globalSearchResults.length ? 0 : prev + 1
      )
      return
    }

    if (event.key === "ArrowUp") {
      event.preventDefault()
      if (globalSearchResults.length === 0) return
      setActiveSearchResultIndex((prev) =>
        prev - 1 < 0 ? globalSearchResults.length - 1 : prev - 1
      )
      return
    }

    if (event.key === "Enter") {
      event.preventDefault()
      const selectedResult = globalSearchResults[activeSearchResultIndex]
      if (selectedResult) {
        focusSearchResult(selectedResult)
      }
    }
  }

  // Initialize workspace on mount if not already initialized — use ref to keep dep stable
  const initRef = React.useRef(initializeWorkspace)
  initRef.current = initializeWorkspace
  useEffect(() => {
    if (!isStoreHydrated) return
    if (!workspaceId) {
      initRef.current()
    }
  }, [isStoreHydrated, workspaceId])

  useEffect(() => {
    if (!workspaceId) return

    let isActive = true

    const applyPrefill = async () => {
      const payload = await consumeWorkspacePlaygroundPrefill()
      if (!payload || !isActive) return
      if (payload.kind !== "knowledge_qa_thread") return

      const sourceCandidates = payload.sources
        .filter((source) => typeof source.mediaId === "number")
        .map((source) => ({
          mediaId: source.mediaId as number,
          title: source.title,
          type: source.type
        }))

      if (sourceCandidates.length > 0) {
        addSources(sourceCandidates)

        const stateAfterAdd = useWorkspaceStore.getState()
        const prefillSourceIds = stateAfterAdd.sources
          .filter((source) =>
            sourceCandidates.some((candidate) => candidate.mediaId === source.mediaId)
          )
          .map((source) => source.id)
        const mergedSelectedIds = new Set([
          ...stateAfterAdd.selectedSourceIds,
          ...prefillSourceIds
        ])
        if (mergedSelectedIds.size > 0) {
          setSelectedSourceIds(Array.from(mergedSelectedIds))
        }
      }

      const noteContent = buildKnowledgeQaSeedNote(payload)
      if (noteContent.trim().length > 0) {
        const titleBase =
          payload.query.trim().length > 0 ? payload.query.trim() : "Knowledge QA import"
        captureToCurrentNote({
          title: `Knowledge QA: ${titleBase.slice(0, 80)}`,
          content: noteContent,
          mode: "append"
        })
      }
    }

    void applyPrefill()

    return () => {
      isActive = false
    }
  }, [addSources, captureToCurrentNote, setSelectedSourceIds, workspaceId])

  useEffect(() => {
    if (typeof window === "undefined") return

    const handleKeyboardShortcut = (event: KeyboardEvent) => {
      const key = event.key.toLowerCase()
      const hasModifier = event.metaKey || event.ctrlKey

      if (hasModifier && key === "k") {
        event.preventDefault()
        setGlobalSearchOpen(true)
        return
      }

      if (hasModifier && !event.shiftKey && key === "1") {
        event.preventDefault()
        focusWorkspacePane("sources")
        return
      }

      if (hasModifier && !event.shiftKey && key === "2") {
        event.preventDefault()
        focusWorkspacePane("chat")
        return
      }

      if (hasModifier && !event.shiftKey && key === "3") {
        event.preventDefault()
        focusWorkspacePane("studio")
        return
      }

      if (hasModifier && event.shiftKey && key === "n") {
        event.preventDefault()
        createNewWorkspace()
        return
      }

      if (hasModifier && !event.shiftKey && key === "n") {
        event.preventDefault()
        const hasNoteContent =
          currentNote.title.trim().length > 0 ||
          currentNote.content.trim().length > 0 ||
          currentNote.keywords.length > 0

        const startNewNote = () => {
          clearCurrentNote()
          focusWorkspacePane("studio")
          window.setTimeout(() => {
            focusWorkspaceNote("title")
          }, 0)
        }

        if (currentNote.isDirty || hasNoteContent) {
          Modal.confirm({
            title: t("playground:studio.newNoteTitle", "Start a new note?"),
            content: t(
              "playground:studio.newNoteMessage",
              "This clears your current note draft."
            ),
            okText: t("playground:studio.newNote", "New note"),
            cancelText: t("common:cancel", "Cancel"),
            onOk: startNewNote
          })
          return
        }

        startNewNote()
        return
      }

      if (event.key === "Escape") {
        event.preventDefault()
        closeGlobalSearch()
      }
    }

    window.addEventListener("keydown", handleKeyboardShortcut)
    return () => {
      window.removeEventListener("keydown", handleKeyboardShortcut)
    }
  }, [
    clearCurrentNote,
    closeGlobalSearch,
    createNewWorkspace,
    currentNote.content,
    currentNote.isDirty,
    currentNote.keywords.length,
    currentNote.title,
    focusWorkspaceNote,
    focusWorkspacePane,
    t
  ])

  useEffect(() => {
    if (typeof window === "undefined") return

    const handleQuotaExceeded = (event: Event) => {
      const customEvent = event as CustomEvent<WorkspaceStorageQuotaEventDetail>
      if (customEvent.detail?.key !== WORKSPACE_STORAGE_KEY) return
      setShowStorageQuotaWarning(true)
    }

    window.addEventListener(
      WORKSPACE_STORAGE_QUOTA_EVENT,
      handleQuotaExceeded as EventListener
    )
    return () => {
      window.removeEventListener(
        WORKSPACE_STORAGE_QUOTA_EVENT,
        handleQuotaExceeded as EventListener
      )
    }
  }, [])

  const surfaceCrossTabSyncWarning = React.useCallback(() => {
    const now = Date.now()
    const shouldShow = shouldSurfaceWorkspaceConflictNotice(
      lastCrossTabSyncWarningRef.current,
      now,
      WORKSPACE_CONFLICT_NOTICE_THROTTLE_MS
    )
    if (!shouldShow) return

    lastCrossTabSyncWarningRef.current = now
    setShowCrossTabSyncWarning(true)
  }, [])

  useEffect(() => {
    if (typeof window === "undefined") return

    const handleStorageEvent = (event: StorageEvent) => {
      if (event.key !== WORKSPACE_STORAGE_KEY) return
      if (event.newValue === event.oldValue) return
      if (event.storageArea && event.storageArea !== window.localStorage) return
      surfaceCrossTabSyncWarning()
    }

    window.addEventListener("storage", handleStorageEvent)
    return () => {
      window.removeEventListener("storage", handleStorageEvent)
    }
  }, [surfaceCrossTabSyncWarning])

  useEffect(() => {
    if (typeof window === "undefined") return
    if (!isWorkspaceBroadcastSyncEnabled()) return
    if (typeof BroadcastChannel === "undefined") return

    const channel = new BroadcastChannel(WORKSPACE_STORAGE_CHANNEL_NAME)
    const handleBroadcastUpdate = (event: MessageEvent<unknown>) => {
      if (!isWorkspaceBroadcastUpdateMessage(event.data)) return
      if (event.data.key !== WORKSPACE_STORAGE_KEY) return
      surfaceCrossTabSyncWarning()
    }

    channel.addEventListener("message", handleBroadcastUpdate)
    return () => {
      channel.removeEventListener("message", handleBroadcastUpdate)
      channel.close()
    }
  }, [surfaceCrossTabSyncWarning])

  useEffect(() => {
    setActiveSearchResultIndex(0)
  }, [globalSearchOpen, globalSearchQuery, globalSearchResults.length])

  useEffect(() => {
    if (!workspaceId) return

    const previousWorkspaceId = previousWorkspaceIdRef.current
    previousWorkspaceIdRef.current = workspaceId

    if (!previousWorkspaceId || previousWorkspaceId === workspaceId) {
      return
    }

    setShowWorkspaceTransitionCue(true)
    if (workspaceTransitionTimerRef.current !== null) {
      window.clearTimeout(workspaceTransitionTimerRef.current)
    }
    workspaceTransitionTimerRef.current = window.setTimeout(() => {
      setShowWorkspaceTransitionCue(false)
      workspaceTransitionTimerRef.current = null
    }, WORKSPACE_SWITCH_TRANSITION_MS)
  }, [workspaceId])

  useEffect(() => {
    if (!isStoreHydrated) return
    if (processingMediaIds.length === 0) return

    let cancelled = false

    const pollStatuses = async () => {
      await Promise.all(
        processingMediaIds.map(async (mediaId) => {
          try {
            const detail = await tldwClient.getMediaDetails(mediaId, {
              include_content: true,
              include_versions: false,
              include_version_content: false
            })
            if (cancelled) return

            if (isMediaLikelyReadyForRag(detail)) {
              setSourceStatusByMediaId(mediaId, "ready")
              delete sourceStatusFailureRef.current[mediaId]
            }
          } catch (error) {
            if (cancelled) return

            const nextFailureCount =
              (sourceStatusFailureRef.current[mediaId] || 0) + 1
            sourceStatusFailureRef.current[mediaId] = nextFailureCount

            const { transient, message } = isTransientSourceStatusError(error)
            if (!transient && nextFailureCount >= 2) {
              setSourceStatusByMediaId(mediaId, "error", message)
              delete sourceStatusFailureRef.current[mediaId]
            }
          }
        })
      )
    }

    void pollStatuses()
    const timer = window.setInterval(
      () => void pollStatuses(),
      WORKSPACE_SOURCE_STATUS_POLL_INTERVAL_MS
    )
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [isStoreHydrated, processingMediaIds, setSourceStatusByMediaId])

  useEffect(() => {
    return () => {
      if (workspaceTransitionTimerRef.current !== null) {
        window.clearTimeout(workspaceTransitionTimerRef.current)
      }
    }
  }, [])

  const handleToggleLeftPane = () => {
    if (isMobile) {
      setLeftDrawerOpen(!leftDrawerOpen)
    } else {
      setLeftPaneCollapsed(leftPaneOpen)
    }
  }

  const handleToggleRightPane = () => {
    if (isMobile) {
      setRightDrawerOpen(!rightDrawerOpen)
    } else {
      setRightPaneCollapsed(rightPaneOpen)
    }
  }

  const handleReloadWorkspaceFromSyncWarning = () => {
    if (typeof window !== "undefined") {
      try {
        window.location.reload()
      } catch (error) {
        console.warn("Workspace reload unavailable", error)
      }
    }
  }

  const getSearchDomainLabel = (domain: WorkspaceGlobalSearchResult["domain"]) => {
    switch (domain) {
      case "source":
        return t("playground:search.sources", "Sources")
      case "chat":
        return t("playground:search.chat", "Chat")
      case "note":
        return t("playground:search.notes", "Notes")
      default:
        return domain
    }
  }

  // Mobile tab items with badges
  const mobileTabItems = [
    {
      key: "sources",
      label: (
        <span className="flex items-center gap-1.5">
          <FileText className="h-4 w-4" />
          <span>{t("playground:sources.title", "Sources")}</span>
          {selectedSourceIds.length > 0 && (
            <span className="ml-1 rounded-full border border-border bg-surface2 px-1.5 py-0.5 text-xs text-text">
              {selectedSourceIds.length}
            </span>
          )}
        </span>
      ),
      children: <SourcesPane />
    },
    {
      key: "chat",
      label: (
        <span className="flex items-center gap-1.5">
          <MessageSquare className="h-4 w-4" />
          <span>{t("playground:chat.title", "Chat")}</span>
        </span>
      ),
      children: <ChatPane />
    },
    {
      key: "studio",
      label: (
        <span className="flex items-center gap-1.5">
          <Sparkles className="h-4 w-4" />
          <span>{t("playground:studio.title", "Studio")}</span>
          {generatedArtifacts.length > 0 && (
            <span className="ml-1 rounded-full border border-border bg-surface2 px-1.5 py-0.5 text-xs text-text">
              {generatedArtifacts.length}
            </span>
          )}
        </span>
      ),
      children: <StudioPane />
    }
  ]

  if (!isStoreHydrated) {
    return <WorkspacePlaygroundSkeleton isMobile={isMobile} />
  }

  return (
    <div className="relative flex h-full flex-col bg-bg text-text">
      <a
        href="#workspace-main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-2 focus:z-[60] focus:rounded focus:bg-surface focus:px-3 focus:py-1.5 focus:text-sm focus:shadow-card"
      >
        {t("playground:workspace.skipToMain", "Skip to chat content")}
      </a>
      <a
        href="#workspace-sources-panel"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-12 focus:z-[60] focus:rounded focus:bg-surface focus:px-3 focus:py-1.5 focus:text-sm focus:shadow-card"
      >
        {t("playground:workspace.skipToSources", "Skip to sources panel")}
      </a>
      <a
        href="#workspace-studio-panel"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-[5.5rem] focus:z-[60] focus:rounded focus:bg-surface focus:px-3 focus:py-1.5 focus:text-sm focus:shadow-card"
      >
        {t("playground:workspace.skipToStudio", "Skip to studio panel")}
      </a>

      {(showStorageQuotaWarning || showCrossTabSyncWarning) && (
        <div className="space-y-2 border-b border-border bg-surface px-3 py-2">
          {showStorageQuotaWarning && (
            <div
              data-testid="workspace-storage-quota-banner"
              className="flex flex-wrap items-center justify-between gap-2 rounded border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-text"
              role="status"
              aria-live="polite"
            >
              <span>
                {t(
                  "playground:workspace.storageQuotaExceeded",
                  "Workspace data is too large to save locally. Delete older outputs or sources to reduce size."
                )}
              </span>
              <button
                type="button"
                className="rounded border border-border px-2 py-1 text-xs font-medium hover:bg-surface2"
                onClick={() => setShowStorageQuotaWarning(false)}
              >
                {t("common:dismiss", "Dismiss")}
              </button>
            </div>
          )}

          {showCrossTabSyncWarning && (
            <div
              data-testid="workspace-storage-sync-banner"
              className="flex flex-wrap items-center justify-between gap-2 rounded border border-primary/40 bg-primary/10 px-3 py-2 text-sm text-text"
              role="alert"
            >
              <span>
                {t(
                  "playground:workspace.externalUpdate",
                  "This workspace changed in another tab. Reload to view the latest state."
                )}
              </span>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  className="rounded border border-primary/40 bg-primary px-2 py-1 text-xs font-medium text-white hover:opacity-90"
                  onClick={handleReloadWorkspaceFromSyncWarning}
                >
                  {t("common:reload", "Reload")}
                </button>
                <button
                  type="button"
                  className="rounded border border-border px-2 py-1 text-xs font-medium hover:bg-surface2"
                  onClick={() => setShowCrossTabSyncWarning(false)}
                >
                  {t("common:later", "Later")}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {isMobile ? (
        <>
          <WorkspaceHeader
            leftPaneOpen={false}
            rightPaneOpen={false}
            onToggleLeftPane={handleToggleLeftPane}
            onToggleRightPane={handleToggleRightPane}
            hideToggles
          />

          <Tabs
            activeKey={activeTab}
            onChange={(key) => setActiveTab(key as WorkspaceTabKey)}
            items={mobileTabItems}
            centered
            className="flex-1 [&_.ant-tabs-content]:h-full [&_.ant-tabs-content-holder]:flex-1 [&_.ant-tabs-tabpane]:h-full"
            tabBarStyle={{ marginBottom: 0, borderBottom: "1px solid var(--border)" }}
          />
        </>
      ) : (
        <>
          <WorkspaceHeader
            leftPaneOpen={!!leftPaneOpen}
            rightPaneOpen={!!rightPaneOpen}
            onToggleLeftPane={handleToggleLeftPane}
            onToggleRightPane={handleToggleRightPane}
          />

          <div className="flex min-h-0 flex-1">
            {leftPaneOpen && (
              <aside
                id="workspace-sources-panel"
                role="complementary"
                aria-label={t("playground:workspace.sourcesPanel", "Sources panel")}
                className="hidden w-72 shrink-0 border-r border-border bg-surface lg:flex lg:flex-col"
              >
                <SourcesPane onHide={() => setLeftPaneCollapsed(true)} />
              </aside>
            )}

            <Drawer
              title={
                <span className="flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  {t("playground:sources.title", "Sources")}
                </span>
              }
              placement="left"
              onClose={() => setLeftDrawerOpen(false)}
              open={leftDrawerOpen}
              mask={false}
              className="lg:hidden"
              styles={{ wrapper: { width: 320 }, body: { padding: 0 } }}
            >
              <SourcesPane />
            </Drawer>

            <main
              id="workspace-main-content"
              className="flex min-w-0 flex-1 flex-col"
            >
              <ChatPane />
            </main>

            {rightPaneOpen && (
              <aside
                id="workspace-studio-panel"
                role="complementary"
                aria-label={t("playground:workspace.studioPanel", "Studio panel")}
                className="hidden w-80 shrink-0 border-l border-border bg-surface lg:flex lg:flex-col"
              >
                <StudioPane onHide={() => setRightPaneCollapsed(true)} />
              </aside>
            )}

            <Drawer
              title={
                <span className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4" />
                  {t("playground:studio.title", "Studio")}
                </span>
              }
              placement="right"
              onClose={() => setRightDrawerOpen(false)}
              open={rightDrawerOpen}
              mask={false}
              className="lg:hidden"
              styles={{ wrapper: { width: 360 }, body: { padding: 0 } }}
            >
              <StudioPane />
            </Drawer>
          </div>
        </>
      )}

      <Modal
        title={
          <span className="flex items-center gap-2 text-base">
            <Search className="h-4 w-4" />
            {t("playground:search.title", "Search workspace")}
          </span>
        }
        open={globalSearchOpen}
        onCancel={closeGlobalSearch}
        footer={null}
        width={680}
        destroyOnHidden
        afterOpenChange={(open) => {
          if (!open) return
          window.setTimeout(() => {
            globalSearchInputRef.current?.focus()
          }, 0)
        }}
      >
        <div className="space-y-3">
          <Input
            ref={globalSearchInputRef}
            value={globalSearchQuery}
            onChange={(event) => setGlobalSearchQuery(event.target.value)}
            onKeyDown={handleSearchInputKeyDown}
            placeholder={t(
              "playground:search.placeholder",
              "Search sources, chat, and notes..."
            )}
            prefix={<Search className="h-4 w-4 text-text-muted" />}
            suffix={
              <span className="hidden items-center gap-0.5 text-xs text-text-muted sm:flex">
                <Command className="h-3 w-3" />K
              </span>
            }
          />
          <p className="text-xs text-text-muted">
            {t(
              "playground:search.hint",
              "Tip: use source:, chat:, or note: to filter results."
            )}
          </p>

          <div className="custom-scrollbar max-h-[360px] space-y-1 overflow-y-auto rounded-lg border border-border p-1">
            {globalSearchResults.length === 0 ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={
                  <span className="text-text-muted">
                    {globalSearchQuery.trim()
                      ? t(
                          "playground:search.noResults",
                          "No matching sources, messages, or notes."
                        )
                      : t(
                          "playground:search.empty",
                          "Start typing to search this workspace."
                        )}
                  </span>
                }
              />
            ) : (
              globalSearchResults.map((result, index) => {
                const isActive = index === activeSearchResultIndex
                return (
                  <button
                    key={result.id}
                    type="button"
                    onClick={() => focusSearchResult(result)}
                    className={`w-full rounded-md border px-3 py-2 text-left transition ${
                      isActive
                        ? "border-primary/40 bg-primary/10"
                        : "border-border hover:bg-surface2"
                    }`}
                    aria-selected={isActive}
                  >
                    <div className="mb-0.5 flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium text-text">
                        {result.title}
                      </span>
                      <span className="shrink-0 text-[11px] font-medium uppercase tracking-wide text-text-muted">
                        {getSearchDomainLabel(result.domain)}
                      </span>
                    </div>
                    <p className="truncate text-xs text-text-muted">{result.subtitle}</p>
                    {result.snippet && (
                      <p className="mt-1 line-clamp-2 text-xs text-text-subtle">
                        {result.snippet}
                      </p>
                    )}
                  </button>
                )
              })
            )}
          </div>
        </div>
      </Modal>

      {showWorkspaceTransitionCue && (
        <div
          data-testid="workspace-switch-transition"
          className="pointer-events-none absolute inset-0 z-50 flex items-center justify-center bg-bg/60 backdrop-blur-[1px]"
        >
          <div className="rounded-md border border-border bg-surface px-4 py-2 text-sm text-text shadow-card">
            <span className="mr-2 inline-block h-3.5 w-3.5 animate-spin rounded-full border border-primary border-t-transparent align-[-2px]" />
            {t("playground:workspace.switching", "Switching workspace...")}
          </div>
        </div>
      )}
    </div>
  )
}

export const WorkspacePlayground: React.FC = () => (
  <WorkspacePlaygroundErrorBoundary>
    <WorkspacePlaygroundBody />
  </WorkspacePlaygroundErrorBoundary>
)

export default WorkspacePlayground
