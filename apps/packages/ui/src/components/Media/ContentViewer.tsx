import {
  ChevronLeft,
  ChevronRight,
  FileSearch,
  ChevronDown,
  ChevronUp,
  Send,
  Copy,
  Sparkles,
  MoreHorizontal,
  MessageSquare,
  Clock,
  FileText,
  StickyNote,
  Edit3,
  ExternalLink,
  Expand,
  Minimize2,
  Loader2,
  Trash2,
  UploadCloud
} from 'lucide-react'
import React, { useState, useEffect, Suspense, useMemo, useRef, useCallback } from 'react'
import { Select, Dropdown, Tooltip, message, Spin } from 'antd'
import { useTranslation } from 'react-i18next'
import type { MenuProps } from 'antd'
import { AnalysisModal } from './AnalysisModal'
import { AnalysisEditModal } from './AnalysisEditModal'
import { VersionHistoryPanel } from './VersionHistoryPanel'
import { DeveloperToolsSection } from './DeveloperToolsSection'
import { DiffViewModal } from './DiffViewModal'
import { MarkdownPreview } from '@/components/Common/MarkdownPreview'
import { useConfirmDanger } from '@/components/Common/confirm-danger'
import { bgRequest } from '@/services/background-proxy'
import type { MediaResultItem } from './types'
import { getTextStats } from '@/utils/text-stats'
import { formatRelativeTime } from '@/utils/dateFormatters'
import {
  type MediaNavigationFormat,
  MEDIA_DISPLAY_MODE_FORMAT_TO_LABEL
} from '@/utils/media-navigation-scope'
import { resolveMediaRenderMode } from '@/utils/media-render-mode'
import { sanitizeMediaRichHtmlWithStats } from '@/utils/media-rich-html-sanitizer'
import { trackMediaNavigationTelemetry } from '@/utils/media-navigation-telemetry'
import {
  describeMediaNavigationTarget,
  type MediaNavigationTargetLike
} from '@/utils/media-navigation-target'
import { applyMediaNavigationTarget } from '@/utils/media-navigation-target-actions'
import { useSetting } from '@/hooks/useSetting'
import { useMediaReadingProgress } from '@/hooks/useMediaReadingProgress'
import {
  MEDIA_COLLAPSED_SECTIONS_SETTING,
  MEDIA_TEXT_SIZE_PRESET_SETTING,
  type MediaTextSizePreset
} from '@/services/settings/ui-settings'
import { estimateReadingTimeMinutes } from './mediaMetadataUtils'

// Lazy load ContentEditModal for code splitting
const ContentEditModal = React.lazy(() =>
  import('./ContentEditModal').then((m) => ({ default: m.ContentEditModal }))
)

const PLAIN_TEXT_MEDIA_TYPES = new Set(['audio', 'video', 'transcript', 'subtitle'])
const MARKDOWN_HINTS = [
  /^#{1,6}\s+/m,
  /^\s*([-*+]|\d+\.)\s+/m,
  /^>\s+/m,
  /```/,
  /`[^`]+`/,
  /\[[^\]]+\]\([^)]+\)/,
  /<\/?[a-z][\s\S]*>/i
]

const looksLikeMarkdown = (text: string) =>
  MARKDOWN_HINTS.some((pattern) => pattern.test(text))

const shouldForceHardBreaks = (text: string, mediaType?: string) => {
  const normalizedType = mediaType?.toLowerCase().trim()
  if (!normalizedType || !PLAIN_TEXT_MEDIA_TYPES.has(normalizedType)) return false
  return !looksLikeMarkdown(text)
}

const TEXT_SIZE_CONTROL_OPTIONS: Array<{
  value: MediaTextSizePreset
  label: string
  className: string
  markdownSize: 'xs' | 'sm' | 'base'
  richClass: string
}> = [
  {
    value: 's',
    label: 'S',
    className: 'text-xs leading-relaxed',
    markdownSize: 'xs',
    richClass: 'prose-xs'
  },
  {
    value: 'm',
    label: 'M',
    className: 'text-sm leading-relaxed',
    markdownSize: 'sm',
    richClass: 'prose-sm'
  },
  {
    value: 'l',
    label: 'L',
    className: 'text-base leading-relaxed',
    markdownSize: 'base',
    richClass: 'prose'
  }
]

const LEADING_TRANSCRIPT_TIMESTAMP_PATTERN =
  /^(\s*)(?:\[(\d{1,2}:\d{2}(?::\d{2})?)\]|(\d{1,2}:\d{2}(?::\d{2})?))(\s*[-–—:]?\s*)(.*)$/

const parseTimestampToSeconds = (value: string): number | null => {
  const trimmed = value.trim()
  if (!trimmed) return null
  const parts = trimmed.split(':').map((part) => Number(part))
  if (parts.some((part) => !Number.isFinite(part) || part < 0)) return null
  if (parts.length === 2) {
    const [minutes, seconds] = parts
    return Math.floor(minutes * 60 + seconds)
  }
  if (parts.length === 3) {
    const [hours, minutes, seconds] = parts
    return Math.floor(hours * 3600 + minutes * 60 + seconds)
  }
  return null
}

const resolveMediaMimeType = (mediaType: string, mediaDetail: any): string => {
  const candidates = [
    mediaDetail?.file_mime_type,
    mediaDetail?.mime_type,
    mediaDetail?.metadata?.mime_type,
    mediaDetail?.metadata?.content_type
  ]
  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim().length > 0) {
      return candidate.trim()
    }
  }
  if (mediaType === 'video') return 'video/mp4'
  if (mediaType === 'audio') return 'audio/mpeg'
  return 'application/octet-stream'
}

export const shouldShowMediaDeveloperTools = (
  env: Record<string, unknown> | null | undefined
): boolean => {
  if (!env || typeof env !== 'object') return false
  const mode = String((env as Record<string, unknown>).MODE || '').toLowerCase()
  return Boolean((env as Record<string, unknown>).DEV) || mode === 'development'
}

const firstNonEmptyString = (...vals: any[]): string => {
  for (const v of vals) {
    if (typeof v === 'string' && v.trim().length > 0) return v
  }
  return ''
}

const firstValidDateString = (...vals: any[]): string | null => {
  for (const v of vals) {
    if (typeof v !== 'string') continue
    const trimmed = v.trim()
    if (!trimmed) continue
    const asDate = new Date(trimmed)
    if (!Number.isNaN(asDate.getTime())) {
      return trimmed
    }
  }
  return null
}

const SAFE_METADATA_PRIORITY_KEYS = [
  'doi',
  'pmid',
  'pmcid',
  'arxiv_id',
  'journal',
  'license'
] as const

const SAFE_METADATA_LABELS: Record<string, string> = {
  doi: 'DOI',
  pmid: 'PMID',
  pmcid: 'PMCID',
  arxiv_id: 'arXiv',
  journal: 'Journal',
  license: 'License'
}

const toDisplayMetadataLabel = (key: string): string => {
  if (SAFE_METADATA_LABELS[key]) return SAFE_METADATA_LABELS[key]
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (match) => match.toUpperCase())
}

const normalizeVectorProcessingStatus = (value: unknown): string | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    if (value >= 1) return 'completed'
    if (value < 0) return 'failed'
    return 'pending'
  }
  if (typeof value === 'string' && value.trim().length > 0) {
    const lowered = value.trim().toLowerCase()
    if (['1', 'true', 'complete', 'completed', 'done', 'success'].includes(lowered)) {
      return 'completed'
    }
    if (['-1', 'false', 'failed', 'error'].includes(lowered)) {
      return 'failed'
    }
    if (['0', 'pending', 'queued', 'in_progress', 'in-progress'].includes(lowered)) {
      return 'pending'
    }
    return lowered
  }
  return null
}

const normalizeChunkingStatus = (value: unknown): string | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    if (value >= 1) return 'completed'
    if (value < 0) return 'failed'
    return 'pending'
  }
  if (typeof value === 'string' && value.trim().length > 0) {
    const lowered = value.trim().toLowerCase()
    if (['1', 'true', 'complete', 'completed', 'done', 'success'].includes(lowered)) {
      return 'completed'
    }
    if (['-1', 'false', 'failed', 'error'].includes(lowered)) {
      return 'failed'
    }
    if (['0', 'pending', 'queued', 'in_progress', 'in-progress'].includes(lowered)) {
      return 'pending'
    }
    return lowered
  }
  return null
}

const processingStatusClass = (status: string): string => {
  if (status.includes('fail') || status.includes('error')) {
    return 'bg-danger/10 text-danger'
  }
  if (status.includes('complete') || status.includes('success') || status === 'done') {
    return 'bg-success/10 text-success'
  }
  return 'bg-warn/10 text-warn'
}

const formatProcessingStatus = (status: string): string =>
  status
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (match) => match.toUpperCase())

const toDisplayMetadataValue = (value: unknown): string => {
  if (value == null) return ''
  if (typeof value === 'string') return value.trim()
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  if (Array.isArray(value)) {
    return value
      .map((entry) => toDisplayMetadataValue(entry))
      .filter((entry) => entry.length > 0)
      .join(', ')
  }
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch {
      return ''
    }
  }
  return ''
}

const normalizeComparableText = (value: string): string =>
  value.replace(/\s+/g, ' ').trim().toLowerCase()

const findHeadingMatchInContent = (
  root: HTMLElement | null,
  title: string,
  options?: { preferLast?: boolean }
): HTMLElement | null => {
  if (!root) return null
  const normalizedTitle = normalizeComparableText(title)
  if (!normalizedTitle) return null
  const preferLast = Boolean(options?.preferLast)

  const headings = Array.from(root.querySelectorAll('h1,h2,h3,h4,h5,h6'))
  const headingCandidates = preferLast ? [...headings].reverse() : headings
  for (const candidate of headingCandidates) {
    if (!(candidate instanceof HTMLElement)) continue
    const text = normalizeComparableText(candidate.textContent || '')
    if (!text) continue
    if (text === normalizedTitle || text.includes(normalizedTitle)) {
      return candidate
    }
  }

  const allBroaderCandidates = Array.from(
    root.querySelectorAll('p,li,blockquote,div,span')
  )
  const broaderCandidates = preferLast
    ? allBroaderCandidates.slice(-1200).reverse()
    : allBroaderCandidates.slice(0, 1200)
  for (const candidate of broaderCandidates) {
    if (!(candidate instanceof HTMLElement)) continue
    const text = normalizeComparableText(candidate.textContent || '')
    if (!text) continue
    if (text === normalizedTitle || text.includes(normalizedTitle)) {
      return candidate
    }
  }

  return null
}

const focusNavigationMatch = (element: HTMLElement): void => {
  element.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
    inline: 'nearest'
  })
  const priorOutline = element.style.outline
  const priorOutlineOffset = element.style.outlineOffset
  const priorTransition = element.style.transition
  element.style.outline = '2px solid rgba(59, 130, 246, 0.45)'
  element.style.outlineOffset = '2px'
  element.style.transition = priorTransition
    ? `${priorTransition}, outline 0.2s ease`
    : 'outline 0.2s ease'
  window.setTimeout(() => {
    element.style.outline = priorOutline
    element.style.outlineOffset = priorOutlineOffset
    element.style.transition = priorTransition
  }, 1300)
}

