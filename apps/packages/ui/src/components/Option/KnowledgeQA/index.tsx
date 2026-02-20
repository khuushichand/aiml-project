/**
 * KnowledgeQA - Research-grade question-answering interface
 *
 * A Perplexity-style Q&A experience combining discoverability with
 * the full power of the RAG pipeline.
 */

import React, { useEffect, useMemo, useRef, useState } from "react"
import { KnowledgeQAProvider, useKnowledgeQA } from "./KnowledgeQAProvider"
import { SettingsPanel } from "./SettingsPanel"
import { ExportDialog } from "./ExportDialog"
import { KnowledgeQALayout } from "./layout/KnowledgeQALayout"
import { useServerOnline } from "@/hooks/useServerOnline"
import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import { useConnectionActions, useConnectionState } from "@/hooks/useConnectionState"
import { WifiOff, AlertCircle } from "lucide-react"
import {
  getRetryCountdownSeconds,
  KNOWLEDGE_QA_RETRY_INTERVAL_MS,
  KNOWLEDGE_QA_RETRY_TICK_MS,
} from "./retryScheduler"
import { useLocation } from "react-router-dom"

function normalizeThreadId(rawValue: string | null | undefined): string | null {
  if (typeof rawValue !== "string") return null
  const candidate = rawValue.trim()
  if (candidate.length === 0) return null
  try {
    const decoded = decodeURIComponent(candidate).trim()
    return decoded.length > 0 ? decoded : null
  } catch {
    return candidate
  }
}

function normalizeShareToken(rawValue: string | null | undefined): string | null {
  if (typeof rawValue !== "string") return null
  const candidate = rawValue.trim()
  if (candidate.length === 0) return null
  try {
    const decoded = decodeURIComponent(candidate).trim()
    return decoded.length > 0 ? decoded : null
  } catch {
    return candidate
  }
}

