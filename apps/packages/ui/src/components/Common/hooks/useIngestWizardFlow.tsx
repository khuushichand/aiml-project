import React from 'react'
import type { QuickIngestTab, TabBadgeState } from "../QuickIngest/types"
import { useConnectionActions, useConnectionState } from '@/hooks/useConnectionState'
import { ConnectionPhase } from "@/types/connection"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type IngestConnectionStatus =
  | "online"
  | "offline"
  | "unconfigured"
  | "unknown"

// ---------------------------------------------------------------------------
// Deps interface
// ---------------------------------------------------------------------------

export interface UseIngestWizardFlowDeps {
  open: boolean
  running: boolean
  /** Planned count from queue hook */
  plannedCount: number
  /** Common options from options hook */
  common: {
    perform_analysis: boolean
    perform_chunking: boolean
    overwrite_existing: boolean
  }
  advancedValues: Record<string, any>
  hasTypeDefaultChanges: boolean
  lastRunError: string | null
  reviewBeforeStorage: boolean
  storeRemote: boolean
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useIngestWizardFlow(deps: UseIngestWizardFlowDeps) {
  const {
    open,
    running,
    plannedCount,
    common,
    advancedValues,
    hasTypeDefaultChanges,
    lastRunError,
    reviewBeforeStorage,
    storeRemote,
  } = deps

  // ---- tab state ----
  const [activeTab, setActiveTab] = React.useState<QuickIngestTab>('queue')
  const [runNonce, setRunNonce] = React.useState(0)
  const [modalReady, setModalReady] = React.useState(false)

  // Auto-switch to results tab when processing starts
  React.useEffect(() => {
    if (runNonce > 0) {
      setActiveTab('results')
    }
  }, [runNonce])

  // Reset to queue tab when modal opens
  React.useEffect(() => {
    if (open) {
      setActiveTab('queue')
    }
  }, [open])

  // ---- connection state ----
  const { phase, isConnected, serverUrl } = useConnectionState()
  const { checkOnce } = useConnectionActions?.() || {}

  const ingestConnectionStatus: IngestConnectionStatus = React.useMemo(() => {
    if (phase === ConnectionPhase.UNCONFIGURED) return "unconfigured"
    if (phase === ConnectionPhase.SEARCHING) return "unknown"
    if (phase === ConnectionPhase.CONNECTED && isConnected) return "online"
    if (phase === ConnectionPhase.ERROR) return "offline"
    if (!isConnected) return "offline"
    return "unknown"
  }, [phase, isConnected])

  const ingestBlocked = ingestConnectionStatus !== "online"
  const isOnlineForIngest = ingestConnectionStatus === "online"
  const isConfiguring = ingestConnectionStatus === "unknown"

  // Mark modal as ready once we have evaluated connection state at least once
  React.useEffect(() => {
    if (!modalReady) {
      setModalReady(true)
    }
  }, [modalReady, ingestBlocked])

  // When modal opens and we are offline, automatically retry connection
  React.useEffect(() => {
    if (open && ingestBlocked) {
      try { checkOnce?.() } catch {}
    }
  }, [open, ingestBlocked, checkOnce])

  // Allow external callers (e.g., tests) to force a connection check
  React.useEffect(() => {
    const handler = () => {
      try { checkOnce?.() } catch {}
    }
    window.addEventListener("tldw:check-connection", handler)
    return () => window.removeEventListener("tldw:check-connection", handler)
  }, [checkOnce])

  // ---- tab badge state ----
  const tabBadges: TabBadgeState = React.useMemo(() => {
    const optionsModified =
      common.perform_analysis !== true ||
      common.perform_chunking !== true ||
      common.overwrite_existing !== false ||
      hasTypeDefaultChanges ||
      reviewBeforeStorage ||
      !storeRemote ||
      Object.keys(advancedValues || {}).some((k) => advancedValues[k] != null)

    return {
      queueCount: plannedCount,
      optionsModified,
      isProcessing: running,
      hasFailure: !running && Boolean(lastRunError)
    }
  }, [
    plannedCount,
    common,
    advancedValues,
    hasTypeDefaultChanges,
    lastRunError,
    reviewBeforeStorage,
    running,
    storeRemote
  ])

  // ---- connection banner text ----
  let connectionBannerTitle: string | null = null
  let connectionBannerBody: string | null = null

  // Note: the actual i18n labels are computed in the component using t();
  // this hook provides the raw connection state for the component to use.

  // ---- inspector state ----
  const [inspectorOpen, setInspectorOpen] = React.useState<boolean>(false)
  const [hasOpenedInspector, setHasOpenedInspector] = React.useState<boolean>(false)
  const [showInspectorIntro, setShowInspectorIntro] = React.useState<boolean>(true)

  const handleCloseInspector = React.useCallback(() => {
    setInspectorOpen(false)
  }, [])

  // ---- onboarding / intro events ----
  React.useEffect(() => {
    if (!open) return
    window.dispatchEvent(new CustomEvent("tldw:quick-ingest-ready"))
  }, [open])

  return {
    // tab state
    activeTab, setActiveTab,
    runNonce, setRunNonce,
    modalReady,
    // connection
    phase,
    isConnected,
    serverUrl,
    checkOnce,
    ingestConnectionStatus,
    ingestBlocked,
    isOnlineForIngest,
    isConfiguring,
    // badges
    tabBadges,
    // inspector
    inspectorOpen, setInspectorOpen,
    hasOpenedInspector, setHasOpenedInspector,
    showInspectorIntro, setShowInspectorIntro,
    handleCloseInspector,
  }
}
