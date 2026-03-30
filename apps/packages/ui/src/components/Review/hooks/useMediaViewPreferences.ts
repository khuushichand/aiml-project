import { useState, useCallback, useEffect, useMemo, useRef } from 'react'
import { useStorage } from '@plasmohq/storage/hook'
import { Storage } from '@plasmohq/storage'
import { safeStorageSerde } from '@/utils/safe-storage'
import { tldwClient } from '@/services/tldw/TldwApiClient'
import { useConnectionState } from '@/hooks/useConnectionState'
import {
  useMediaAnalysisDisplayModeSelector,
  useMediaNavigationGeneratedFallbackDefault,
  useMediaNavigationPanel,
  useMediaRichRendering
} from '@/hooks/useFeatureFlags'
import {
  buildMediaNavigationScopeKey,
  coerceMediaNavigationFormat,
  type MediaNavigationFormat
} from '@/utils/media-navigation-scope'
import {
  hashMediaNavigationScopeKey,
} from '@/utils/media-navigation-telemetry'
import { normalizeRequestedMediaRenderMode } from '@/utils/media-render-mode'

const MEDIA_NAVIGATION_PANEL_VISIBLE_STORAGE_KEY =
  'media:navigation:panelVisible'
const MEDIA_NAVIGATION_GENERATED_FALLBACK_STORAGE_KEY =
  'media:navigation:includeGeneratedFallback'
const MEDIA_SIDEBAR_COLLAPSED_STORAGE_KEY = 'media:sidebar:collapsed'
const MEDIA_LIBRARY_TOOLS_COLLAPSED_STORAGE_KEY = 'media:tools:collapsed'
const MEDIA_RESULTS_MIN_VISIBLE_ROWS = 5
const MEDIA_RESULTS_MAX_VISIBLE_ROWS = 20
const MEDIA_RESULTS_ROW_HEIGHT_STANDARD_PX = 68
const MEDIA_RESULTS_ROW_HEIGHT_COMPACT_PX = 52
const MEDIA_RESULTS_HEADER_PX = 42
const MEDIA_RESULTS_FOOTER_PX = 98
const MEDIA_RESULTS_CONTENT_HEIGHT_STEP_PX = 120
const MEDIA_RESULTS_CONTENT_CHARS_STEP = 1_300
const MEDIA_SIDEBAR_CHROME_BUFFER_PX = 420
const MEDIA_SIDEBAR_MIN_HEIGHT_PX = 960
const MEDIA_SIDEBAR_END_BUFFER_PX = 15