// Main page component (inner, uses context)
function KnowledgeQAContent() {
  const {
    settingsPanelOpen,
    setSettingsPanelOpen,
    currentThreadId,
    selectThread,
    selectSharedThread,
  } = useKnowledgeQA()
  const [exportDialogOpen, setExportDialogOpen] = useState(false)
  const [retryNowMs, setRetryNowMs] = useState(() => Date.now())
  const routeHydratedThreadRef = useRef<string | null>(null)
  const routeHydratedShareRef = useRef<string | null>(null)
  const location = useLocation()
  const online = useServerOnline(KNOWLEDGE_QA_RETRY_INTERVAL_MS)
  const { capabilities, loading: capabilitiesLoading, refresh: refreshCapabilities } =
    useServerCapabilities()
  const { checkOnce } = useConnectionActions()
  const { isChecking, lastCheckedAt } = useConnectionState()

  // Check if RAG is supported
  const hasRag = capabilities?.hasRag ?? true
  const retryCountdownSeconds = useMemo(
    () =>
      getRetryCountdownSeconds({
        lastAttemptAt: lastCheckedAt,
        now: retryNowMs,
        retryIntervalMs: KNOWLEDGE_QA_RETRY_INTERVAL_MS,
      }),
    [lastCheckedAt, retryNowMs]
  )
  const routeThreadId = useMemo(() => {
    const pathMatch = location.pathname.match(/\/knowledge\/thread\/([^/?#]+)/i)
    if (pathMatch?.[1]) {
      return normalizeThreadId(pathMatch[1])
    }
    const searchParams = new URLSearchParams(location.search)
    return normalizeThreadId(searchParams.get("thread"))
  }, [location.pathname, location.search])
  const routeShareToken = useMemo(() => {
    const pathMatch = location.pathname.match(/\/knowledge\/shared\/([^/?#]+)/i)
    if (pathMatch?.[1]) {
      return normalizeShareToken(pathMatch[1])
    }
    const searchParams = new URLSearchParams(location.search)
    return normalizeShareToken(searchParams.get("share"))
  }, [location.pathname, location.search])

  useEffect(() => {
    if (online) {
      return
    }
    setRetryNowMs(Date.now())
    const interval = window.setInterval(
      () => setRetryNowMs(Date.now()),
      KNOWLEDGE_QA_RETRY_TICK_MS
    )
    return () => window.clearInterval(interval)
  }, [online])

  useEffect(() => {
    if (!routeShareToken) {
      routeHydratedShareRef.current = null
      return
    }
    if (routeHydratedShareRef.current === routeShareToken) {
      return
    }
    routeHydratedShareRef.current = routeShareToken
    void selectSharedThread(routeShareToken)
  }, [routeShareToken, selectSharedThread])

  useEffect(() => {
    if (routeShareToken) {
      routeHydratedThreadRef.current = null
      return
    }
    if (!routeThreadId) {
      routeHydratedThreadRef.current = null
      return
    }
    if (routeHydratedThreadRef.current === routeThreadId) {
      return
    }
    routeHydratedThreadRef.current = routeThreadId
    if (currentThreadId === routeThreadId) {
      return
    }
    void selectThread(routeThreadId)
  }, [currentThreadId, routeShareToken, routeThreadId, selectThread])

  const handleRetryConnection = () => {
    void checkOnce()
  }

  const handleRetryCapabilities = () => {
    void refreshCapabilities()
  }

  // Offline state
  if (!online) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center max-w-md">
          <WifiOff className="w-16 h-16 mx-auto mb-4 text-text-muted" />
          <h2 className="text-xl font-semibold mb-2">Server Offline</h2>
          <p className="text-text-muted mb-3">
            Cannot connect to the server. Please ensure the tldw server is running
            and try again.
          </p>
          <button
            type="button"
            onClick={handleRetryConnection}
            disabled={isChecking}
            className="px-3 py-1.5 rounded-md border border-border bg-surface text-text-subtle hover:bg-hover hover:text-text transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {isChecking ? "Checking connection..." : "Retry connection"}
          </button>
          <p className="mt-2 text-xs text-text-muted">
            Retrying automatically in {retryCountdownSeconds}s...
          </p>
        </div>
      </div>
    )
  }

  // No RAG support
  if (!capabilitiesLoading && !hasRag) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center max-w-md">
          <AlertCircle className="w-16 h-16 mx-auto mb-4 text-text-muted" />
          <h2 className="text-xl font-semibold mb-2">RAG Not Available</h2>
          <p className="text-text-muted mb-2">
            Knowledge search requires the RAG module to be enabled on the server.
          </p>
          <p className="text-text-muted mb-4">
            Configure embedding models and enable RAG in your server setup, then
            restart the server and retry capability detection.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2">
            <button
              type="button"
              onClick={handleRetryCapabilities}
              className="px-3 py-1.5 rounded-md border border-border bg-surface text-text-subtle hover:bg-hover hover:text-text transition-colors"
            >
              Retry capability check
            </button>
            <a
              href="https://github.com/rmusser01/tldw_server2#readme"
              target="_blank"
              rel="noreferrer"
              className="px-3 py-1.5 rounded-md border border-primary/40 bg-primary/10 text-primary hover:bg-primary/15 transition-colors"
            >
              Open setup guide
            </a>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="relative flex h-full">
      <KnowledgeQALayout onExportClick={() => setExportDialogOpen(true)} />

      {/* Settings panel (drawer) */}
      <SettingsPanel
        open={settingsPanelOpen}
        onClose={() => setSettingsPanelOpen(false)}
      />

      {/* Export dialog */}
      <ExportDialog
        open={exportDialogOpen}
        onClose={() => setExportDialogOpen(false)}
      />
    </div>
  )
}

// Export the wrapped component
export function KnowledgeQA() {
  return (
    <KnowledgeQAProvider>
      <KnowledgeQAContent />
    </KnowledgeQAProvider>
  )
}

// Also export individual components for flexibility
export { KnowledgeQAProvider, useKnowledgeQA } from "./KnowledgeQAProvider"
export { SearchBar } from "./SearchBar"
export { AnswerPanel } from "./AnswerPanel"
export { SearchDetailsPanel } from "./SearchDetailsPanel"
export { ConversationThread } from "./ConversationThread"
export { SourceCard } from "./SourceCard"
export { SourceList } from "./SourceList"
export { FollowUpInput } from "./FollowUpInput"
export { HistorySidebar } from "./HistorySidebar"
export { SettingsPanel } from "./SettingsPanel"
export { ExportDialog } from "./ExportDialog"
export { KnowledgeQALayout } from "./layout/KnowledgeQALayout"
export type * from "./types"
