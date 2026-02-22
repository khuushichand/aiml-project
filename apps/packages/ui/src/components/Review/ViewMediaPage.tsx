import React, { useState, useCallback, useEffect, useMemo, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CheckSquare,
  Square,
  Download,
  Tags,
  Trash2,
  X,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Storage } from '@plasmohq/storage'
import { useStorage } from '@plasmohq/storage/hook'
import { safeStorageSerde } from '@/utils/safe-storage'
import { bgRequest } from '@/services/background-proxy'
import { tldwClient } from '@/services/tldw/TldwApiClient'
import { useServerOnline } from '@/hooks/useServerOnline'
import { useServerCapabilities } from '@/hooks/useServerCapabilities'
import { useConnectionState } from '@/hooks/useConnectionState'
import { useDemoMode } from '@/context/demo-mode'
import { useMessageOption } from '@/hooks/useMessageOption'
import { useAntdMessage } from '@/hooks/useAntdMessage'
import { useUndoNotification } from '@/hooks/useUndoNotification'
import { useDebounce } from '@/hooks/useDebounce'
import FeatureEmptyState from '@/components/Common/FeatureEmptyState'
import { SearchBar } from '@/components/Media/SearchBar'
import { FilterPanel } from '@/components/Media/FilterPanel'
import { ResultsList } from '@/components/Media/ResultsList'
import { ContentViewer } from '@/components/Media/ContentViewer'
import { MediaSectionNavigator } from '@/components/Media/MediaSectionNavigator'
import { Pagination } from '@/components/Media/Pagination'
import { JumpToNavigator } from '@/components/Media/JumpToNavigator'
import { KeyboardShortcutsOverlay } from '@/components/Media/KeyboardShortcutsOverlay'
import { FilterChips } from '@/components/Media/FilterChips'
import { MediaIngestJobsPanel } from '@/components/Media/MediaIngestJobsPanel'
import {
  MediaLibraryStatsPanel,
  type MediaLibraryStorageUsage
} from '@/components/Media/MediaLibraryStatsPanel'
import type { MediaResultItem } from '@/components/Media/types'
import {
  useMediaNavigation
} from '@/hooks/useMediaNavigation'
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
  getMediaNavigationResumeEntry,
  resolveMediaNavigationResumeSelection,
  saveMediaNavigationResumeSelection
} from '@/utils/media-navigation-resume'
import {
  hashMediaNavigationScopeKey,
  type MediaNavigationFallbackKind,
  trackMediaNavigationTelemetry
} from '@/utils/media-navigation-telemetry'
import { normalizeRequestedMediaRenderMode } from '@/utils/media-render-mode'
import { clearSetting, getSetting, setSetting } from '@/services/settings/registry'
import {
  DISCUSS_MEDIA_PROMPT_SETTING,
  LAST_MEDIA_ID_SETTING,
  MEDIA_REVIEW_SELECTION_SETTING
} from '@/services/settings/ui-settings'
import {
  buildMediaSearchPayload,
  DEFAULT_MEDIA_SEARCH_FIELDS,
  hasDefaultMediaSearchFields,
  hasMediaSearchFilters,
  type MediaBoostFields,
  type MediaDateRange,
  type MediaSearchField,
  type MediaSearchMode,
  type MediaSortBy
} from '@/components/Review/mediaSearchRequest'
import {
  buildMetadataSearchPath,
  createMetadataSearchFilter,
  normalizeMetadataSearchFilters,
  type MetadataMatchMode,
  type MetadataSearchFilter,
  validateMetadataSearchFilters
} from '@/components/Review/mediaMetadataSearchRequest'
import {
  isMediaOnly,
  isNotesOnly,
  resolveKindsForTab
} from '@/components/Review/mediaKinds'
import {
  buildMediaPermalinkSearch,
  getMediaPermalinkIdFromSearch,
  normalizeMediaPermalinkId
} from '@/components/Review/mediaPermalink'
import {
  parseMediaFilterParams,
  buildMediaFilterSearch,
  hasMediaFilterParams
} from '@/components/Review/mediaFilterParams'
import { buildFlashcardsGenerateRoute } from "@/services/tldw/flashcards-generate-handoff"
import { downloadBlob } from '@/utils/download-blob'
import {
  getImmediateCachedMediaTypes,
  isMediaTypesCacheFresh,
  MEDIA_TYPES_CACHE_KEY,
  MEDIA_TYPES_CACHE_TTL_MS,
  normalizeMediaTypesCacheRecord,
  seedMediaTypesCache
} from '@/components/Review/mediaTypeCache'

const MEDIA_NAVIGATION_PANEL_VISIBLE_STORAGE_KEY =
  'media:navigation:panelVisible'
const MEDIA_NAVIGATION_GENERATED_FALLBACK_STORAGE_KEY =
  'media:navigation:includeGeneratedFallback'
const MEDIA_SIDEBAR_COLLAPSED_STORAGE_KEY = 'media:sidebar:collapsed'
const MEDIA_LIBRARY_TOOLS_COLLAPSED_STORAGE_KEY = 'media:tools:collapsed'
export const MEDIA_STALE_CHECK_INTERVAL_MS = 30_000
const MEDIA_KEYWORD_ENDPOINT_RETRY_COOLDOWN_MS = 30_000
const MEDIA_COLLECTIONS_STORAGE_KEY = 'media:collections:v1'
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

type MediaCollectionRecord = {
  id: string
  name: string
  itemIds: string[]
  createdAt: string
  updatedAt: string
}

const ViewMediaPage: React.FC = () => {
  const { t } = useTranslation(['review', 'common', 'settings'])
  const navigate = useNavigate()
  const isOnline = useServerOnline()
  const { capabilities, loading: capsLoading } = useServerCapabilities()
  const { demoEnabled } = useDemoMode()

  // Check media support
  const mediaUnsupported = !capsLoading && capabilities && !capabilities.hasMedia

  if (!isOnline && demoEnabled) {
    return (
      <div className="flex h-full items-center justify-center">
        <FeatureEmptyState
          title={t('review:mediaEmpty.offlineTitle', {
            defaultValue: 'Media API not available offline'
          })}
          description={t('review:mediaEmpty.offlineDescription', {
            defaultValue:
              'This feature requires connection to the tldw server. Please check your server connection.'
          })}
          examples={[]}
        />
      </div>
    )
  }

  if (!isOnline) {
    return (
      <div className="flex h-full items-center justify-center">
        <FeatureEmptyState
          title={t('review:mediaEmpty.offlineTitle', {
            defaultValue: 'Server offline'
          })}
          description={t('review:mediaEmpty.offlineDescription', {
            defaultValue: 'Please check your server connection.'
          })}
          examples={[]}
        />
      </div>
    )
  }

  if (isOnline && mediaUnsupported) {
    return (
      <FeatureEmptyState
        title={
          <span className="inline-flex items-center gap-2">
            <span className="rounded-full bg-warn/10 px-2 py-0.5 text-[11px] font-medium text-warn">
              {t('review:mediaEmpty.featureUnavailableBadge', {
                defaultValue: 'Feature unavailable'
              })}
            </span>
            <span>
              {t('review:mediaEmpty.offlineTitle', {
                defaultValue: 'Media API not available on this server'
              })}
            </span>
          </span>
        }
        description={t('review:mediaEmpty.offlineDescription', {
          defaultValue:
            'This workspace depends on Media Review support in your tldw server. You can continue using chat, notes, and other tools while you upgrade to a version that includes Media.'
        })}
        examples={[
          t('review:mediaEmpty.offlineExample1', {
            defaultValue:
              'Open Diagnostics to confirm your server version and available APIs.'
          }),
          t('review:mediaEmpty.offlineExample2', {
            defaultValue: 'After upgrading, reload the extension and return to Media.'
          }),
          t('review:mediaEmpty.offlineTechnicalDetails', {
            defaultValue:
              'Technical details: this tldw server does not advertise the Media endpoints (for example, /api/v1/media and /api/v1/media/search).'
          })
        ]}
        primaryActionLabel={t('settings:healthSummary.diagnostics', {
          defaultValue: 'Open Diagnostics'
        })}
        onPrimaryAction={() => navigate('/settings/health')}
      />
    )
  }

  return <MediaPageContent />
}

const deriveMediaMeta = (m: any): {
  type: string
  created_at?: string
  status?: any
  source?: string | null
  duration?: number | null
  author?: string | null
  published_at?: string | null
  transcription_model?: string | null
  word_count?: number | null
  page_count?: number | null
} => {
  const rawType = m?.type ?? m?.media_type ?? ''
  const type = typeof rawType === 'string' ? rawType.toLowerCase().trim() : ''
  const status =
    m?.status ??
    m?.ingest_status ??
    m?.ingestStatus ??
    m?.processing_state ??
    m?.processingStatus

  let source: string | null = null
  const rawSource =
    (m?.source as string | null | undefined) ??
    (m?.origin as string | null | undefined) ??
    (m?.provider as string | null | undefined)
  if (typeof rawSource === 'string' && rawSource.trim().length > 0) {
    source = rawSource.trim()
  } else if (m?.url) {
    try {
      const u = new URL(String(m.url))
      const host = u.hostname.replace(/^www\./i, '')
      if (/youtube\.com|youtu\.be/i.test(host)) {
        source = 'YouTube'
      } else if (/vimeo\.com/i.test(host)) {
        source = 'Vimeo'
      } else if (/soundcloud\.com/i.test(host)) {
        source = 'SoundCloud'
      } else {
        source = host
      }
    } catch {
      // ignore URL parse errors
    }
  }

  let duration: number | null = null
  const rawDuration =
    (m?.duration as number | string | null | undefined) ??
    (m?.media_duration as number | string | null | undefined) ??
    (m?.length_seconds as number | string | null | undefined) ??
    (m?.duration_seconds as number | string | null | undefined)
  if (typeof rawDuration === 'number') {
    duration = rawDuration
  } else if (typeof rawDuration === 'string') {
    const n = Number(rawDuration)
    if (!Number.isNaN(n)) {
      duration = n
    }
  }

  // Extract author from various possible locations
  const rawAuthor =
    m?.author ??
    m?.authors ??
    m?.metadata?.author ??
    m?.metadata?.authors ??
    m?.safe_metadata?.author ??
    m?.safe_metadata?.authors ??
    m?.metadata?.creator ??
    m?.safe_metadata?.creator
  const author = typeof rawAuthor === 'string' && rawAuthor.trim().length > 0
    ? rawAuthor.trim()
    : Array.isArray(rawAuthor) && rawAuthor.length > 0
      ? rawAuthor.filter((a: any) => typeof a === 'string' && a.trim()).join(', ')
      : null

  // Extract publication date (distinct from ingestion created_at)
  const rawPublished =
    m?.published_at ??
    m?.publication_date ??
    m?.metadata?.publication_date ??
    m?.metadata?.published_at ??
    m?.metadata?.date ??
    m?.safe_metadata?.publication_date ??
    m?.safe_metadata?.published_at ??
    m?.safe_metadata?.date ??
    m?.metadata?.publish_date ??
    m?.safe_metadata?.publish_date
  const published_at = typeof rawPublished === 'string' && rawPublished.trim().length > 0
    ? rawPublished.trim()
    : null

  // Extract transcription model
  const rawTranscriptionModel =
    m?.transcription_model ??
    m?.metadata?.transcription_model ??
    m?.safe_metadata?.transcription_model ??
    m?.processing?.transcription_model
  const transcription_model = typeof rawTranscriptionModel === 'string' && rawTranscriptionModel.trim().length > 0
    ? rawTranscriptionModel.trim()
    : null

  // Extract word count
  const rawWordCount =
    m?.word_count ??
    m?.metadata?.word_count ??
    m?.safe_metadata?.word_count ??
    m?.content_length
  const word_count = typeof rawWordCount === 'number' && rawWordCount > 0 ? rawWordCount : null

  // Extract page count
  const rawPageCount =
    m?.metadata?.page_count ??
    m?.metadata?.num_pages ??
    m?.safe_metadata?.page_count ??
    m?.safe_metadata?.num_pages ??
    m?.page_count
  const page_count = typeof rawPageCount === 'number' && rawPageCount > 0 ? Math.trunc(rawPageCount) : null

  return {
    type,
    created_at: m?.created_at,
    status,
    source,
    duration,
    author,
    published_at,
    transcription_model,
    word_count,
    page_count
  }
}

const extractKeywordsFromMedia = (m: any): string[] => {
  const possibleKeywordFields = [
    m?.metadata?.keywords,
    m?.keywords,
    m?.tags,
    m?.metadata?.tags,
    m?.processing?.keywords
  ]

  for (const field of possibleKeywordFields) {
    if (field && Array.isArray(field) && field.length > 0) {
      const keywords = field
        .map((k: any) => {
          if (typeof k === 'string') return k
          if (k && typeof k === 'object' && k.keyword) return k.keyword
          if (k && typeof k === 'object' && k.text) return k.text
          if (k && typeof k === 'object' && k.tag) return k.tag
          if (k && typeof k === 'object' && k.name) return k.name
          return null
        })
        .filter((k): k is string => k !== null && k.trim().length > 0)

      if (keywords.length > 0) return keywords
    }
  }
  return []
}

const getErrorStatusCode = (error: unknown): number | null => {
  if (!error || typeof error !== 'object') return null
  const candidate = error as Record<string, unknown>
  const rawStatus =
    candidate.status ??
    (candidate.response &&
    typeof candidate.response === 'object' &&
    (candidate.response as Record<string, unknown>).status != null
      ? (candidate.response as Record<string, unknown>).status
      : null) ??
    candidate.statusCode
  const parsed = Number(rawStatus)
  return Number.isFinite(parsed) ? parsed : null
}

const isMediaEndpointMissingError = (error: unknown): boolean => {
  const statusCode = getErrorStatusCode(error)
  if (statusCode !== 404 && statusCode !== 405 && statusCode !== 410) {
    return false
  }
  const message = error instanceof Error ? error.message : String(error || '')
  return /\/api\/v1\/media(?:\/|\?|$)/i.test(message)
}

const toNonNegativeFiniteNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value) && value >= 0) return value
  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value)
    if (Number.isFinite(parsed) && parsed >= 0) return parsed
  }
  return null
}

const DEFAULT_MEDIA_LIBRARY_STORAGE_USAGE: MediaLibraryStorageUsage = {
  loading: true,
  error: null,
  totalMb: null,
  quotaMb: null,
  usagePercentage: null,
  warning: null
}