export function useMediaViewPreferences() {
  const { serverUrl } = useConnectionState()
  const [mediaNavigationPanelEnabled] = useMediaNavigationPanel()
  const [includeGeneratedFallbackDefault] =
    useMediaNavigationGeneratedFallbackDefault()
  const [mediaRichRenderingEnabled] = useMediaRichRendering()
  const [mediaDisplayModeSelectorEnabled] =
    useMediaAnalysisDisplayModeSelector()

  const [sidebarCollapsed, setSidebarCollapsed] = useStorage<boolean>(
    MEDIA_SIDEBAR_COLLAPSED_STORAGE_KEY,
    false
  )
  const [libraryToolsCollapsed, setLibraryToolsCollapsed] = useStorage<boolean>(
    MEDIA_LIBRARY_TOOLS_COLLAPSED_STORAGE_KEY,
    true
  )
  const [navigationPanelVisible, setNavigationPanelVisible] = useStorage<boolean>(
    MEDIA_NAVIGATION_PANEL_VISIBLE_STORAGE_KEY,
    true
  )
  const [includeGeneratedFallback, setIncludeGeneratedFallback] =
    useStorage<boolean>(
      MEDIA_NAVIGATION_GENERATED_FALLBACK_STORAGE_KEY,
      includeGeneratedFallbackDefault
    )
  const [resultsViewMode, setResultsViewMode] = useStorage<'standard' | 'compact'>(
    'media:results:viewMode',
    'standard'
  )
  const [navigationDisplayMode, setNavigationDisplayMode] =
    useState<MediaNavigationFormat>('auto')
  const [navigationDisplayModeLoaded, setNavigationDisplayModeLoaded] =
    useState(false)
  const [navigationScopeAuth, setNavigationScopeAuth] = useState<{
    authMode: string | null
    accessToken: string | null
  }>({
    authMode: null,
    accessToken: null
  })
  const [jumpToCollapsed, setJumpToCollapsed] = useState(true)

  const [contentHeight, setContentHeight] = useState<number>(0)
  const contentDivRef = useRef<HTMLDivElement | null>(null)
  const contentMeasureRafRef = useRef<number | null>(null)
  const contentResizeObserverRef = useRef<ResizeObserver | null>(null)

  const sidebarCollapsedValue = sidebarCollapsed === true
  const libraryToolsCollapsedValue = libraryToolsCollapsed !== false
  const navigationPanelVisibleValue = navigationPanelVisible !== false
  const includeGeneratedFallbackValue = includeGeneratedFallback !== false

  const navigationScopeKey = useMemo(
    () =>
      buildMediaNavigationScopeKey({
        serverUrl: serverUrl ?? undefined,
        authMode: navigationScopeAuth.authMode,
        accessToken: navigationScopeAuth.accessToken
      }),
    [navigationScopeAuth.accessToken, navigationScopeAuth.authMode, serverUrl]
  )
  const navigationScopeKeyHash = useMemo(
    () => hashMediaNavigationScopeKey(navigationScopeKey),
    [navigationScopeKey]
  )
  const navigationDisplayModeStorageKey = useMemo(
    () => `tldw:media:navigation:displayMode:${navigationScopeKey}`,
    [navigationScopeKey]
  )

  // Load auth scope
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const cfg = await tldwClient.getConfig().catch(() => null)
      if (cancelled) return
      setNavigationScopeAuth({
        authMode: cfg?.authMode || null,
        accessToken: cfg?.accessToken || null
      })
    })()
    return () => {
      cancelled = true
    }
  }, [serverUrl])

  // Load navigation display mode from storage
  useEffect(() => {
    let cancelled = false
    setNavigationDisplayModeLoaded(false)
    ;(async () => {
      try {
        const storage = new Storage({ area: 'local', serde: safeStorageSerde } as any)
        const persisted = await storage.get(navigationDisplayModeStorageKey)
        if (cancelled) return
        const parsed = coerceMediaNavigationFormat(persisted, 'auto')
        setNavigationDisplayMode(
          normalizeRequestedMediaRenderMode(parsed, mediaRichRenderingEnabled)
        )
      } catch {
        if (!cancelled) {
          setNavigationDisplayMode('auto')
        }
      } finally {
        if (!cancelled) {
          setNavigationDisplayModeLoaded(true)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [mediaRichRenderingEnabled, navigationDisplayModeStorageKey])

  // Downgrade HTML mode when rich rendering is disabled
  useEffect(() => {
    if (!mediaRichRenderingEnabled && navigationDisplayMode === 'html') {
      setNavigationDisplayMode('auto')
    }
  }, [mediaRichRenderingEnabled, navigationDisplayMode])

  // Persist navigation display mode
  useEffect(() => {
    if (!navigationDisplayModeLoaded) return
    const persistedMode = normalizeRequestedMediaRenderMode(
      navigationDisplayMode,
      mediaRichRenderingEnabled
    )
    const storage = new Storage({ area: 'local', serde: safeStorageSerde } as any)
    void storage.set(navigationDisplayModeStorageKey, persistedMode).catch(() => {})
  }, [
    mediaRichRenderingEnabled,
    navigationDisplayMode,
    navigationDisplayModeLoaded,
    navigationDisplayModeStorageKey
  ])

  // Content measurement
  const clearContentMeasurement = useCallback(() => {
    if (contentMeasureRafRef.current != null) {
      cancelAnimationFrame(contentMeasureRafRef.current)
      contentMeasureRafRef.current = null
    }
    if (contentResizeObserverRef.current) {
      contentResizeObserverRef.current.disconnect()
      contentResizeObserverRef.current = null
    }
  }, [])

  const scheduleContentMeasure = useCallback(() => {
    const node = contentDivRef.current
    if (!node) return
    if (contentMeasureRafRef.current != null) {
      cancelAnimationFrame(contentMeasureRafRef.current)
    }
    contentMeasureRafRef.current = requestAnimationFrame(() => {
      const activeNode = contentDivRef.current
      if (!activeNode) return
      const measuredHeight = Math.max(activeNode.scrollHeight, activeNode.clientHeight)
      setContentHeight((prev) => (prev === measuredHeight ? prev : measuredHeight))
    })
  }, [])

  const contentRef = useCallback((node: HTMLDivElement | null) => {
    clearContentMeasurement()
    contentDivRef.current = node
    if (!node) return
    scheduleContentMeasure()
    if (typeof window === 'undefined' || typeof window.ResizeObserver !== 'function') {
      return
    }
    const observer = new ResizeObserver(() => {
      scheduleContentMeasure()
    })
    observer.observe(node)
    contentResizeObserverRef.current = observer
  }, [clearContentMeasurement, scheduleContentMeasure])

  useEffect(() => {
    return () => {
      clearContentMeasurement()
    }
  }, [clearContentMeasurement])

  // Compute sidebar dimensions
  const computeSidebarDimensions = useCallback((
    pageSize: number,
    selectedContent: string
  ) => {
    const sidebarTargetVisibleRows = (() => {
      const maxRowsFromPageSize = Math.min(
        MEDIA_RESULTS_MAX_VISIBLE_ROWS,
        Math.max(MEDIA_RESULTS_MIN_VISIBLE_ROWS, pageSize)
      )
      const rowsFromMeasuredHeight =
        contentHeight > 0
          ? Math.ceil(contentHeight / MEDIA_RESULTS_CONTENT_HEIGHT_STEP_PX)
          : 0
      const rowsFromContentLength =
        selectedContent.trim().length > 0
          ? Math.ceil(selectedContent.trim().length / MEDIA_RESULTS_CONTENT_CHARS_STEP)
          : 0
      const dynamicRows = Math.max(rowsFromMeasuredHeight, rowsFromContentLength)
      return Math.min(
        maxRowsFromPageSize,
        Math.max(MEDIA_RESULTS_MIN_VISIBLE_ROWS, dynamicRows)
      )
    })()

    const sidebarResultsRowHeightPx =
      resultsViewMode === 'compact'
        ? MEDIA_RESULTS_ROW_HEIGHT_COMPACT_PX
        : MEDIA_RESULTS_ROW_HEIGHT_STANDARD_PX
    const computedSidebarResultsListMinHeightPx =
      MEDIA_RESULTS_HEADER_PX + sidebarTargetVisibleRows * sidebarResultsRowHeightPx
    const computedSidebarResultsPanelMinHeightPx =
      computedSidebarResultsListMinHeightPx + MEDIA_RESULTS_FOOTER_PX
    const mediaPageMinHeightPx = Math.max(
      MEDIA_SIDEBAR_MIN_HEIGHT_PX,
      MEDIA_SIDEBAR_CHROME_BUFFER_PX + computedSidebarResultsPanelMinHeightPx
    )

    return {
      sidebarResultsListMinHeightPx: computedSidebarResultsListMinHeightPx,
      sidebarResultsPanelMinHeightPx: computedSidebarResultsPanelMinHeightPx,
      mediaPageMinHeightPx
    }
  }, [contentHeight, resultsViewMode])

  return {
    // Feature flags
    mediaNavigationPanelEnabled,
    mediaRichRenderingEnabled,
    mediaDisplayModeSelectorEnabled,
    // Sidebar
    sidebarCollapsed, setSidebarCollapsed,
    sidebarCollapsedValue,
    libraryToolsCollapsed, setLibraryToolsCollapsed,
    libraryToolsCollapsedValue,
    // Navigation panel
    navigationPanelVisible, setNavigationPanelVisible,
    navigationPanelVisibleValue,
    includeGeneratedFallback, setIncludeGeneratedFallback,
    includeGeneratedFallbackValue,
    // Navigation display
    navigationDisplayMode, setNavigationDisplayMode,
    navigationDisplayModeLoaded,
    navigationScopeKey,
    navigationScopeKeyHash,
    // Results view
    resultsViewMode, setResultsViewMode,
    jumpToCollapsed, setJumpToCollapsed,
    // Content measurement
    contentHeight,
    contentRef,
    scheduleContentMeasure,
    // Dimensions
    computeSidebarDimensions,
    MEDIA_SIDEBAR_END_BUFFER_PX,
  }
}