const scrollToCharOffset = (
  container: HTMLElement,
  targetStart: number,
  contentLength: number
): boolean => {
  if (!Number.isFinite(targetStart) || targetStart < 0) return false
  if (!Number.isFinite(contentLength) || contentLength <= 0) return false

  const ratio = Math.min(
    1,
    Math.max(0, targetStart / Math.max(1, contentLength - 1))
  )
  const containerMaxScroll = container.scrollHeight - container.clientHeight
  if (Number.isFinite(containerMaxScroll) && containerMaxScroll > 0) {
    const top = Math.round(containerMaxScroll * ratio)
    if (typeof container.scrollTo === 'function') {
      container.scrollTo({ top, behavior: 'smooth' })
    } else {
      container.scrollTop = top
    }
    return true
  }

  // Some media layouts scroll the document viewport instead of the local container.
  if (typeof document === 'undefined') return false
  const docScroller =
    document.scrollingElement instanceof HTMLElement
      ? document.scrollingElement
      : document.documentElement instanceof HTMLElement
        ? document.documentElement
        : null
  if (!docScroller) return false

  const docMaxScroll = docScroller.scrollHeight - docScroller.clientHeight
  if (!Number.isFinite(docMaxScroll) || docMaxScroll <= 0) return false
  const top = Math.round(docMaxScroll * ratio)

  if (typeof window !== 'undefined' && typeof window.scrollTo === 'function') {
    window.scrollTo({ top, behavior: 'smooth' })
  } else if (typeof docScroller.scrollTo === 'function') {
    docScroller.scrollTo({ top, behavior: 'smooth' })
  } else {
    docScroller.scrollTop = top
  }
  return true
}

const scrollToPageNumber = (
  container: HTMLElement,
  pageNumber: number,
  pageCountHint: number
): boolean => {
  if (!Number.isFinite(pageNumber) || pageNumber < 1) return false
  if (!Number.isFinite(pageCountHint) || pageCountHint < 1) return false

  const ratio = Math.min(
    1,
    Math.max(0, (pageNumber - 1) / Math.max(1, pageCountHint - 1))
  )
  const containerMaxScroll = container.scrollHeight - container.clientHeight
  if (Number.isFinite(containerMaxScroll) && containerMaxScroll > 0) {
    const top = Math.round(containerMaxScroll * ratio)
    if (typeof container.scrollTo === 'function') {
      container.scrollTo({ top, behavior: 'smooth' })
    } else {
      container.scrollTop = top
    }
    return true
  }

  // Some media layouts scroll the document viewport instead of the local container.
  if (typeof document === 'undefined') return false
  const docScroller =
    document.scrollingElement instanceof HTMLElement
      ? document.scrollingElement
      : document.documentElement instanceof HTMLElement
        ? document.documentElement
        : null
  if (!docScroller) return false

  const docMaxScroll = docScroller.scrollHeight - docScroller.clientHeight
  if (!Number.isFinite(docMaxScroll) || docMaxScroll <= 0) return false
  const top = Math.round(docMaxScroll * ratio)

  if (typeof window !== 'undefined' && typeof window.scrollTo === 'function') {
    window.scrollTo({ top, behavior: 'smooth' })
  } else if (typeof docScroller.scrollTo === 'function') {
    docScroller.scrollTo({ top, behavior: 'smooth' })
  } else {
    docScroller.scrollTop = top
  }
  return true
}

interface ContentViewerProps {
  selectedMedia: MediaResultItem | null
  content: string
  mediaDetail?: any
  contentDisplayMode?: MediaNavigationFormat
  resolvedContentFormat?: MediaNavigationFormat | null
  showContentDisplayModeSelector?: boolean
  allowRichRendering?: boolean
  onContentDisplayModeChange?: (mode: MediaNavigationFormat) => void
  isDetailLoading?: boolean
  onPrevious?: () => void
  onNext?: () => void
  hasPrevious?: boolean
  hasNext?: boolean
  currentIndex?: number
  totalResults?: number
  onChatWithMedia?: () => void
  onChatAboutMedia?: () => void
  onRefreshMedia?: () => void
  onKeywordsUpdated?: (mediaId: string | number, keywords: string[]) => void
  onCreateNoteWithContent?: (content: string, title: string) => void
  onOpenInMultiReview?: () => void
  onSendAnalysisToChat?: (text: string) => void
  contentRef?: (node: HTMLDivElement | null) => void
  onDeleteItem?: (item: MediaResultItem, detail: any | null) => Promise<void>
  navigationTarget?: MediaNavigationTargetLike | null
  navigationNodeTitle?: string | null
  navigationPageCountHint?: number | null
  navigationSelectionNonce?: number
}


