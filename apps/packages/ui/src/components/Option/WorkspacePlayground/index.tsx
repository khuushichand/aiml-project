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
export const WorkspacePlayground: React.FC = () => {
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

  // Workspace store
  const workspaceId = useWorkspaceStore((s) => s.workspaceId)
  const initializeWorkspace = useWorkspaceStore((s) => s.initializeWorkspace)
  const addSources = useWorkspaceStore((s) => s.addSources)
  const setSelectedSourceIds = useWorkspaceStore((s) => s.setSelectedSourceIds)
  const captureToCurrentNote = useWorkspaceStore((s) => s.captureToCurrentNote)
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

      if (event.key === "Escape" && globalSearchOpen) {
        event.preventDefault()
        closeGlobalSearch()
      }
    }

    window.addEventListener("keydown", handleKeyboardShortcut)
    return () => {
      window.removeEventListener("keydown", handleKeyboardShortcut)
    }
  }, [closeGlobalSearch, globalSearchOpen])

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
            <span className="ml-1 rounded-full bg-primary px-1.5 py-0.5 text-xs text-white">
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
            <span className="ml-1 rounded-full bg-success px-1.5 py-0.5 text-xs text-white">
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
              <aside className="hidden w-72 shrink-0 border-r border-border bg-surface lg:flex lg:flex-col">
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

            <main className="flex min-w-0 flex-1 flex-col">
              <ChatPane />
            </main>

            {rightPaneOpen && (
              <aside className="hidden w-80 shrink-0 border-l border-border bg-surface lg:flex lg:flex-col">
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

export default WorkspacePlayground