const MediaPageContent: React.FC = () => {
  const { t } = useTranslation(['review', 'common'])
  const navigate = useNavigate()
  const location = useLocation()
  const message = useAntdMessage()
  const { showUndoNotification } = useUndoNotification()
  const {
    setChatMode,
    setSelectedKnowledge,
    setRagMediaIds
  } = useMessageOption()
  const { serverUrl } = useConnectionState()
  const [mediaNavigationPanelEnabled] = useMediaNavigationPanel()
  const [includeGeneratedFallbackDefault] =
    useMediaNavigationGeneratedFallbackDefault()
  const [mediaRichRenderingEnabled] = useMediaRichRendering()
  const [mediaDisplayModeSelectorEnabled] =
    useMediaAnalysisDisplayModeSelector()

  const [shortcutsOverlayOpen, setShortcutsOverlayOpen] = useState(false)
  const [searchMode, setSearchMode] = useState<MediaSearchMode>('full_text')
  const [query, setQuery] = useState<string>('')
  const debouncedQuery = useDebounce(query, 300)
  const [kinds, setKinds] = useState<{ media: boolean; notes: boolean }>({
    media: true,
    notes: false
  })
  const [selected, setSelected] = useState<MediaResultItem | null>(null)
  const [pendingInitialMediaId, setPendingInitialMediaId] = useState<string | null>(null)
  const [pendingInitialMediaIdSource, setPendingInitialMediaIdSource] = useState<
    'url' | 'setting' | null
  >(null)
  const [searchCollapsed, setSearchCollapsed] = useState(false)
  const [jumpToCollapsed, setJumpToCollapsed] = useState(true)
  const [page, setPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(20)
  const [mediaTotal, setMediaTotal] = useState<number>(0)
  const [notesTotal, setNotesTotal] = useState<number>(0)
  const [combinedTotal, setCombinedTotal] = useState<number>(0)
  const [mediaTypes, setMediaTypes] = useState<string[]>([])
  const [availableMediaTypes, setAvailableMediaTypes] = useState<string[]>([])
  const [keywordTokens, setKeywordTokens] = useState<string[]>([])
  const [excludeKeywordTokens, setExcludeKeywordTokens] = useState<string[]>([])
  const [sortBy, setSortBy] = useState<MediaSortBy>('relevance')
  const [dateRange, setDateRange] = useState<MediaDateRange>({
    startDate: null,
    endDate: null
  })
  const [exactPhrase, setExactPhrase] = useState<string>('')
  const [searchFields, setSearchFields] = useState<MediaSearchField[]>([
    ...DEFAULT_MEDIA_SEARCH_FIELDS
  ])
  const [enableBoostFields, setEnableBoostFields] = useState(false)
  const [boostFields, setBoostFields] = useState<MediaBoostFields>({
    title: 2,
    content: 1
  })
  const [metadataFilters, setMetadataFilters] = useState<MetadataSearchFilter[]>([
    createMetadataSearchFilter()
  ])
  const [metadataMatchMode, setMetadataMatchMode] =
    useState<MetadataMatchMode>('all')
  const [metadataValidationError, setMetadataValidationError] = useState<string | null>(
    null
  )
  const [keywordOptions, setKeywordOptions] = useState<string[]>([])
  const [keywordSourceMode, setKeywordSourceMode] = useState<'endpoint' | 'results'>('results')
  const [selectedContent, setSelectedContent] = useState<string>('')
  const [selectedDetail, setSelectedDetail] = useState<any>(null)
  const [selectedNavigationNodeId, setSelectedNavigationNodeId] =
    useState<string | null>(null)
  const [navigationSelectionNonce, setNavigationSelectionNonce] = useState(0)
  const [navigationScopeAuth, setNavigationScopeAuth] = useState<{
    authMode: string | null
    accessToken: string | null
  }>({
    authMode: null,
    accessToken: null
  })
  const [navigationDisplayMode, setNavigationDisplayMode] =
    useState<MediaNavigationFormat>('auto')
  const [navigationDisplayModeLoaded, setNavigationDisplayModeLoaded] =
    useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailFetchError, setDetailFetchError] = useState<{
    mediaId: string | number
    message: string
  } | null>(null)
  const [mediaApiUnavailable, setMediaApiUnavailable] = useState(false)
  const [staleSelectionNotice, setStaleSelectionNotice] = useState<string | null>(
    null
  )
  const [contentHeight, setContentHeight] = useState<number>(0)
  const permalinkMediaId = useMemo(
    () => getMediaPermalinkIdFromSearch(location.search),
    [location.search]
  )

  // Favorites state - persisted to extension storage
  const [favorites, setFavorites] = useStorage<string[]>('media:favorites', [])
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
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false)
  const [bulkSelectionMode, setBulkSelectionMode] = useState(false)
  const [bulkSelectedIds, setBulkSelectedIds] = useState<string[]>([])
  const [bulkKeywordsDraft, setBulkKeywordsDraft] = useState('')
  const [bulkExportFormat, setBulkExportFormat] = useState<'json' | 'markdown' | 'text'>(
    'json'
  )
  const [resultsViewMode, setResultsViewMode] = useStorage<'standard' | 'compact'>(
    'media:results:viewMode',
    'standard'
  )
  const [readingProgressMap, setReadingProgressMap] = useState<Map<string, number>>(new Map())
  const [mediaCollections, setMediaCollections] = useStorage<MediaCollectionRecord[]>(
    MEDIA_COLLECTIONS_STORAGE_KEY,
    []
  )
  const [activeCollectionId, setActiveCollectionId] = useState<string | null>(null)
  const [collectionDraftName, setCollectionDraftName] = useState('')
  const [libraryStorageUsage, setLibraryStorageUsage] = useState<MediaLibraryStorageUsage>(
    DEFAULT_MEDIA_LIBRARY_STORAGE_USAGE
  )
  const searchInputRef = useRef<HTMLInputElement | null>(null)
  const contentDivRef = useRef<HTMLDivElement | null>(null)
  const contentMeasureRafRef = useRef<number | null>(null)
  const contentResizeObserverRef = useRef<ResizeObserver | null>(null)
  const sidebarCollapsedValue = sidebarCollapsed === true
  const libraryToolsCollapsedValue = libraryToolsCollapsed !== false
  const hasRunInitialSearch = React.useRef(false)
  const hasInitializedFromUrl = React.useRef(false)
  const suppressUrlSync = React.useRef(false)
  const keywordEndpointUnavailableRef = React.useRef(false)
  const keywordEndpointRetryAtRef = React.useRef(0)
  const pendingSectionSelectionTelemetryRef = React.useRef<{
    nodeId: string
    startedAt: number
    source: 'user' | 'restore'
  } | null>(null)
  const mediaApiUnavailableNotifiedRef = useRef(false)
  const lastTruncatedTelemetryKeyRef = React.useRef<string>('')
  const lastFallbackTelemetryKeyRef = React.useRef<string>('')
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

  // Favorites helpers
  const favoritesSet = useMemo(() => new Set(favorites || []), [favorites])
  const selectedMediaIdForNavigation =
    selected?.kind === 'media' && selected?.id != null ? selected.id : null
  const navigationControlsEnabled =
    mediaNavigationPanelEnabled && selectedMediaIdForNavigation != null
  const navigationEnabled = navigationControlsEnabled
  const navigationPanelVisibleValue = navigationPanelVisible !== false
  const includeGeneratedFallbackValue = includeGeneratedFallback !== false

  const {
    data: navigationData,
    isLoading: isNavigationLoading,
    error: navigationError,
    refetch: refetchNavigation
  } = useMediaNavigation(selectedMediaIdForNavigation, {
    enabled: navigationEnabled,
    includeGeneratedFallback: includeGeneratedFallbackValue
  })
  const navigationNodes = navigationData?.nodes || []
  const selectedNavigationNode = useMemo(
    () =>
      selectedNavigationNodeId
        ? navigationNodes.find((node) => node.id === selectedNavigationNodeId) || null
        : null,
    [navigationNodes, selectedNavigationNodeId]
  )
  const showNavigationPanel =
    navigationEnabled &&
    navigationPanelVisibleValue &&
    (isNavigationLoading || Boolean(navigationError) || navigationNodes.length > 0)

  const effectiveContentFormat: MediaNavigationFormat | null = null
  const selectedNavigationTarget = useMemo(() => {
    if (!showNavigationPanel || !selectedNavigationNodeId) return null
    if (!selectedNavigationNode) return null
    return {
      target_type: selectedNavigationNode.target_type,
      target_start: selectedNavigationNode.target_start,
      target_end: selectedNavigationNode.target_end,
      target_href: selectedNavigationNode.target_href
    }
  }, [selectedNavigationNode, selectedNavigationNodeId, showNavigationPanel])
  const navigationPageCountHint = useMemo(() => {
    const toPositiveInt = (value: unknown): number | null => {
      if (typeof value === 'number' && Number.isFinite(value)) {
        const parsed = Math.trunc(value)
        return parsed > 0 ? parsed : null
      }
      if (typeof value === 'string' && value.trim().length > 0) {
        const parsed = Number.parseInt(value, 10)
        return Number.isFinite(parsed) && parsed > 0 ? parsed : null
      }
      return null
    }

    const explicitCandidates = [
      selectedDetail?.page_count,
      selectedDetail?.pageCount,
      selectedDetail?.num_pages,
      selectedDetail?.numPages,
      selectedDetail?.total_pages,
      selectedDetail?.totalPages,
      selectedDetail?.metadata?.page_count,
      selectedDetail?.metadata?.num_pages,
      selectedDetail?.metadata?.total_pages,
      selected?.raw?.page_count,
      selected?.raw?.num_pages,
      selected?.raw?.total_pages
    ]
    for (const candidate of explicitCandidates) {
      const parsed = toPositiveInt(candidate)
      if (parsed != null) return parsed
    }

    let maxPage = 0
    for (const node of navigationNodes) {
      if (node.target_type !== 'page') continue
      if (typeof node.target_start !== 'number' || !Number.isFinite(node.target_start)) {
        continue
      }
      const parsed = Math.trunc(node.target_start)
      if (parsed > maxPage) maxPage = parsed
    }
    return maxPage > 0 ? maxPage : null
  }, [navigationNodes, selected?.raw, selectedDetail])

  const effectiveContent = selectedContent
  const effectiveDetailLoading = detailLoading
  const navigationStatusLabel = useMemo(() => {
    if (!navigationEnabled) return ''
    if (isNavigationLoading) {
      return t('review:mediaNavigation.loading', {
        defaultValue: 'Loading sections...'
      })
    }
    if (navigationError) {
      return t('review:mediaNavigation.error', {
        defaultValue: 'Section navigation unavailable'
      })
    }
    if (navigationNodes.length === 0) {
      return t('review:mediaNavigation.noStructure', {
        defaultValue: 'No section structure'
      })
    }
    const generatedNodeCount = navigationNodes.filter(
      (node) => node.source === 'generated'
    ).length
    if (generatedNodeCount === navigationNodes.length) {
      return t('review:mediaNavigation.generatedCount', {
        defaultValue: 'Generated sections: {{count}}',
        count: navigationNodes.length
      })
    }
    return t('review:mediaNavigation.sectionCount', {
      defaultValue: 'Sections: {{count}}',
      count: navigationNodes.length
    })
  }, [isNavigationLoading, navigationEnabled, navigationError, navigationNodes, t])

  const handleNavigationPanelVisibilityChange = useCallback(
    (nextVisible: boolean) => {
      void setNavigationPanelVisible(nextVisible)
      if (!nextVisible) {
        pendingSectionSelectionTelemetryRef.current = null
      }
      void trackMediaNavigationTelemetry({
        type: 'media_navigation_rollout_control_changed',
        scope_key_hash: navigationScopeKeyHash,
        media_id: selectedMediaIdForNavigation,
        control: 'panel_visible',
        enabled: nextVisible
      })
    },
    [navigationScopeKeyHash, selectedMediaIdForNavigation, setNavigationPanelVisible]
  )

  const handleGeneratedFallbackToggle = useCallback(
    (nextEnabled: boolean) => {
      void setIncludeGeneratedFallback(nextEnabled)
      lastFallbackTelemetryKeyRef.current = ''
      setSelectedNavigationNodeId(null)
      pendingSectionSelectionTelemetryRef.current = null
      void trackMediaNavigationTelemetry({
        type: 'media_navigation_rollout_control_changed',
        scope_key_hash: navigationScopeKeyHash,
        media_id: selectedMediaIdForNavigation,
        control: 'include_generated_fallback',
        enabled: nextEnabled
      })
    },
    [
      navigationScopeKeyHash,
      selectedMediaIdForNavigation,
      setIncludeGeneratedFallback
    ]
  )

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

  useEffect(() => {
    if (!mediaRichRenderingEnabled && navigationDisplayMode === 'html') {
      setNavigationDisplayMode('auto')
    }
  }, [mediaRichRenderingEnabled, navigationDisplayMode])

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

  const persistNavigationSelection = useCallback(
    async (node: {
      id: string
      path_label: string | null
      title: string
      level: number
    }) => {
      if (selectedMediaIdForNavigation == null) return
      const evictionStats = await saveMediaNavigationResumeSelection({
        scopeKey: navigationScopeKey,
        mediaId: selectedMediaIdForNavigation,
        node,
        navigationVersion: navigationData?.navigation_version
      }).catch(() => null)
      if (!evictionStats) return

      if (evictionStats.evicted_lru_count > 0) {
        void trackMediaNavigationTelemetry({
          type: 'media_navigation_resume_state_evicted',
          scope_key_hash: navigationScopeKeyHash,
          evicted_entry_count: evictionStats.evicted_lru_count,
          reason: 'lru'
        })
      }
      if (evictionStats.evicted_stale_count > 0) {
        void trackMediaNavigationTelemetry({
          type: 'media_navigation_resume_state_evicted',
          scope_key_hash: navigationScopeKeyHash,
          evicted_entry_count: evictionStats.evicted_stale_count,
          reason: 'stale'
        })
      }
    },
    [
      navigationData?.navigation_version,
      navigationScopeKey,
      navigationScopeKeyHash,
      selectedMediaIdForNavigation
    ]
  )

  useEffect(() => {
    if (!navigationData?.stats?.truncated) return
    if (selectedMediaIdForNavigation == null) return
    const telemetryKey = [
      selectedMediaIdForNavigation,
      navigationData.navigation_version || 'unknown',
      navigationData.stats.returned_node_count,
      navigationData.stats.node_count
    ].join(':')
    if (lastTruncatedTelemetryKeyRef.current === telemetryKey) return
    lastTruncatedTelemetryKeyRef.current = telemetryKey

    void trackMediaNavigationTelemetry({
      type: 'media_navigation_payload_truncated',
      scope_key_hash: navigationScopeKeyHash,
      media_id: selectedMediaIdForNavigation,
      requested_max_nodes: null,
      returned_node_count: navigationData.stats.returned_node_count,
      node_count: navigationData.stats.node_count
    })
  }, [navigationData, navigationScopeKeyHash, selectedMediaIdForNavigation])

  useEffect(() => {
    if (!navigationEnabled || selectedMediaIdForNavigation == null) return
    if (isNavigationLoading || navigationError || !navigationData) return

    let fallbackKind: MediaNavigationFallbackKind | null = null
    let source: string | null = null

    if (!navigationData.available || navigationNodes.length === 0) {
      fallbackKind = 'no_structure'
    } else {
      const hasGeneratedNodes = navigationNodes.some(
        (node) => node.source === 'generated'
      )
      if (hasGeneratedNodes) {
        fallbackKind = 'generated'
        source = 'generated'
      }
    }

    if (!fallbackKind) return

    const telemetryKey = [
      selectedMediaIdForNavigation,
      navigationData.navigation_version || 'unknown',
      fallbackKind,
      source || 'none',
      navigationNodes.length
    ].join(':')
    if (lastFallbackTelemetryKeyRef.current === telemetryKey) return
    lastFallbackTelemetryKeyRef.current = telemetryKey

    void trackMediaNavigationTelemetry({
      type: 'media_navigation_fallback_used',
      scope_key_hash: navigationScopeKeyHash,
      media_id: selectedMediaIdForNavigation,
      fallback_kind: fallbackKind,
      source
    })
  }, [
    isNavigationLoading,
    navigationData,
    navigationEnabled,
    navigationError,
    navigationNodes,
    navigationScopeKeyHash,
    selectedMediaIdForNavigation
  ])

  useEffect(() => {
    const pendingSelection = pendingSectionSelectionTelemetryRef.current
    if (!pendingSelection) return
    if (!showNavigationPanel || !selectedNavigationNodeId) return
    if (selectedMediaIdForNavigation == null) return
    if (pendingSelection.nodeId !== selectedNavigationNodeId) return

    const selectedNode = navigationNodes.find(
      (node) => node.id === selectedNavigationNodeId
    )
    if (!selectedNode) return

    pendingSectionSelectionTelemetryRef.current = null
    const latencyMs = Math.max(0, Date.now() - pendingSelection.startedAt)

    void trackMediaNavigationTelemetry({
      type: 'media_navigation_section_selected',
      media_id: selectedMediaIdForNavigation,
      node_id: selectedNode.id,
      depth: selectedNode.level || 0,
      latency_ms: latencyMs,
      source: pendingSelection.source
    })
  }, [
    navigationNodes,
    selectedMediaIdForNavigation,
    selectedNavigationNodeId,
    showNavigationPanel
  ])

  const toggleFavorite = useCallback((id: string) => {
    const idStr = String(id)
    setFavorites((prev: string[] | undefined) => {
      const currentFavorites = prev || []
      const set = new Set(currentFavorites)
      if (set.has(idStr)) {
        set.delete(idStr)
      } else {
        set.add(idStr)
      }
      return Array.from(set)
    })
  }, [setFavorites])

  const isFavorite = useCallback((id: string) => {
    return favoritesSet.has(String(id))
  }, [favoritesSet])

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
    scheduleContentMeasure()
  }, [scheduleContentMeasure, selected?.id, effectiveContent.length])

  useEffect(() => {
    return () => {
      clearContentMeasurement()
    }
  }, [clearContentMeasurement])

  useEffect(() => {
    setSelectedNavigationNodeId(null)
    setNavigationSelectionNonce(0)
    pendingSectionSelectionTelemetryRef.current = null
  }, [selected?.id, selected?.kind])

  useEffect(() => {
    if (!showNavigationPanel) return
    if (navigationNodes.length === 0) {
      setSelectedNavigationNodeId(null)
      pendingSectionSelectionTelemetryRef.current = null
      return
    }
    const hasCurrentSelection =
      !!selectedNavigationNodeId &&
      navigationNodes.some((node) => node.id === selectedNavigationNodeId)
    if (hasCurrentSelection || selectedMediaIdForNavigation == null) return

    let cancelled = false
    ;(async () => {
      const resumeEntry = await getMediaNavigationResumeEntry({
        scopeKey: navigationScopeKey,
        mediaId: selectedMediaIdForNavigation
      }).catch(() => null)
      if (cancelled) return

      const resolvedSelection = resolveMediaNavigationResumeSelection({
        nodes: navigationNodes,
        navigationVersion: navigationData?.navigation_version,
        resumeEntry
      })

      const nextNodeId = resolvedSelection?.nodeId || navigationNodes[0]?.id || null
      if (!nextNodeId) {
        setSelectedNavigationNodeId(null)
        return
      }

      const nextNode =
        navigationNodes.find((node) => node.id === nextNodeId) || navigationNodes[0]
      if (!nextNode) return

      setSelectedNavigationNodeId(nextNode.id)
      setNavigationSelectionNonce((prev) => prev + 1)
      void persistNavigationSelection(nextNode)

      if (resumeEntry && resolvedSelection) {
        pendingSectionSelectionTelemetryRef.current = {
          nodeId: nextNode.id,
          startedAt: Date.now(),
          source: 'restore'
        }
        void trackMediaNavigationTelemetry({
          type: 'media_navigation_resume_state_restored',
          scope_key_hash: navigationScopeKeyHash,
          media_id: selectedMediaIdForNavigation,
          outcome: resolvedSelection.outcome
        })
      }
    })()

    return () => {
      cancelled = true
    }
  }, [
    navigationData?.navigation_version,
    navigationNodes,
    navigationScopeKey,
    navigationScopeKeyHash,
    persistNavigationSelection,
    selectedMediaIdForNavigation,
    selectedNavigationNodeId,
    showNavigationPanel
  ])

  const markMediaApiUnavailable = useCallback((error?: unknown) => {
    if (mediaApiUnavailableNotifiedRef.current) return
    if (error && !isMediaEndpointMissingError(error)) return
    mediaApiUnavailableNotifiedRef.current = true
    setMediaApiUnavailable(true)
    setMediaTotal(0)
    message.warning(
      t('review:mediaPage.mediaApiUnavailable', {
        defaultValue:
          'Media list/search endpoints are unavailable on this server. Media loading has been paused.'
      })
    )
  }, [message, t])

  // Initialize filter state from URL params on first mount
  useEffect(() => {
    if (hasInitializedFromUrl.current) return
    hasInitializedFromUrl.current = true
    if (!hasMediaFilterParams(location.search)) return
    const urlFilters = parseMediaFilterParams(location.search)
    suppressUrlSync.current = true
    if (urlFilters.q) setQuery(urlFilters.q)
    if (urlFilters.types?.length) setMediaTypes(urlFilters.types)
    if (urlFilters.keywords?.length) setKeywordTokens(urlFilters.keywords)
    if (urlFilters.excludeKeywords?.length) setExcludeKeywordTokens(urlFilters.excludeKeywords)
    if (urlFilters.sort) setSortBy(urlFilters.sort)
    if (urlFilters.dateStart || urlFilters.dateEnd) {
      setDateRange({ startDate: urlFilters.dateStart || null, endDate: urlFilters.dateEnd || null })
    }
    if (urlFilters.searchMode) setSearchMode(urlFilters.searchMode)
    if (urlFilters.exactPhrase) setExactPhrase(urlFilters.exactPhrase)
    if (urlFilters.fields?.length) setSearchFields(urlFilters.fields)
    if (urlFilters.page) setPage(urlFilters.page)
    if (urlFilters.pageSize) setPageSize(urlFilters.pageSize)
    // Allow URL sync after a tick so initial state doesn't immediately re-write
    requestAnimationFrame(() => { suppressUrlSync.current = false })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Sync filter state to URL on change
  useEffect(() => {
    if (suppressUrlSync.current) return
    if (!hasRunInitialSearch.current) return
    const nextSearch = buildMediaFilterSearch(location.search, {
      q: query || undefined,
      types: mediaTypes.length > 0 ? mediaTypes : undefined,
      keywords: keywordTokens.length > 0 ? keywordTokens : undefined,
      excludeKeywords: excludeKeywordTokens.length > 0 ? excludeKeywordTokens : undefined,
      sort: sortBy,
      dateStart: dateRange.startDate,
      dateEnd: dateRange.endDate,
      searchMode: searchMode,
      exactPhrase: exactPhrase || undefined,
      fields:
        searchFields.length > 0 && !hasDefaultMediaSearchFields(searchFields)
          ? searchFields
          : undefined,
      page: page,
      pageSize: pageSize
    })
    if (nextSearch === location.search) return
    navigate(
      { pathname: location.pathname, search: nextSearch, hash: location.hash },
      { replace: true }
    )
  }, [
    dateRange.endDate,
    dateRange.startDate,
    exactPhrase,
    excludeKeywordTokens,
    keywordTokens,
    location.hash,
    location.pathname,
    location.search,
    mediaTypes,
    navigate,
    page,
    pageSize,
    query,
    searchFields,
    searchMode,
    sortBy
  ])

  const runSearch = useCallback(async (): Promise<MediaResultItem[]> => {
    const results: MediaResultItem[] = []
    const hasTextQuery = query.trim().length > 0
    const hasQuery =
      hasTextQuery ||
      (searchMode === 'full_text' && exactPhrase.trim().length > 0)
    const hasMediaFilters = hasMediaSearchFilters({
      mediaTypes,
      includeKeywords: keywordTokens,
      excludeKeywords: excludeKeywordTokens,
      sortBy,
      dateRange,
      exactPhrase,
      fields: searchFields,
      boostFields: enableBoostFields ? boostFields : undefined
    })
    let actualMediaCount = 0
    let actualNotesCount = 0

    if (kinds.media && !mediaApiUnavailable) {
      try {
        if (searchMode === 'metadata') {
          const normalizedFilters = normalizeMetadataSearchFilters(metadataFilters)
          const validationError = validateMetadataSearchFilters(normalizedFilters)
          if (validationError) {
            setMetadataValidationError(validationError)
            setMediaTotal(0)
            actualMediaCount = 0
          } else {
            setMetadataValidationError(null)
            const path = buildMetadataSearchPath({
              filters: normalizedFilters,
              matchMode: metadataMatchMode,
              page,
              perPage: pageSize
            })
            const metadataResp = await bgRequest<any>({
              path: path as any,
              method: 'GET' as any
            })
            const rows = Array.isArray(metadataResp?.results)
              ? metadataResp.results
              : []

            const includeTerms = keywordTokens
              .map((token) => token.trim().toLowerCase())
              .filter(Boolean)
            const excludeTerms = excludeKeywordTokens
              .map((token) => token.trim().toLowerCase())
              .filter(Boolean)
            const startMs = dateRange.startDate
              ? new Date(dateRange.startDate).getTime()
              : null
            const endMs = dateRange.endDate
              ? new Date(dateRange.endDate).getTime()
              : null
            const textQuery = query.trim().toLowerCase()

            let filteredRows = rows.filter((row: any) => {
              const type = String(row?.type ?? '').toLowerCase()
              if (mediaTypes.length > 0 && !mediaTypes.includes(type)) {
                return false
              }

              if (startMs != null || endMs != null) {
                const createdAt = row?.created_at ? new Date(row.created_at).getTime() : null
                if (createdAt == null || Number.isNaN(createdAt)) {
                  return false
                }
                if (startMs != null && createdAt < startMs) {
                  return false
                }
                if (endMs != null && createdAt > endMs) {
                  return false
                }
              }

              const metadataPayload =
                row?.safe_metadata && typeof row.safe_metadata === 'object'
                  ? JSON.stringify(row.safe_metadata)
                  : ''
              const haystack =
                `${String(row?.title ?? '')} ${metadataPayload}`.toLowerCase()

              if (textQuery && !haystack.includes(textQuery)) {
                return false
              }
              if (includeTerms.some((term) => !haystack.includes(term))) {
                return false
              }
              if (excludeTerms.some((term) => haystack.includes(term))) {
                return false
              }

              return true
            })

            if (sortBy === 'date_desc') {
              filteredRows = filteredRows.sort(
                (a, b) =>
                  (new Date(b?.created_at ?? 0).getTime() || 0) -
                  (new Date(a?.created_at ?? 0).getTime() || 0)
              )
            } else if (sortBy === 'date_asc') {
              filteredRows = filteredRows.sort(
                (a, b) =>
                  (new Date(a?.created_at ?? 0).getTime() || 0) -
                  (new Date(b?.created_at ?? 0).getTime() || 0)
              )
            } else if (sortBy === 'title_asc') {
              filteredRows = filteredRows.sort((a, b) =>
                String(a?.title ?? '').localeCompare(String(b?.title ?? ''))
              )
            } else if (sortBy === 'title_desc') {
              filteredRows = filteredRows.sort((a, b) =>
                String(b?.title ?? '').localeCompare(String(a?.title ?? ''))
              )
            }

            const metadataKeys = [
              'doi',
              'pmid',
              'pmcid',
              'arxiv_id',
              's2_paper_id',
              'journal',
              'license'
            ]

            for (const row of filteredRows) {
              const id = row?.media_id ?? row?.id ?? row?.pk ?? row?.uuid
              const type =
                typeof row?.type === 'string'
                  ? row.type.toLowerCase().trim()
                  : 'document'
              if (type && !availableMediaTypes.includes(type)) {
                setAvailableMediaTypes((prev) =>
                  prev.includes(type) ? prev : [...prev, type]
                )
              }

              const safeMetadata =
                row?.safe_metadata && typeof row.safe_metadata === 'object'
                  ? row.safe_metadata
                  : {}
              const snippet = metadataKeys
                .map((key) => {
                  const value = safeMetadata?.[key]
                  if (value == null || String(value).trim().length === 0) {
                    return null
                  }
                  return `${key}: ${String(value)}`
                })
                .filter((value): value is string => Boolean(value))
                .join(' • ')

              results.push({
                kind: 'media',
                id,
                title: row?.title || `Media ${id}`,
                snippet,
                keywords: [],
                meta: {
                  type,
                  created_at: row?.created_at
                },
                raw: row
              })
            }

            const serverTotal = Number(metadataResp?.pagination?.total || rows.length || 0)
            const hasClientSideConstraints =
              hasTextQuery ||
              mediaTypes.length > 0 ||
              keywordTokens.length > 0 ||
              excludeKeywordTokens.length > 0 ||
              Boolean(dateRange.startDate || dateRange.endDate) ||
              sortBy !== 'relevance'

            const effectiveMediaTotal = hasClientSideConstraints
              ? filteredRows.length
              : serverTotal
            setMediaTotal(effectiveMediaTotal)
            actualMediaCount = effectiveMediaTotal
          }
        } else if (!hasQuery && !hasMediaFilters) {
          // Blank browse: GET listing with pagination
          const listing = await bgRequest<any>({
            path: `/api/v1/media/?page=${page}&results_per_page=${pageSize}&include_keywords=true` as any,
            method: 'GET' as any
          })
          const items = Array.isArray(listing?.items) ? listing.items : []
          const pagination = listing?.pagination
          const mediaServerTotal = Number(pagination?.total_items || items.length || 0)
          setMediaTotal(mediaServerTotal)
          actualMediaCount = mediaServerTotal
          for (const m of items) {
            const id = m?.id ?? m?.media_id ?? m?.pk ?? m?.uuid
            const meta = deriveMediaMeta(m)
            const type = meta.type
            if (type && !availableMediaTypes.includes(type)) {
              setAvailableMediaTypes((prev) =>
                prev.includes(type) ? prev : [...prev, type]
              )
            }
            const keywords = extractKeywordsFromMedia(m)

            results.push({
              kind: 'media',
              id,
              title: m?.title || m?.filename || `Media ${id}`,
              snippet: m?.snippet || m?.summary || '',
              keywords,
              meta: meta,
              raw: m
            })
          }
        } else {
          // Search with optional filters and pagination
          const body = buildMediaSearchPayload({
            query,
            mediaTypes,
            includeKeywords: keywordTokens,
            excludeKeywords: excludeKeywordTokens,
            sortBy,
            dateRange,
            exactPhrase,
            fields: searchFields,
            boostFields: enableBoostFields ? boostFields : undefined
          })
          const mediaResp = await bgRequest<any>({
            path: `/api/v1/media/search?page=${page}&results_per_page=${pageSize}&include_keywords=true` as any,
            method: 'POST' as any,
            headers: { 'Content-Type': 'application/json' },
            body
          })
          const items = Array.isArray(mediaResp?.items)
            ? mediaResp.items
            : Array.isArray(mediaResp?.results)
              ? mediaResp.results
              : []
          const pagination = mediaResp?.pagination
          const mediaServerTotal = Number(pagination?.total_items || items.length || 0)
          setMediaTotal(mediaServerTotal)
          actualMediaCount = mediaServerTotal
          for (const m of items) {
            const id = m?.id ?? m?.media_id ?? m?.pk ?? m?.uuid
            const meta = deriveMediaMeta(m)
            const type = meta.type
            if (type && !availableMediaTypes.includes(type)) {
              setAvailableMediaTypes((prev) =>
                prev.includes(type) ? prev : [...prev, type]
              )
            }
            const keywords = extractKeywordsFromMedia(m)

            results.push({
              kind: 'media',
              id,
              title: m?.title || m?.filename || `Media ${id}`,
              snippet: m?.snippet || m?.summary || '',
              keywords,
              meta: meta,
              raw: m
            })
          }
        }
      } catch (err) {
        if (isMediaEndpointMissingError(err)) {
          markMediaApiUnavailable(err)
          actualMediaCount = 0
          setMediaTotal(0)
        } else {
          console.error('Media search error:', err)
          message.error(t('review:mediaPage.searchError', { defaultValue: 'Failed to search media' }))
        }
      }
    } else if (kinds.media) {
      setMediaTotal(0)
      actualMediaCount = 0
    }

    // Fetch notes if enabled
    if (kinds.notes && searchMode !== 'metadata') {
      try {
        // Helper to extract keywords from note
        const extractNoteKeywords = (note: any): string[] => {
          const possibleFields = [
            note?.metadata?.keywords,
            note?.keywords,
            note?.tags
          ]
          for (const field of possibleFields) {
            if (field && Array.isArray(field) && field.length > 0) {
              return field
                .map((k: any) => {
                  if (typeof k === 'string') return k
                  if (k && typeof k === 'object' && k.keyword) return k.keyword
                  if (k && typeof k === 'object' && k.text) return k.text
                  return null
                })
                .filter((k): k is string => k !== null && k.trim().length > 0)
            }
          }
          return []
        }

        if (hasTextQuery) {
          // Search notes with server-side pagination.
          // Prefer POST /api/v1/notes/search/ with SearchRequest so the server can
          // apply keyword filtering; fall back to GET on older servers.
          const keywordFilterActive = keywordTokens.length > 0
          let notesResp: any
          let usedKeywordServerFilter = false

          try {
            const body: any = { query }
            if (keywordFilterActive) {
              body.must_have = keywordTokens
              usedKeywordServerFilter = true
            }
            notesResp = await bgRequest<any>({
              path: `/api/v1/notes/search/?page=${page}&results_per_page=${pageSize}&include_keywords=true` as any,
              method: 'POST' as any,
              headers: { 'Content-Type': 'application/json' },
              body
            })
          } catch {
            // Fallback: legacy GET search without keyword-aware pagination
            usedKeywordServerFilter = false
            notesResp = await bgRequest<any>({
              path: `/api/v1/notes/search/?query=${encodeURIComponent(
                query
              )}&page=${page}&results_per_page=${pageSize}&include_keywords=true` as any,
              method: 'GET' as any
            })
          }

          const items = Array.isArray(notesResp) ? notesResp : (notesResp?.items || [])
          const pagination = notesResp?.pagination

          // If the API cannot filter by keywords, apply client-side filtering and
          // base the total on the filtered subset so pagination reflects what is visible.
          let filteredItems = items
          if (keywordFilterActive && !usedKeywordServerFilter) {
            filteredItems = items.filter((n: any) => {
              const noteKws = extractNoteKeywords(n)
              return keywordTokens.some((kw) =>
                noteKws.some((nkw) => nkw.toLowerCase().includes(kw.toLowerCase()))
              )
            })
          }

          if (keywordFilterActive && !usedKeywordServerFilter) {
            const notesClientTotal = filteredItems.length
            setNotesTotal(notesClientTotal)
            actualNotesCount = notesClientTotal
          } else {
            const notesServerTotal = Number(pagination?.total_items || items.length || 0)
            setNotesTotal(notesServerTotal)
            actualNotesCount = notesServerTotal
          }

          for (const n of filteredItems) {
            const id = n?.id ?? n?.note_id ?? n?.pk ?? n?.uuid
            results.push({
              kind: 'note',
              id,
              title: n?.title || `Note ${id}`,
              snippet: n?.content?.substring(0, 200) || '',
              keywords: extractNoteKeywords(n),
              meta: {
                type: 'note',
                source: n?.metadata?.conversation_id ? 'conversation' : null
              },
              raw: n
            })
          }
        } else {
          // Browse notes with pagination
          const notesResp = await bgRequest<any>({
            path: `/api/v1/notes/?page=${page}&results_per_page=${pageSize}` as any,
            method: 'GET' as any
          })
          const items = Array.isArray(notesResp?.items) ? notesResp.items : []
          const pagination = notesResp?.pagination
          const notesServerTotal = Number(pagination?.total_items || items.length || 0)
          setNotesTotal(notesServerTotal)
          actualNotesCount = notesServerTotal

          for (const n of items) {
            const id = n?.id ?? n?.note_id ?? n?.pk ?? n?.uuid
            results.push({
              kind: 'note',
              id,
              title: n?.title || `Note ${id}`,
              snippet: n?.content?.substring(0, 200) || '',
              keywords: extractNoteKeywords(n),
              meta: {
                type: 'note',
                source: n?.metadata?.conversation_id ? 'conversation' : null
              },
              raw: n
            })
          }
        }
      } catch (err) {
        console.error('Notes search error:', err)
        message.error(t('review:mediaPage.notesSearchError', { defaultValue: 'Failed to search notes' }))
      }
    }

    // Set combined total after all filtering is complete
    const finalCombinedTotal = actualMediaCount + actualNotesCount
    setCombinedTotal(finalCombinedTotal)

    return results
  }, [
    searchMode,
    query,
    kinds,
    mediaTypes,
    keywordTokens,
    excludeKeywordTokens,
    sortBy,
    dateRange.startDate,
    dateRange.endDate,
    exactPhrase,
    searchFields,
    enableBoostFields,
    boostFields.title,
    boostFields.content,
    metadataMatchMode,
    metadataFilters,
    mediaApiUnavailable,
    markMediaApiUnavailable,
    message,
    page,
    pageSize,
    availableMediaTypes,
    t
  ])

  const { data: results = [], refetch, isLoading, isFetching } = useQuery({
    queryKey: [
      'media-search',
      query,
      kinds,
      mediaTypes,
      keywordTokens.join('|'),
      excludeKeywordTokens.join('|'),
      sortBy,
      dateRange.startDate,
      dateRange.endDate,
      exactPhrase,
      searchFields.join('|'),
      enableBoostFields,
      boostFields.title,
      boostFields.content,
      searchMode,
      metadataMatchMode,
      JSON.stringify(metadataFilters),
      page,
      pageSize
    ],
    queryFn: runSearch,
    enabled: false
  })

  const normalizedMetadataFilters = useMemo(
    () => normalizeMetadataSearchFilters(metadataFilters),
    [metadataFilters]
  )

  // Compute active filters state
  const hasActiveFilters =
    mediaTypes.length > 0 ||
    keywordTokens.length > 0 ||
    excludeKeywordTokens.length > 0 ||
    Boolean(dateRange.startDate || dateRange.endDate) ||
    sortBy !== 'relevance' ||
    Boolean(exactPhrase.trim()) ||
    !hasDefaultMediaSearchFields(searchFields) ||
    enableBoostFields ||
    searchMode === 'metadata' ||
    normalizedMetadataFilters.length > 0 ||
    showFavoritesOnly ||
    Boolean(activeCollectionId)

  const activeFilterCount = useMemo(() => {
    return (
      mediaTypes.length +
      keywordTokens.length +
      excludeKeywordTokens.length +
      Number(Boolean(dateRange.startDate || dateRange.endDate)) +
      Number(sortBy !== 'relevance') +
      Number(Boolean(exactPhrase.trim())) +
      Number(!hasDefaultMediaSearchFields(searchFields)) +
      Number(enableBoostFields) +
      Number(searchMode === 'metadata') +
      Number(normalizedMetadataFilters.length > 0) +
      Number(showFavoritesOnly) +
      Number(Boolean(activeCollectionId))
    )
  }, [
    activeCollectionId,
    dateRange.endDate,
    dateRange.startDate,
    enableBoostFields,
    exactPhrase,
    excludeKeywordTokens.length,
    keywordTokens.length,
    mediaTypes.length,
    normalizedMetadataFilters.length,
    searchFields,
    searchMode,
    showFavoritesOnly,
    sortBy
  ])

  const resetAllFilters = useCallback(() => {
    setSearchMode('full_text')
    setMediaTypes([])
    setKeywordTokens([])
    setExcludeKeywordTokens([])
    setDateRange({ startDate: null, endDate: null })
    setSortBy('relevance')
    setExactPhrase('')
    setSearchFields([...DEFAULT_MEDIA_SEARCH_FIELDS])
    setEnableBoostFields(false)
    setBoostFields({ title: 2, content: 1 })
    setMetadataFilters([createMetadataSearchFilter()])
    setMetadataMatchMode('all')
    setMetadataValidationError(null)
    setShowFavoritesOnly(false)
    setActiveCollectionId(null)
    setPage(1)
  }, [])

  useEffect(() => {
    if (searchMode !== 'metadata') {
      setMetadataValidationError(null)
      return
    }
    setKinds((prev) => (prev.media && !prev.notes ? prev : { media: true, notes: false }))
    setNotesTotal(0)
  }, [searchMode])

  // Filter results by favorites if enabled
  const displayResults = useMemo(() => {
    let nextResults = results
    if (showFavoritesOnly) {
      nextResults = nextResults.filter((item) => favoritesSet.has(String(item.id)))
    }
    if (activeCollectionId) {
      const collection = mediaCollections.find((entry) => entry.id === activeCollectionId)
      if (!collection) {
        return []
      }
      const allowedIdSet = new Set(collection.itemIds.map((id) => String(id)))
      nextResults = nextResults.filter((item) => allowedIdSet.has(String(item.id)))
    }
    return nextResults
  }, [
    activeCollectionId,
    favoritesSet,
    mediaCollections,
    results,
    showFavoritesOnly
  ])

  const sidebarTargetVisibleRows = useMemo(() => {
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
  }, [contentHeight, pageSize, selectedContent])

  const sidebarResultsRowHeightPx =
    resultsViewMode === 'compact'
      ? MEDIA_RESULTS_ROW_HEIGHT_COMPACT_PX
      : MEDIA_RESULTS_ROW_HEIGHT_STANDARD_PX
  const computedSidebarResultsListMinHeightPx =
    MEDIA_RESULTS_HEADER_PX + sidebarTargetVisibleRows * sidebarResultsRowHeightPx
  const computedSidebarResultsPanelMinHeightPx =
    computedSidebarResultsListMinHeightPx + MEDIA_RESULTS_FOOTER_PX
  const sidebarResultsListMinHeightPx = computedSidebarResultsListMinHeightPx
  const sidebarResultsPanelMinHeightPx = computedSidebarResultsPanelMinHeightPx
  const mediaPageMinHeightPx = Math.max(
    MEDIA_SIDEBAR_MIN_HEIGHT_PX,
    MEDIA_SIDEBAR_CHROME_BUFFER_PX + sidebarResultsPanelMinHeightPx
  )
  // Fetch reading progress for visible media items
  useEffect(() => {
    const mediaIds = displayResults
      .filter((r) => r.kind === 'media')
      .map((r) => String(r.id))
    if (mediaIds.length === 0) {
      setReadingProgressMap(new Map())
      return
    }
    const getReadingProgress = (tldwClient as any).getReadingProgress
    if (typeof getReadingProgress !== 'function') {
      setReadingProgressMap(new Map())
      return
    }
    let cancelled = false
    const fetchProgress = async () => {
      const entries: Array<[string, number]> = []
      // Fetch in parallel but limit concurrency
      const batchSize = 10
      for (let i = 0; i < mediaIds.length; i += batchSize) {
        const batch = mediaIds.slice(i, i + batchSize)
        const results = await Promise.allSettled(
          batch.map((id) => getReadingProgress.call(tldwClient, id))
        )
        if (cancelled) return
        for (let j = 0; j < results.length; j++) {
          const result = results[j]
          if (result.status === 'fulfilled' && result.value?.has_progress !== false) {
            const pct = result.value?.percent_complete
            if (typeof pct === 'number' && pct > 0) {
              entries.push([batch[j], pct])
            }
          }
        }
      }
      if (!cancelled) {
        setReadingProgressMap(new Map(entries))
      }
    }
    void fetchProgress()
    return () => { cancelled = true }
  }, [displayResults])

  const hasJumpTo = displayResults.length > 5
  const activeCollection = useMemo(
    () => mediaCollections.find((entry) => entry.id === activeCollectionId) || null,
    [activeCollectionId, mediaCollections]
  )
  const bulkSelectedIdSet = useMemo(
    () => new Set(bulkSelectedIds),
    [bulkSelectedIds]
  )
  const bulkSelectedItems = useMemo(
    () => displayResults.filter((item) => bulkSelectedIdSet.has(String(item.id))),
    [bulkSelectedIdSet, displayResults]
  )
  const bulkSelectedMediaItems = useMemo(
    () => bulkSelectedItems.filter((item) => item.kind === 'media'),
    [bulkSelectedItems]
  )
  const bulkSelectedNoteCount = bulkSelectedItems.length - bulkSelectedMediaItems.length

  useEffect(() => {
    if (bulkSelectedIds.length === 0) return
    const visibleIdSet = new Set(displayResults.map((item) => String(item.id)))
    setBulkSelectedIds((prev) => {
      const next = prev.filter((id) => visibleIdSet.has(id))
      return next.length === prev.length ? prev : next
    })
  }, [bulkSelectedIds.length, displayResults])

  useEffect(() => {
    if (bulkSelectionMode || bulkSelectedIds.length === 0) return
    setBulkSelectedIds([])
  }, [bulkSelectedIds.length, bulkSelectionMode])

  useEffect(() => {
    if (!activeCollectionId) return
    const exists = mediaCollections.some((entry) => entry.id === activeCollectionId)
    if (!exists) {
      setActiveCollectionId(null)
    }
  }, [activeCollectionId, mediaCollections])

  const refreshLibraryStorageUsage = useCallback(async () => {
    setLibraryStorageUsage((prev) => ({
      ...prev,
      loading: true,
      error: null
    }))

    try {
      const response = await bgRequest<any>({
        path: '/api/v1/storage/usage' as any,
        method: 'GET' as any
      })
      const totalMb = toNonNegativeFiniteNumber(
        response?.usage?.total_mb ?? response?.usage?.totalMb
      )
      const quotaMb = toNonNegativeFiniteNumber(response?.quota_mb ?? response?.quotaMb)
      const usagePercentage = toNonNegativeFiniteNumber(
        response?.usage_percentage ?? response?.usagePercentage
      )
      const warning =
        typeof response?.warning === 'string' && response.warning.trim().length > 0
          ? response.warning.trim()
          : null

      setLibraryStorageUsage({
        loading: false,
        error: null,
        totalMb,
        quotaMb,
        usagePercentage,
        warning
      })
    } catch {
      setLibraryStorageUsage({
        loading: false,
        error: 'Unable to load storage usage.',
        totalMb: null,
        quotaMb: null,
        usagePercentage: null,
        warning: null
      })
    }
  }, [])

  useEffect(() => {
    void refreshLibraryStorageUsage()
  }, [refreshLibraryStorageUsage])

  useEffect(() => {
    if (!permalinkMediaId) return
    if (selected?.kind === 'media' && selected?.id != null) return
    setPendingInitialMediaId(permalinkMediaId)
    setPendingInitialMediaIdSource('url')
  }, [permalinkMediaId, selected?.id, selected?.kind])

  useEffect(() => {
    if (permalinkMediaId) return
    if (selected?.kind === 'media' && selected?.id != null) return
    let cancelled = false
    ;(async () => {
      const lastMediaId = normalizeMediaPermalinkId(
        await getSetting(LAST_MEDIA_ID_SETTING)
      )
      if (cancelled || !lastMediaId) return
      setPendingInitialMediaId((prev) => prev ?? lastMediaId)
      setPendingInitialMediaIdSource((prev) => prev ?? 'setting')
    })()
    return () => {
      cancelled = true
    }
  }, [permalinkMediaId, selected?.id, selected?.kind])

  // Compute total pages for pagination
  const activeTotalCount =
    kinds.media && kinds.notes
      ? combinedTotal
      : kinds.notes
        ? notesTotal
        : mediaTotal
  const totalPages = Math.ceil(activeTotalCount / pageSize)

  // Auto-refetch when debounced query changes (including clearing to empty)
  useEffect(() => {
    if (!hasRunInitialSearch.current) {
      hasRunInitialSearch.current = true
      if (debouncedQuery === '') return
    }
    if (page !== 1) {
      setPage(1)
      return
    }
    refetch()
  }, [debouncedQuery, page, refetch])

  // Auto-refetch when paginating
  useEffect(() => {
    refetch()
  }, [page, pageSize, refetch])

  // Refetch when switching between media/notes kinds.
  useEffect(() => {
    if (!hasRunInitialSearch.current) return
    setPage(1)
    refetch()
  }, [kinds, refetch])

  // Reset to page 1 when filters change and refetch
  useEffect(() => {
    if (page !== 1) {
      setPage(1)
      return
    }
    refetch()
  }, [
    searchMode,
    page,
    mediaTypes,
    keywordTokens,
    excludeKeywordTokens,
    sortBy,
    dateRange.startDate,
    dateRange.endDate,
    exactPhrase,
    searchFields,
    enableBoostFields,
    boostFields.title,
    boostFields.content,
    metadataMatchMode,
    metadataFilters,
    refetch
  ])

  // Initial load: populate media types and auto-browse first page
  useEffect(() => {
    const immediateCachedTypes = getImmediateCachedMediaTypes()
    if (immediateCachedTypes.length > 0) {
      setAvailableMediaTypes((prev) =>
        Array.from(new Set<string>([...prev, ...immediateCachedTypes])) as string[]
      )
    }

    ;(async () => {
      try {
        const storage = new Storage({ area: 'local', serde: safeStorageSerde } as any)
        const cached = normalizeMediaTypesCacheRecord(
          await storage.get(MEDIA_TYPES_CACHE_KEY).catch(() => null)
        )
        const now = Date.now()
        if (cached && isMediaTypesCacheFresh(cached.cachedAt, now, MEDIA_TYPES_CACHE_TTL_MS)) {
          setAvailableMediaTypes(
            Array.from(new Set<string>(cached.types)) as string[]
          )
          seedMediaTypesCache(cached.types, { cachedAt: cached.cachedAt })
        }

        // Sample first up-to-3 pages to enrich types list
        const first = await bgRequest<any>({
          path: `/api/v1/media/?page=1&results_per_page=50` as any,
          method: 'GET' as any
        })
        const totalPages = Math.max(
          1,
          Number(first?.pagination?.total_pages || 1)
        )
        const pagesToFetch = [1, 2, 3].filter((p) => p <= totalPages)
        const listings = await Promise.all(
          pagesToFetch.map((p) =>
            p === 1
              ? Promise.resolve(first)
              : bgRequest<any>({
                  path: `/api/v1/media/?page=${p}&results_per_page=50` as any,
                  method: 'GET' as any
                })
          )
        )
        const typeSet = new Set<string>()
        for (const listing of listings) {
          const items = Array.isArray(listing?.items) ? listing.items : []
          for (const m of items) {
            const t = deriveMediaMeta(m).type
            if (t) typeSet.add(t)
          }
        }
        const newTypes = Array.from(typeSet)
        if (newTypes.length) {
          setAvailableMediaTypes((prev) =>
            Array.from(new Set<string>([...prev, ...newTypes])) as string[]
          )
          const cacheRecord = seedMediaTypesCache(newTypes, { cachedAt: now })
          if (cacheRecord) {
            await storage.set(MEDIA_TYPES_CACHE_KEY, cacheRecord)
          }
        }
      } catch (error) {
        if (isMediaEndpointMissingError(error)) {
          mediaApiUnavailableNotifiedRef.current = true
          setMediaApiUnavailable(true)
          setMediaTotal(0)
        }
      }

      // Auto-browse: if there is no query or filters, fetch first page
      try {
        // Always fetch on mount - filters are guaranteed empty at this point
        await refetch()
      } catch {}
    })()
  }, []) // Intentionally empty - runs only on mount with initial (empty) filters

  // Load keyword suggestions for the filter dropdown.
  // Preferred source: `/api/v1/media/keywords` endpoint.
  // Fallback source: keywords from currently loaded results.
  const loadKeywordSuggestions = useCallback(async (searchText?: string) => {
    const normalizeKeywords = (items: any[]): string[] => {
      const out = new Set<string>()
      for (const item of items) {
        const raw =
          typeof item === 'string'
            ? item
            : item?.keyword ?? item?.text ?? item?.tag ?? item?.name

        if (typeof raw !== 'string') continue
        const trimmed = raw.trim()
        if (!trimmed) continue
        if (searchText && !trimmed.toLowerCase().includes(searchText.toLowerCase())) {
          continue
        }
        out.add(trimmed)
      }
      return Array.from(out)
    }

    if (mediaApiUnavailable) {
      const keywordsFromResults = new Set<string>()
      for (const result of results) {
        if (!result.keywords) continue
        for (const kw of result.keywords) {
          if (!searchText || kw.toLowerCase().includes(searchText.toLowerCase())) {
            keywordsFromResults.add(kw)
          }
        }
      }
      setKeywordOptions(Array.from(keywordsFromResults))
      setKeywordSourceMode('results')
      return
    }

    const now = Date.now()
    if (
      !keywordEndpointUnavailableRef.current ||
      now >= keywordEndpointRetryAtRef.current
    ) {
      try {
        const trimmedSearch = searchText?.trim()
        const endpointPath = trimmedSearch
          ? `/api/v1/media/keywords?query=${encodeURIComponent(trimmedSearch)}`
          : '/api/v1/media/keywords'
        const keywordResp = await bgRequest<any>({
          path: endpointPath as any,
          method: 'GET' as any
        })
        const endpointItems = Array.isArray(keywordResp)
          ? keywordResp
          : Array.isArray(keywordResp?.keywords)
            ? keywordResp.keywords
            : Array.isArray(keywordResp?.items)
              ? keywordResp.items
              : null

        if (!endpointItems) {
          throw new Error('Unexpected keyword endpoint response')
        }

        setKeywordOptions(normalizeKeywords(endpointItems))
        setKeywordSourceMode('endpoint')
        keywordEndpointUnavailableRef.current = false
        keywordEndpointRetryAtRef.current = 0
        return
      } catch {
        keywordEndpointUnavailableRef.current = true
        keywordEndpointRetryAtRef.current =
          Date.now() + MEDIA_KEYWORD_ENDPOINT_RETRY_COOLDOWN_MS
      }
    }

    const keywordsFromResults = new Set<string>()
    for (const result of results) {
      if (!result.keywords) continue
      for (const kw of result.keywords) {
        if (!searchText || kw.toLowerCase().includes(searchText.toLowerCase())) {
          keywordsFromResults.add(kw)
        }
      }
    }
    setKeywordOptions(Array.from(keywordsFromResults))
    setKeywordSourceMode('results')
  }, [mediaApiUnavailable, results])

  // Keep keyword suggestions in sync with results
  useEffect(() => {
    loadKeywordSuggestions()
  }, [loadKeywordSuggestions, results])

  const fetchSelectedDetails = useCallback(async (item: MediaResultItem) => {
    if (item.kind === 'media') {
      return bgRequest<any>({
        path: `/api/v1/media/${item.id}` as any,
        method: 'GET' as any
      })
    }
    if (item.kind === 'note') {
      return item.raw
    }
    return null
  }, [])

  const contentFromDetail = useCallback((detail: any): string => {
    if (!detail) return ''

    const firstString = (...vals: any[]): string => {
      for (const v of vals) {
        if (typeof v === 'string' && v.trim().length > 0) return v
      }
      return ''
    }

    if (typeof detail === 'string') return detail
    if (typeof detail !== 'object') return ''

    // Check content object first (tldw API structure)
    if (detail.content && typeof detail.content === 'object') {
      const contentText = firstString(
        detail.content.text,
        detail.content.content,
        detail.content.raw_text
      )
      if (contentText) return contentText
    }

    // Try root level string fields
    const fromRoot = firstString(
      detail.text,
      detail.transcript,
      detail.raw_text,
      detail.rawText,
      detail.raw_content,
      detail.rawContent
    )
    if (fromRoot) return fromRoot

    // Try latest_version object
    const lv = detail.latest_version || detail.latestVersion
    if (lv && typeof lv === 'object') {
      const fromLatest = firstString(
        lv.content,
        lv.text,
        lv.transcript,
        lv.raw_text,
        lv.rawText
      )
      if (fromLatest) return fromLatest
    }

    // Try data object
    const data = detail.data
    if (data && typeof data === 'object') {
      const fromData = firstString(
        data.content,
        data.text,
        data.transcript,
        data.raw_text,
        data.rawText
      )
      if (fromData) return fromData
    }

    return ''
  }, [])

  // Extract keywords from media detail
  const extractKeywordsFromDetail = (detail: any): string[] => {
    return extractKeywordsFromMedia(detail)
  }

  const resolveDetailFetchErrorMessage = useCallback((error: unknown): string => {
    const statusCode = getErrorStatusCode(error)
    if (statusCode === 404) {
      return t('review:mediaPage.detailUnavailable', {
        defaultValue: 'This item is no longer available. It may have been deleted.'
      })
    }
    return t('review:mediaPage.detailFetchFailed', {
      defaultValue: 'Unable to load this item. Please try again.'
    })
  }, [t])

  // Track selected ID to avoid re-fetching on keyword updates
  const [lastFetchedId, setLastFetchedId] = useState<string | number | null>(null)

  const loadSelectedDetails = useCallback(async (item: MediaResultItem) => {
    setDetailLoading(true)
    setDetailFetchError(null)
    setSelectedContent('')
    setSelectedDetail(null)

    try {
      const detail = await fetchSelectedDetails(item)
      const content = contentFromDetail(detail)
      setSelectedContent(String(content || ''))
      setSelectedDetail(detail)
      setLastFetchedId(item.id)

      const keywords = extractKeywordsFromDetail(detail)
      if (keywords.length > 0 && (!item.keywords || item.keywords.length === 0)) {
        setSelected((prev) => {
          if (!prev || prev.id !== item.id) return prev
          return { ...prev, keywords }
        })
      }

      return true
    } catch (error) {
      console.error('Error fetching media details:', error)
      setSelectedContent('')
      setSelectedDetail(null)
      setDetailFetchError({
        mediaId: item.id,
        message: resolveDetailFetchErrorMessage(error)
      })
      return false
    } finally {
      setDetailLoading(false)
    }
  }, [
    contentFromDetail,
    fetchSelectedDetails,
    resolveDetailFetchErrorMessage
  ])
  const loadSelectedDetailsRef = useRef(loadSelectedDetails)

  useEffect(() => {
    loadSelectedDetailsRef.current = loadSelectedDetails
  }, [loadSelectedDetails])

  useEffect(() => {
    if (!staleSelectionNotice) return
    const timer = window.setTimeout(() => {
      setStaleSelectionNotice(null)
    }, 8000)
    return () => {
      window.clearTimeout(timer)
    }
  }, [staleSelectionNotice])

  useEffect(() => {
    if (!pendingInitialMediaId) return

    const pendingId = pendingInitialMediaId
    const pendingSource = pendingInitialMediaIdSource
    const matchingResult = displayResults.find(
      (item) => item.kind === 'media' && String(item.id) === pendingId
    )
    if (matchingResult) {
      setSelected(matchingResult)
      setPendingInitialMediaId(null)
      setPendingInitialMediaIdSource(null)
      if (pendingSource === 'setting') {
        void clearSetting(LAST_MEDIA_ID_SETTING)
      }
      return
    }

    let cancelled = false
    ;(async () => {
      try {
        const detail = await bgRequest<any>({
          path: `/api/v1/media/${pendingId}` as any,
          method: 'GET' as any
        })
        if (cancelled) return

        const resolvedId = detail?.id ?? detail?.media_id ?? pendingId
        const hydratedSelection: MediaResultItem = {
          kind: 'media',
          id: resolvedId,
          title: detail?.title || detail?.filename || `Media ${resolvedId}`,
          snippet: detail?.snippet || detail?.summary || '',
          keywords: extractKeywordsFromMedia(detail),
          meta: deriveMediaMeta(detail),
          raw: detail
        }

        setSelected(hydratedSelection)
        setSelectedContent(String(contentFromDetail(detail) || ''))
        setSelectedDetail(detail)
        setLastFetchedId(resolvedId)
      } catch (error) {
        console.debug('Failed to hydrate permalink media selection', error)
      } finally {
        if (cancelled) return
        setPendingInitialMediaId(null)
        setPendingInitialMediaIdSource(null)
        if (pendingSource === 'setting') {
          void clearSetting(LAST_MEDIA_ID_SETTING)
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [
    contentFromDetail,
    displayResults,
    pendingInitialMediaId,
    pendingInitialMediaIdSource
  ])

  // Load selected item content
  useEffect(() => {
    const currentSelection = selected
    if (!currentSelection) {
      setSelectedContent('')
      setSelectedDetail(null)
      setLastFetchedId(null)
      setDetailFetchError(null)
      setDetailLoading(false)
      return
    }

    if (currentSelection.id === lastFetchedId) {
      return
    }

    void loadSelectedDetailsRef.current(currentSelection)
  }, [lastFetchedId, selected?.id])

  useEffect(() => {
    if (!selected || selected.kind !== 'media') return
    if (detailLoading) return

    let cancelled = false
    let inFlight = false
    const selectedId = String(selected.id)
    const selectedValue = selected.id

    const reconcileStaleSelection = async () => {
      if (inFlight || cancelled) return
      inFlight = true
      try {
        await bgRequest<any>({
          path: `/api/v1/media/${selectedId}` as any,
          method: 'GET' as any
        })
      } catch (error) {
        const statusCode = getErrorStatusCode(error)
        if (statusCode !== 404 && statusCode !== 410) {
          return
        }
        if (cancelled) return

        const staleMessage = t('review:mediaPage.staleSelectionRecovered', {
          defaultValue:
            'The selected item is no longer available. Your selection was updated.'
        })
        setStaleSelectionNotice(staleMessage)
        message.warning(staleMessage)

        const currentIndex = displayResults.findIndex(
          (item) => String(item.id) === selectedId
        )
        const refreshed = await refetch()
        const refreshedResults = Array.isArray(refreshed?.data)
          ? (refreshed.data as MediaResultItem[])
          : []
        const remaining = refreshedResults.filter(
          (item) => String(item.id) !== selectedId
        )

        if (remaining.length > 0) {
          const nextIndex =
            currentIndex >= 0
              ? Math.min(currentIndex, remaining.length - 1)
              : 0
          const replacement = remaining[nextIndex]
          setLastFetchedId(null)
          setSelected(replacement)
          setDetailFetchError({
            mediaId: selectedValue,
            message: t('review:mediaPage.detailUnavailable', {
              defaultValue: 'This item is no longer available. It may have been deleted.'
            })
          })
          return
        }

        setSelected(null)
        setSelectedContent('')
        setSelectedDetail(null)
        setLastFetchedId(null)
        setDetailFetchError({
          mediaId: selectedValue,
          message: t('review:mediaPage.detailUnavailable', {
            defaultValue: 'This item is no longer available. It may have been deleted.'
          })
        })
      } finally {
        inFlight = false
      }
    }

    const interval = window.setInterval(() => {
      void reconcileStaleSelection()
    }, MEDIA_STALE_CHECK_INTERVAL_MS)

    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [
    detailLoading,
    displayResults,
    message,
    refetch,
    selected?.id,
    selected?.kind,
    t
  ])

  const selectedMediaPermalinkId =
    selected?.kind === 'media' && selected?.id != null ? String(selected.id) : null

  useEffect(() => {
    if (!selectedMediaPermalinkId) return
    void setSetting(LAST_MEDIA_ID_SETTING, selectedMediaPermalinkId)
  }, [selectedMediaPermalinkId])

  useEffect(() => {
    if (
      selectedMediaPermalinkId == null &&
      pendingInitialMediaIdSource === 'url' &&
      pendingInitialMediaId
    ) {
      return
    }
    const nextSearch = buildMediaPermalinkSearch(
      location.search,
      selectedMediaPermalinkId
    )
    if (nextSearch === location.search) return
    navigate(
      {
        pathname: location.pathname,
        search: nextSearch,
        hash: location.hash
      },
      { replace: true }
    )
  }, [
    location.hash,
    location.pathname,
    location.search,
    navigate,
    pendingInitialMediaId,
    pendingInitialMediaIdSource,
    selectedMediaPermalinkId
  ])

  // Note: Removed auto-clear effect that cleared selection when item wasn't in current results.
  // This caused UX issues - selection was lost when changing filters or pages.
  // The selection now persists until the user explicitly selects a different item.

  // Refresh media details (e.g., after generating analysis)
  const handleRefreshMedia = useCallback(async () => {
    if (!selected) return
    const refreshed = await loadSelectedDetails(selected)
    if (refreshed && showNavigationPanel) {
      void refetchNavigation()
    }
  }, [
    loadSelectedDetails,
    refetchNavigation,
    selected,
    showNavigationPanel
  ])

  const handleRetryDetailFetch = useCallback(() => {
    if (!selected) return
    void loadSelectedDetails(selected)
  }, [loadSelectedDetails, selected])

  const handleSearch = () => {
    setPage(1)
    refetch()
  }

  const handleToggleBulkSelectionMode = useCallback(() => {
    setBulkSelectionMode((prev) => !prev)
    setBulkKeywordsDraft('')
  }, [])

  const toggleBulkItemSelection = useCallback((id: string | number) => {
    const idStr = String(id)
    setBulkSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(idStr)) {
        next.delete(idStr)
      } else {
        next.add(idStr)
      }
      return Array.from(next)
    })
  }, [])

  const handleSelectAllVisibleItems = useCallback(() => {
    setBulkSelectedIds(displayResults.map((item) => String(item.id)))
  }, [displayResults])

  const handleClearBulkSelection = useCallback(() => {
    setBulkSelectedIds([])
  }, [])

  const handleBulkAddKeywords = useCallback(async () => {
    const keywordsToAdd = bulkKeywordsDraft
      .split(',')
      .map((keyword) => keyword.trim())
      .filter((keyword, index, all) => keyword.length > 0 && all.indexOf(keyword) === index)

    if (keywordsToAdd.length === 0) {
      message.warning(
        t('review:mediaPage.bulkAddKeywordsMissing', {
          defaultValue: 'Enter at least one keyword.'
        })
      )
      return
    }

    if (bulkSelectedMediaItems.length === 0) {
      message.warning(
        t('review:mediaPage.bulkAddKeywordsNoMedia', {
          defaultValue: 'Select at least one media item to tag.'
        })
      )
      return
    }

    let updatedCount = 0
    let failedCount = 0
    const updatedKeywordMap = new Map<string, string[]>()

    for (const item of bulkSelectedMediaItems) {
      const currentKeywords = Array.isArray(item.keywords) ? item.keywords : []
      const mergedKeywords = Array.from(new Set([...currentKeywords, ...keywordsToAdd]))
      try {
        await bgRequest({
          path: `/api/v1/media/${item.id}` as any,
          method: 'PUT' as any,
          headers: { 'Content-Type': 'application/json' },
          body: { keywords: mergedKeywords }
        })
        updatedKeywordMap.set(String(item.id), mergedKeywords)
        updatedCount += 1
      } catch {
        failedCount += 1
      }
    }

    if (updatedKeywordMap.size > 0) {
      setSelected((prev) => {
        if (!prev) return prev
        const nextKeywords = updatedKeywordMap.get(String(prev.id))
        if (!nextKeywords) return prev
        return { ...prev, keywords: nextKeywords }
      })
      await refetch()
    }

    if (failedCount > 0) {
      message.warning(
        t('review:mediaPage.bulkAddKeywordsPartial', {
          defaultValue: 'Updated {{updated}} item(s), {{failed}} failed.',
          updated: updatedCount,
          failed: failedCount
        })
      )
    } else {
      message.success(
        t('review:mediaPage.bulkAddKeywordsSuccess', {
          defaultValue: 'Updated keywords for {{count}} item(s).',
          count: updatedCount
        })
      )
    }

    if (bulkSelectedNoteCount > 0) {
      message.warning(
        t('review:mediaPage.bulkAddKeywordsSkippedNotes', {
          defaultValue: 'Skipped {{count}} note item(s).',
          count: bulkSelectedNoteCount
        })
      )
    }
  }, [
    bulkKeywordsDraft,
    bulkSelectedMediaItems,
    bulkSelectedNoteCount,
    message,
    refetch,
    t
  ])

  const handleBulkDelete = useCallback(async () => {
    if (bulkSelectedItems.length === 0) {
      message.warning(
        t('review:mediaPage.bulkDeleteNothingSelected', {
          defaultValue: 'Select items to delete.'
        })
      )
      return
    }

    const parseVersion = (value: unknown): number | null => {
      if (typeof value === 'number' && Number.isFinite(value)) return value
      if (typeof value === 'string') {
        const trimmed = value.trim()
        if (/^\d+$/.test(trimmed)) return Number.parseInt(trimmed, 10)
      }
      return null
    }

    let deletedCount = 0
    let failedCount = 0
    const deletedIdSet = new Set<string>()

    for (const item of bulkSelectedItems) {
      try {
        if (item.kind === 'note') {
          const latest = await bgRequest<any>({
            path: `/api/v1/notes/${item.id}` as any,
            method: 'GET' as any
          })
          const expectedVersion =
            parseVersion(latest?.version) ?? parseVersion(latest?.metadata?.version)
          if (expectedVersion == null) {
            throw new Error('Missing expected version')
          }
          await bgRequest({
            path: `/api/v1/notes/${item.id}` as any,
            method: 'DELETE' as any,
            headers: { 'expected-version': String(expectedVersion) }
          })
        } else {
          await bgRequest({
            path: `/api/v1/media/${item.id}` as any,
            method: 'DELETE' as any
          })
        }
        deletedIdSet.add(String(item.id))
        deletedCount += 1
      } catch {
        failedCount += 1
      }
    }

    if (deletedIdSet.size > 0) {
      setFavorites((prev: string[] | undefined) =>
        (prev || []).filter((favoriteId) => !deletedIdSet.has(String(favoriteId)))
      )
      setSelected((prev) => {
        if (!prev) return prev
        if (!deletedIdSet.has(String(prev.id))) return prev
        return null
      })
      setBulkSelectedIds((prev) => prev.filter((id) => !deletedIdSet.has(id)))
      setSelectedContent('')
      setSelectedDetail(null)
      setLastFetchedId(null)
      await refetch()
      void refreshLibraryStorageUsage()
    }

    if (failedCount > 0) {
      message.warning(
        t('review:mediaPage.bulkDeletePartial', {
          defaultValue: 'Deleted {{deleted}} item(s), {{failed}} failed.',
          deleted: deletedCount,
          failed: failedCount
        })
      )
      return
    }

    message.success(
      t('review:mediaPage.bulkDeleteSuccess', {
        defaultValue: 'Deleted {{count}} item(s).',
        count: deletedCount
      })
    )
  }, [
    bulkSelectedItems,
    message,
    refetch,
    refreshLibraryStorageUsage,
    setFavorites,
    t
  ])

  const handleBulkExport = useCallback(() => {
    if (bulkSelectedItems.length === 0) {
      message.warning(
        t('review:mediaPage.bulkExportNothingSelected', {
          defaultValue: 'Select items to export.'
        })
      )
      return
    }

    const exportPayload = {
      exported_at: new Date().toISOString(),
      items: bulkSelectedItems.map((item) => ({
        id: item.id,
        kind: item.kind,
        title: item.title || `${item.kind} ${item.id}`,
        snippet: item.snippet || '',
        keywords: Array.isArray(item.keywords) ? item.keywords : [],
        type: item.meta?.type || null,
        source: item.meta?.source || null
      }))
    }

    let fileContent = ''
    let extension = 'json'
    let mimeType = 'application/json'

    if (bulkExportFormat === 'markdown') {
      extension = 'md'
      mimeType = 'text/markdown'
      const lines: string[] = ['# Media Bulk Export', '']
      for (const item of exportPayload.items) {
        lines.push(`## ${item.title}`)
        lines.push(`- ID: ${item.id}`)
        lines.push(`- Kind: ${item.kind}`)
        if (item.type) lines.push(`- Type: ${item.type}`)
        if (item.source) lines.push(`- Source: ${item.source}`)
        if (item.keywords.length > 0) {
          lines.push(`- Keywords: ${item.keywords.join(', ')}`)
        }
        if (item.snippet) {
          lines.push('', item.snippet)
        }
        lines.push('')
      }
      fileContent = lines.join('\n')
    } else if (bulkExportFormat === 'text') {
      extension = 'txt'
      mimeType = 'text/plain'
      const lines: string[] = []
      for (const item of exportPayload.items) {
        lines.push(`${item.title} [${item.kind} #${item.id}]`)
        if (item.type) lines.push(`Type: ${item.type}`)
        if (item.source) lines.push(`Source: ${item.source}`)
        if (item.keywords.length > 0) lines.push(`Keywords: ${item.keywords.join(', ')}`)
        if (item.snippet) lines.push(`Snippet: ${item.snippet}`)
        lines.push('')
      }
      fileContent = lines.join('\n')
    } else {
      fileContent = JSON.stringify(exportPayload, null, 2)
    }

    const blob = new Blob([fileContent], { type: mimeType })
    downloadBlob(blob, `media-bulk-export-${Date.now()}.${extension}`)
    message.success(
      t('review:mediaPage.bulkExportReady', {
        defaultValue: 'Bulk export ready.'
      })
    )
  }, [bulkExportFormat, bulkSelectedItems, message, t])

  const handleAddSelectionToCollection = useCallback(() => {
    if (bulkSelectedItems.length === 0) {
      message.warning(
        t('review:mediaPage.collectionRequiresSelection', {
          defaultValue: 'Select at least one item first.'
        })
      )
      return
    }

    const targetCollectionName =
      collectionDraftName.trim() || activeCollection?.name?.trim() || ''
    if (!targetCollectionName) {
      message.warning(
        t('review:mediaPage.collectionNameRequired', {
          defaultValue: 'Enter a collection name.'
        })
      )
      return
    }

    const selectedItemIds = bulkSelectedItems.map((item) => String(item.id))
    const now = new Date().toISOString()
    const normalizedName = targetCollectionName.toLowerCase()
    const existing = mediaCollections.find(
      (entry) => entry.name.trim().toLowerCase() === normalizedName
    )
    if (existing) {
      setMediaCollections((prevCollections) => {
        const collections = Array.isArray(prevCollections) ? prevCollections : []
        return collections.map((entry) => {
          if (entry.id !== existing.id) return entry
          const mergedIds = Array.from(
            new Set([...entry.itemIds.map((id) => String(id)), ...selectedItemIds])
          )
          return {
            ...entry,
            itemIds: mergedIds,
            updatedAt: now
          }
        })
      })
      setActiveCollectionId(existing.id)
    } else {
      const slug =
        targetCollectionName
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, '-')
          .replace(/(^-|-$)/g, '') || 'collection'
      const created: MediaCollectionRecord = {
        id: `${slug}-${Date.now()}`,
        name: targetCollectionName,
        itemIds: Array.from(new Set(selectedItemIds)),
        createdAt: now,
        updatedAt: now
      }
      setMediaCollections((prevCollections) => {
        const collections = Array.isArray(prevCollections) ? prevCollections : []
        return [...collections, created]
      })
      setActiveCollectionId(created.id)
    }
    setCollectionDraftName('')
    message.success(
      t('review:mediaPage.collectionSaved', {
        defaultValue: 'Saved selection to collection.'
      })
    )
  }, [
    activeCollection?.name,
    bulkSelectedItems,
    collectionDraftName,
    mediaCollections,
    message,
    setMediaCollections,
    t
  ])

  const handleOpenSelectionInMultiReview = useCallback(async () => {
    if (bulkSelectedIds.length === 0) {
      message.warning(
        t('review:mediaPage.bulkOpenInMultiReviewNone', {
          defaultValue: 'Select items to open in multi-review.'
        })
      )
      return
    }
    await setSetting(MEDIA_REVIEW_SELECTION_SETTING, bulkSelectedIds)
    await setSetting(LAST_MEDIA_ID_SETTING, String(bulkSelectedIds[0]))
    navigate('/media-multi')
  }, [bulkSelectedIds, message, navigate, t])

  const handleOpenCollectionInMultiReview = useCallback(async () => {
    if (!activeCollection || activeCollection.itemIds.length === 0) {
      message.warning(
        t('review:mediaPage.collectionEmpty', {
          defaultValue: 'No items in this collection.'
        })
      )
      return
    }
    const collectionIds = activeCollection.itemIds.map((id) => String(id))
    await setSetting(MEDIA_REVIEW_SELECTION_SETTING, collectionIds)
    await setSetting(LAST_MEDIA_ID_SETTING, String(collectionIds[0]))
    navigate('/media-multi')
  }, [activeCollection, message, navigate, t])

  const handleKindChange = useCallback((nextKind: 'media' | 'notes') => {
    if (searchMode === 'metadata' && nextKind === 'notes') {
      return
    }
    setKinds((prev) => resolveKindsForTab(prev, nextKind))
    setPage(1)
  }, [searchMode])

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }

  const selectedIndex = displayResults.findIndex((r) => r.id === selected?.id)
  const hasPrevious = selectedIndex > 0
  const hasNext = selectedIndex >= 0 && selectedIndex < displayResults.length - 1

  const handlePrevious = () => {
    if (hasPrevious) {
      setSelected(displayResults[selectedIndex - 1])
    }
  }

  const handleNext = () => {
    if (hasNext) {
      setSelected(displayResults[selectedIndex + 1])
    }
  }

  const handleDeleteItem = useCallback(
    async (item: MediaResultItem, detail: any | null) => {
      const id = item.id
      const idStr = String(id)
      const wasFavorite = favoritesSet.has(idStr)
      const itemTitle =
        item.title ||
        `${t('review:mediaPage.media', { defaultValue: 'Media' })} ${idStr}`

      // Helper to parse version from various sources
      const parseVersionCandidate = (value: unknown): number | null => {
        if (typeof value === 'number' && Number.isFinite(value)) return value
        if (typeof value === 'string') {
          const trimmed = value.trim()
          if (/^\d+$/.test(trimmed)) return Number.parseInt(trimmed, 10)
        }
        return null
      }

      // Store the version used for delete so we can use it for restore (incremented by 1)
      let deletedAtVersion: number | null = null

      try {
        if (item.kind === 'note') {
          let expectedVersion: number | null = null
          const versionCandidates = [
            detail?.version,
            detail?.metadata?.version,
            item.raw?.version,
            item.raw?.metadata?.version
          ]
          for (const candidate of versionCandidates) {
            const parsed = parseVersionCandidate(candidate)
            if (parsed != null) {
              expectedVersion = parsed
              break
            }
          }
          if (expectedVersion == null) {
            try {
              const latest = await bgRequest<any>({
                path: `/api/v1/notes/${id}` as any,
                method: 'GET' as any
              })
              expectedVersion =
                parseVersionCandidate(latest?.version) ??
                parseVersionCandidate(latest?.metadata?.version)
            } catch {
              throw new Error(
                t('review:mediaPage.noteDeleteNeedsReload', {
                  defaultValue: 'Unable to delete note. Reload and try again.'
                })
              )
            }
          }
          if (expectedVersion == null) {
            throw new Error(
              t('review:mediaPage.noteDeleteNeedsReload', {
                defaultValue: 'Unable to delete note. Reload and try again.'
              })
            )
          }
          await bgRequest({
            path: `/api/v1/notes/${id}` as any,
            method: 'DELETE' as any,
            headers: { 'expected-version': String(expectedVersion) }
          })
          // After soft-delete, the version is incremented by 1
          deletedAtVersion = expectedVersion + 1
        } else {
          await bgRequest({
            path: `/api/v1/media/${id}` as any,
            method: 'DELETE' as any
          })
        }
      } catch (err) {
        const status = err && typeof err === 'object' && 'status' in err
          ? (err as { status?: number }).status
          : undefined
        const msg = err && typeof err === 'object' && 'message' in err
          ? String((err as { message?: unknown }).message || '')
          : ''
        if (
          item.kind === 'note' &&
          (status === 409 ||
            msg.toLowerCase().includes('expected-version') ||
            msg.toLowerCase().includes('version'))
        ) {
          throw new Error(
            t('review:mediaPage.noteDeleteNeedsReload', {
              defaultValue: 'Unable to delete note. Reload and try again.'
            })
          )
        }
        throw err
      }

      setFavorites((prev: string[] | undefined) =>
        (prev || []).filter((fav) => fav !== idStr)
      )

      const remainingResults = displayResults.filter(
        (r) => String(r.id) !== idStr
      )
      if (remainingResults.length > 0) {
        const currentIndex = displayResults.findIndex(
          (r) => String(r.id) === idStr
        )
        const nextIndex =
          currentIndex >= 0
            ? Math.min(currentIndex, remainingResults.length - 1)
            : 0
        setSelected(remainingResults[nextIndex])
      } else {
        setSelected(null)
        setSelectedContent('')
        setSelectedDetail(null)
        setLastFetchedId(null)
      }

      void refetch()
      void refreshLibraryStorageUsage()

      // Show undo notification for both media and notes
      showUndoNotification({
        title: t('review:mediaPage.itemMovedToTrash', {
          defaultValue: 'Moved to trash'
        }),
        description: t('review:mediaPage.itemMovedToTrashDesc', {
          defaultValue: '"{{title}}" moved to trash.',
          title: itemTitle
        }),
        onUndo: async () => {
          if (item.kind === 'note') {
            // Restore note using the new API
            if (deletedAtVersion != null) {
              await bgRequest({
                path: `/api/v1/notes/${id}/restore?expected_version=${deletedAtVersion}` as any,
                method: 'POST' as any
              })
            }
          } else {
            await bgRequest({
              path: `/api/v1/media/${id}/restore` as any,
              method: 'POST' as any
            })
          }
          if (wasFavorite) {
            setFavorites((prev: string[] | undefined) => {
              const next = new Set(prev || [])
              next.add(idStr)
              return Array.from(next)
            })
          }
          const refreshed = await refetch()
          void refreshLibraryStorageUsage()
          const restoredItem = refreshed.data?.find(
            (r: MediaResultItem) => String(r.id) === idStr
          )
          if (restoredItem) {
            setSelected((prev) => {
              const prevId = prev?.id != null ? String(prev.id) : null
              if (!prevId || prevId === idStr) return restoredItem
              return prev
            })
          }
        }
      })
    },
    [
      displayResults,
      favoritesSet,
      refetch,
      refreshLibraryStorageUsage,
      setFavorites,
      showUndoNotification,
      t
    ]
  )

  // Keyboard shortcuts for navigation (j/k for items, arrows for pages, ? for help)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if typing in input
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        (e.target as HTMLElement)?.isContentEditable
      ) {
        return
      }

      switch (e.key) {
        case '?':
          e.preventDefault()
          setShortcutsOverlayOpen((prev) => !prev)
          break
        case '/':
          if (e.ctrlKey || e.metaKey || e.altKey) break
          e.preventDefault()
          if (searchCollapsed) {
            setSearchCollapsed(false)
            window.setTimeout(() => {
              const input = searchInputRef.current
              if (!input) return
              input.focus()
              input.select()
            }, 0)
          } else {
            const input = searchInputRef.current
            if (input) {
              input.focus()
              input.select()
            }
          }
          break
        case 'j':
          if (hasNext) {
            e.preventDefault()
            setSelected(displayResults[selectedIndex + 1])
          }
          break
        case 'k':
          if (hasPrevious) {
            e.preventDefault()
            setSelected(displayResults[selectedIndex - 1])
          }
          break
        case 'ArrowLeft':
          if (page > 1) {
            e.preventDefault()
            setPage((p) => p - 1)
          }
          break
        case 'ArrowRight':
          if (page < totalPages) {
            e.preventDefault()
            setPage((p) => p + 1)
          }
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [
    hasNext,
    hasPrevious,
    page,
    totalPages,
    results,
    searchCollapsed,
    selectedIndex,
  ])

  const handleChatWithMedia = useCallback(() => {
    if (!selected) return

    const title = selected.title || String(selected.id)
    const content = effectiveContent || ''

    try {
      const payload = {
        mediaId: String(selected.id),
        title,
        content,
        mode: 'normal' as const
      }
      void setSetting(DISCUSS_MEDIA_PROMPT_SETTING, payload)
      try {
        window.dispatchEvent(
          new CustomEvent('tldw:discuss-media', {
            detail: payload
          })
        )
      } catch {
        // ignore event errors
      }
    } catch {
      // ignore storage errors
    }
    setChatMode('normal')
    setSelectedKnowledge(null as any)
    setRagMediaIds(null)
    navigate('/')
    message.success(
      t(
        'review:reviewPage.chatPrepared',
        'Prepared chat with this media in the composer.'
      )
    )
  }, [
    effectiveContent,
    message,
    navigate,
    selected,
    setChatMode,
    setRagMediaIds,
    setSelectedKnowledge,
    t
  ])

  const handleChatAboutMedia = useCallback(() => {
    if (!selected) return

    const idNum = Number(selected.id)
    if (!Number.isFinite(idNum)) {
      message.warning(
        t(
          'review:reviewPage.chatAboutMediaInvalidId',
          'This media item does not have a numeric id yet.'
        )
      )
      return
    }
    setSelectedKnowledge(null as any)
    setRagMediaIds([idNum])
    setChatMode('rag')
    try {
      const payload = {
        mediaId: String(selected.id),
        mode: 'rag_media' as const
      }
      void setSetting(DISCUSS_MEDIA_PROMPT_SETTING, payload)
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('tldw:discuss-media', { detail: payload }))
      }
    } catch {
      // ignore storage/event errors
    }
    navigate('/')
    try {
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('tldw:focus-composer'))
      }
    } catch {
      // ignore
    }
    message.success(
      t(
        'review:reviewPage.chatAboutMediaRagSent',
        'Opened media-scoped RAG chat.'
      )
    )
  }, [selected, setSelectedKnowledge, setRagMediaIds, setChatMode, navigate, message, t])

  const handleGenerateFlashcardsFromMedia = useCallback(
    (payload: {
      text: string
      sourceId?: string
      sourceTitle?: string
    }) => {
      const sourceText = String(payload.text || "").trim()
      if (!sourceText) {
        message.warning(
          t("review:mediaPage.generateFlashcardsEmpty", {
            defaultValue: "No content available to generate flashcards."
          })
        )
        return
      }

      navigate(
        buildFlashcardsGenerateRoute({
          text: sourceText,
          sourceType: "media",
          sourceId:
            payload.sourceId ||
            (selected?.id != null ? String(selected.id) : undefined),
          sourceTitle: payload.sourceTitle || selected?.title || undefined
        })
      )
    },
    [message, navigate, selected, t]
  )

  const handleCreateNoteWithContent = useCallback(async (noteContent: string, title: string) => {
    try {
      await bgRequest({
        path: '/api/v1/notes/' as any,
        method: 'POST' as any,
        headers: { 'Content-Type': 'application/json' },
        body: {
          title: title,
          content: noteContent,
          keywords: selected?.keywords || []
        }
      })
      message.success('Note created successfully')
      navigate('/notes')
    } catch (err) {
      console.error('Failed to create note:', err)
      message.error('Failed to create note')
    }
  }, [selected, message, navigate])

  const handleOpenInMultiReview = useCallback(() => {
    if (!selected) return
    void setSetting(LAST_MEDIA_ID_SETTING, String(selected.id))
    navigate('/media-multi')
  }, [selected, navigate])

  const handleSendAnalysisToChat = useCallback((text: string) => {
    if (!text.trim()) {
      message.warning(t('review:reviewPage.nothingToSend', 'Nothing to send'))
      return
    }
    try {
      const payload = {
        mediaId: selected ? String(selected.id) : undefined,
        title: selected?.title || 'Analysis',
        content: `Please review this analysis and continue the discussion:\n\n${text}`,
        mode: 'normal' as const
      }
      void setSetting(DISCUSS_MEDIA_PROMPT_SETTING, payload)
      window.dispatchEvent(new CustomEvent('tldw:discuss-media', { detail: payload }))
    } catch {
      // ignore storage errors
    }
    setChatMode('normal')
    setSelectedKnowledge(null as any)
    setRagMediaIds(null)
    navigate('/')
    message.success(t('review:reviewPage.sentToChat', 'Sent to chat'))
  }, [selected, setChatMode, setSelectedKnowledge, setRagMediaIds, navigate, message, t])

  return (
    <div
      className="relative flex min-h-full bg-bg"
      style={{ minHeight: `${mediaPageMinHeightPx}px` }}
    >
      {/* Left Sidebar */}
      <div
        className={`bg-surface border-r border-border flex h-full min-h-0 flex-col transition-[width] duration-300 ease-in-out ${
          sidebarCollapsedValue ? 'w-0' : 'w-full md:w-[22rem] lg:w-[25rem]'
        }`}
        style={{
          overflowX: 'hidden',
          overflowY: 'auto'
        }}
      >
        <div
          className="flex min-h-full flex-col bg-surface"
          hidden={sidebarCollapsedValue}
          aria-hidden={sidebarCollapsedValue}
        >
          {/* Header */}
          <div className="shrink-0 border-b border-border/80 bg-surface px-4 py-3.5">
            <div className="flex items-center justify-between gap-3">
              <h1 className="text-text text-base font-semibold">
                {t('review:mediaPage.mediaInspector', { defaultValue: 'Media Inspector' })}
              </h1>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-medium tabular-nums text-text-muted">
                  {displayResults.length} / {
                    kinds.media && kinds.notes
                      ? combinedTotal
                      : kinds.notes
                        ? notesTotal
                        : mediaTotal
                  }
                </span>
                <button
                  type="button"
                  onClick={() => navigate('/media-trash')}
                  className="inline-flex h-7 items-center gap-1 rounded-md border border-border px-2 text-[11px] text-text-muted hover:bg-surface2 hover:text-text"
                  aria-label={t('review:mediaPage.openTrash', { defaultValue: 'Trash' })}
                  title={t('review:mediaPage.openTrash', { defaultValue: 'Trash' })}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  {t('review:mediaPage.openTrash', { defaultValue: 'Trash' })}
                </button>
                <button
                  type="button"
                  onClick={handleToggleBulkSelectionMode}
                  className={`inline-flex h-7 items-center gap-1 rounded-md border px-2 text-[11px] ${
                    bulkSelectionMode
                      ? 'border-primary bg-primary/10 text-primaryStrong'
                      : 'border-border text-text-muted hover:bg-surface2 hover:text-text'
                  }`}
                  data-testid="media-bulk-mode-toggle"
                  aria-pressed={bulkSelectionMode}
                >
                  {bulkSelectionMode ? (
                    <CheckSquare className="h-3.5 w-3.5" />
                  ) : (
                    <Square className="h-3.5 w-3.5" />
                  )}
                  {t('review:mediaPage.bulkMode', { defaultValue: 'Bulk' })}
                </button>
              </div>
            </div>

            <div className="mt-3 inline-flex items-center gap-1 rounded-lg border border-border bg-surface2/70 p-1">
              <button
                type="button"
                onClick={() => handleKindChange('media')}
                className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium transition-colors ${
                  isMediaOnly(kinds)
                    ? 'bg-primary text-white'
                    : 'text-text hover:bg-surface'
                }`}
                aria-pressed={isMediaOnly(kinds)}
                aria-label={t('review:mediaPage.showMediaOnly', { defaultValue: 'Show media only' })}
              >
                <span>{t('review:mediaPage.media', { defaultValue: 'Media' })}</span>
                <span className="rounded-full bg-black/10 px-1.5 py-0.5 text-[10px] font-medium">
                  {mediaTotal}
                </span>
              </button>
              <button
                type="button"
                onClick={() => handleKindChange('notes')}
                className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium transition-colors ${
                  isNotesOnly(kinds)
                    ? 'bg-primary text-white'
                    : 'text-text hover:bg-surface'
                } ${searchMode === 'metadata' ? 'opacity-50 cursor-not-allowed' : ''}`}
                disabled={searchMode === 'metadata'}
                title={
                  searchMode === 'metadata'
                    ? t('review:mediaPage.notesDisabledInMetadataMode', {
                        defaultValue: 'Notes are unavailable in metadata mode'
                      })
                    : undefined
                }
                aria-pressed={isNotesOnly(kinds)}
                aria-label={t('review:mediaPage.showNotesOnly', { defaultValue: 'Show notes only' })}
              >
                <span>{t('review:mediaPage.notes', { defaultValue: 'Notes' })}</span>
                <span className="rounded-full bg-black/10 px-1.5 py-0.5 text-[10px] font-medium">
                  {notesTotal}
                </span>
              </button>
            </div>
          </div>

          {/* Controls: Find Media + Jump To + Bulk Toolbar */}
          <div
            className="min-h-0 shrink overflow-y-auto border-b border-border/80"
          >

          {/* Find Media */}
          <div className="bg-surface px-4 py-3.5 space-y-3 border-b border-border/40">
            <div className="flex items-center justify-between">
              <span className="px-1 py-1 text-sm font-medium text-text">
                {t('review:mediaPage.findMedia', { defaultValue: 'Find media' })}
              </span>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setSearchCollapsed((prev) => !prev)}
                  className="inline-flex h-7 w-7 items-center justify-center rounded-md text-text-muted hover:bg-surface2 hover:text-text"
                  aria-expanded={!searchCollapsed}
                  aria-controls="media-search-panel"
                  aria-label={
                    searchCollapsed
                      ? t('review:mediaPage.expandFindMediaPanel', { defaultValue: 'Expand find media panel' })
                      : t('review:mediaPage.collapseFindMediaPanel', { defaultValue: 'Collapse find media panel' })
                  }
                >
                <ChevronDown
                  className={`w-4 h-4 transition-transform ${searchCollapsed ? '' : 'rotate-180'}`}
                />
                </button>
              </div>
            </div>
            {!searchCollapsed && (
              <div
                id="media-search-panel"
                className="space-y-2.5 pb-1 pr-1"
                onKeyDown={handleKeyPress}
              >
                <SearchBar
                  value={query}
                  onChange={setQuery}
                  inputRef={searchInputRef}
                  hasActiveFilters={hasActiveFilters}
                  onClearAll={resetAllFilters}
                />
                <FilterChips
                  mediaTypes={mediaTypes}
                  keywords={keywordTokens}
                  excludedKeywords={excludeKeywordTokens}
                  showFavoritesOnly={showFavoritesOnly}
                  activeFilterCount={activeFilterCount}
                  onRemoveMediaType={(type) => {
                    setMediaTypes((prev) => prev.filter((t) => t !== type))
                    setPage(1)
                  }}
                  onRemoveKeyword={(keyword) => {
                    setKeywordTokens((prev) => prev.filter((k) => k !== keyword))
                    setPage(1)
                  }}
                  onRemoveExcludedKeyword={(keyword) => {
                    setExcludeKeywordTokens((prev) => prev.filter((k) => k !== keyword))
                    setPage(1)
                  }}
                  onToggleFavorites={() => {
                    setShowFavoritesOnly(false)
                    setPage(1)
                  }}
                  onClearAll={resetAllFilters}
                />
                <button
                  onClick={handleSearch}
                  data-testid="media-search-submit"
                  className="w-full rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-primaryStrong"
                >
                  {t('review:mediaPage.search', { defaultValue: 'Search' })}
                </button>
                <FilterPanel
                  searchMode={searchMode}
                  onSearchModeChange={(nextMode) => {
                    if (nextMode === searchMode) return
                    setSearchMode(nextMode)
                    if (nextMode === 'metadata') {
                      setKinds({ media: true, notes: false })
                    }
                    setPage(1)
                  }}
                  mediaTypes={availableMediaTypes}
                  selectedMediaTypes={mediaTypes}
                  onMediaTypesChange={setMediaTypes}
                  sortBy={sortBy}
                  onSortByChange={(nextSort) => {
                    setSortBy(nextSort)
                    setPage(1)
                  }}
                  dateRange={dateRange}
                  onDateRangeChange={(nextDateRange) => {
                    setDateRange(nextDateRange)
                    setPage(1)
                  }}
                  exactPhrase={exactPhrase}
                  onExactPhraseChange={(nextExactPhrase) => {
                    setExactPhrase(nextExactPhrase)
                    setPage(1)
                  }}
                  searchFields={searchFields}
                  onSearchFieldsChange={(nextFields) => {
                    setSearchFields(nextFields)
                    setPage(1)
                  }}
                  enableBoostFields={enableBoostFields}
                  onEnableBoostFieldsChange={(enabled) => {
                    setEnableBoostFields(enabled)
                    setPage(1)
                  }}
                  boostFields={boostFields}
                  onBoostFieldsChange={(nextBoostFields) => {
                    setBoostFields(nextBoostFields)
                    setPage(1)
                  }}
                  metadataFilters={metadataFilters}
                  onMetadataFiltersChange={(nextFilters) => {
                    setMetadataFilters(nextFilters)
                    setPage(1)
                  }}
                  metadataMatchMode={metadataMatchMode}
                  onMetadataMatchModeChange={(mode) => {
                    setMetadataMatchMode(mode)
                    setPage(1)
                  }}
                  metadataValidationError={metadataValidationError}
                  selectedKeywords={keywordTokens}
                  onKeywordsChange={(kws) => {
                    setKeywordTokens(kws)
                    setPage(1)
                  }}
                  selectedExcludedKeywords={excludeKeywordTokens}
                  onExcludedKeywordsChange={(kws) => {
                    setExcludeKeywordTokens(kws)
                    setPage(1)
                  }}
                  keywordOptions={keywordOptions}
                  keywordSourceMode={keywordSourceMode}
                  onKeywordSearch={(txt) => {
                    loadKeywordSuggestions(txt)
                  }}
                  showFavoritesOnly={showFavoritesOnly}
                  onShowFavoritesOnlyChange={(show) => {
                    setShowFavoritesOnly(show)
                    setPage(1)
                  }}
                  favoritesCount={favoritesSet.size}
                  activeFilterCount={activeFilterCount}
                  onClearAll={resetAllFilters}
                />
                <div className="space-y-2 rounded-md border border-border/80 bg-surface2/60 px-2.5 py-2">
                  <div className="flex items-center gap-2">
                    <label
                      htmlFor="media-collection-filter"
                      className="text-[11px] font-medium text-text-muted"
                    >
                      {t('review:mediaPage.collectionFilterLabel', {
                        defaultValue: 'Collection'
                      })}
                    </label>
                    <select
                      id="media-collection-filter"
                      value={activeCollectionId || ''}
                      onChange={(event) => {
                        const nextValue = event.target.value.trim()
                        setActiveCollectionId(nextValue || null)
                        setPage(1)
                      }}
                      className="h-7 flex-1 rounded border border-border bg-surface px-2 text-[11px] text-text"
                      data-testid="media-collection-filter"
                    >
                      <option value="">
                        {t('review:mediaPage.collectionAll', {
                          defaultValue: 'All items'
                        })}
                      </option>
                      {mediaCollections.map((collection) => (
                        <option key={collection.id} value={collection.id}>
                          {collection.name} ({collection.itemIds.length})
                        </option>
                      ))}
                    </select>
                  </div>
                  {activeCollection ? (
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-[11px] text-text-muted">
                        {t('review:mediaPage.collectionItemsVisible', {
                          defaultValue: '{{count}} item(s) in this collection.',
                          count: activeCollection.itemIds.length
                        })}
                      </p>
                      <button
                        type="button"
                        onClick={() => {
                          void handleOpenCollectionInMultiReview()
                        }}
                        className="rounded border border-border px-2 py-1 text-[11px] font-medium text-text hover:bg-surface"
                        data-testid="media-collection-open-multi"
                      >
                        {t('review:mediaPage.collectionOpenMultiReview', {
                          defaultValue: 'Open in multi-review'
                        })}
                      </button>
                    </div>
                  ) : (
                    <p className="text-[11px] text-text-muted">
                      {t('review:mediaPage.collectionHint', {
                        defaultValue:
                          'Create collections from bulk selection to organize related items.'
                      })}
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          {bulkSelectionMode && (
            <div
              className="border-b border-border bg-surface2 px-4 py-3 space-y-2.5"
              data-testid="media-bulk-toolbar"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] font-medium text-text-muted">
                  {t('review:mediaPage.bulkSelectedCount', {
                    defaultValue: '{{count}} selected',
                    count: bulkSelectedItems.length
                  })}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleSelectAllVisibleItems}
                    className="inline-flex h-8 items-center gap-1 rounded-md border border-border px-2 text-[11px] text-text hover:bg-surface"
                    data-testid="media-bulk-select-all"
                  >
                    <CheckSquare className="h-3.5 w-3.5" />
                    {t('review:mediaPage.selectAllVisible', {
                      defaultValue: 'Select visible'
                    })}
                  </button>
                  <button
                    type="button"
                    onClick={handleClearBulkSelection}
                    className="inline-flex h-8 items-center gap-1 rounded-md border border-border px-2 text-[11px] text-text hover:bg-surface"
                    data-testid="media-bulk-clear"
                  >
                    <X className="h-3.5 w-3.5" />
                    {t('review:mediaPage.clearSelection', {
                      defaultValue: 'Clear'
                    })}
                  </button>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <input
                  value={bulkKeywordsDraft}
                  onChange={(event) => setBulkKeywordsDraft(event.target.value)}
                  placeholder={t('review:mediaPage.bulkKeywordsPlaceholder', {
                    defaultValue: 'Keywords (comma separated)'
                  })}
                  className="h-8 min-w-[180px] flex-1 rounded-md border border-border bg-surface px-2 text-[11px] text-text"
                  data-testid="media-bulk-keywords-input"
                />
                <button
                  type="button"
                  onClick={() => void handleBulkAddKeywords()}
                  disabled={bulkSelectedItems.length === 0}
                  className="inline-flex h-8 items-center gap-1 rounded-md border border-border px-2 text-[11px] text-text hover:bg-surface disabled:cursor-not-allowed disabled:opacity-60"
                  data-testid="media-bulk-tag"
                >
                  <Tags className="h-3.5 w-3.5" />
                  {t('review:mediaPage.bulkAddKeywords', { defaultValue: 'Add tags' })}
                </button>
                <button
                  type="button"
                  onClick={() => void handleBulkDelete()}
                  disabled={bulkSelectedItems.length === 0}
                  className="inline-flex h-8 items-center gap-1 rounded-md border border-danger/50 px-2 text-[11px] text-danger hover:bg-danger/10 disabled:cursor-not-allowed disabled:opacity-60"
                  data-testid="media-bulk-delete"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  {t('review:mediaPage.bulkDelete', { defaultValue: 'Delete' })}
                </button>
              </div>

              <div className="flex items-center gap-2">
                <input
                  value={collectionDraftName}
                  onChange={(event) => setCollectionDraftName(event.target.value)}
                  placeholder={t('review:mediaPage.collectionNamePlaceholder', {
                    defaultValue: 'Collection name'
                  })}
                  className="h-8 min-w-[140px] rounded-md border border-border bg-surface px-2 text-[11px] text-text"
                  data-testid="media-bulk-collection-name"
                />
                <button
                  type="button"
                  onClick={handleAddSelectionToCollection}
                  disabled={bulkSelectedItems.length === 0}
                  className="inline-flex h-8 items-center gap-1 rounded-md border border-border px-2 text-[11px] text-text hover:bg-surface disabled:cursor-not-allowed disabled:opacity-60"
                  data-testid="media-bulk-add-collection"
                >
                  {t('review:mediaPage.collectionAddSelection', {
                    defaultValue: 'Add to collection'
                  })}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    void handleOpenSelectionInMultiReview()
                  }}
                  disabled={bulkSelectedItems.length === 0}
                  className="inline-flex h-8 items-center gap-1 rounded-md border border-border px-2 text-[11px] text-text hover:bg-surface disabled:cursor-not-allowed disabled:opacity-60"
                  data-testid="media-bulk-open-multi"
                >
                  {t('review:mediaPage.bulkOpenMultiReview', {
                    defaultValue: 'Open selection'
                  })}
                </button>
              </div>

              <div className="flex items-center gap-2">
                <select
                  value={bulkExportFormat}
                  onChange={(event) =>
                    setBulkExportFormat(event.target.value as 'json' | 'markdown' | 'text')
                  }
                  className="h-8 rounded-md border border-border bg-surface px-2 text-[11px] text-text"
                  data-testid="media-bulk-export-format"
                >
                  <option value="json">
                    {t('review:mediaPage.bulkExportJson', {
                      defaultValue: 'JSON'
                    })}
                  </option>
                  <option value="markdown">
                    {t('review:mediaPage.bulkExportMarkdown', {
                      defaultValue: 'Markdown'
                    })}
                  </option>
                  <option value="text">
                    {t('review:mediaPage.bulkExportText', {
                      defaultValue: 'Plain text'
                    })}
                  </option>
                </select>
                <button
                  type="button"
                  onClick={handleBulkExport}
                  disabled={bulkSelectedItems.length === 0}
                  className="inline-flex h-8 items-center gap-1 rounded-md border border-border px-2 text-[11px] text-text hover:bg-surface disabled:cursor-not-allowed disabled:opacity-60"
                  data-testid="media-bulk-export"
                >
                  <Download className="h-3.5 w-3.5" />
                  {t('review:mediaPage.bulkExport', { defaultValue: 'Export' })}
                </button>
              </div>
            </div>
          )}

          </div>
          {/* end Controls wrapper */}

          {/* Results + pagination flow */}
          <div
            className="flex min-h-0 flex-1 flex-col bg-surface"
            data-sidebar-target-min-height={sidebarResultsPanelMinHeightPx}
            style={{
              minHeight: `${sidebarResultsPanelMinHeightPx}px`
            }}
          >
            <div
              className="min-h-0 flex-1 overflow-y-auto"
              data-sidebar-target-list-height={sidebarResultsListMinHeightPx}
              style={{
                minHeight: `${sidebarResultsListMinHeightPx}px`
              }}
            >
              <ResultsList
                results={displayResults}
                selectedId={selected?.id || null}
                onSelect={(id) => {
                  if (bulkSelectionMode) {
                    toggleBulkItemSelection(id)
                    return
                  }
                  const item = displayResults.find((r) => r.id === id)
                  if (item) setSelected(item)
                }}
                totalCount={activeTotalCount}
                loadedCount={displayResults.length}
                isLoading={isLoading || isFetching}
                hasActiveFilters={hasActiveFilters}
                searchQuery={query}
                onClearSearch={() => {
                  setQuery('')
                }}
                onClearFilters={resetAllFilters}
                onOpenQuickIngest={() => {
                  if (typeof window !== 'undefined') {
                    window.dispatchEvent(new CustomEvent('tldw:open-quick-ingest'))
                  }
                }}
                favorites={favoritesSet}
                onToggleFavorite={toggleFavorite}
                selectionMode={bulkSelectionMode}
                selectedIds={bulkSelectedIdSet}
                onToggleSelected={toggleBulkItemSelection}
                readingProgress={readingProgressMap}
                viewMode={resultsViewMode === 'compact' ? 'compact' : 'standard'}
                onViewModeChange={(mode) => void setResultsViewMode(mode)}
              />
            </div>
            <div className="shrink-0 border-t border-border bg-surface">
              <Pagination
                currentPage={page}
                totalPages={totalPages}
                onPageChange={setPage}
                totalItems={
                  kinds.media && kinds.notes
                    ? combinedTotal
                    : kinds.notes
                      ? notesTotal
                      : mediaTotal
                }
                itemsPerPage={pageSize}
                currentItemsCount={results.length}
                pageSizeOptions={[20, 50, 100]}
                onItemsPerPageChange={(nextPageSize) => {
                  if (nextPageSize === pageSize) return
                  setPageSize(nextPageSize)
                  setPage(1)
                }}
              />
              {/* Keyboard shortcuts hint */}
              <div className="border-t border-border px-4 py-1.5 flex items-center justify-center">
                <button
                  type="button"
                  onClick={() => setShortcutsOverlayOpen(true)}
                  className="inline-flex items-center gap-1.5 text-xs text-text-muted hover:text-text transition-colors"
                  title={t('review:shortcuts.pressForHelp', { defaultValue: 'Press ? for keyboard shortcuts' })}
                >
                  <kbd className="inline-flex items-center justify-center min-w-[18px] h-5 px-1 text-[10px] font-mono bg-surface2 border border-border rounded text-text-muted">
                    ?
                  </kbd>
                  <span>{t('review:shortcuts.forKeyboardShortcuts', { defaultValue: 'for shortcuts' })}</span>
                </button>
              </div>
            </div>
          </div>

          {hasJumpTo && (
            <div className="shrink-0 border-t border-border bg-surface px-4 py-2.5">
              <button
                type="button"
                onClick={() => setJumpToCollapsed((prev) => !prev)}
                className="flex w-full items-center justify-between rounded-md px-1 py-1 text-sm font-medium text-text hover:bg-surface2/60"
                aria-expanded={!jumpToCollapsed}
                aria-controls="media-jump-bottom-panel"
              >
                <span>{t('review:mediaPage.jumpTo', { defaultValue: 'Jump to' })}</span>
                <ChevronDown
                  className={`w-4 h-4 transition-transform ${jumpToCollapsed ? '' : 'rotate-180'}`}
                />
              </button>
              {!jumpToCollapsed && (
                <div
                  id="media-jump-bottom-panel"
                  className="mt-2 overflow-y-auto pr-1"
                >
                  <JumpToNavigator
                    results={displayResults.map((r) => ({ id: r.id, title: r.title }))}
                    selectedId={selected?.id || null}
                    onSelect={(id) => {
                      const item = displayResults.find((r) => r.id === id)
                      if (item) setSelected(item)
                    }}
                    maxButtons={12}
                    showLabel={false}
                  />
                </div>
              )}
            </div>
          )}

          <div
            className="shrink-0 border-t border-border bg-surface"
            data-testid="media-sidebar-bottom-utilities"
          >
            <button
              type="button"
              onClick={() => setLibraryToolsCollapsed(!libraryToolsCollapsedValue)}
              className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-text hover:bg-surface2/40 hover:text-text"
              aria-expanded={!libraryToolsCollapsedValue}
              aria-controls="media-library-tools-panel"
              data-testid="media-library-tools-toggle"
            >
              <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-text-muted">
                {t('review:mediaPage.libraryTools', { defaultValue: 'Library tools' })}
              </span>
              <ChevronDown
                className={`h-4 w-4 text-text-muted transition-transform ${
                  libraryToolsCollapsedValue ? '' : 'rotate-180'
                }`}
              />
            </button>

            {!libraryToolsCollapsedValue && (
              <div id="media-library-tools-panel">
                <MediaIngestJobsPanel />
                <MediaLibraryStatsPanel
                  results={displayResults}
                  totalCount={activeTotalCount}
                  storageUsage={libraryStorageUsage}
                />
              </div>
            )}
          </div>
          <div
            className="shrink-0 border-t border-border/50 bg-surface2/40"
            style={{ height: `${MEDIA_SIDEBAR_END_BUFFER_PX}px` }}
            aria-hidden="true"
            data-testid="media-sidebar-end-buffer"
          />
        </div>
      </div>

      {/* Collapse Button */}
      <button
        onClick={() => setSidebarCollapsed(!sidebarCollapsedValue)}
        className="relative w-6 self-stretch bg-surface border-r border-border hover:bg-surface2 flex items-center justify-center group transition-colors"
        aria-label={sidebarCollapsedValue ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        <div className="flex items-center justify-center w-full h-full">
          {sidebarCollapsedValue ? (
            <ChevronRight className="w-4 h-4 text-text-subtle group-hover:text-text" />
          ) : (
            <ChevronLeft className="w-4 h-4 text-text-subtle group-hover:text-text" />
          )}
        </div>
      </button>

      {/* Main Content Area */}
      <div className="flex-1 flex min-h-0 flex-col">
        {navigationEnabled ? (
          <div className="border-b border-border bg-surface px-3 py-2">
            <div className="flex flex-wrap items-center gap-3 text-xs text-text-muted">
              <label className="inline-flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={navigationPanelVisibleValue}
                  onChange={(event) =>
                    handleNavigationPanelVisibilityChange(event.target.checked)
                  }
                  className="h-3.5 w-3.5 rounded border-border bg-surface"
                />
                <span>
                  {t('review:mediaNavigation.showPanel', {
                    defaultValue: 'Show chapters/sections panel'
                  })}
                </span>
              </label>

              <label className="inline-flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeGeneratedFallbackValue}
                  onChange={(event) =>
                    handleGeneratedFallbackToggle(event.target.checked)
                  }
                  className="h-3.5 w-3.5 rounded border-border bg-surface"
                />
                <span>
                  {t('review:mediaNavigation.generatedFallback', {
                    defaultValue: 'Allow generated fallback structure'
                  })}
                </span>
              </label>

              <span className="ml-auto rounded bg-surface2 px-2 py-0.5 text-[11px] text-text-subtle">
                {navigationStatusLabel}
              </span>
            </div>
          </div>
        ) : null}

        <div className="flex-1 flex min-h-0 flex-col md:flex-row">
          {showNavigationPanel ? (
            <MediaSectionNavigator
              nodes={navigationNodes}
              selectedNodeId={selectedNavigationNodeId}
              loading={isNavigationLoading}
              error={navigationError}
              onRetry={() => {
                void refetchNavigation()
              }}
              onSelectNode={(node) => {
                setSelectedNavigationNodeId(node.id)
                setNavigationSelectionNonce((prev) => prev + 1)
                pendingSectionSelectionTelemetryRef.current = {
                  nodeId: node.id,
                  startedAt: Date.now(),
                  source: 'user'
                }
                void persistNavigationSelection(node)
              }}
            />
          ) : null}

          <div className="flex-1 flex flex-col min-h-0">
            {staleSelectionNotice ? (
              <div
                className="mx-3 mt-3 rounded-md border border-border bg-surface2 px-3 py-2 text-sm text-text"
                data-testid="media-stale-selection-notice"
              >
                {staleSelectionNotice}
              </div>
            ) : null}
            {selected &&
            detailFetchError &&
            String(detailFetchError.mediaId) === String(selected.id) ? (
              <div
                className="mx-3 mt-3 rounded-md border border-warn/30 bg-warn/10 px-3 py-2 text-sm text-warn"
                data-testid="media-detail-fetch-error"
              >
                <p className="m-0">{detailFetchError.message}</p>
                <button
                  type="button"
                  onClick={handleRetryDetailFetch}
                  className="mt-2 inline-flex items-center rounded border border-warn/40 bg-surface px-2 py-1 text-xs text-warn hover:bg-surface2"
                  data-testid="media-detail-fetch-retry"
                >
                  {t('common:retry', { defaultValue: 'Retry' })}
                </button>
              </div>
            ) : null}
            <ContentViewer
              selectedMedia={selected}
              content={effectiveContent}
              mediaDetail={selectedDetail}
              contentDisplayMode={normalizeRequestedMediaRenderMode(
                navigationDisplayMode,
                mediaRichRenderingEnabled
              )}
              resolvedContentFormat={effectiveContentFormat}
              showContentDisplayModeSelector={mediaDisplayModeSelectorEnabled}
              allowRichRendering={mediaRichRenderingEnabled}
              onContentDisplayModeChange={(mode) => {
                setNavigationDisplayMode(
                  normalizeRequestedMediaRenderMode(mode, mediaRichRenderingEnabled)
                )
              }}
              isDetailLoading={effectiveDetailLoading}
              onPrevious={handlePrevious}
              onNext={handleNext}
              hasPrevious={hasPrevious}
              hasNext={hasNext}
              currentIndex={selectedIndex >= 0 ? selectedIndex : 0}
              totalResults={displayResults.length}
              onChatWithMedia={handleChatWithMedia}
              onChatAboutMedia={handleChatAboutMedia}
              onGenerateFlashcardsFromContent={handleGenerateFlashcardsFromMedia}
              onRefreshMedia={handleRefreshMedia}
              onKeywordsUpdated={(mediaId, keywords) => {
                // Update the selected item with new keywords
                if (selected && selected.id === mediaId) {
                  setSelected({ ...selected, keywords })
                }
                // Refresh the list to show updated keywords
                refetch()
              }}
              onDeleteItem={handleDeleteItem}
              onCreateNoteWithContent={handleCreateNoteWithContent}
              onOpenInMultiReview={handleOpenInMultiReview}
              onSendAnalysisToChat={handleSendAnalysisToChat}
              contentRef={contentRef}
              navigationTarget={selectedNavigationTarget}
              navigationNodeTitle={selectedNavigationNode?.title || null}
              navigationPageCountHint={navigationPageCountHint}
              navigationSelectionNonce={navigationSelectionNonce}
            />
          </div>
        </div>
      </div>

      {/* Keyboard Shortcuts Overlay */}
      <KeyboardShortcutsOverlay
        open={shortcutsOverlayOpen}
        onClose={() => setShortcutsOverlayOpen(false)}
      />
    </div>
  )
}

export default ViewMediaPage