export function ContentViewer({
  selectedMedia,
  content,
  mediaDetail,
  contentDisplayMode = 'auto',
  resolvedContentFormat = null,
  showContentDisplayModeSelector = false,
  allowRichRendering = false,
  onContentDisplayModeChange,
  isDetailLoading = false,
  onPrevious,
  onNext,
  hasPrevious = false,
  hasNext = false,
  currentIndex = 0,
  totalResults = 0,
  onChatWithMedia,
  onChatAboutMedia,
  onRefreshMedia,
  onKeywordsUpdated,
  onCreateNoteWithContent,
  onOpenInMultiReview,
  onSendAnalysisToChat,
  contentRef,
  onDeleteItem,
  navigationTarget = null,
  navigationNodeTitle = null,
  navigationPageCountHint = null,
  navigationSelectionNonce = 0
}: ContentViewerProps) {
  const { t } = useTranslation(['review', 'common'])
  const confirmDanger = useConfirmDanger()
  const [collapsedSections, setCollapsedSections] = useSetting(
    MEDIA_COLLAPSED_SECTIONS_SETTING
  )
  const [textSizePreset, setTextSizePreset] = useSetting(
    MEDIA_TEXT_SIZE_PRESET_SETTING
  )
  const [analysisModalOpen, setAnalysisModalOpen] = useState(false)
  const [editingKeywords, setEditingKeywords] = useState<string[]>([])
  const [savingKeywords, setSavingKeywords] = useState(false)
  const saveKeywordsTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  // New state for enhanced features
  const [contentExpanded, setContentExpanded] = useState(true)
  const [analysisEditModalOpen, setAnalysisEditModalOpen] = useState(false)
  const [editingAnalysisText, setEditingAnalysisText] = useState('')
  const [optimisticAnalysis, setOptimisticAnalysis] = useState('')
  const [activeAnalysisIndex, setActiveAnalysisIndex] = useState(0)
  const [analysisExpanded, setAnalysisExpanded] = useState(false)
  const [diffModalOpen, setDiffModalOpen] = useState(false)
  const [diffLeftText, setDiffLeftText] = useState('')
  const [diffRightText, setDiffRightText] = useState('')
  const [diffLeftLabel, setDiffLeftLabel] = useState('')
  const [diffRightLabel, setDiffRightLabel] = useState('')
  const [diffMetadataSummary, setDiffMetadataSummary] = useState<{
    left: string[]
    right: string[]
    changed: string[]
  } | null>(null)
  const [contentEditModalOpen, setContentEditModalOpen] = useState(false)
  const [editingContentText, setEditingContentText] = useState('')
  const [metadataDetailsExpanded, setMetadataDetailsExpanded] = useState(false)
  const [showBackToTop, setShowBackToTop] = useState(false)
  const [embeddedMediaUrl, setEmbeddedMediaUrl] = useState<string | null>(null)
  const [embeddedMediaLoading, setEmbeddedMediaLoading] = useState(false)
  const [embeddedMediaError, setEmbeddedMediaError] = useState<string | null>(null)
  const [deletingItem, setDeletingItem] = useState(false)
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null)
  const lastSanitizationTelemetryKeyRef = useRef<string>('')
  const lastAppliedNavigationTargetKeyRef = useRef<string>('')
  const lastAppliedNavigationTitleKeyRef = useRef<string>('')
  const lastAppliedNavigationPageKeyRef = useRef<string>('')
  const titleRetryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pageRetryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const contentBodyRef = useRef<HTMLDivElement | null>(null)
  const contentScrollContainerRef = useRef<HTMLDivElement | null>(null)
  const mediaPlayerRef = useRef<HTMLMediaElement | null>(null)
  const embeddedMediaObjectUrlRef = useRef<string | null>(null)

  const resolvedTextSizePreset: MediaTextSizePreset = useMemo(() => {
    const normalized = String(textSizePreset || '').toLowerCase()
    if (normalized === 's' || normalized === 'l') return normalized
    return 'm'
  }, [textSizePreset])
  const textSizeControl =
    TEXT_SIZE_CONTROL_OPTIONS.find(
      (option) => option.value === resolvedTextSizePreset
    ) || TEXT_SIZE_CONTROL_OPTIONS[1]
  const contentBodyTypographyClass = textSizeControl.className
  const markdownPreviewSize = textSizeControl.markdownSize
  const richTextTypographyClass = textSizeControl.richClass
  const selectedMediaId = selectedMedia?.id != null ? String(selectedMedia.id) : null
  const isAwaitingSelectionUpdate =
    !!pendingDeleteId && !!selectedMediaId && pendingDeleteId === selectedMediaId
  const mediaType = String(
    selectedMedia?.meta?.type || mediaDetail?.type || mediaDetail?.media_type || ''
  )
    .toLowerCase()
    .trim()
  const isPlayableMediaType = mediaType === 'audio' || mediaType === 'video'
  const hasOriginalFile = Boolean(
    mediaDetail?.has_original_file ??
      mediaDetail?.hasOriginalFile ??
      selectedMedia?.raw?.has_original_file ??
      selectedMedia?.raw?.hasOriginalFile
  )
  const shouldShowEmbeddedPlayer =
    selectedMedia?.kind === 'media' && isPlayableMediaType && hasOriginalFile
  const embeddedMediaMimeType = useMemo(
    () => resolveMediaMimeType(mediaType, mediaDetail),
    [mediaDetail, mediaType]
  )
  const showDeveloperTools = useMemo(() => {
    try {
      const runtimeEnv = (import.meta as any)?.env || {}
      return shouldShowMediaDeveloperTools(runtimeEnv)
    } catch {
      return false
    }
  }, [])

  useMediaReadingProgress({
    mediaId: selectedMedia?.id ?? null,
    mediaKind: selectedMedia?.kind ?? null,
    mediaDetail,
    contentLength: content.length,
    scrollContainerRef: contentScrollContainerRef,
    hasNavigationTarget: Boolean(navigationTarget)
  })

  useEffect(() => {
    const container = contentScrollContainerRef.current
    if (!container) {
      setShowBackToTop(false)
      return
    }

    const updateVisibility = () => {
      setShowBackToTop(container.scrollTop >= 500)
    }

    updateVisibility()
    container.addEventListener('scroll', updateVisibility, { passive: true })
    return () => {
      container.removeEventListener('scroll', updateVisibility)
    }
  }, [content.length, selectedMedia?.id])

  const handleBackToTop = useCallback(() => {
    const container = contentScrollContainerRef.current
    if (!container) return
    if (typeof container.scrollTo === 'function') {
      container.scrollTo({ top: 0, behavior: 'smooth' })
    } else {
      container.scrollTop = 0
    }
    setShowBackToTop(false)
  }, [])

  useEffect(() => {
    const revokeObjectUrl = () => {
      if (
        embeddedMediaObjectUrlRef.current &&
        typeof URL !== 'undefined' &&
        typeof URL.revokeObjectURL === 'function'
      ) {
        URL.revokeObjectURL(embeddedMediaObjectUrlRef.current)
        embeddedMediaObjectUrlRef.current = null
      }
    }

    mediaPlayerRef.current = null
    setEmbeddedMediaError(null)
    setEmbeddedMediaLoading(false)
    setEmbeddedMediaUrl(null)
    revokeObjectUrl()

    if (!shouldShowEmbeddedPlayer || !selectedMediaId) {
      return () => {
        revokeObjectUrl()
      }
    }

    let cancelled = false
    setEmbeddedMediaLoading(true)

    ;(async () => {
      try {
        const fileBuffer = await bgRequest<ArrayBuffer>({
          path: `/api/v1/media/${selectedMediaId}/file` as any,
          method: 'GET' as any,
          responseType: 'arrayBuffer'
        })
        if (cancelled) return

        const asArrayBuffer =
          fileBuffer instanceof ArrayBuffer
            ? fileBuffer
            : fileBuffer && (fileBuffer as any).buffer instanceof ArrayBuffer
              ? (fileBuffer as any).buffer
              : null
        if (!asArrayBuffer) {
          throw new Error('No media file bytes returned')
        }
        if (typeof URL === 'undefined' || typeof URL.createObjectURL !== 'function') {
          throw new Error('Object URLs are unavailable in this environment')
        }

        const blob = new Blob([asArrayBuffer], { type: embeddedMediaMimeType })
        const objectUrl = URL.createObjectURL(blob)
        embeddedMediaObjectUrlRef.current = objectUrl
        setEmbeddedMediaUrl(objectUrl)
      } catch (error) {
        if (cancelled) return
        console.debug('Failed to load embedded media file', error)
        setEmbeddedMediaError('Unable to load media preview.')
      } finally {
        if (!cancelled) {
          setEmbeddedMediaLoading(false)
        }
      }
    })()

    return () => {
      cancelled = true
      revokeObjectUrl()
    }
  }, [embeddedMediaMimeType, selectedMediaId, shouldShowEmbeddedPlayer])

  const handleTranscriptTimestampSeek = useCallback((timestamp: string) => {
    const seconds = parseTimestampToSeconds(timestamp)
    if (seconds == null) return
    const player = mediaPlayerRef.current
    if (!player) return
    player.currentTime = seconds
  }, [])

  // Content length threshold for collapse (2500 chars)
  const CONTENT_COLLAPSE_THRESHOLD = 2500
  const shouldShowExpandToggle = content && content.length > CONTENT_COLLAPSE_THRESHOLD
  const contentForPreview = useMemo(() => {
    if (!content) return ''
    if (selectedMedia?.kind === 'note') return content
    const normalized = content.replace(/\r\n/g, '\n')
    if (!shouldForceHardBreaks(normalized, selectedMedia?.meta?.type)) {
      return normalized
    }
    return normalized.replace(/\n/g, '  \n')
  }, [content, selectedMedia?.kind, selectedMedia?.meta?.type])
  const effectiveRenderMode = useMemo(
    () =>
      resolveMediaRenderMode({
        requestedMode: contentDisplayMode,
        resolvedContentFormat,
        allowRichRendering
      }),
    [allowRichRendering, contentDisplayMode, resolvedContentFormat]
  )
  const transcriptLines = useMemo(
    () => (content ? content.replace(/\r\n/g, '\n').split('\n') : []),
    [content]
  )
  const hasClickableTranscriptTimestamps = useMemo(
    () =>
      shouldShowEmbeddedPlayer &&
      transcriptLines.some((line) => LEADING_TRANSCRIPT_TIMESTAMP_PATTERN.test(line)),
    [shouldShowEmbeddedPlayer, transcriptLines]
  )
  const richSanitization = useMemo(() => {
    if (effectiveRenderMode !== 'html' || !content) {
      return {
        html: '',
        removed_node_count: 0,
        removed_attribute_count: 0,
        blocked_url_schemes: [] as string[]
      }
    }
    return sanitizeMediaRichHtmlWithStats(content)
  }, [content, effectiveRenderMode])
  const sanitizedRichContent = richSanitization.html
  const navigationTargetDescription = useMemo(
    () => describeMediaNavigationTarget(navigationTarget),
    [navigationTarget]
  )
  const displayModeOptions = useMemo(() => {
    const baseModes: MediaNavigationFormat[] = ['auto', 'plain', 'markdown']
    if (allowRichRendering) baseModes.push('html')
    return baseModes.map((mode) => ({
      value: mode,
      label: MEDIA_DISPLAY_MODE_FORMAT_TO_LABEL[mode]
    }))
  }, [allowRichRendering])

  useEffect(() => {
    if (!selectedMediaId || !navigationTarget) {
      lastAppliedNavigationTargetKeyRef.current = ''
      return
    }
    const targetKey = [
      selectedMediaId,
      navigationTarget.target_type,
      navigationTarget.target_start ?? 'null',
      navigationTarget.target_end ?? 'null',
      navigationTarget.target_href ?? 'null',
      content.length,
      navigationSelectionNonce
    ].join(':')
    if (lastAppliedNavigationTargetKeyRef.current === targetKey) return
    lastAppliedNavigationTargetKeyRef.current = targetKey

    applyMediaNavigationTarget(navigationTarget, {
      root: contentBodyRef.current,
      mediaId: selectedMediaId
    })
  }, [content.length, navigationSelectionNonce, navigationTarget, selectedMediaId])

  useEffect(() => {
    if (titleRetryTimerRef.current) {
      clearTimeout(titleRetryTimerRef.current)
      titleRetryTimerRef.current = null
    }
    if (!selectedMediaId || !navigationTarget) {
      lastAppliedNavigationTitleKeyRef.current = ''
      return
    }
    if (
      navigationTarget.target_type !== 'char_range' &&
      navigationTarget.target_type !== 'page'
    ) {
      return
    }
    const title = String(navigationNodeTitle || '').trim()
    if (!title) return

    const key = [
      selectedMediaId,
      navigationTarget.target_type,
      title.toLowerCase(),
      content.length,
      navigationTarget.target_start ?? 'null',
      navigationTarget.target_end ?? 'null',
      navigationSelectionNonce
    ].join(':')
    if (lastAppliedNavigationTitleKeyRef.current === key) return

    let attempts = 0
    const attemptNavigationTitleJump = (): boolean => {
      const match = findHeadingMatchInContent(contentBodyRef.current, title, {
        preferLast: navigationTarget.target_type === 'page'
      })
      if (match) {
        lastAppliedNavigationTitleKeyRef.current = key
        focusNavigationMatch(match)
        return true
      }

      if (navigationTarget.target_type === 'page') {
        return false
      }

      const start = navigationTarget.target_start
      if (
        typeof start === 'number' &&
        Number.isFinite(start) &&
        contentScrollContainerRef.current
      ) {
        const didScroll = scrollToCharOffset(
          contentScrollContainerRef.current,
          start,
          content.length
        )
        if (didScroll) {
          lastAppliedNavigationTitleKeyRef.current = key
          return true
        }
      }
      return false
    }

    const runAttempt = () => {
      if (attemptNavigationTitleJump()) return
      if (attempts >= 10) return
      attempts += 1
      titleRetryTimerRef.current = setTimeout(runAttempt, 120)
    }
    runAttempt()

    return () => {
      if (titleRetryTimerRef.current) {
        clearTimeout(titleRetryTimerRef.current)
        titleRetryTimerRef.current = null
      }
    }
  }, [
    content.length,
    navigationNodeTitle,
    navigationSelectionNonce,
    navigationTarget,
    selectedMediaId
  ])

  useEffect(() => {
    if (pageRetryTimerRef.current) {
      clearTimeout(pageRetryTimerRef.current)
      pageRetryTimerRef.current = null
    }
    if (!selectedMediaId || !navigationTarget) {
      lastAppliedNavigationPageKeyRef.current = ''
      return
    }
    if (navigationTarget.target_type !== 'page') return

    const pageStart = navigationTarget.target_start
    if (typeof pageStart !== 'number' || !Number.isFinite(pageStart) || pageStart < 1) {
      return
    }
    if (!contentScrollContainerRef.current) return

    const pageCountHint =
      typeof navigationPageCountHint === 'number' &&
      Number.isFinite(navigationPageCountHint) &&
      navigationPageCountHint > 0
        ? Math.trunc(navigationPageCountHint)
        : Math.max(1, Math.trunc(pageStart))

    const key = [
      selectedMediaId,
      Math.trunc(pageStart),
      pageCountHint,
      content.length,
      navigationSelectionNonce
    ].join(':')
    if (lastAppliedNavigationPageKeyRef.current === key) return

    const container = contentScrollContainerRef.current
    if (!container) return

    let attempts = 0
    const attemptNavigationPageJump = (): boolean => {
      const didScroll = scrollToPageNumber(
        container,
        pageStart,
        pageCountHint
      )
      if (didScroll) {
        lastAppliedNavigationPageKeyRef.current = key
        return true
      }
      return false
    }

    const runAttempt = () => {
      if (attemptNavigationPageJump()) return
      if (attempts >= 10) return
      attempts += 1
      pageRetryTimerRef.current = setTimeout(runAttempt, 120)
    }
    runAttempt()

    return () => {
      if (pageRetryTimerRef.current) {
        clearTimeout(pageRetryTimerRef.current)
        pageRetryTimerRef.current = null
      }
    }
  }, [
    content.length,
    navigationPageCountHint,
    navigationSelectionNonce,
    navigationTarget,
    selectedMediaId
  ])

  useEffect(() => {
    return () => {
      if (titleRetryTimerRef.current) {
        clearTimeout(titleRetryTimerRef.current)
      }
      if (pageRetryTimerRef.current) {
        clearTimeout(pageRetryTimerRef.current)
      }
    }
  }, [])

  useEffect(() => {
    if (effectiveRenderMode !== 'html') return
    const removedNodeCount = richSanitization.removed_node_count
    const removedAttributeCount = richSanitization.removed_attribute_count
    const blockedSchemes = richSanitization.blocked_url_schemes
      .map((scheme) => String(scheme || '').trim().toLowerCase())
      .filter(Boolean)

    if (
      removedNodeCount <= 0 &&
      removedAttributeCount <= 0 &&
      blockedSchemes.length === 0
    ) {
      return
    }

    const dedupeKey = [
      selectedMediaId || 'none',
      content.length,
      removedNodeCount,
      removedAttributeCount,
      blockedSchemes.join(',')
    ].join(':')
    if (lastSanitizationTelemetryKeyRef.current === dedupeKey) return
    lastSanitizationTelemetryKeyRef.current = dedupeKey

    void trackMediaNavigationTelemetry({
      type: 'media_rich_sanitization_applied',
      removed_node_count: removedNodeCount,
      removed_attribute_count: removedAttributeCount,
      blocked_url_count: blockedSchemes.length
    })

    const uniqueSchemes = new Set(blockedSchemes)
    for (const scheme of uniqueSchemes) {
      void trackMediaNavigationTelemetry({
        type: 'media_rich_sanitization_blocked_url',
        scheme
      })
    }
  }, [content.length, effectiveRenderMode, richSanitization, selectedMediaId])

  useEffect(() => {
    if (!pendingDeleteId) return
    if (!selectedMediaId || pendingDeleteId !== selectedMediaId) {
      setPendingDeleteId(null)
    }
  }, [pendingDeleteId, selectedMediaId])

  const resolveNoteVersion = useCallback((detail: any, raw: any): number | null => {
    const candidates = [
      detail?.version,
      detail?.metadata?.version,
      raw?.version,
      raw?.metadata?.version
    ]
    for (const candidate of candidates) {
      if (typeof candidate === 'number' && Number.isFinite(candidate)) return candidate
      if (typeof candidate === 'string' && candidate.trim().length > 0) {
        const parsed = Number(candidate)
        if (Number.isFinite(parsed)) return parsed
      }
    }
    return null
  }, [])

  const getVersionNumber = useCallback((v: any): number | null => {
    const raw = v?.version_number ?? v?.version
    if (typeof raw === 'number' && Number.isFinite(raw)) return raw
    if (typeof raw === 'string' && raw.trim().length > 0) {
      const parsed = Number(raw)
      if (Number.isFinite(parsed)) return parsed
    }
    return null
  }, [])

  const pickLatestVersion = useCallback((versions: any[]): any | null => {
    if (!Array.isArray(versions) || versions.length === 0) return null
    let best: any | null = null
    let bestNum = -Infinity
    for (const v of versions) {
      const num = getVersionNumber(v)
      if (num != null && num > bestNum) {
        best = v
        bestNum = num
      }
    }
    return best || versions[0]
  }, [getVersionNumber])

  const latestVersion = useMemo(() => {
    if (!mediaDetail || typeof mediaDetail !== 'object') return null
    const direct = mediaDetail.latest_version || mediaDetail.latestVersion
    if (direct && typeof direct === 'object') return direct
    const versions = Array.isArray(mediaDetail.versions) ? mediaDetail.versions : []
    return pickLatestVersion(versions)
  }, [mediaDetail, pickLatestVersion])

  const derivedPrompt = useMemo(() => {
    if (!mediaDetail) return ''
    const fromRoot = firstNonEmptyString(mediaDetail.prompt)
    if (fromRoot) return fromRoot
    const fromProcessing = firstNonEmptyString(mediaDetail?.processing?.prompt)
    if (fromProcessing) return fromProcessing
    return firstNonEmptyString(latestVersion?.prompt)
  }, [mediaDetail, latestVersion])

  const persistedAnalysisContent = useMemo(() => {
    if (!mediaDetail) return ''
    const fromProcessing = firstNonEmptyString(mediaDetail?.processing?.analysis)
    if (fromProcessing) return fromProcessing
    const fromAnalysis = firstNonEmptyString(mediaDetail?.analysis)
    if (fromAnalysis) return fromAnalysis
    const fromAnalysisContent = firstNonEmptyString(
      mediaDetail?.analysis_content,
      mediaDetail?.analysisContent
    )
    if (fromAnalysisContent) return fromAnalysisContent
    if (Array.isArray(mediaDetail?.analyses)) {
      for (const entry of mediaDetail.analyses) {
        const text = typeof entry === 'string'
          ? entry
          : (entry?.content || entry?.text || entry?.summary || entry?.analysis_content || '')
        const resolved = firstNonEmptyString(text)
        if (resolved) return resolved
      }
    }
    const fromVersion = firstNonEmptyString(
      latestVersion?.analysis_content,
      latestVersion?.analysis
    )
    if (fromVersion) return fromVersion
    return firstNonEmptyString(mediaDetail?.summary)
  }, [mediaDetail, latestVersion])

  const derivedAnalysisContent = useMemo(() => {
    if (optimisticAnalysis) return optimisticAnalysis
    return persistedAnalysisContent
  }, [optimisticAnalysis, persistedAnalysisContent])

  useEffect(() => {
    setOptimisticAnalysis('')
  }, [selectedMedia?.id])

  useEffect(() => {
    if (persistedAnalysisContent) {
      setOptimisticAnalysis('')
    }
  }, [persistedAnalysisContent])

  useEffect(() => {
    setActiveAnalysisIndex(0)
    setAnalysisExpanded(false)
  }, [selectedMedia?.id])

  useEffect(() => {
    setMetadataDetailsExpanded(false)
  }, [selectedMedia?.id])

  useEffect(() => {
    setAnalysisExpanded(false)
  }, [activeAnalysisIndex])

  // Sync editing keywords with selected media
  useEffect(() => {
    if (saveKeywordsTimeout.current) {
      clearTimeout(saveKeywordsTimeout.current)
      saveKeywordsTimeout.current = null
    }
    setEditingKeywords(selectedMedia?.keywords || [])
  }, [selectedMedia?.id, selectedMedia?.keywords])

  // Save keywords to API (debounced)
  const persistKeywords = useCallback(
    async (newKeywords: string[]) => {
      if (!selectedMedia) return
      setSavingKeywords(true)
      try {
        const endpoint =
          selectedMedia.kind === 'note'
            ? `/api/v1/notes/${selectedMedia.id}`
            : `/api/v1/media/${selectedMedia.id}`
        const headers: Record<string, string> = { 'Content-Type': 'application/json' }
        if (selectedMedia.kind === 'note') {
          let expectedVersion = resolveNoteVersion(mediaDetail, selectedMedia.raw)
          if (expectedVersion == null) {
            try {
              const latest = await bgRequest<any>({
                path: `/api/v1/notes/${selectedMedia.id}` as any,
                method: 'GET' as any
              })
              expectedVersion = resolveNoteVersion(latest, null)
            } catch {
              expectedVersion = null
            }
          }
          if (expectedVersion == null) {
            throw new Error(
              t('review:mediaPage.noteUpdateNeedsReload', {
                defaultValue: 'Unable to update note. Reload and try again.'
              })
            )
          }
          headers['expected-version'] = String(expectedVersion)
        }

        await bgRequest({
          path: endpoint as any,
          method: 'PUT' as any,
          headers,
          body: { keywords: newKeywords }
        })
        setEditingKeywords(newKeywords)
        if (onKeywordsUpdated) {
          onKeywordsUpdated(selectedMedia.id, newKeywords)
        }
        message.success(
          t('review:mediaPage.keywordsSaved', {
            defaultValue: 'Keywords saved'
          })
        )
      } catch (err) {
        console.error('Failed to save keywords:', err)
        message.error(
          t('review:mediaPage.keywordsSaveFailed', {
            defaultValue: 'Failed to save keywords'
          })
        )
      } finally {
        setSavingKeywords(false)
      }
    },
    [mediaDetail, onKeywordsUpdated, resolveNoteVersion, selectedMedia, t]
  )

  const handleDeleteItem = useCallback(async () => {
    if (!selectedMedia || !onDeleteItem || deletingItem) return
    const ok = await confirmDanger({
      title: t('common:confirmTitle', { defaultValue: 'Please confirm' }),
      content: t('review:mediaPage.deleteItemConfirm', {
        defaultValue: 'Delete this item? This cannot be undone.'
      }),
      okText: t('common:delete', { defaultValue: 'Delete' }),
      cancelText: t('common:cancel', { defaultValue: 'Cancel' })
    })
    if (!ok) return
    setDeletingItem(true)
    try {
      await onDeleteItem(selectedMedia, mediaDetail ?? null)
      setPendingDeleteId(String(selectedMedia.id))
      message.success(t('common:deleted', { defaultValue: 'Deleted' }))
    } catch (err) {
      const msg =
        err && typeof err === 'object' && 'message' in err
          ? String((err as { message?: unknown }).message)
          : ''
      message.error(msg || t('common:deleteFailed', { defaultValue: 'Delete failed' }))
    } finally {
      setDeletingItem(false)
    }
  }, [confirmDanger, deletingItem, mediaDetail, onDeleteItem, selectedMedia, t])

  const handleSaveKeywords = (newKeywords: string[]) => {
    setEditingKeywords(newKeywords)
    if (saveKeywordsTimeout.current) {
      clearTimeout(saveKeywordsTimeout.current)
    }
    saveKeywordsTimeout.current = setTimeout(() => {
      persistKeywords(newKeywords)
    }, 500)
  }

  useEffect(() => {
    return () => {
      if (saveKeywordsTimeout.current) {
        clearTimeout(saveKeywordsTimeout.current)
      }
    }
  }, [])

  // Extract analyses from media detail
  const existingAnalyses = useMemo(() => {
    if (!mediaDetail) return []
    const analyses: Array<{ type: string; text: string }> = []

    // Check processing.analysis (tldw API structure)
    if (mediaDetail.processing?.analysis && typeof mediaDetail.processing.analysis === 'string' && mediaDetail.processing.analysis.trim()) {
      analyses.push({ type: 'Analysis', text: mediaDetail.processing.analysis })
    }

    // Check for summary field (root level)
    if (mediaDetail.summary && typeof mediaDetail.summary === 'string' && mediaDetail.summary.trim()) {
      analyses.push({ type: 'Summary', text: mediaDetail.summary })
    }

    // Check for analysis field (root level)
    const rootAnalysis = typeof mediaDetail.analysis === 'string' ? mediaDetail.analysis.trim() : ''
    if (rootAnalysis) {
      analyses.push({ type: 'Analysis', text: rootAnalysis })
    }

    // Check for analysis_content field (root level, alternate API shape)
    const rootAnalysisContent = firstNonEmptyString(
      mediaDetail.analysis_content,
      mediaDetail.analysisContent
    )
    if (rootAnalysisContent && rootAnalysisContent !== rootAnalysis) {
      analyses.push({ type: 'Analysis', text: rootAnalysisContent })
    }

    // Check for analyses array
    if (Array.isArray(mediaDetail.analyses)) {
      mediaDetail.analyses.forEach((a: any, idx: number) => {
        const text = typeof a === 'string' ? a : (a?.content || a?.text || a?.summary || a?.analysis_content || '')
        const type = typeof a === 'object' && a?.type ? a.type : `Analysis ${idx + 1}`
        if (text && text.trim()) {
          analyses.push({ type, text })
        }
      })
    }

    // Check versions array for analysis_content
    if (Array.isArray(mediaDetail.versions)) {
      mediaDetail.versions.forEach((v: any, idx: number) => {
        if (v?.analysis_content && typeof v.analysis_content === 'string' && v.analysis_content.trim()) {
          const versionNum = v?.version_number || idx + 1
          analyses.push({ type: `Analysis (Version ${versionNum})`, text: v.analysis_content })
        }
      })
    }

    if (optimisticAnalysis) {
      const trimmed = optimisticAnalysis.trim()
      if (trimmed && !analyses.some((entry) => entry.text.trim() === trimmed)) {
        analyses.unshift({ type: 'Analysis', text: optimisticAnalysis })
      }
    }

    return analyses
  }, [mediaDetail, optimisticAnalysis])

  useEffect(() => {
    if (existingAnalyses.length === 0) {
      setActiveAnalysisIndex(0)
      return
    }
    if (activeAnalysisIndex >= existingAnalyses.length) {
      setActiveAnalysisIndex(existingAnalyses.length - 1)
    }
  }, [activeAnalysisIndex, existingAnalyses.length])

  const toggleSection = (section: string) => {
    void setCollapsedSections((prev) => ({
      ...prev,
      [section]: !prev[section]
    }))
  }

  const copyTextWithToasts = async (
    text: string,
    successKey: string,
    defaultSuccess: string
  ) => {
    if (!text) return
    if (!navigator.clipboard?.writeText) {
      message.error(
        t('mediaPage.copyNotSupported', 'Copy is not supported here')
      )
      return
    }
    try {
      await navigator.clipboard.writeText(text)
      message.success(t(successKey, { defaultValue: defaultSuccess }))
    } catch (err) {
      console.error('Failed to copy text:', err)
      message.error(t('mediaPage.copyFailed', 'Failed to copy'))
    }
  }

  const handleCopyContent = () => {
    if (!content) return
    copyTextWithToasts(content, 'mediaPage.contentCopied', 'Content copied')
  }

  const handleCopyMetadata = () => {
    if (!selectedMedia) return
    const metadata = {
      id: selectedMedia.id,
      title: selectedMedia.title,
      type: selectedMedia.meta?.type,
      source: selectedMedia.meta?.source,
      duration: selectedMedia.meta?.duration
    }
    copyTextWithToasts(
      JSON.stringify(metadata, null, 2),
      'mediaPage.metadataCopied',
      'Metadata copied'
    )
  }

  // Get the first/selected analysis for creating note with analysis
  const activeAnalysis =
    existingAnalyses.length > 0
      ? existingAnalyses[Math.min(activeAnalysisIndex, existingAnalyses.length - 1)]
      : null

  const selectedAnalysis = activeAnalysis

  const analysisText = activeAnalysis?.text || ''
  const ANALYSIS_COLLAPSE_THRESHOLD = 2000
  const analysisIsLong = analysisText.length > ANALYSIS_COLLAPSE_THRESHOLD
  const analysisShown =
    !analysisIsLong || analysisExpanded
      ? analysisText
      : `${analysisText.slice(0, ANALYSIS_COLLAPSE_THRESHOLD)}…`

  // Check if viewing a note vs media
  const isNote = selectedMedia?.kind === 'note'

  // Actions dropdown menu items — grouped by purpose
  const actionMenuItems: MenuProps['items'] = [
    // Use group: Chat actions
    ...(!isNote && (onChatWithMedia || onChatAboutMedia) ? [{
      key: 'group-use',
      type: 'group' as const,
      label: t('review:mediaPage.menuGroupUse', { defaultValue: 'Use' }),
      children: [
        ...(onChatWithMedia ? [{
          key: 'chat-with',
          label: t('review:reviewPage.chatWithMedia', {
            defaultValue: 'Chat with this media'
          }),
          icon: <Send className="w-4 h-4" />,
          onClick: onChatWithMedia
        }] : []),
        ...(onChatAboutMedia ? [{
          key: 'chat-about',
          label: t('review:reviewPage.chatAboutMedia', {
            defaultValue: 'Chat about this media'
          }),
          icon: <MessageSquare className="w-4 h-4" />,
          onClick: onChatAboutMedia
        }] : [])
      ]
    }] : []),
    // Create group: Note actions
    ...(!isNote && onCreateNoteWithContent ? [
      { type: 'divider' as const },
      {
        key: 'group-create',
        type: 'group' as const,
        label: t('review:mediaPage.menuGroupCreate', { defaultValue: 'Create' }),
        children: [
          {
            key: 'create-note-content',
            label: t('review:mediaPage.createNoteWithContent', {
              defaultValue: 'Create note with content'
            }),
            icon: <StickyNote className="w-4 h-4" />,
            onClick: () => {
              const title = selectedMedia?.title || t('review:mediaPage.untitled', { defaultValue: 'Untitled' })
              onCreateNoteWithContent(content, title)
            }
          },
          ...(selectedAnalysis ? [{
            key: 'create-note-content-analysis',
            label: t('review:mediaPage.createNoteWithContentAnalysis', {
              defaultValue: 'Create note with content + analysis'
            }),
            icon: <StickyNote className="w-4 h-4" />,
            onClick: () => {
              const title = selectedMedia?.title || t('review:mediaPage.untitled', { defaultValue: 'Untitled' })
              const noteContent = `${content}\n\n---\n\n## Analysis\n\n${selectedAnalysis.text}`
              onCreateNoteWithContent(noteContent, title)
            }
          }] : [])
        ]
      }
    ] : []),
    // Copy group
    ...(!isNote && (onChatWithMedia || onChatAboutMedia || onCreateNoteWithContent)
      ? [{ type: 'divider' as const }]
      : []),
    {
      key: 'group-copy',
      type: 'group' as const,
      label: t('review:mediaPage.menuGroupCopy', { defaultValue: 'Copy' }),
      children: [
        {
          key: 'copy-content',
          label: t('review:mediaPage.copyContent', { defaultValue: 'Copy content' }),
          icon: <Copy className="w-4 h-4" />,
          onClick: handleCopyContent
        },
        {
          key: 'copy-metadata',
          label: t('review:mediaPage.copyMetadata', { defaultValue: 'Copy metadata' }),
          icon: <Copy className="w-4 h-4" />,
          onClick: handleCopyMetadata
        }
      ]
    },
    // Advanced group
    ...(!isNote && onOpenInMultiReview ? [
      { type: 'divider' as const },
      {
        key: 'open-multi-review',
        label: t('review:reviewPage.openInMulti', 'Open in Multi-Item Review'),
        icon: <ExternalLink className="w-4 h-4" />,
        onClick: onOpenInMultiReview
      }
    ] : [])
  ]

  // Use API-provided word count if available, otherwise calculate
  const { wordCount, charCount, paragraphCount } = useMemo(() => {
    const text = content || ''
    const apiWordCount = mediaDetail?.content?.word_count
    const {
      wordCount: computedWordCount,
      charCount,
      paragraphCount
    } = getTextStats(text)
    const wordCountValue =
      typeof apiWordCount === 'number' ? apiWordCount : computedWordCount
    return {
      wordCount: wordCountValue,
      charCount,
      paragraphCount
    }
  }, [content, mediaDetail])
  const readingTimeMinutes = useMemo(
    () =>
      estimateReadingTimeMinutes({
        wordCount,
        charCount
      }),
    [charCount, wordCount]
  )
  const ingestedAt = useMemo(
    () =>
      firstValidDateString(
        selectedMedia?.meta?.created_at,
        mediaDetail?.created_at,
        mediaDetail?.ingested_at,
        mediaDetail?.metadata?.created_at,
        selectedMedia?.raw?.created_at
      ),
    [
      mediaDetail?.created_at,
      mediaDetail?.ingested_at,
      mediaDetail?.metadata?.created_at,
      selectedMedia?.meta?.created_at,
      selectedMedia?.raw?.created_at
    ]
  )
  const lastModifiedAt = useMemo(
    () =>
      firstValidDateString(
        mediaDetail?.updated_at,
        mediaDetail?.last_modified,
        mediaDetail?.last_modified_at,
        mediaDetail?.modified_at,
        mediaDetail?.metadata?.updated_at,
        mediaDetail?.metadata?.last_modified,
        selectedMedia?.raw?.updated_at,
        selectedMedia?.raw?.last_modified
      ),
    [
      mediaDetail?.last_modified,
      mediaDetail?.last_modified_at,
      mediaDetail?.metadata?.last_modified,
      mediaDetail?.metadata?.updated_at,
      mediaDetail?.modified_at,
      mediaDetail?.updated_at,
      selectedMedia?.raw?.last_modified,
      selectedMedia?.raw?.updated_at
    ]
  )
  const ingestedLabel = ingestedAt
    ? formatRelativeTime(ingestedAt, t, { compact: true })
    : null
  const lastModifiedLabel = lastModifiedAt
    ? formatRelativeTime(lastModifiedAt, t, { compact: true })
    : null
  const readingTimeLabel =
    readingTimeMinutes != null
      ? t('review:mediaPage.readingTime', {
          defaultValue: `${readingTimeMinutes} min read`,
          minutes: readingTimeMinutes
        })
      : null
  const safeMetadata = useMemo(() => {
    const fromDetail = mediaDetail?.safe_metadata
    if (fromDetail && typeof fromDetail === 'object' && !Array.isArray(fromDetail)) {
      return fromDetail as Record<string, unknown>
    }
    const fromRaw = selectedMedia?.raw?.safe_metadata
    if (fromRaw && typeof fromRaw === 'object' && !Array.isArray(fromRaw)) {
      return fromRaw as Record<string, unknown>
    }
    return {} as Record<string, unknown>
  }, [mediaDetail?.safe_metadata, selectedMedia?.raw?.safe_metadata])
  const safeMetadataEntries = useMemo(() => {
    const entries = Object.entries(safeMetadata)
      .map(([key, value]) => ({
        key,
        label: toDisplayMetadataLabel(key),
        value: toDisplayMetadataValue(value)
      }))
      .filter((entry) => entry.value.length > 0)

    const priorityEntries = SAFE_METADATA_PRIORITY_KEYS.flatMap((key) => {
      const match = entries.find((entry) => entry.key === key)
      return match ? [match] : []
    })
    const priorityKeySet = new Set<string>(SAFE_METADATA_PRIORITY_KEYS)
    const remainingEntries = entries
      .filter((entry) => !priorityKeySet.has(entry.key))
      .sort((left, right) => left.label.localeCompare(right.label))

    return [...priorityEntries, ...remainingEntries]
  }, [safeMetadata])
  const chunkingStatus = useMemo(() => {
    const candidates = [
      mediaDetail?.chunking_status,
      mediaDetail?.processing?.chunking_status,
      mediaDetail?.processing?.chunking,
      selectedMedia?.raw?.chunking_status,
      selectedMedia?.raw?.processing?.chunking_status
    ]
    for (const candidate of candidates) {
      const normalized = normalizeChunkingStatus(candidate)
      if (normalized) return normalized
    }
    return null
  }, [
    mediaDetail?.chunking_status,
    mediaDetail?.processing?.chunking,
    mediaDetail?.processing?.chunking_status,
    selectedMedia?.raw?.chunking_status,
    selectedMedia?.raw?.processing?.chunking_status
  ])
  const vectorProcessingStatus = useMemo(() => {
    const candidates = [
      mediaDetail?.vector_processing,
      mediaDetail?.vector_processing_status,
      mediaDetail?.processing?.vector_processing,
      mediaDetail?.processing?.vector_processing_status,
      selectedMedia?.raw?.vector_processing,
      selectedMedia?.raw?.vector_processing_status,
      selectedMedia?.raw?.processing?.vector_processing,
      selectedMedia?.raw?.processing?.vector_processing_status
    ]
    for (const candidate of candidates) {
      const normalized = normalizeVectorProcessingStatus(candidate)
      if (normalized) return normalized
    }
    return null
  }, [
    mediaDetail?.processing?.vector_processing,
    mediaDetail?.processing?.vector_processing_status,
    mediaDetail?.vector_processing,
    mediaDetail?.vector_processing_status,
    selectedMedia?.raw?.processing?.vector_processing,
    selectedMedia?.raw?.processing?.vector_processing_status,
    selectedMedia?.raw?.vector_processing,
    selectedMedia?.raw?.vector_processing_status
  ])
  const processingStatusBadges = useMemo(() => {
    const badges: Array<{ key: 'chunking' | 'vector'; label: string; status: string }> = []
    if (chunkingStatus) {
      badges.push({
        key: 'chunking',
        label: t('review:mediaPage.chunkingStatusLabel', {
          defaultValue: 'Chunking'
        }),
        status: chunkingStatus
      })
    }
    if (vectorProcessingStatus) {
      badges.push({
        key: 'vector',
        label: t('review:mediaPage.vectorStatusLabel', {
          defaultValue: 'Vector'
        }),
        status: vectorProcessingStatus
      })
    }
    return badges
  }, [chunkingStatus, t, vectorProcessingStatus])
  const hasDetailedMetadata =
    processingStatusBadges.length > 0 || safeMetadataEntries.length > 0

  if (!selectedMedia || isAwaitingSelectionUpdate) {
    return (
      <div className="flex-1 flex items-center justify-center bg-bg">
        <div className="text-center max-w-md px-6">
          <div className="mb-6 flex justify-center">
            <div className="w-32 h-32 rounded-full bg-gradient-to-br from-primary/10 to-primary/20 flex items-center justify-center">
              <FileSearch className="w-16 h-16 text-primary" />
            </div>
          </div>
          <h2 className="mb-2 text-xl font-semibold text-text">
            {isAwaitingSelectionUpdate
              ? t('common:deleted', { defaultValue: 'Deleted' })
              : t('review:mediaPage.noSelectionTitle', {
                  defaultValue: 'No media item selected'
                })}
          </h2>
          <p className="text-text-muted">
            {isAwaitingSelectionUpdate
              ? t('review:mediaPage.loadingContent', {
                  defaultValue: 'Loading content...'
                })
              : t('review:mediaPage.noSelectionDescription', {
                  defaultValue:
                    'Select a media item from the left sidebar to view its content and analyses here.'
                })}
          </p>
          {!isAwaitingSelectionUpdate && (
            <>
              <p className="mt-4 text-xs text-text-subtle">
                {t('review:mediaPage.keyboardHint', {
                  defaultValue: 'Tip: Use j/k to navigate items, arrow keys to change pages'
                })}
              </p>
              <button
                type="button"
                onClick={() => {
                  if (typeof window !== 'undefined') {
                    window.dispatchEvent(new CustomEvent('tldw:open-quick-ingest'))
                  }
                }}
                className="mt-4 inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-sm text-text hover:bg-surface2"
              >
                <UploadCloud className="h-4 w-4" />
                {t('review:mediaPage.openQuickIngest', {
                  defaultValue: 'Open Quick Ingest'
                })}
              </button>
            </>
          )}
        </div>
      </div>
    )
  }

  return (
    <div ref={contentRef} className="relative flex-1 flex flex-col bg-bg">
      {/* Compact Header */}
      <div className="px-4 py-2 border-b border-border bg-surface">
        <div className="flex flex-col md:flex-row items-center gap-3">
          {/* Left: Navigation */}
          <div className="flex items-center gap-1">
            <Tooltip
              title={t('review:reviewPage.prevItem', { defaultValue: 'Previous' })}
            >
              <button
                onClick={onPrevious}
                disabled={!hasPrevious}
                className="p-1.5 text-text-muted hover:bg-surface2 rounded disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label={t('review:reviewPage.prevItem', { defaultValue: 'Previous' })}
                title={t('review:reviewPage.prevItem', { defaultValue: 'Previous' })}
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
            </Tooltip>
            <span className="text-xs text-text-muted tabular-nums min-w-[40px] text-center">
              {totalResults > 0 ? `${currentIndex + 1}/${totalResults}` : '0/0'}
            </span>
            <Tooltip
              title={t('review:reviewPage.nextItem', { defaultValue: 'Next' })}
            >
              <button
                onClick={onNext}
                disabled={!hasNext}
                className="p-1.5 text-text-muted hover:bg-surface2 rounded disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label={t('review:reviewPage.nextItem', { defaultValue: 'Next' })}
                title={t('review:reviewPage.nextItem', { defaultValue: 'Next' })}
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </Tooltip>
          </div>

          {/* Center: Title */}
          <Tooltip title={selectedMedia.title || ''} placement="bottom">
            <h3 className="flex-1 text-sm font-medium text-text truncate text-center px-2 max-w-[300px] md:max-w-none">
              {selectedMedia.title || `${selectedMedia.kind} ${selectedMedia.id}`}
            </h3>
          </Tooltip>

          {/* Right: Chat Button + Actions Dropdown */}
          <div className="flex items-center gap-1">
            {!isNote && onChatWithMedia && (
              <Tooltip title={t('review:reviewPage.chatWithMedia', { defaultValue: 'Chat with this media' })}>
                <button
                  onClick={onChatWithMedia}
                  className="p-1.5 text-text-muted hover:bg-surface2 rounded"
                  aria-label={t('review:reviewPage.chatWithMedia', { defaultValue: 'Chat with this media' })}
                  title={t('review:reviewPage.chatWithMedia', { defaultValue: 'Chat with this media' })}
                >
                  <MessageSquare className="w-4 h-4" />
                </button>
              </Tooltip>
            )}
            <Dropdown
              menu={{ items: actionMenuItems }}
              trigger={['click']}
              placement="bottomRight"
            >
              <button
                className="p-1.5 text-text-muted hover:bg-surface2 rounded"
                aria-label={t('review:mediaPage.actionsLabel', {
                  defaultValue: 'Actions'
                })}
                title={t('review:mediaPage.actionsLabel', {
                  defaultValue: 'Actions'
                })}
              >
                <MoreHorizontal className="w-4 h-4" />
              </button>
            </Dropdown>
          </div>
        </div>
      </div>

      {/* Content Area */}
      <div ref={contentScrollContainerRef} className="flex-1 overflow-y-auto p-4">
        {isDetailLoading ? (
          <div
            className="flex flex-col items-center justify-center h-64 text-text-muted"
            role="status"
            aria-live="polite"
          >
            <Loader2 className="w-8 h-8 animate-spin mb-3" />
            <span className="text-sm">
              {t('review:mediaPage.loadingContent', { defaultValue: 'Loading content...' })}
            </span>
          </div>
        ) : (
        <div className="max-w-4xl mx-auto">
          {/* Meta Row */}
          <div
            className="flex items-center gap-3 flex-wrap text-xs text-text-muted mb-3"
            data-testid="media-metadata-bar"
          >
            {selectedMedia.meta?.type && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-surface2 text-text capitalize font-medium">
                {selectedMedia.meta.type}
              </span>
            )}
            {selectedMedia.meta?.source && (
              <span className="truncate max-w-[200px]" title={selectedMedia.meta.source}>
                {selectedMedia.meta.source}
              </span>
            )}
            {(() => {
              const rawDuration = selectedMedia.meta?.duration as
                | number
                | string
                | null
                | undefined
              const durationSeconds =
                typeof rawDuration === 'number'
                  ? rawDuration
                  : typeof rawDuration === 'string'
                    ? Number(rawDuration)
                    : null
              const durationLabel = formatDuration(durationSeconds)
              if (!durationLabel) return null
              return (
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {durationLabel}
                </span>
              )
            })()}
            {ingestedLabel && (
              <span
                className="inline-flex items-center gap-1 rounded bg-surface2 px-1.5 py-0.5"
                data-testid="media-ingested-date"
                title={ingestedAt || undefined}
              >
                {t('review:mediaPage.ingestedLabel', { defaultValue: 'Ingested' })}{' '}
                {ingestedLabel}
              </span>
            )}
            {lastModifiedLabel && (
              <span
                className="inline-flex items-center gap-1 rounded bg-surface2 px-1.5 py-0.5"
                data-testid="media-last-modified-date"
                title={lastModifiedAt || undefined}
              >
                {t('review:mediaPage.lastModifiedLabel', { defaultValue: 'Updated' })}{' '}
                {lastModifiedLabel}
              </span>
            )}
            <span className="flex items-center gap-1">
              <FileText className="w-3 h-3" />
              {wordCount.toLocaleString()} {t('review:mediaPage.words', { defaultValue: 'words' })}
            </span>
            {readingTimeLabel && (
              <span
                className="inline-flex items-center gap-1 rounded bg-surface2 px-1.5 py-0.5"
                data-testid="media-reading-time"
              >
                {readingTimeLabel}
              </span>
            )}
            {processingStatusBadges.map((badge) => (
              <span
                key={badge.key}
                className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 ${processingStatusClass(
                  badge.status
                )}`}
                data-testid={`media-processing-status-${badge.key}`}
                data-status={badge.status}
              >
                {badge.label}: {formatProcessingStatus(badge.status)}
              </span>
            ))}
          </div>

          <div className="mb-4 rounded-lg border border-border bg-surface">
            <button
              type="button"
              onClick={() => setMetadataDetailsExpanded((prev) => !prev)}
              className="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-medium text-text hover:bg-surface2"
              aria-expanded={metadataDetailsExpanded}
              data-testid="metadata-details-toggle"
            >
              <span>
                {t('review:mediaPage.metadataDetailsLabel', {
                  defaultValue: 'Metadata details'
                })}
              </span>
              <span className="text-text-muted">
                {metadataDetailsExpanded
                  ? t('review:mediaPage.hideMetadataDetails', {
                      defaultValue: 'Hide'
                    })
                  : t('review:mediaPage.showMetadataDetails', {
                      defaultValue: hasDetailedMetadata ? 'Show' : 'Open'
                    })}
              </span>
            </button>
            {metadataDetailsExpanded && (
              <div
                className="space-y-3 border-t border-border px-3 py-2 text-xs"
                data-testid="metadata-details-panel"
              >
                <div className="space-y-1">
                  <p className="font-medium text-text">
                    {t('review:mediaPage.processingStatusLabel', {
                      defaultValue: 'Processing status'
                    })}
                  </p>
                  {processingStatusBadges.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {processingStatusBadges.map((badge) => (
                        <span
                          key={`detail-${badge.key}`}
                          className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 ${processingStatusClass(
                            badge.status
                          )}`}
                          data-testid={`metadata-processing-${badge.key}`}
                          data-status={badge.status}
                        >
                          {badge.label}: {formatProcessingStatus(badge.status)}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-text-muted" data-testid="metadata-processing-empty">
                      {t('review:mediaPage.processingStatusEmpty', {
                        defaultValue: 'Processing status is not available for this item.'
                      })}
                    </p>
                  )}
                </div>
                <div className="space-y-1">
                  <p className="font-medium text-text">
                    {t('review:mediaPage.additionalMetadataLabel', {
                      defaultValue: 'Additional metadata'
                    })}
                  </p>
                  {safeMetadataEntries.length > 0 ? (
                    <dl className="grid gap-1">
                      {safeMetadataEntries.map((entry) => (
                        <div
                          key={entry.key}
                          className="grid grid-cols-[minmax(0,150px)_1fr] gap-2 rounded bg-surface2 px-2 py-1"
                          data-testid={`metadata-field-${entry.key}`}
                        >
                          <dt className="text-text-muted">{entry.label}</dt>
                          <dd className="break-words text-text">{entry.value}</dd>
                        </div>
                      ))}
                    </dl>
                  ) : (
                    <p className="text-text-muted" data-testid="metadata-safe-empty">
                      {t('review:mediaPage.additionalMetadataEmpty', {
                        defaultValue: 'No additional metadata is available for this item.'
                      })}
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Keywords - Compact */}
          <div className="mb-4">
            <Select
              mode="tags"
              allowClear
              data-testid="media-keywords-select"
              placeholder={
                savingKeywords
                  ? t('review:mediaPage.savingKeywords', { defaultValue: 'Saving...' })
                  : t('review:mediaPage.keywordsPlaceholder', { defaultValue: 'Add keywords...' })
              }
              className="w-full"
              size="small"
              value={editingKeywords}
              onChange={(vals) => {
                handleSaveKeywords(vals as string[])
              }}
              loading={savingKeywords}
              disabled={savingKeywords}
              tokenSeparators={[',']}
              suffixIcon={savingKeywords ? <Spin size="small" /> : undefined}
            />
          </div>

          {/* Main Content */}
          <div className="bg-surface border border-border rounded-lg mb-2 overflow-hidden">
            <div className="flex items-center justify-between px-3 py-2 bg-surface2">
              <button
                onClick={() => toggleSection('content')}
                className="flex items-center gap-2 hover:bg-surface -ml-1 px-1 rounded transition-colors"
                title={t('review:mediaPage.content', { defaultValue: 'Content' })}
              >
                <span className="text-sm font-medium text-text">
                  {t('review:mediaPage.content', { defaultValue: 'Content' })}
                </span>
                {collapsedSections.content ? (
                  <ChevronDown className="w-4 h-4 text-text-subtle" />
                ) : (
                  <ChevronUp className="w-4 h-4 text-text-subtle" />
                )}
              </button>
              <div className="flex items-center gap-1">
                {navigationTargetDescription ? (
                  <span className="rounded bg-surface px-2 py-0.5 text-[11px] text-text-muted">
                    {navigationTargetDescription}
                  </span>
                ) : null}
                {showContentDisplayModeSelector && onContentDisplayModeChange ? (
                  <Select
                    size="small"
                    value={contentDisplayMode}
                    options={displayModeOptions}
                    onChange={(value) =>
                      onContentDisplayModeChange(value as MediaNavigationFormat)
                    }
                    className="min-w-[132px]"
                    popupMatchSelectWidth={false}
                    aria-label={t('review:mediaPage.displayMode', {
                      defaultValue: 'Display mode'
                    })}
                  />
                ) : null}
                <div
                  className="inline-flex items-center rounded-md border border-border bg-surface p-0.5"
                  role="group"
                  aria-label={t('review:mediaPage.textSize', {
                    defaultValue: 'Text size'
                  })}
                >
                  {TEXT_SIZE_CONTROL_OPTIONS.map((option) => {
                    const isActive = option.value === resolvedTextSizePreset
                    return (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => {
                          if (option.value === resolvedTextSizePreset) return
                          void setTextSizePreset(option.value)
                        }}
                        className={`rounded px-1.5 py-0.5 text-[11px] font-medium transition-colors ${
                          isActive
                            ? 'bg-primary text-white'
                            : 'text-text-muted hover:bg-surface2 hover:text-text'
                        }`}
                        aria-pressed={isActive}
                        aria-label={t('review:mediaPage.textSizeOption', {
                          defaultValue: 'Text size {{size}}',
                          size: option.label
                        })}
                        title={t('review:mediaPage.textSizeOption', {
                          defaultValue: 'Text size {{size}}',
                          size: option.label
                        })}
                      >
                        {option.label}
                      </button>
                    )
                  })}
                </div>
                {!isNote && content && (
                  <button
                    onClick={() => {
                      setEditingContentText(content)
                      setContentEditModalOpen(true)
                    }}
                    className="p-1 text-text-muted hover:text-text transition-colors"
                    title={t('review:mediaPage.editContent', {
                      defaultValue: 'Edit content'
                    })}
                    aria-label={t('review:mediaPage.editContent', {
                      defaultValue: 'Edit content'
                    })}
                  >
                    <Edit3 className="w-4 h-4" />
                  </button>
                )}
                {/* Expand/collapse toggle for long content */}
                {!collapsedSections.content && shouldShowExpandToggle && (
                  <button
                    onClick={() => setContentExpanded((v) => !v)}
                    className="p-1 text-text-muted hover:text-text transition-colors"
                    title={
                      contentExpanded
                        ? t('review:mediaPage.collapse', {
                            defaultValue: 'Collapse'
                          })
                        : t('review:mediaPage.expand', {
                            defaultValue: 'Expand'
                          })
                    }
                  >
                    {contentExpanded ? (
                      <Minimize2 className="w-4 h-4" />
                    ) : (
                      <Expand className="w-4 h-4" />
                    )}
                  </button>
                )}
              </div>
            </div>
            {!collapsedSections.content && (
              <div className="p-3 bg-surface animate-in fade-in slide-in-from-top-1 duration-150">
                {shouldShowEmbeddedPlayer ? (
                  <div className="mb-3 rounded-md border border-border bg-surface2 p-2">
                    {embeddedMediaLoading ? (
                      <div
                        className="flex items-center gap-2 text-xs text-text-muted"
                        data-testid="embedded-media-loading"
                      >
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        {t('review:mediaPage.loadingMediaPreview', {
                          defaultValue: 'Loading media preview...'
                        })}
                      </div>
                    ) : embeddedMediaUrl ? (
                      mediaType === 'video' ? (
                        <video
                          ref={(node) => {
                            mediaPlayerRef.current = node
                          }}
                          src={embeddedMediaUrl}
                          controls
                          preload="metadata"
                          className="w-full rounded"
                          data-testid="embedded-video-player"
                        />
                      ) : (
                        <audio
                          ref={(node) => {
                            mediaPlayerRef.current = node
                          }}
                          src={embeddedMediaUrl}
                          controls
                          preload="metadata"
                          className="w-full"
                          data-testid="embedded-audio-player"
                        />
                      )
                    ) : embeddedMediaError ? (
                      <p className="m-0 text-xs text-warn">{embeddedMediaError}</p>
                    ) : null}
                  </div>
                ) : null}
                <div
                  ref={contentBodyRef}
                  className={`text-sm text-text leading-relaxed ${
                    !contentExpanded && shouldShowExpandToggle ? 'max-h-64 overflow-hidden relative' : ''
                  }`}
                >
                  {effectiveRenderMode === 'plain' ? (
                    hasClickableTranscriptTimestamps ? (
                      <div
                        className={`m-0 space-y-1 whitespace-pre-wrap text-text font-mono ${contentBodyTypographyClass}`}
                      >
                        {transcriptLines.map((line, lineIndex) => {
                          const match = line.match(LEADING_TRANSCRIPT_TIMESTAMP_PATTERN)
                          if (!match) {
                            return (
                              <div key={`line-${lineIndex}`}>
                                {line.length > 0 ? line : '\u00A0'}
                              </div>
                            )
                          }
                          const timestamp = match[2] || match[3] || ''
                          const tail = `${match[1] || ''}${match[4] || ''}${match[5] || ''}`
                          return (
                            <div key={`line-${lineIndex}`} className="flex flex-wrap items-start gap-2">
                              <button
                                type="button"
                                onClick={() => handleTranscriptTimestampSeek(timestamp)}
                                className="rounded border border-border bg-surface px-1.5 py-0.5 text-[11px] text-primary hover:bg-surface2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                                aria-label={t('review:mediaPage.seekToTimestamp', {
                                  defaultValue: 'Seek to {{timestamp}}',
                                  timestamp
                                })}
                              >
                                {timestamp}
                              </button>
                              <span className="flex-1 whitespace-pre-wrap break-words">{tail}</span>
                            </div>
                          )
                        })}
                      </div>
                    ) : (
                      <pre
                        className={`whitespace-pre-wrap text-text font-mono m-0 ${contentBodyTypographyClass}`}
                      >
                        {content ||
                          t('review:mediaPage.noContent', {
                            defaultValue: 'No content available'
                          })}
                      </pre>
                    )
                  ) : effectiveRenderMode === 'html' ? (
                    content ? (
                      <div
                        className={`${richTextTypographyClass} break-words dark:prose-invert max-w-none prose-p:leading-relaxed`}
                        dangerouslySetInnerHTML={{
                          __html: sanitizedRichContent
                        }}
                      />
                    ) : (
                      <p className="m-0 text-sm text-text-muted">
                        {t('review:mediaPage.noContent', {
                          defaultValue: 'No content available'
                        })}
                      </p>
                    )
                  ) : (
                    <MarkdownPreview
                      content={
                        contentForPreview ||
                        t('review:mediaPage.noContent', {
                          defaultValue: 'No content available'
                        })
                      }
                      size={markdownPreviewSize}
                    />
                  )}
                  {/* Fade overlay when collapsed */}
                  {!contentExpanded && shouldShowExpandToggle && (
                    <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-surface to-transparent" />
                  )}
                </div>
                {/* Show more/less button */}
                {shouldShowExpandToggle && (
                  <button
                    onClick={() => setContentExpanded(v => !v)}
                    className="mt-2 text-xs text-primary hover:underline"
                    title={
                      contentExpanded
                        ? t('review:mediaPage.showLess', { defaultValue: 'Show less' })
                        : t('review:mediaPage.showMore', {
                            defaultValue: `Show more (${Math.round(content.length / 1000)}k chars)`
                          })
                    }
                  >
                    {contentExpanded
                      ? t('review:mediaPage.showLess', { defaultValue: 'Show less' })
                      : t('review:mediaPage.showMore', {
                          defaultValue: `Show more (${Math.round(content.length / 1000)}k chars)`
                        })}
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Analysis - only for media, not notes */}
          {!isNote && (
            <div className="bg-surface border border-border rounded-lg mb-2 overflow-hidden">
              <div className="flex items-center justify-between px-3 py-2 bg-surface2">
              <button
                onClick={() => toggleSection('analysis')}
                className="flex items-center gap-2 hover:bg-surface -ml-1 px-1 rounded transition-colors"
                title={t('review:reviewPage.analysisTitle', { defaultValue: 'Analysis' })}
              >
                <span className="text-sm font-medium text-text">
                  {t('review:reviewPage.analysisTitle', { defaultValue: 'Analysis' })}
                </span>
                  {collapsedSections.analysis ? (
                    <ChevronDown className="w-4 h-4 text-text-subtle" />
                  ) : (
                    <ChevronUp className="w-4 h-4 text-text-subtle" />
                  )}
                </button>
                <div className="flex items-center gap-2">
                <button
                  onClick={() => setAnalysisModalOpen(true)}
                  className="px-2 py-1 bg-primary hover:bg-primaryStrong text-white rounded text-xs font-medium flex items-center gap-1 transition-colors"
                  title={t('review:mediaPage.generateAnalysisHint', {
                    defaultValue: 'Generate new analysis'
                  })}
                >
                  <Sparkles className="w-3 h-3" />
                  {t('review:mediaPage.generateAnalysis', { defaultValue: 'Generate' })}
                </button>
                  {existingAnalyses.length > 0 && (
                    <>
                      {/* Send to chat button */}
                      {onSendAnalysisToChat && (
                        <button
                          onClick={() => {
                            if (activeAnalysis) onSendAnalysisToChat(activeAnalysis.text)
                          }}
                          className="p-1 text-text-muted hover:text-text transition-colors"
                          title={t('review:reviewPage.sendAnalysisToChat', {
                            defaultValue: 'Send analysis to chat'
                          })}
                        >
                          <Send className="w-3.5 h-3.5" />
                          </button>
                      )}
                      {/* Copy analysis button */}
                      <button
                        onClick={() =>
                          activeAnalysis &&
                          copyTextWithToasts(
                            activeAnalysis.text,
                            'mediaPage.analysisCopied',
                            'Analysis copied'
                          )
                        }
                        className="p-1 text-text-muted hover:text-text transition-colors"
                        title={t('review:reviewPage.copyAnalysis', { defaultValue: 'Copy analysis' })}
                      >
                        <Copy className="w-3.5 h-3.5" />
                      </button>
                      {/* Edit analysis button */}
                      <button
                        onClick={() => {
                          if (!activeAnalysis) return
                          setEditingAnalysisText(activeAnalysis.text)
                          setAnalysisEditModalOpen(true)
                        }}
                        className="p-1 text-text-muted hover:text-text transition-colors"
                        title={t('review:mediaPage.editAnalysis', { defaultValue: 'Edit analysis' })}
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                      </button>
                    </>
                  )}
                  {activeAnalysis && analysisIsLong && (
                    <button
                      onClick={() => {
                        if (collapsedSections.analysis) {
                          toggleSection('analysis')
                          setAnalysisExpanded(true)
                          return
                        }
                        setAnalysisExpanded((v) => !v)
                      }}
                      className="p-1 text-text-muted hover:text-text transition-colors"
                      aria-label={
                        collapsedSections.analysis || !analysisExpanded
                          ? `${t('review:reviewPage.expandAnalysis', { defaultValue: 'Expand' })} ${t('review:reviewPage.analysisTitle', { defaultValue: 'Analysis' })}`
                          : `${t('review:reviewPage.collapseAnalysis', { defaultValue: 'Collapse' })} ${t('review:reviewPage.analysisTitle', { defaultValue: 'Analysis' })}`
                      }
                      title={
                        collapsedSections.analysis || !analysisExpanded
                          ? `${t('review:reviewPage.expandAnalysis', { defaultValue: 'Expand' })} ${t('review:reviewPage.analysisTitle', { defaultValue: 'Analysis' })}`
                          : `${t('review:reviewPage.collapseAnalysis', { defaultValue: 'Collapse' })} ${t('review:reviewPage.analysisTitle', { defaultValue: 'Analysis' })}`
                      }
                    >
                      {collapsedSections.analysis || !analysisExpanded ? (
                        <Expand className="w-4 h-4" />
                      ) : (
                        <Minimize2 className="w-4 h-4" />
                      )}
                    </button>
                  )}
                </div>
              </div>
              {!collapsedSections.analysis && (
                <div className="p-3 bg-surface animate-in fade-in slide-in-from-top-1 duration-150">
                  {existingAnalyses.length > 0 ? (
                    <div className="space-y-3">
                      {existingAnalyses.length > 1 && (
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-text-muted">
                            {t('review:mediaPage.analysis', { defaultValue: 'Analysis' })}
                          </span>
                          <Select
                            size="small"
                            value={activeAnalysisIndex}
                            onChange={setActiveAnalysisIndex}
                            className="min-w-[220px]"
                            aria-label={t('review:mediaPage.analysis', { defaultValue: 'Analysis' })}
                          >
                            {existingAnalyses.map((analysis, idx) => (
                              <Select.Option key={idx} value={idx}>
                                {analysis.type}
                              </Select.Option>
                            ))}
                          </Select>
                        </div>
                      )}
                      {activeAnalysis && (() => {
                        const trimmedOptimistic = optimisticAnalysis.trim()
                        const isOptimistic =
                          trimmedOptimistic && activeAnalysis.text.trim() === trimmedOptimistic
                        return (
                          <div className="space-y-1">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-medium text-text-muted uppercase">
                                  {activeAnalysis.type}
                                </span>
                                {isOptimistic && (
                                  <span className="text-[10px] uppercase tracking-wide bg-surface2 text-text-muted border border-border rounded px-1.5 py-0.5">
                                    {t('review:mediaPage.analysisPending', {
                                      defaultValue: 'Pending save'
                                    })}
                                  </span>
                                )}
                              </div>
                              <button
                                onClick={() =>
                                  copyTextWithToasts(
                                    activeAnalysis.text,
                                    'mediaPage.analysisCopied',
                                    'Analysis copied'
                                  )
                                }
                                className="p-0.5 text-text-subtle hover:text-text"
                                aria-label={t('review:mediaPage.copyAnalysis', {
                                  defaultValue: 'Copy analysis to clipboard'
                                })}
                                title={t('review:mediaPage.copyAnalysis', {
                                  defaultValue: 'Copy analysis to clipboard'
                                })}
                              >
                                <Copy className="w-3 h-3" />
                              </button>
                            </div>
                            <div className="text-sm text-text whitespace-pre-wrap leading-relaxed">
                            {analysisShown}
                            </div>
                          </div>
                        )
                      })()}
                    </div>
                  ) : (
                    <div className="text-sm text-text-muted text-center py-4">
                      {t('review:reviewPage.noAnalysis', {
                        defaultValue: 'No analysis yet'
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Statistics */}
          <div className="bg-surface border border-border rounded-lg mb-2 overflow-hidden">
            <button
              onClick={() => toggleSection('statistics')}
              className="w-full flex items-center justify-between px-3 py-2 bg-surface2 hover:bg-surface transition-colors"
              title={t('review:mediaPage.statistics', { defaultValue: 'Statistics' })}
            >
              <span className="text-sm font-medium text-text">
                {t('review:mediaPage.statistics', { defaultValue: 'Statistics' })}
              </span>
              {collapsedSections.statistics ? (
                <ChevronDown className="w-4 h-4 text-text-subtle" />
              ) : (
                <ChevronUp className="w-4 h-4 text-text-subtle" />
              )}
            </button>
            {!collapsedSections.statistics && (
              <div className="p-3 bg-surface animate-in fade-in slide-in-from-top-1 duration-150">
                <div className="grid grid-cols-3 gap-3 text-sm">
                  <div className="flex flex-col">
                    <span className="text-text-muted text-xs">
                      {t('review:mediaPage.words', { defaultValue: 'Words' })}
                    </span>
                    <span className="text-text font-medium">
                      {wordCount}
                    </span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-text-muted text-xs">
                      {t('review:mediaPage.characters', { defaultValue: 'Characters' })}
                    </span>
                    <span className="text-text font-medium">
                      {charCount}
                    </span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-text-muted text-xs">
                      {t('review:mediaPage.paragraphs', { defaultValue: 'Paragraphs' })}
                    </span>
                    <span className="text-text font-medium">
                      {paragraphCount}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Metadata */}
          <div className="bg-surface border border-border rounded-lg mb-2 overflow-hidden">
            <button
              onClick={() => toggleSection('metadata')}
              className="w-full flex items-center justify-between px-3 py-2 bg-surface2 hover:bg-surface transition-colors"
              title={t('review:mediaPage.metadata', { defaultValue: 'Metadata' })}
            >
              <span className="text-sm font-medium text-text">
                {t('review:mediaPage.metadata', { defaultValue: 'Metadata' })}
              </span>
              {collapsedSections.metadata ? (
                <ChevronDown className="w-4 h-4 text-text-subtle" />
              ) : (
                <ChevronUp className="w-4 h-4 text-text-subtle" />
              )}
            </button>
            {!collapsedSections.metadata && (
              <div className="p-3 bg-surface animate-in fade-in slide-in-from-top-1 duration-150">
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between py-1">
                    <span className="text-text-muted text-xs">
                      {t('review:mediaPage.idLabel', { defaultValue: 'ID' })}
                    </span>
                    <span className="text-text font-mono text-xs">
                      {selectedMedia.id}
                    </span>
                  </div>
                  {selectedMedia.meta?.type && (
                    <div className="flex justify-between py-1">
                      <span className="text-text-muted text-xs">
                        {t('review:mediaPage.typeLabel', { defaultValue: 'Type' })}
                      </span>
                      <span className="text-text text-xs capitalize">
                        {selectedMedia.meta.type}
                      </span>
                    </div>
                  )}
                  <div className="flex justify-between py-1">
                    <span className="text-text-muted text-xs">
                      {t('review:mediaPage.titleLabel', { defaultValue: 'Title' })}
                    </span>
                    <span className="text-text text-xs truncate max-w-[200px]">
                      {selectedMedia.title || t('review:mediaPage.notAvailable', { defaultValue: 'N/A' })}
                    </span>
                  </div>
                  {selectedMedia.meta?.source && (
                    <div className="flex justify-between py-1">
                      <span className="text-text-muted text-xs">
                        {t('review:mediaPage.source', { defaultValue: 'Source' })}
                      </span>
                      <span className="text-text text-xs truncate max-w-[200px]">
                        {selectedMedia.meta.source}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Version History - only for media */}
          {!isNote && (
            <div className="mb-2">
              <VersionHistoryPanel
                mediaId={selectedMedia.id}
                currentContent={content}
                currentPrompt={derivedPrompt}
                currentAnalysis={derivedAnalysisContent}
                onVersionLoad={(vContent, vAnalysis, vPrompt, vNum) => {
                  // Update the analysis edit text with the loaded version
                  if (vAnalysis) {
                    setEditingAnalysisText(vAnalysis)
                    setAnalysisEditModalOpen(true)
                  }
                }}
                onRefresh={onRefreshMedia}
                onShowDiff={(left, right, leftLabel, rightLabel, metadataDiff) => {
                  setDiffLeftText(left)
                  setDiffRightText(right)
                  setDiffLeftLabel(leftLabel)
                  setDiffRightLabel(rightLabel)
                  setDiffMetadataSummary(metadataDiff || null)
                  setDiffModalOpen(true)
                }}
              />
            </div>
          )}

          {/* Developer Tools */}
          {showDeveloperTools ? (
            <DeveloperToolsSection
              data={mediaDetail}
              label={t('review:mediaPage.developerTools', {
                defaultValue: 'Developer Tools'
              })}
            />
          ) : null}
          {selectedMedia && onDeleteItem && (
            <div className="mt-2">
              <button
                type="button"
                onClick={handleDeleteItem}
                disabled={deletingItem}
                className="w-full inline-flex items-center justify-center gap-2 rounded-md border border-danger/30 px-3 py-2 text-sm text-danger hover:bg-danger/10 disabled:opacity-60"
                title={t('review:mediaPage.deleteItem', { defaultValue: 'Delete item' })}
              >
                {deletingItem ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
                {deletingItem
                  ? t('review:mediaPage.deletingItem', { defaultValue: 'Deleting...' })
                  : t('review:mediaPage.deleteItem', { defaultValue: 'Delete item' })}
              </button>
            </div>
          )}
        </div>
        )}
      </div>

      {showBackToTop && (
        <button
          type="button"
          onClick={handleBackToTop}
          className="absolute bottom-4 right-4 z-20 inline-flex items-center gap-1 rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium text-text shadow-sm hover:bg-surface2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          aria-label={t('review:mediaPage.backToTop', {
            defaultValue: 'Back to top'
          })}
          title={t('review:mediaPage.backToTop', {
            defaultValue: 'Back to top'
          })}
        >
          <ChevronUp className="h-3.5 w-3.5" />
          {t('review:mediaPage.backToTop', {
            defaultValue: 'Back to top'
          })}
        </button>
      )}

      {/* Analysis Generation Modal - only for media */}
      {selectedMedia && !isNote && (
        <AnalysisModal
          open={analysisModalOpen}
          onClose={() => setAnalysisModalOpen(false)}
          mediaId={selectedMedia.id}
          mediaContent={content}
          onAnalysisGenerated={(analysisText) => {
            if (analysisText) {
              setOptimisticAnalysis(analysisText)
            }
            if (onRefreshMedia) {
              onRefreshMedia()
            }
          }}
        />
      )}

      {/* Analysis Edit Modal */}
      <AnalysisEditModal
        open={analysisEditModalOpen}
        onClose={() => setAnalysisEditModalOpen(false)}
        initialText={editingAnalysisText}
        mediaId={selectedMedia?.id}
        content={content}
        prompt={derivedPrompt}
        onSendToChat={onSendAnalysisToChat}
        onSaveNewVersion={() => {
          if (onRefreshMedia) {
            onRefreshMedia()
          }
        }}
      />

      {/* Content Edit Modal */}
      {selectedMedia && !isNote && (
        <Suspense fallback={null}>
          <ContentEditModal
            open={contentEditModalOpen}
            onClose={() => setContentEditModalOpen(false)}
            initialText={editingContentText || content}
            mediaId={selectedMedia.id}
            analysisContent={derivedAnalysisContent}
            prompt={derivedPrompt}
            onSaveNewVersion={() => {
              if (onRefreshMedia) {
                onRefreshMedia()
              }
            }}
          />
        </Suspense>
      )}

      {/* Diff View Modal */}
      <DiffViewModal
        open={diffModalOpen}
        onClose={() => {
          setDiffModalOpen(false)
          setDiffMetadataSummary(null)
        }}
        leftText={diffLeftText}
        rightText={diffRightText}
        leftLabel={diffLeftLabel}
        rightLabel={diffRightLabel}
        metadataDiff={diffMetadataSummary || undefined}
      />
    </div>
  )
}

function formatDuration(seconds: number | null | undefined): string | null {
  if (seconds == null || !Number.isFinite(Number(seconds))) return null
  const total = Math.max(0, Math.floor(Number(seconds)))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
  }
  return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}
