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
  UploadCloud,
  User,
  Download
} from 'lucide-react'
import React, { useState, useEffect, Suspense, useMemo, useRef, useCallback } from 'react'
import { Select, Dropdown, Tooltip, message, Spin, Modal } from 'antd'
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
import { downloadBlob } from '@/utils/download-blob'
import {
  MEDIA_COLLAPSED_SECTIONS_SETTING,
  MEDIA_HIDE_TRANSCRIPT_TIMINGS_SETTING,
  MEDIA_TEXT_SIZE_PRESET_SETTING,
  type MediaTextSizePreset
} from '@/services/settings/ui-settings'
import { estimateReadingTimeMinutes } from './mediaMetadataUtils'
import {
  hasLeadingTranscriptTimings,
  parseLeadingTranscriptTiming,
  stripLeadingTranscriptTimings
} from '@/utils/media-transcript-display'

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

export const LARGE_PLAIN_CONTENT_THRESHOLD_CHARS = 120_000
export const LARGE_PLAIN_CONTENT_CHUNK_CHARS = 32_000
const LARGE_PLAIN_CONTENT_PREFETCH_MARGIN_PX = 640

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

type DocumentIntelligenceTab =
  | 'outline'
  | 'insights'
  | 'references'
  | 'figures'
  | 'annotations'

type MediaExportFormat = 'json' | 'markdown' | 'text' | 'bibtex'
type MediaAnnotationColor = 'yellow' | 'green' | 'blue' | 'pink'
type ReingestSchedulePreset = 'hourly' | 'daily' | 'weekly'

interface MediaAnnotationEntry {
  id: string
  media_id: number
  location: string
  text: string
  color: MediaAnnotationColor
  note?: string
  annotation_type: 'highlight' | 'page_note'
  created_at?: string
  updated_at?: string
}

interface DocumentIntelligencePanelState<T = any> {
  loading: boolean
  error: string | null
  data: T[]
}

type DocumentIntelligencePanelsState = Record<
  DocumentIntelligenceTab,
  DocumentIntelligencePanelState
>

const DOCUMENT_INTELLIGENCE_TABS: Array<{
  key: DocumentIntelligenceTab
  label: string
}> = [
  { key: 'outline', label: 'Outline' },
  { key: 'insights', label: 'Insights' },
  { key: 'references', label: 'References' },
  { key: 'figures', label: 'Figures' },
  { key: 'annotations', label: 'Annotations' }
]

const ANNOTATION_COLOR_OPTIONS: Array<{
  value: MediaAnnotationColor
  label: string
}> = [
  { value: 'yellow', label: 'Yellow' },
  { value: 'green', label: 'Green' },
  { value: 'blue', label: 'Blue' },
  { value: 'pink', label: 'Pink' }
]

const REINGEST_CRON_BY_PRESET: Record<ReingestSchedulePreset, string> = {
  hourly: '0 * * * *',
  daily: '0 9 * * *',
  weekly: '0 9 * * MON'
}

const createDefaultDocumentIntelligencePanels =
  (): DocumentIntelligencePanelsState => ({
    outline: { loading: false, error: null, data: [] },
    insights: { loading: false, error: null, data: [] },
    references: { loading: false, error: null, data: [] },
    figures: { loading: false, error: null, data: [] },
    annotations: { loading: false, error: null, data: [] }
  })

const createLoadingDocumentIntelligencePanels =
  (): DocumentIntelligencePanelsState => ({
    outline: { loading: true, error: null, data: [] },
    insights: { loading: true, error: null, data: [] },
    references: { loading: true, error: null, data: [] },
    figures: { loading: true, error: null, data: [] },
    annotations: { loading: true, error: null, data: [] }
  })

const getErrorStatusCode = (error: unknown): number | null => {
  if (!error || typeof error !== 'object') return null
  const candidate = (error as any).status ?? (error as any).statusCode
  return typeof candidate === 'number' && Number.isFinite(candidate)
    ? candidate
    : null
}

const toExportFileStem = (selectedMedia: MediaResultItem): string => {
  const fromTitle = String(selectedMedia.title || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
  const safeTitle = fromTitle.length > 0 ? fromTitle : `media-${selectedMedia.id}`
  return `${safeTitle}-${selectedMedia.id}`
}

const toDisplayMetadataLabel = (key: string): string => {
  if (SAFE_METADATA_LABELS[key]) return SAFE_METADATA_LABELS[key]
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (match) => match.toUpperCase())
}

const sanitizeBibtexValue = (value: string): string =>
  value
    .replace(/\\/g, '\\\\')
    .replace(/[{}]/g, '')
    .replace(/\s+/g, ' ')
    .trim()

const toCitationFieldString = (value: unknown): string => {
  if (value == null) return ''
  if (typeof value === 'string') return value.trim()
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  if (Array.isArray(value)) {
    return value
      .flatMap((entry) => {
        if (typeof entry === 'string') return [entry.trim()]
        if (entry && typeof entry === 'object' && 'name' in entry) {
          const name = (entry as { name?: unknown }).name
          return typeof name === 'string' ? [name.trim()] : []
        }
        return []
      })
      .filter(Boolean)
      .join(' and ')
  }
  return ''
}

const toCitationKey = (
  selectedMedia: MediaResultItem,
  safeMetadata: Record<string, unknown>
): string => {
  const doi = toCitationFieldString(safeMetadata.doi)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
  if (doi.length > 0) return doi

  const titleSlug = String(selectedMedia.title || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
  if (titleSlug.length > 0) {
    const year = toCitationFieldString(
      safeMetadata.year ?? safeMetadata.publication_year ?? safeMetadata.published_year
    )
      .replace(/[^\d]/g, '')
      .slice(0, 4)
    return `${titleSlug}${year ? `_${year}` : ''}`
  }

  return `media_${String(selectedMedia.id).replace(/[^a-z0-9]+/gi, '_')}`
}

const buildBibtexExport = (
  selectedMedia: MediaResultItem,
  exportPayload: {
    title: string
    source: string
    exported_at: string
  },
  safeMetadata: Record<string, unknown>
): string => {
  const entryType = 'article'
  const entryKey = toCitationKey(selectedMedia, safeMetadata)
  const yearField = toCitationFieldString(
    safeMetadata.year ??
      safeMetadata.publication_year ??
      safeMetadata.published_year ??
      safeMetadata.published_at
  )
    .replace(/[^\d]/g, '')
    .slice(0, 4)
  const rawFieldTuples: Array<[string, string]> = [
    ['title', exportPayload.title || `Media ${selectedMedia.id}`],
    ['author', toCitationFieldString(safeMetadata.authors ?? safeMetadata.author)],
    ['journal', toCitationFieldString(safeMetadata.journal)],
    ['year', yearField],
    ['doi', toCitationFieldString(safeMetadata.doi)],
    ['url', toCitationFieldString(safeMetadata.url) || exportPayload.source],
    ['pmid', toCitationFieldString(safeMetadata.pmid)],
    ['eprint', toCitationFieldString(safeMetadata.arxiv_id ?? safeMetadata.arxiv)]
  ]
  const fieldTuples = rawFieldTuples.filter(([, value]) => value.trim().length > 0)

  const body = fieldTuples
    .map(([field, value], index) => {
      const suffix = index === fieldTuples.length - 1 ? '' : ','
      return `  ${field} = {${sanitizeBibtexValue(value)}}${suffix}`
    })
    .join('\n')

  return [`@${entryType}{${entryKey},`, body, '}'].join('\n')
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

const normalizeFindQuery = (value: string): string => value.trim().toLowerCase()

export const findInContentOffsets = (text: string, query: string): number[] => {
  if (!text) return []
  const normalizedQuery = normalizeFindQuery(query)
  if (!normalizedQuery) return []

  const haystack = text.toLowerCase()
  const offsets: number[] = []
  let fromIndex = 0

  while (fromIndex < haystack.length) {
    const index = haystack.indexOf(normalizedQuery, fromIndex)
    if (index === -1) break
    offsets.push(index)
    fromIndex = index + Math.max(1, normalizedQuery.length)
  }

  return offsets
}

export const getNextFindMatchIndex = (
  currentIndex: number,
  totalMatches: number,
  direction: 1 | -1
): number => {
  if (!Number.isFinite(totalMatches) || totalMatches <= 0) return -1
  if (!Number.isFinite(currentIndex) || currentIndex < 0 || currentIndex >= totalMatches) {
    return direction === -1 ? totalMatches - 1 : 0
  }
  if (direction === 1) {
    return (currentIndex + 1) % totalMatches
  }
  return (currentIndex - 1 + totalMatches) % totalMatches
}

const LARGE_PLAIN_TEXT_THRESHOLD_CHARS = 200_000
const LARGE_PLAIN_TEXT_CHUNK_SIZE = 16_000
const LARGE_PLAIN_TEXT_INITIAL_CHUNKS = 3
const LARGE_PLAIN_TEXT_INCREMENT_CHUNKS = 2
const LARGE_PLAIN_TEXT_SCROLL_PREFETCH_PX = 480

export const splitLargePlainTextChunks = (
  text: string,
  targetChunkSize: number = LARGE_PLAIN_TEXT_CHUNK_SIZE
): string[] => {
  if (!text) return []
  if (!Number.isFinite(targetChunkSize) || targetChunkSize <= 0) {
    return [text]
  }

  const chunks: string[] = []
  let start = 0
  while (start < text.length) {
    let end = Math.min(text.length, start + targetChunkSize)
    if (end < text.length) {
      const newlineIndex = text.lastIndexOf('\n', end)
      if (newlineIndex > start + Math.floor(targetChunkSize / 3)) {
        end = newlineIndex + 1
      }
    }
    chunks.push(text.slice(start, end))
    start = end
  }
  return chunks
}

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
  onGenerateFlashcardsFromContent?: (payload: {
    text: string
    sourceId?: string
    sourceTitle?: string
  }) => void
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
  onGenerateFlashcardsFromContent,
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
  const [hideTranscriptTimings, setHideTranscriptTimings] = useSetting(
    MEDIA_HIDE_TRANSCRIPT_TIMINGS_SETTING
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
  const [exportModalOpen, setExportModalOpen] = useState(false)
  const [exportFormat, setExportFormat] = useState<MediaExportFormat>('json')
  const [scheduleRefreshModalOpen, setScheduleRefreshModalOpen] = useState(false)
  const [scheduleRefreshPreset, setScheduleRefreshPreset] =
    useState<ReingestSchedulePreset>('daily')
  const [scheduleRefreshSubmitting, setScheduleRefreshSubmitting] = useState(false)
  const [metadataDetailsExpanded, setMetadataDetailsExpanded] = useState(false)
  const [activeIntelligenceTab, setActiveIntelligenceTab] =
    useState<DocumentIntelligenceTab>('outline')
  const [documentIntelligencePanels, setDocumentIntelligencePanels] =
    useState<DocumentIntelligencePanelsState>(() =>
      createDefaultDocumentIntelligencePanels()
    )
  const [loadedDocumentIntelligenceMediaId, setLoadedDocumentIntelligenceMediaId] =
    useState<string | null>(null)
  const [annotationSelectionText, setAnnotationSelectionText] = useState('')
  const [annotationSelectionLocation, setAnnotationSelectionLocation] = useState('')
  const [annotationManualText, setAnnotationManualText] = useState('')
  const [annotationDraftNote, setAnnotationDraftNote] = useState('')
  const [annotationDraftColor, setAnnotationDraftColor] =
    useState<MediaAnnotationColor>('yellow')
  const [annotationCreating, setAnnotationCreating] = useState(false)
  const [annotationUpdatingId, setAnnotationUpdatingId] = useState<string | null>(null)
  const [annotationDeletingId, setAnnotationDeletingId] = useState<string | null>(null)
  const [annotationSyncing, setAnnotationSyncing] = useState(false)
  const [showBackToTop, setShowBackToTop] = useState(false)
  const [visiblePlainContentChars, setVisiblePlainContentChars] = useState(
    () => content.length
  )
  const [embeddedMediaUrl, setEmbeddedMediaUrl] = useState<string | null>(null)
  const [embeddedMediaLoading, setEmbeddedMediaLoading] = useState(false)
  const [embeddedMediaError, setEmbeddedMediaError] = useState<string | null>(null)
  const [deletingItem, setDeletingItem] = useState(false)
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null)
  const [findBarOpen, setFindBarOpen] = useState(false)
  const [findQuery, setFindQuery] = useState('')
  const [findMatchOffsets, setFindMatchOffsets] = useState<number[]>([])
  const [activeFindMatchIndex, setActiveFindMatchIndex] = useState(-1)
  const [contentSelectionAnnouncement, setContentSelectionAnnouncement] = useState('')
  const lastSanitizationTelemetryKeyRef = useRef<string>('')
  const lastAppliedNavigationTargetKeyRef = useRef<string>('')
  const lastAppliedNavigationTitleKeyRef = useRef<string>('')
  const lastAppliedNavigationPageKeyRef = useRef<string>('')
  const lastContentSelectionAnnouncementKeyRef = useRef<string>('')
  const titleRetryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pageRetryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const rootContainerRef = useRef<HTMLDivElement | null>(null)
  const findInputRef = useRef<HTMLInputElement | null>(null)
  const findMatchElementRefs = useRef<Array<HTMLElement | null>>([])
  const contentBodyRef = useRef<HTMLDivElement | null>(null)
  const contentScrollContainerRef = useRef<HTMLDivElement | null>(null)
  const mediaPlayerRef = useRef<HTMLMediaElement | null>(null)
  const embeddedMediaObjectUrlRef = useRef<string | null>(null)

  const setRootContainerRef = useCallback(
    (node: HTMLDivElement | null) => {
      rootContainerRef.current = node
      if (contentRef) {
        contentRef(node)
      }
    },
    [contentRef]
  )

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
  const selectedMediaAnnouncementLabel = useMemo(() => {
    if (!selectedMedia) return ''
    const title = String(selectedMedia.title || '').trim()
    if (title) return title
    const kind = String(selectedMedia.kind || 'media').trim() || 'media'
    return `${kind} ${selectedMedia.id}`
  }, [selectedMedia])
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
  const shouldHideTranscriptTimings = hideTranscriptTimings ?? true
  const displayContent = useMemo(
    () =>
      shouldHideTranscriptTimings
        ? stripLeadingTranscriptTimings(content)
        : content,
    [content, shouldHideTranscriptTimings]
  )

  const mediaReadingProgress = useMediaReadingProgress({
    mediaId: selectedMedia?.id ?? null,
    mediaKind: selectedMedia?.kind ?? null,
    mediaDetail,
    contentLength: content.length,
    scrollContainerRef: contentScrollContainerRef,
    hasNavigationTarget: Boolean(navigationTarget)
  })
  const progressPercent = mediaReadingProgress?.progressPercent

  useEffect(() => {
    if (!selectedMediaId || !selectedMediaAnnouncementLabel) {
      lastContentSelectionAnnouncementKeyRef.current = ''
      setContentSelectionAnnouncement('')
      return
    }

    const stateLabel = isDetailLoading ? 'loading' : 'ready'
    const announcementKey = `${selectedMediaId}:${stateLabel}`
    if (lastContentSelectionAnnouncementKeyRef.current === announcementKey) return

    lastContentSelectionAnnouncementKeyRef.current = announcementKey
    const statusPrefix = isDetailLoading
      ? t('review:mediaPage.contentAnnouncementLoading', { defaultValue: 'Loading' })
      : t('review:mediaPage.contentAnnouncementShowing', { defaultValue: 'Showing' })
    setContentSelectionAnnouncement(`${statusPrefix} ${selectedMediaAnnouncementLabel}`)
  }, [isDetailLoading, selectedMediaAnnouncementLabel, selectedMediaId, t])

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
  const shouldShowExpandToggle =
    displayContent && displayContent.length > CONTENT_COLLAPSE_THRESHOLD
  const contentForPreview = useMemo(() => {
    if (!displayContent) return ''
    if (selectedMedia?.kind === 'note') return displayContent
    const normalized = displayContent.replace(/\r\n/g, '\n')
    if (!shouldForceHardBreaks(normalized, selectedMedia?.meta?.type)) {
      return normalized
    }
    return normalized.replace(/\n/g, '  \n')
  }, [displayContent, selectedMedia?.kind, selectedMedia?.meta?.type])
  const effectiveRenderMode = useMemo(
    () =>
      resolveMediaRenderMode({
        requestedMode: contentDisplayMode,
        resolvedContentFormat,
        allowRichRendering
      }),
    [allowRichRendering, contentDisplayMode, resolvedContentFormat]
  )
  const normalizedFindQuery = useMemo(() => normalizeFindQuery(findQuery), [findQuery])
  const transcriptLines = useMemo(
    () => (content ? content.replace(/\r\n/g, '\n').split('\n') : []),
    [content]
  )
  const hasTranscriptTimingLines = useMemo(
    () => hasLeadingTranscriptTimings(content),
    [content]
  )
  const hasClickableTranscriptTimestamps = useMemo(
    () => shouldShowEmbeddedPlayer && hasTranscriptTimingLines,
    [hasTranscriptTimingLines, shouldShowEmbeddedPlayer]
  )
  const shouldRenderTranscriptTimestampChips =
    hasClickableTranscriptTimestamps &&
    !shouldHideTranscriptTimings &&
    !normalizedFindQuery
  const shouldUseChunkedPlainRendering = useMemo(
    () =>
      effectiveRenderMode === 'plain' &&
      !shouldRenderTranscriptTimestampChips &&
      !normalizedFindQuery &&
      displayContent.length > LARGE_PLAIN_CONTENT_THRESHOLD_CHARS,
    [
      displayContent.length,
      effectiveRenderMode,
      normalizedFindQuery,
      shouldRenderTranscriptTimestampChips
    ]
  )
  const visiblePlainContent = useMemo(() => {
    if (!displayContent) return ''
    if (!shouldUseChunkedPlainRendering) return displayContent
    return displayContent.slice(
      0,
      Math.max(0, Math.min(displayContent.length, visiblePlainContentChars))
    )
  }, [displayContent, shouldUseChunkedPlainRendering, visiblePlainContentChars])
  const hasUnrenderedPlainContent =
    shouldUseChunkedPlainRendering && visiblePlainContentChars < displayContent.length
  const loadMorePlainContent = useCallback(() => {
    if (!shouldUseChunkedPlainRendering) return
    setVisiblePlainContentChars((prev) =>
      Math.min(
        displayContent.length,
        Math.max(0, prev) + LARGE_PLAIN_CONTENT_CHUNK_CHARS
      )
    )
  }, [displayContent.length, shouldUseChunkedPlainRendering])
  const findMatchCount = findMatchOffsets.length

  const moveFindMatch = useCallback(
    (direction: 1 | -1) => {
      setActiveFindMatchIndex((prev) =>
        getNextFindMatchIndex(prev, findMatchOffsets.length, direction)
      )
    },
    [findMatchOffsets.length]
  )

  const closeFindBar = useCallback(() => {
    setFindBarOpen(false)
    setFindQuery('')
    setFindMatchOffsets([])
    setActiveFindMatchIndex(-1)
    findMatchElementRefs.current = []
  }, [])

  const highlightedPlainContent = useMemo<React.ReactNode>(() => {
    findMatchElementRefs.current = []
    if (!displayContent) {
      return t('review:mediaPage.noContent', {
        defaultValue: 'No content available'
      })
    }
    if (!normalizedFindQuery || findMatchOffsets.length === 0) {
      return shouldUseChunkedPlainRendering ? visiblePlainContent : displayContent
    }

    const parts: React.ReactNode[] = []
    const queryLength = normalizedFindQuery.length
    let cursor = 0

    findMatchOffsets.forEach((start, index) => {
      if (start < cursor) return
      if (start > cursor) {
        parts.push(displayContent.slice(cursor, start))
      }
      const end = Math.min(displayContent.length, start + queryLength)
      const isActive = index === activeFindMatchIndex
      parts.push(
        <mark
          key={`find-match-${index}-${start}`}
          ref={(node) => {
            findMatchElementRefs.current[index] = node
          }}
          data-find-match-index={index}
          className={
            isActive
              ? 'rounded bg-primary/30 text-text px-0.5'
              : 'rounded bg-warn/20 text-text px-0.5'
          }
        >
          {displayContent.slice(start, end)}
        </mark>
      )
      cursor = end
    })

    if (cursor < displayContent.length) {
      parts.push(displayContent.slice(cursor))
    }

    return <>{parts}</>
  }, [
    activeFindMatchIndex,
    displayContent,
    findMatchOffsets,
    normalizedFindQuery,
    shouldUseChunkedPlainRendering,
    t,
    visiblePlainContent
  ])

  useEffect(() => {
    if (!displayContent) {
      setVisiblePlainContentChars(0)
      return
    }
    if (!shouldUseChunkedPlainRendering) {
      setVisiblePlainContentChars(displayContent.length)
      return
    }
    setVisiblePlainContentChars(
      Math.min(displayContent.length, LARGE_PLAIN_CONTENT_CHUNK_CHARS)
    )
  }, [displayContent.length, selectedMedia?.id, shouldUseChunkedPlainRendering])

  useEffect(() => {
    if (!hasUnrenderedPlainContent) return
    const container = contentScrollContainerRef.current
    if (!container) return

    const maybeLoadMore = () => {
      if (container.clientHeight <= 0 || container.scrollHeight <= 0) {
        return
      }
      if (
        container.scrollTop + container.clientHeight <
        container.scrollHeight - LARGE_PLAIN_CONTENT_PREFETCH_MARGIN_PX
      ) {
        return
      }
      setVisiblePlainContentChars((prev) =>
        Math.min(
          displayContent.length,
          Math.max(0, prev) + LARGE_PLAIN_CONTENT_CHUNK_CHARS
        )
      )
    }

    if (
      visiblePlainContentChars === LARGE_PLAIN_CONTENT_CHUNK_CHARS &&
      container.scrollTop > 0
    ) {
      maybeLoadMore()
    }
    container.addEventListener('scroll', maybeLoadMore, { passive: true })
    return () => {
      container.removeEventListener('scroll', maybeLoadMore)
    }
  }, [displayContent.length, hasUnrenderedPlainContent, visiblePlainContentChars])

  useEffect(() => {
    const offsets = findInContentOffsets(displayContent, findQuery)
    setFindMatchOffsets(offsets)
    setActiveFindMatchIndex(offsets.length > 0 ? 0 : -1)
  }, [displayContent, findQuery])

  useEffect(() => {
    setFindBarOpen(false)
    setFindQuery('')
    setFindMatchOffsets([])
    setActiveFindMatchIndex(-1)
    findMatchElementRefs.current = []
  }, [selectedMedia?.id])

  useEffect(() => {
    if (!findBarOpen) return
    const timer = window.setTimeout(() => {
      findInputRef.current?.focus()
      findInputRef.current?.select()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [findBarOpen])

  useEffect(() => {
    if (activeFindMatchIndex < 0 || findMatchOffsets.length === 0) return

    const activeNode = findMatchElementRefs.current[activeFindMatchIndex]
    if (activeNode && typeof activeNode.scrollIntoView === 'function') {
      activeNode.scrollIntoView({ behavior: 'smooth', block: 'center' })
      return
    }

    const container = contentScrollContainerRef.current
    const offset = findMatchOffsets[activeFindMatchIndex]
    if (container && Number.isFinite(offset) && displayContent.length > 0) {
      scrollToCharOffset(container, offset, displayContent.length)
    }
  }, [activeFindMatchIndex, displayContent.length, findMatchOffsets])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey)) return
      if (event.key.toLowerCase() !== 'f') return

      const target = event.target as HTMLElement | null
      const isTypingTarget =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        Boolean(target?.isContentEditable)
      if (isTypingTarget) return

      const root = rootContainerRef.current
      if (
        root &&
        target &&
        target !== document.body &&
        !root.contains(target)
      ) {
        return
      }

      event.preventDefault()
      setFindBarOpen(true)
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  const richSanitization = useMemo(() => {
    if (effectiveRenderMode !== 'html' || !displayContent) {
      return {
        html: '',
        removed_node_count: 0,
        removed_attribute_count: 0,
        blocked_url_schemes: [] as string[]
      }
    }
    return sanitizeMediaRichHtmlWithStats(displayContent)
  }, [displayContent, effectiveRenderMode])
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
    if (!displayContent) return
    copyTextWithToasts(
      displayContent,
      'mediaPage.contentCopied',
      'Content copied'
    )
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

  const handleExportMedia = () => {
    if (isNote || !selectedMedia) return
    setExportModalOpen(true)
  }

  const confirmExportMedia = () => {
    if (isNote || !selectedMedia) return

    const citationSafeMetadata =
      mediaDetail?.safe_metadata &&
      typeof mediaDetail.safe_metadata === 'object' &&
      !Array.isArray(mediaDetail.safe_metadata)
        ? (mediaDetail.safe_metadata as Record<string, unknown>)
        : selectedMedia?.raw?.safe_metadata &&
            typeof selectedMedia.raw.safe_metadata === 'object' &&
            !Array.isArray(selectedMedia.raw.safe_metadata)
          ? (selectedMedia.raw.safe_metadata as Record<string, unknown>)
          : {}

    const exportPayload = {
      id: selectedMedia.id,
      title: selectedMedia.title || '',
      type: selectedMedia.meta?.type || '',
      source: selectedMedia.meta?.source || '',
      keywords: editingKeywords,
      content,
      analysis: selectedAnalysis?.text || '',
      exported_at: new Date().toISOString()
    }

    let output = ''
    let extension = 'txt'
    let mimeType = 'text/plain;charset=utf-8'

    if (exportFormat === 'json') {
      output = JSON.stringify(exportPayload, null, 2)
      extension = 'json'
      mimeType = 'application/json;charset=utf-8'
    } else if (exportFormat === 'bibtex') {
      output = buildBibtexExport(selectedMedia, exportPayload, citationSafeMetadata)
      extension = 'bib'
      mimeType = 'application/x-bibtex;charset=utf-8'
    } else if (exportFormat === 'markdown') {
      output = [
        `# ${exportPayload.title || `Media ${exportPayload.id}`}`,
        '',
        `- ID: ${exportPayload.id}`,
        `- Type: ${exportPayload.type || 'N/A'}`,
        `- Source: ${exportPayload.source || 'N/A'}`,
        `- Keywords: ${
          Array.isArray(exportPayload.keywords) && exportPayload.keywords.length > 0
            ? exportPayload.keywords.join(', ')
            : 'None'
        }`,
        `- Exported At: ${exportPayload.exported_at}`,
        '',
        '## Content',
        '',
        exportPayload.content || '',
        '',
        '## Analysis',
        '',
        exportPayload.analysis || ''
      ].join('\n')
      extension = 'md'
      mimeType = 'text/markdown;charset=utf-8'
    } else {
      output = [
        `Title: ${exportPayload.title || `Media ${exportPayload.id}`}`,
        `ID: ${exportPayload.id}`,
        `Type: ${exportPayload.type || 'N/A'}`,
        `Source: ${exportPayload.source || 'N/A'}`,
        `Keywords: ${
          Array.isArray(exportPayload.keywords) && exportPayload.keywords.length > 0
            ? exportPayload.keywords.join(', ')
            : 'None'
        }`,
        `Exported At: ${exportPayload.exported_at}`,
        '',
        'Content:',
        exportPayload.content || '',
        '',
        'Analysis:',
        exportPayload.analysis || ''
      ].join('\n')
      extension = 'txt'
      mimeType = 'text/plain;charset=utf-8'
    }

    try {
      const blob = new Blob([output], { type: mimeType })
      downloadBlob(blob, `${toExportFileStem(selectedMedia)}.${extension}`)
      message.success(
        t('review:mediaPage.exportSuccess', {
          defaultValue: 'Export ready.'
        })
      )
      setExportModalOpen(false)
    } catch (error) {
      console.error('Failed to export media:', error)
      message.error(
        t('review:mediaPage.exportFailed', {
          defaultValue: 'Unable to export this item.'
        })
      )
    }
  }

  const handleReprocessMedia = async () => {
    if (isNote || !selectedMediaId) return

    try {
      await bgRequest({
        path: `/api/v1/media/${selectedMediaId}/reprocess` as any,
        method: 'POST' as any,
        headers: { 'Content-Type': 'application/json' },
        body: {
          perform_chunking: true,
          generate_embeddings: true,
          force_regenerate_embeddings: true
        }
      })
      message.success(
        t('review:mediaPage.reprocessQueued', {
          defaultValue: 'Reprocessing started.'
        })
      )
      if (onRefreshMedia) {
        onRefreshMedia()
      }
    } catch (error) {
      console.error('Failed to start reprocess:', error)
      message.error(
        t('review:mediaPage.reprocessFailed', {
          defaultValue:
            'Unable to start reprocessing. Please try again.'
        })
      )
    }
  }

  const sourceUrlForScheduling = useMemo(() => {
    const candidate = firstNonEmptyString(
      selectedMedia?.raw?.url,
      mediaDetail?.url,
      mediaDetail?.source_url,
      mediaDetail?.sourceUrl
    )
    if (!candidate) return ''
    try {
      const parsed = new URL(candidate)
      if (!['http:', 'https:'].includes(parsed.protocol)) return ''
      return candidate
    } catch {
      return ''
    }
  }, [
    mediaDetail?.sourceUrl,
    mediaDetail?.source_url,
    mediaDetail?.url,
    selectedMedia?.raw?.url
  ])

  const handleScheduleSourceRefresh = useCallback(async () => {
    if (!selectedMedia || selectedMedia.kind === 'note' || !sourceUrlForScheduling) return
    const sourceName =
      selectedMedia.title?.trim() ||
      t('review:mediaPage.untitled', { defaultValue: 'Untitled' })
    const scheduleExpr = REINGEST_CRON_BY_PRESET[scheduleRefreshPreset]
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'

    setScheduleRefreshSubmitting(true)
    try {
      const createdSource = await bgRequest<{ id?: number | string }>({
        path: '/api/v1/watchlists/sources' as any,
        method: 'POST' as any,
        body: {
          name: sourceName,
          url: sourceUrlForScheduling,
          source_type: 'site',
          active: true,
          tags: ['media-refresh']
        }
      })
      const sourceId = Number(createdSource?.id)
      if (!Number.isFinite(sourceId) || sourceId <= 0) {
        throw new Error('Invalid watchlist source id')
      }

      await bgRequest({
        path: '/api/v1/watchlists/jobs' as any,
        method: 'POST' as any,
        body: {
          name: `Refresh: ${sourceName}`,
          description: `Scheduled source refresh for media ${selectedMedia.id}`,
          scope: { sources: [sourceId] },
          schedule_expr: scheduleExpr,
          timezone,
          active: true,
          output_prefs: {
            ingest: {
              persist_to_media_db: true
            }
          }
        }
      })
      message.success(
        t('review:mediaPage.scheduleRefreshSuccess', {
          defaultValue: 'Scheduled source refresh monitor.'
        })
      )
      setScheduleRefreshModalOpen(false)
    } catch (error) {
      console.error('Failed to schedule source refresh:', error)
      message.error(
        t('review:mediaPage.scheduleRefreshFailed', {
          defaultValue: 'Unable to schedule source refresh.'
        })
      )
    } finally {
      setScheduleRefreshSubmitting(false)
    }
  }, [scheduleRefreshPreset, selectedMedia, sourceUrlForScheduling, t])

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
  const canScheduleSourceRefresh = !isNote && sourceUrlForScheduling.length > 0
  const intelligenceSectionCollapsed = collapsedSections.intelligence ?? true
  const chatWithLabel = t('review:reviewPage.chatWithMedia', {
    defaultValue: 'Chat with this media'
  })
  const chatWithClarifiedLabel = t('review:reviewPage.chatWithMediaClarified', {
    defaultValue: 'Chat with this media (full content)'
  })
  const chatAboutClarifiedLabel = t('review:reviewPage.chatAboutMediaClarified', {
    defaultValue: 'Chat about this media (RAG context)'
  })

  const fetchDocumentIntelligence = useCallback(async () => {
    if (!selectedMediaId || isNote) return
    const encodedMediaId = encodeURIComponent(selectedMediaId)
    setDocumentIntelligencePanels(createLoadingDocumentIntelligencePanels())

    const results = await Promise.allSettled([
      bgRequest<any>({
        path: `/api/v1/media/${encodedMediaId}/outline` as any,
        method: 'GET' as any
      }),
      bgRequest<any>({
        path: `/api/v1/media/${encodedMediaId}/insights` as any,
        method: 'POST' as any,
        body: {}
      }),
      bgRequest<any>({
        path: `/api/v1/media/${encodedMediaId}/references?enrich=true&limit=25` as any,
        method: 'GET' as any
      }),
      bgRequest<any>({
        path: `/api/v1/media/${encodedMediaId}/figures?min_size=50` as any,
        method: 'GET' as any
      }),
      bgRequest<any>({
        path: `/api/v1/media/${encodedMediaId}/annotations` as any,
        method: 'GET' as any
      })
    ])

    const nextPanels = createDefaultDocumentIntelligencePanels()
    const assignError = (tab: DocumentIntelligenceTab, error: unknown) => {
      const statusCode = getErrorStatusCode(error)
      if (statusCode === 404 || statusCode === 410 || statusCode === 422) {
        nextPanels[tab] = { loading: false, error: null, data: [] }
        return
      }
      nextPanels[tab] = {
        loading: false,
        error: t('review:mediaPage.intelligenceLoadError', {
          defaultValue: 'Unable to load this panel. Try again.'
        }),
        data: []
      }
    }

    const [
      outlineResult,
      insightsResult,
      referencesResult,
      figuresResult,
      annotationsResult
    ] = results

    if (outlineResult.status === 'fulfilled') {
      nextPanels.outline = {
        loading: false,
        error: null,
        data: Array.isArray(outlineResult.value?.entries)
          ? outlineResult.value.entries
          : []
      }
    } else {
      assignError('outline', outlineResult.reason)
    }

    if (insightsResult.status === 'fulfilled') {
      nextPanels.insights = {
        loading: false,
        error: null,
        data: Array.isArray(insightsResult.value?.insights)
          ? insightsResult.value.insights
          : []
      }
    } else {
      assignError('insights', insightsResult.reason)
    }

    if (referencesResult.status === 'fulfilled') {
      nextPanels.references = {
        loading: false,
        error: null,
        data: Array.isArray(referencesResult.value?.references)
          ? referencesResult.value.references
          : []
      }
    } else {
      assignError('references', referencesResult.reason)
    }

    if (figuresResult.status === 'fulfilled') {
      nextPanels.figures = {
        loading: false,
        error: null,
        data: Array.isArray(figuresResult.value?.figures)
          ? figuresResult.value.figures
          : []
      }
    } else {
      assignError('figures', figuresResult.reason)
    }

    if (annotationsResult.status === 'fulfilled') {
      nextPanels.annotations = {
        loading: false,
        error: null,
        data: Array.isArray(annotationsResult.value?.annotations)
          ? annotationsResult.value.annotations
          : []
      }
    } else {
      assignError('annotations', annotationsResult.reason)
    }

    setDocumentIntelligencePanels(nextPanels)
    setLoadedDocumentIntelligenceMediaId(selectedMediaId)
  }, [isNote, selectedMediaId, t])
  const fetchDocumentIntelligenceRef = useRef(fetchDocumentIntelligence)

  useEffect(() => {
    fetchDocumentIntelligenceRef.current = fetchDocumentIntelligence
  }, [fetchDocumentIntelligence])

  useEffect(() => {
    setActiveIntelligenceTab('outline')
    setDocumentIntelligencePanels(createDefaultDocumentIntelligencePanels())
    setLoadedDocumentIntelligenceMediaId(null)
    setAnnotationSelectionText('')
    setAnnotationSelectionLocation('')
    setAnnotationManualText('')
    setAnnotationDraftNote('')
    setAnnotationDraftColor('yellow')
  }, [selectedMediaId, selectedMedia?.kind])

  useEffect(() => {
    if (intelligenceSectionCollapsed) return
    if (!selectedMediaId || isNote) return
    if (loadedDocumentIntelligenceMediaId === selectedMediaId) return
    void fetchDocumentIntelligenceRef.current()
  }, [
    intelligenceSectionCollapsed,
    isNote,
    loadedDocumentIntelligenceMediaId,
    selectedMediaId
  ])

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
          label: chatWithClarifiedLabel,
          icon: <Send className="w-4 h-4" />,
          onClick: onChatWithMedia
        }] : []),
        ...(onChatAboutMedia ? [{
          key: 'chat-about',
          label: chatAboutClarifiedLabel,
          icon: <MessageSquare className="w-4 h-4" />,
          onClick: onChatAboutMedia
        }] : [])
      ]
    }] : []),
    // Create group: Note actions
    ...(!isNote && (onCreateNoteWithContent || onGenerateFlashcardsFromContent)
      ? [
      { type: 'divider' as const },
      {
        key: 'group-create',
        type: 'group' as const,
        label: t('review:mediaPage.menuGroupCreate', { defaultValue: 'Create' }),
        children: [
          ...(onCreateNoteWithContent
            ? [
                {
                  key: 'create-note-content',
                  label: t('review:mediaPage.createNoteWithContent', {
                    defaultValue: 'Create note with content'
                  }),
                  icon: <StickyNote className="w-4 h-4" />,
                  onClick: () => {
                    const title =
                      selectedMedia?.title ||
                      t('review:mediaPage.untitled', { defaultValue: 'Untitled' })
                    onCreateNoteWithContent(content, title)
                  }
                },
                ...(selectedAnalysis
                  ? [
                      {
                        key: 'create-note-content-analysis',
                        label: t('review:mediaPage.createNoteWithContentAnalysis', {
                          defaultValue: 'Create note with content + analysis'
                        }),
                        icon: <StickyNote className="w-4 h-4" />,
                        onClick: () => {
                          const title =
                            selectedMedia?.title ||
                            t('review:mediaPage.untitled', {
                              defaultValue: 'Untitled'
                            })
                          const noteContent = `${content}\n\n---\n\n## Analysis\n\n${selectedAnalysis.text}`
                          onCreateNoteWithContent(noteContent, title)
                        }
                      }
                    ]
                  : [])
              ]
            : []),
          ...(onGenerateFlashcardsFromContent && content.trim().length > 0
            ? [
                {
                  key: 'generate-flashcards-content',
                  label: t('review:mediaPage.generateFlashcardsFromContent', {
                    defaultValue: 'Generate flashcards from content'
                  }),
                  icon: <Sparkles className="w-4 h-4" />,
                  onClick: () =>
                    onGenerateFlashcardsFromContent({
                      text: content,
                      sourceId:
                        selectedMedia?.id != null ? String(selectedMedia.id) : undefined,
                      sourceTitle: selectedMedia?.title
                    })
                }
              ]
            : [])
        ]
      }
    ]
      : []),
    // Copy group
    ...(!isNote &&
    (onChatWithMedia ||
      onChatAboutMedia ||
      onCreateNoteWithContent ||
      onGenerateFlashcardsFromContent)
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
    ...(!isNote ? [
      { type: 'divider' as const },
      {
        key: 'export-media',
        label: t('review:mediaPage.exportMedia', {
          defaultValue: 'Export content'
        }),
        icon: <Download className="w-4 h-4" />,
        onClick: handleExportMedia
      },
      {
        key: 'reprocess-media',
        label: t('review:mediaPage.reprocessMedia', {
          defaultValue: 'Reprocess content'
        }),
        icon: <UploadCloud className="w-4 h-4" />,
        onClick: () => {
          void handleReprocessMedia()
        }
      },
      ...(canScheduleSourceRefresh
        ? [
            {
              key: 'schedule-refresh',
              label: t('review:mediaPage.scheduleSourceRefresh', {
                defaultValue: 'Schedule source refresh'
              }),
              icon: <Clock className="w-4 h-4" />,
              onClick: () => setScheduleRefreshModalOpen(true)
            }
          ]
        : []),
      ...(onOpenInMultiReview
        ? [
            {
              key: 'open-multi-review',
              label: t('review:reviewPage.openInMulti', 'Open in Multi-Item Review'),
              icon: <ExternalLink className="w-4 h-4" />,
              onClick: onOpenInMultiReview
            }
          ]
        : [])
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
  const activeDocumentIntelligencePanel =
    documentIntelligencePanels[activeIntelligenceTab]
  const annotationPanelEntries = useMemo(
    () =>
      Array.isArray(documentIntelligencePanels.annotations.data)
        ? (documentIntelligencePanels.annotations.data as MediaAnnotationEntry[])
        : [],
    [documentIntelligencePanels.annotations.data]
  )

  const setAnnotationPanelEntries = useCallback(
    (
      updater:
        | MediaAnnotationEntry[]
        | ((prev: MediaAnnotationEntry[]) => MediaAnnotationEntry[])
    ) => {
      setDocumentIntelligencePanels((prev) => {
        const previousRows = Array.isArray(prev.annotations.data)
          ? (prev.annotations.data as MediaAnnotationEntry[])
          : []
        const nextRows =
          typeof updater === 'function'
            ? (updater as (prev: MediaAnnotationEntry[]) => MediaAnnotationEntry[])(previousRows)
            : updater
        return {
          ...prev,
          annotations: {
            loading: false,
            error: null,
            data: nextRows
          }
        }
      })
    },
    []
  )

  const clearAnnotationDraft = useCallback(() => {
    setAnnotationSelectionText('')
    setAnnotationSelectionLocation('')
    setAnnotationManualText('')
    setAnnotationDraftNote('')
    setAnnotationDraftColor('yellow')
  }, [])

  const handleCaptureAnnotationSelection = useCallback(() => {
    if (!selectedMediaId || isNote) return
    if (typeof window === 'undefined' || typeof window.getSelection !== 'function') {
      return
    }

    const contentNode = contentBodyRef.current
    const selection = window.getSelection()
    if (!contentNode || !selection || selection.rangeCount === 0 || selection.isCollapsed) {
      return
    }

    const range = selection.getRangeAt(0)
    const anchorNode = range.commonAncestorContainer
    if (!contentNode.contains(anchorNode)) {
      return
    }

    const selectedText = selection.toString().trim()
    if (!selectedText) return

    setAnnotationSelectionText(selectedText.slice(0, 4000))
    setAnnotationSelectionLocation(`selection:${Date.now()}`)
    setActiveIntelligenceTab('annotations')
    if (collapsedSections.intelligence ?? true) {
      void setCollapsedSections((prev) => ({
        ...prev,
        intelligence: false
      }))
    }
  }, [collapsedSections.intelligence, isNote, selectedMediaId, setCollapsedSections])

  const handleCreateAnnotation = useCallback(async () => {
    if (!selectedMediaId || isNote) return

    const highlightText =
      annotationSelectionText.trim() || annotationManualText.trim()
    const noteText = annotationDraftNote.trim()
    if (!highlightText && !noteText) {
      message.warning(
        t('review:mediaPage.annotationCreateEmpty', {
          defaultValue: 'Select text or enter annotation text first.'
        })
      )
      return
    }

    const annotationType = highlightText ? 'highlight' : 'page_note'
    const annotationLocation =
      annotationSelectionLocation || `manual:${Date.now()}`

    setAnnotationCreating(true)
    try {
      const created = await bgRequest<MediaAnnotationEntry>({
        path: `/api/v1/media/${encodeURIComponent(selectedMediaId)}/annotations` as any,
        method: 'POST' as any,
        headers: { 'Content-Type': 'application/json' },
        body: {
          location: annotationLocation,
          text: highlightText || noteText,
          color: annotationDraftColor,
          note: noteText || undefined,
          annotation_type: annotationType
        }
      })
      setAnnotationPanelEntries((prev) => [...prev, created])
      setLoadedDocumentIntelligenceMediaId(selectedMediaId)
      clearAnnotationDraft()
      message.success(
        t('review:mediaPage.annotationSaved', {
          defaultValue: 'Annotation saved.'
        })
      )
    } catch (error) {
      console.error('Failed to create annotation:', error)
      message.error(
        t('review:mediaPage.annotationSaveFailed', {
          defaultValue: 'Unable to save annotation.'
        })
      )
    } finally {
      setAnnotationCreating(false)
    }
  }, [
    annotationDraftColor,
    annotationDraftNote,
    annotationManualText,
    annotationSelectionLocation,
    annotationSelectionText,
    clearAnnotationDraft,
    isNote,
    selectedMediaId,
    setAnnotationPanelEntries,
    t
  ])

  const handleUpdateAnnotationNote = useCallback(
    async (annotation: MediaAnnotationEntry) => {
      if (!selectedMediaId || isNote) return
      const nextNote = window.prompt(
        t('review:mediaPage.annotationEditPrompt', {
          defaultValue: 'Update annotation note'
        }),
        annotation.note || ''
      )
      if (nextNote == null) return

      setAnnotationUpdatingId(annotation.id)
      try {
        const updated = await bgRequest<MediaAnnotationEntry>({
          path: `/api/v1/media/${encodeURIComponent(selectedMediaId)}/annotations/${encodeURIComponent(annotation.id)}` as any,
          method: 'PUT' as any,
          headers: { 'Content-Type': 'application/json' },
          body: { note: nextNote }
        })
        setAnnotationPanelEntries((prev) =>
          prev.map((entry) => (entry.id === annotation.id ? updated : entry))
        )
      } catch (error) {
        console.error('Failed to update annotation:', error)
        message.error(
          t('review:mediaPage.annotationUpdateFailed', {
            defaultValue: 'Unable to update annotation.'
          })
        )
      } finally {
        setAnnotationUpdatingId(null)
      }
    },
    [isNote, selectedMediaId, setAnnotationPanelEntries, t]
  )

  const handleDeleteAnnotation = useCallback(
    async (annotationId: string) => {
      if (!selectedMediaId || isNote) return

      setAnnotationDeletingId(annotationId)
      try {
        await bgRequest({
          path: `/api/v1/media/${encodeURIComponent(selectedMediaId)}/annotations/${encodeURIComponent(annotationId)}` as any,
          method: 'DELETE' as any
        })
        setAnnotationPanelEntries((prev) =>
          prev.filter((entry) => entry.id !== annotationId)
        )
      } catch (error) {
        console.error('Failed to delete annotation:', error)
        message.error(
          t('review:mediaPage.annotationDeleteFailed', {
            defaultValue: 'Unable to delete annotation.'
          })
        )
      } finally {
        setAnnotationDeletingId(null)
      }
    },
    [isNote, selectedMediaId, setAnnotationPanelEntries, t]
  )

  const handleSyncAnnotations = useCallback(async () => {
    if (!selectedMediaId || isNote) return

    setAnnotationSyncing(true)
    try {
      await bgRequest({
        path: `/api/v1/media/${encodeURIComponent(selectedMediaId)}/annotations/sync` as any,
        method: 'POST' as any,
        headers: { 'Content-Type': 'application/json' },
        body: {
          annotations: annotationPanelEntries.map((entry) => ({
            location: entry.location,
            text: entry.text,
            color: entry.color,
            note: entry.note,
            annotation_type: entry.annotation_type
          })),
          client_ids: annotationPanelEntries.map((entry) => entry.id)
        }
      })
      message.success(
        t('review:mediaPage.annotationSyncSuccess', {
          defaultValue: 'Annotations synced.'
        })
      )
    } catch (error) {
      console.error('Failed to sync annotations:', error)
      message.error(
        t('review:mediaPage.annotationSyncFailed', {
          defaultValue: 'Unable to sync annotations.'
        })
      )
    } finally {
      setAnnotationSyncing(false)
    }
  }, [annotationPanelEntries, isNote, selectedMediaId, t])

  const renderDocumentIntelligencePanel = () => {
    if (!activeDocumentIntelligencePanel) {
      return null
    }

    if (activeDocumentIntelligencePanel.loading) {
      return (
        <div
          className="text-xs text-text-muted"
          data-testid="media-intelligence-loading"
        >
          {t('review:mediaPage.intelligenceLoading', {
            defaultValue: 'Loading intelligence data...'
          })}
        </div>
      )
    }

    if (activeDocumentIntelligencePanel.error) {
      return (
        <div className="space-y-2" data-testid="media-intelligence-error">
          <p className="text-xs text-danger">{activeDocumentIntelligencePanel.error}</p>
          <button
            type="button"
            onClick={() => {
              void fetchDocumentIntelligence()
            }}
            className="rounded border border-border bg-surface2 px-2 py-1 text-xs text-text hover:bg-surface"
            data-testid="media-intelligence-retry"
          >
            {t('common:retry', { defaultValue: 'Retry' })}
          </button>
        </div>
      )
    }

    if (
      activeIntelligenceTab !== 'annotations' &&
      (!Array.isArray(activeDocumentIntelligencePanel.data) ||
        activeDocumentIntelligencePanel.data.length === 0)
    ) {
      return (
        <div
          className="text-xs text-text-muted"
          data-testid="media-intelligence-empty"
        >
          {t(`review:mediaPage.intelligenceEmpty.${activeIntelligenceTab}`, {
            defaultValue: `No ${activeIntelligenceTab} available for this item.`
          })}
        </div>
      )
    }

    if (activeIntelligenceTab === 'outline') {
      return (
        <ul className="space-y-1 text-xs" data-testid="media-intelligence-outline-list">
          {activeDocumentIntelligencePanel.data.map((entry: any, index: number) => (
            <li
              key={`${entry?.title || 'entry'}-${entry?.page || index}-${index}`}
              className="flex items-start justify-between gap-2 rounded bg-surface2 px-2 py-1 text-text"
              data-testid="media-intelligence-outline-item"
            >
              <span className="truncate">{entry?.title || `Section ${index + 1}`}</span>
              <span className="shrink-0 text-text-muted">{entry?.page ?? '—'}</span>
            </li>
          ))}
        </ul>
      )
    }

    if (activeIntelligenceTab === 'insights') {
      return (
        <ul className="space-y-2 text-xs" data-testid="media-intelligence-insights-list">
          {activeDocumentIntelligencePanel.data.map((entry: any, index: number) => (
            <li
              key={`${entry?.category || 'insight'}-${index}`}
              className="rounded bg-surface2 px-2 py-1.5"
              data-testid="media-intelligence-insight-item"
            >
              <p className="font-medium text-text">{entry?.title || `Insight ${index + 1}`}</p>
              <p className="mt-1 whitespace-pre-wrap text-text-muted">
                {entry?.content || ''}
              </p>
            </li>
          ))}
        </ul>
      )
    }

    if (activeIntelligenceTab === 'references') {
      return (
        <ul className="space-y-1 text-xs" data-testid="media-intelligence-references-list">
          {activeDocumentIntelligencePanel.data.map((entry: any, index: number) => {
            const label =
              entry?.title ||
              entry?.raw_text ||
              t('review:mediaPage.referenceLabel', {
                defaultValue: `Reference ${index + 1}`
              })
            return (
              <li
                key={`${entry?.doi || entry?.url || 'reference'}-${index}`}
                className="rounded bg-surface2 px-2 py-1 text-text"
                data-testid="media-intelligence-reference-item"
              >
                {label}
              </li>
            )
          })}
        </ul>
      )
    }

    if (activeIntelligenceTab === 'figures') {
      return (
        <ul className="space-y-1 text-xs" data-testid="media-intelligence-figures-list">
          {activeDocumentIntelligencePanel.data.map((entry: any, index: number) => (
            <li
              key={`${entry?.id || 'figure'}-${index}`}
              className="rounded bg-surface2 px-2 py-1 text-text"
              data-testid="media-intelligence-figure-item"
            >
              {entry?.caption || `Figure ${index + 1}`} (p.{entry?.page ?? '—'})
            </li>
          ))}
        </ul>
      )
    }

    const annotationEntries = Array.isArray(activeDocumentIntelligencePanel.data)
      ? (activeDocumentIntelligencePanel.data as MediaAnnotationEntry[])
      : []

    return (
      <div className="space-y-2 text-xs" data-testid="media-intelligence-annotations-panel">
        <div className="space-y-2 rounded border border-border bg-surface2 p-2">
          <p className="text-[11px] text-text-muted">
            {annotationSelectionText
              ? t('review:mediaPage.annotationSelectionCaptured', {
                  defaultValue: 'Selection captured. Add details and save.'
                })
              : t('review:mediaPage.annotationManualHint', {
                  defaultValue: 'Create an annotation from selected text or enter text manually.'
                })}
          </p>
          {annotationSelectionText ? (
            <p
              className="max-h-20 overflow-y-auto rounded border border-border bg-surface px-2 py-1 text-text"
              data-testid="media-annotation-selection-preview"
            >
              {annotationSelectionText}
            </p>
          ) : null}
          <textarea
            value={annotationManualText}
            onChange={(event) => setAnnotationManualText(event.target.value)}
            placeholder={t('review:mediaPage.annotationTextPlaceholder', {
              defaultValue: 'Annotation text'
            })}
            className="min-h-[56px] w-full rounded border border-border bg-surface px-2 py-1 text-xs text-text"
            data-testid="media-annotation-manual-text"
          />
          <input
            value={annotationDraftNote}
            onChange={(event) => setAnnotationDraftNote(event.target.value)}
            placeholder={t('review:mediaPage.annotationNotePlaceholder', {
              defaultValue: 'Optional note'
            })}
            className="h-8 w-full rounded border border-border bg-surface px-2 text-xs text-text"
            data-testid="media-annotation-note-input"
          />
          <div className="flex items-center gap-2">
            <select
              value={annotationDraftColor}
              onChange={(event) =>
                setAnnotationDraftColor(event.target.value as MediaAnnotationColor)
              }
              className="h-8 rounded border border-border bg-surface px-2 text-xs text-text"
              data-testid="media-annotation-color"
            >
              {ANNOTATION_COLOR_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => {
                void handleCreateAnnotation()
              }}
              disabled={annotationCreating}
              className="inline-flex h-8 items-center rounded border border-border px-2 text-xs text-text hover:bg-surface disabled:cursor-not-allowed disabled:opacity-60"
              data-testid="media-annotation-create"
            >
              {annotationCreating
                ? t('review:mediaPage.annotationSaving', {
                    defaultValue: 'Saving...'
                  })
                : t('review:mediaPage.annotationSave', {
                    defaultValue: 'Save annotation'
                  })}
            </button>
            <button
              type="button"
              onClick={() => {
                void handleSyncAnnotations()
              }}
              disabled={annotationSyncing || annotationEntries.length === 0}
              className="inline-flex h-8 items-center rounded border border-border px-2 text-xs text-text hover:bg-surface disabled:cursor-not-allowed disabled:opacity-60"
              data-testid="media-annotation-sync"
            >
              {annotationSyncing
                ? t('review:mediaPage.annotationSyncing', {
                    defaultValue: 'Syncing...'
                  })
                : t('review:mediaPage.annotationSync', {
                    defaultValue: 'Sync now'
                  })}
            </button>
            <button
              type="button"
              onClick={clearAnnotationDraft}
              className="inline-flex h-8 items-center rounded border border-border px-2 text-xs text-text hover:bg-surface"
              data-testid="media-annotation-clear-draft"
            >
              {t('common:clear', { defaultValue: 'Clear' })}
            </button>
          </div>
        </div>

        {annotationEntries.length > 0 ? (
          <ul className="space-y-1 text-xs" data-testid="media-intelligence-annotations-list">
            {annotationEntries.map((entry, index) => (
              <li
                key={`${entry?.id || 'annotation'}-${index}`}
                className="rounded bg-surface2 px-2 py-1 text-text"
                data-testid="media-intelligence-annotation-item"
              >
                <p>{entry?.text || entry?.note || `Annotation ${index + 1}`}</p>
                {entry?.note ? (
                  <p className="mt-1 text-[11px] text-text-muted">{entry.note}</p>
                ) : null}
                <div className="mt-1 flex items-center gap-2">
                  <span className="rounded bg-surface px-1.5 py-0.5 text-[10px] uppercase text-text-muted">
                    {entry.color || 'yellow'}
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      void handleUpdateAnnotationNote(entry)
                    }}
                    disabled={annotationUpdatingId === entry.id}
                    className="rounded border border-border px-2 py-0.5 text-[11px] text-text hover:bg-surface disabled:cursor-not-allowed disabled:opacity-60"
                    data-testid={`media-annotation-edit-${entry.id}`}
                  >
                    {annotationUpdatingId === entry.id
                      ? t('review:mediaPage.annotationUpdating', {
                          defaultValue: 'Updating...'
                        })
                      : t('common:edit', { defaultValue: 'Edit' })}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      void handleDeleteAnnotation(entry.id)
                    }}
                    disabled={annotationDeletingId === entry.id}
                    className="rounded border border-danger/50 px-2 py-0.5 text-[11px] text-danger hover:bg-danger/10 disabled:cursor-not-allowed disabled:opacity-60"
                    data-testid={`media-annotation-delete-${entry.id}`}
                  >
                    {annotationDeletingId === entry.id
                      ? t('review:mediaPage.annotationDeleting', {
                          defaultValue: 'Deleting...'
                        })
                      : t('common:delete', { defaultValue: 'Delete' })}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    )
  }

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
    <div ref={setRootContainerRef} className="relative flex-1 flex flex-col bg-bg">
      <div
        className="sr-only"
        aria-live="polite"
        aria-atomic="true"
        data-testid="content-selection-live-region"
      >
        {contentSelectionAnnouncement}
      </div>
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
              <Tooltip
                title={t('review:reviewPage.chatWithMediaTooltipClarified', {
                  defaultValue:
                    'Chat with this media by sending its full content to the composer.'
                })}
              >
                <button
                  onClick={onChatWithMedia}
                  className="p-1.5 text-text-muted hover:bg-surface2 rounded"
                  aria-label={chatWithLabel}
                  title={chatWithLabel}
                >
                  <MessageSquare className="w-4 h-4" />
                </button>
              </Tooltip>
            )}
            {!isNote && (
              <Tooltip title={t('review:mediaPage.analyzeButtonTooltip', { defaultValue: 'Generate AI analysis of this content' })}>
                <button
                  onClick={() => setAnalysisModalOpen(true)}
                  className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-primaryStrong bg-primary/10 hover:bg-primary/20 rounded transition-colors"
                  aria-label={t('review:mediaPage.analyzeButton', { defaultValue: 'Analyze' })}
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  {t('review:mediaPage.analyzeButton', { defaultValue: 'Analyze' })}
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
      <div
        ref={contentScrollContainerRef}
        className="flex-1 overflow-y-auto p-4"
        data-testid="content-scroll-container"
      >
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
            {selectedMedia.meta?.author && (
              <span
                className="inline-flex items-center gap-1 rounded bg-surface2 px-1.5 py-0.5"
                data-testid="media-author"
                title={selectedMedia.meta.author}
              >
                <User className="w-3 h-3" />
                <span className="truncate max-w-[200px]">{selectedMedia.meta.author}</span>
              </span>
            )}
            {selectedMedia.meta?.published_at && (
              <span
                className="inline-flex items-center gap-1 rounded bg-surface2 px-1.5 py-0.5"
                data-testid="media-published-date"
              >
                {t('review:mediaPage.publishedLabel', { defaultValue: 'Published' })}{' '}
                {(() => {
                  try {
                    const d = new Date(selectedMedia.meta.published_at)
                    return Number.isNaN(d.getTime())
                      ? selectedMedia.meta.published_at
                      : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short' })
                  } catch {
                    return selectedMedia.meta.published_at
                  }
                })()}
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
            {typeof progressPercent === 'number' && Number.isFinite(progressPercent) && (
              <span
                className="inline-flex items-center gap-1 rounded bg-surface2 px-1.5 py-0.5"
                data-testid="media-reading-progress"
                title={t('review:mediaPage.readingProgressTooltip', {
                  defaultValue: 'Reading progress'
                })}
              >
                {t('review:mediaPage.readingProgressLabel', {
                  defaultValue: '{{percent}}% read',
                  percent: Math.round(progressPercent)
                })}
              </span>
            )}
            {/* Transcription model */}
            {(() => {
              const model =
                mediaDetail?.transcription_model ??
                mediaDetail?.metadata?.transcription_model ??
                mediaDetail?.safe_metadata?.transcription_model ??
                mediaDetail?.processing?.transcription_model ??
                selectedMedia?.meta?.transcription_model
              if (typeof model !== 'string' || !model.trim()) return null
              return (
                <span
                  className="inline-flex items-center gap-1 rounded bg-surface2 px-1.5 py-0.5"
                  data-testid="media-transcription-model"
                  title={t('review:mediaPage.transcriptionModelTooltip', {
                    defaultValue: 'Transcription model used'
                  })}
                >
                  {t('review:mediaPage.transcriptionModelBadge', {
                    defaultValue: 'STT: {{model}}',
                    model: model.trim()
                  })}
                </span>
              )
            })()}
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
                {hasTranscriptTimingLines ? (
                  <button
                    type="button"
                    onClick={() => {
                      void setHideTranscriptTimings((prev) => !(prev ?? true))
                    }}
                    className="rounded border border-border bg-surface px-2 py-0.5 text-[11px] text-text-muted hover:bg-surface2 hover:text-text"
                    aria-label={
                      shouldHideTranscriptTimings
                        ? t('review:mediaPage.showTimings', {
                            defaultValue: 'Show timings'
                          })
                        : t('review:mediaPage.hideTimings', {
                            defaultValue: 'Hide timings'
                          })
                    }
                    title={
                      shouldHideTranscriptTimings
                        ? t('review:mediaPage.showTimings', {
                            defaultValue: 'Show timings'
                          })
                        : t('review:mediaPage.hideTimings', {
                            defaultValue: 'Hide timings'
                          })
                    }
                  >
                    {shouldHideTranscriptTimings
                      ? t('review:mediaPage.showTimings', {
                          defaultValue: 'Show timings'
                        })
                      : t('review:mediaPage.hideTimings', {
                          defaultValue: 'Hide timings'
                        })}
                  </button>
                ) : null}
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
                <button
                  type="button"
                  onClick={() => setFindBarOpen(true)}
                  className="p-1 text-text-muted hover:text-text transition-colors"
                  title={t('review:mediaPage.findInContent', {
                    defaultValue: 'Find in content'
                  })}
                  aria-label={t('review:mediaPage.findInContent', {
                    defaultValue: 'Find in content'
                  })}
                  data-testid="content-find-toggle"
                >
                  <FileSearch className="w-4 h-4" />
                </button>
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
                {findBarOpen && (
                  <div
                    className="mb-3 rounded-md border border-border bg-surface2 px-2 py-1.5"
                    data-testid="content-find-bar"
                  >
                    <div className="flex items-center gap-2">
                      <label htmlFor="content-find-input" className="sr-only">
                        {t('review:mediaPage.findInContent', {
                          defaultValue: 'Find in content'
                        })}
                      </label>
                      <input
                        id="content-find-input"
                        ref={findInputRef}
                        type="text"
                        className="h-7 w-full rounded border border-border bg-surface px-2 text-xs text-text outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                        placeholder={t('review:mediaPage.findPlaceholder', {
                          defaultValue: 'Find in content'
                        })}
                        value={findQuery}
                        onChange={(event) => setFindQuery(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === 'Escape') {
                            event.preventDefault()
                            closeFindBar()
                            return
                          }
                          if (event.key === 'Enter') {
                            event.preventDefault()
                            moveFindMatch(event.shiftKey ? -1 : 1)
                          }
                        }}
                        data-testid="content-find-input"
                      />
                      <span
                        className="whitespace-nowrap text-[11px] text-text-muted"
                        data-testid="content-find-count"
                      >
                        {findMatchCount > 0 && activeFindMatchIndex >= 0
                          ? `${activeFindMatchIndex + 1}/${findMatchCount}`
                          : `0/${findMatchCount}`}
                      </span>
                      <button
                        type="button"
                        onClick={() => moveFindMatch(-1)}
                        className="inline-flex h-7 w-7 items-center justify-center rounded border border-border bg-surface text-text-muted hover:text-text disabled:cursor-not-allowed disabled:opacity-40"
                        aria-label={t('review:mediaPage.findPrevious', {
                          defaultValue: 'Previous match'
                        })}
                        title={t('review:mediaPage.findPrevious', {
                          defaultValue: 'Previous match'
                        })}
                        disabled={findMatchCount === 0}
                        data-testid="content-find-prev"
                      >
                        <ChevronUp className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => moveFindMatch(1)}
                        className="inline-flex h-7 w-7 items-center justify-center rounded border border-border bg-surface text-text-muted hover:text-text disabled:cursor-not-allowed disabled:opacity-40"
                        aria-label={t('review:mediaPage.findNext', {
                          defaultValue: 'Next match'
                        })}
                        title={t('review:mediaPage.findNext', {
                          defaultValue: 'Next match'
                        })}
                        disabled={findMatchCount === 0}
                        data-testid="content-find-next"
                      >
                        <ChevronDown className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={closeFindBar}
                        className="inline-flex h-7 items-center rounded border border-border bg-surface px-2 text-[11px] text-text-muted hover:text-text"
                        aria-label={t('common:close', { defaultValue: 'Close' })}
                        title={t('common:close', { defaultValue: 'Close' })}
                        data-testid="content-find-close"
                      >
                        {t('common:close', { defaultValue: 'Close' })}
                      </button>
                    </div>
                  </div>
                )}
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
                  onMouseUp={handleCaptureAnnotationSelection}
                  onKeyUp={handleCaptureAnnotationSelection}
                >
                  {effectiveRenderMode === 'plain' ? (
                    shouldRenderTranscriptTimestampChips ? (
                      <div
                        className={`m-0 space-y-1 whitespace-pre-wrap text-text font-mono ${contentBodyTypographyClass}`}
                      >
                        {transcriptLines.map((line, lineIndex) => {
                          const parsed = parseLeadingTranscriptTiming(line)
                          if (!parsed) {
                            return (
                              <div key={`line-${lineIndex}`}>
                                {line.length > 0 ? line : '\u00A0'}
                              </div>
                            )
                          }
                          const timestamp = parsed.timestamp
                          const tail = `${parsed.leadingWhitespace}${parsed.separator}${parsed.text}`
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
                      <div className="space-y-2">
                        <pre
                          className={`whitespace-pre-wrap text-text font-mono m-0 ${contentBodyTypographyClass}`}
                        >
                          {highlightedPlainContent}
                        </pre>
                        {hasUnrenderedPlainContent ? (
                          <div
                            className="flex flex-wrap items-center justify-between gap-2 rounded border border-border bg-surface2 px-2 py-1 text-[11px] text-text-muted"
                            data-testid="large-content-window-status"
                            data-visible-chars={visiblePlainContentChars}
                            data-total-chars={displayContent.length}
                          >
                            <span data-testid="large-content-window-progress">
                              {t('review:mediaPage.largeContentProgress', {
                                defaultValue: `Showing ${visiblePlainContentChars}/${displayContent.length} characters`
                              })}
                            </span>
                            <button
                              type="button"
                              onClick={loadMorePlainContent}
                              className="rounded border border-border bg-surface px-2 py-0.5 text-[11px] text-primary hover:bg-surface2"
                              data-testid="large-content-window-load-more"
                            >
                              {t('review:mediaPage.largeContentLoadMore', {
                                defaultValue: 'Load more'
                              })}
                            </button>
                          </div>
                        ) : null}
                      </div>
                    )
                  ) : effectiveRenderMode === 'html' ? (
                    displayContent ? (
                      <div
                        className={`${richTextTypographyClass} break-words dark:prose-invert max-w-none prose-p:leading-relaxed`}
                        role="region"
                        aria-label={t('review:mediaPage.contentRegion', { defaultValue: 'Media content' })}
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
                            defaultValue: `Show more (${Math.round(displayContent.length / 1000)}k chars)`
                          })
                    }
                  >
                    {contentExpanded
                      ? t('review:mediaPage.showLess', { defaultValue: 'Show less' })
                      : t('review:mediaPage.showMore', {
                          defaultValue: `Show more (${Math.round(displayContent.length / 1000)}k chars)`
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

          {/* Document Intelligence */}
          {!isNote && (
            <div
              className="bg-surface border border-border rounded-lg mb-2 overflow-hidden"
              data-testid="media-intelligence-section"
            >
              <button
                onClick={() => toggleSection('intelligence')}
                className="w-full flex items-center justify-between px-3 py-2 bg-surface2 hover:bg-surface transition-colors"
                title={t('review:mediaPage.documentIntelligence', {
                  defaultValue: 'Document Intelligence'
                })}
                data-testid="media-intelligence-toggle"
              >
                <span className="text-sm font-medium text-text">
                  {t('review:mediaPage.documentIntelligence', {
                    defaultValue: 'Document Intelligence'
                  })}
                </span>
                {intelligenceSectionCollapsed ? (
                  <ChevronDown className="w-4 h-4 text-text-subtle" />
                ) : (
                  <ChevronUp className="w-4 h-4 text-text-subtle" />
                )}
              </button>
              {!intelligenceSectionCollapsed && (
                <div
                  className="space-y-2 p-3 bg-surface animate-in fade-in slide-in-from-top-1 duration-150"
                  data-testid="media-intelligence-panel"
                >
                  <div className="flex flex-wrap gap-1">
                    {DOCUMENT_INTELLIGENCE_TABS.map((tab) => {
                      const isActive = tab.key === activeIntelligenceTab
                      return (
                        <button
                          key={tab.key}
                          type="button"
                          onClick={() => setActiveIntelligenceTab(tab.key)}
                          className={`rounded border px-2 py-1 text-xs transition-colors ${
                            isActive
                              ? 'border-primary bg-primary text-white'
                              : 'border-border bg-surface2 text-text hover:bg-surface'
                          }`}
                          aria-pressed={isActive}
                          data-testid={`media-intelligence-tab-${tab.key}`}
                        >
                          {t(`review:mediaPage.documentIntelligenceTab.${tab.key}`, {
                            defaultValue: tab.label
                          })}
                        </button>
                      )
                    })}
                  </div>
                  <div data-testid="media-intelligence-content">
                    {renderDocumentIntelligencePanel()}
                  </div>
                </div>
              )}
            </div>
          )}

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

      {/* Schedule refresh modal */}
      {selectedMedia && !isNote && (
        <Modal
          open={scheduleRefreshModalOpen}
          onCancel={() => {
            if (!scheduleRefreshSubmitting) {
              setScheduleRefreshModalOpen(false)
            }
          }}
          footer={null}
          title={t('review:mediaPage.scheduleSourceRefresh', {
            defaultValue: 'Schedule source refresh'
          })}
          destroyOnHidden
        >
          <div className="space-y-3" data-testid="media-schedule-refresh-modal">
            <p className="m-0 text-xs text-text-muted">
              {t('review:mediaPage.scheduleSourceRefreshHint', {
                defaultValue:
                  'Create a watchlist monitor to re-fetch this source URL on a schedule.'
              })}
            </p>
            <p className="m-0 rounded border border-border bg-surface2 px-2 py-1 text-[11px] text-text">
              {sourceUrlForScheduling || t('review:mediaPage.scheduleSourceRefreshNoUrl', {
                defaultValue: 'No source URL available for scheduling.'
              })}
            </p>
            <div className="flex flex-wrap gap-2">
              {(
                ['hourly', 'daily', 'weekly'] as ReingestSchedulePreset[]
              ).map((preset) => {
                const isActive = scheduleRefreshPreset === preset
                const label =
                  preset === 'hourly'
                    ? t('review:mediaPage.schedulePresetHourly', { defaultValue: 'Hourly' })
                    : preset === 'daily'
                      ? t('review:mediaPage.schedulePresetDaily', { defaultValue: 'Daily' })
                      : t('review:mediaPage.schedulePresetWeekly', { defaultValue: 'Weekly' })
                return (
                  <button
                    key={preset}
                    type="button"
                    className={`rounded border px-2 py-1 text-xs transition-colors ${
                      isActive
                        ? 'border-primary bg-primary text-white'
                        : 'border-border bg-surface2 text-text hover:bg-surface'
                    }`}
                    onClick={() => setScheduleRefreshPreset(preset)}
                    aria-pressed={isActive}
                    data-testid={`media-schedule-refresh-preset-${preset}`}
                  >
                    {label}
                  </button>
                )
              })}
            </div>
            <div className="text-xs text-text-muted" data-testid="media-schedule-refresh-cron">
              {t('review:mediaPage.scheduleSourceRefreshCron', {
                defaultValue: 'Cron: {{cron}}',
                cron: REINGEST_CRON_BY_PRESET[scheduleRefreshPreset]
              })}
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                className="rounded border border-border px-3 py-1.5 text-xs text-text hover:bg-surface2"
                onClick={() => setScheduleRefreshModalOpen(false)}
                disabled={scheduleRefreshSubmitting}
              >
                {t('common:cancel', { defaultValue: 'Cancel' })}
              </button>
              <button
                type="button"
                className="rounded border border-primary bg-primary px-3 py-1.5 text-xs text-white hover:bg-primaryStrong disabled:opacity-60"
                onClick={() => {
                  void handleScheduleSourceRefresh()
                }}
                disabled={scheduleRefreshSubmitting || !sourceUrlForScheduling}
                data-testid="media-schedule-refresh-confirm"
              >
                {scheduleRefreshSubmitting
                  ? t('review:mediaPage.scheduleSourceRefreshSubmitting', {
                      defaultValue: 'Scheduling...'
                    })
                  : t('review:mediaPage.scheduleSourceRefreshConfirm', {
                      defaultValue: 'Schedule'
                    })}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Export Modal */}
      {selectedMedia && !isNote && (
        <Modal
          open={exportModalOpen}
          onCancel={() => setExportModalOpen(false)}
          footer={null}
          title={t('review:mediaPage.exportMedia', {
            defaultValue: 'Export content'
          })}
          destroyOnHidden
        >
          <div className="space-y-3" data-testid="media-export-modal">
            <div className="flex flex-wrap gap-2">
              {(
                [
                  ['json', 'JSON'],
                  ['markdown', 'Markdown'],
                  ['text', 'Plain text'],
                  ['bibtex', 'BibTeX']
                ] as Array<[MediaExportFormat, string]>
              ).map(([format, label]) => {
                const isActive = exportFormat === format
                return (
                  <button
                    key={format}
                    type="button"
                    className={`rounded border px-2 py-1 text-xs transition-colors ${
                      isActive
                        ? 'border-primary bg-primary text-white'
                        : 'border-border bg-surface2 text-text hover:bg-surface'
                    }`}
                    onClick={() => setExportFormat(format)}
                    aria-pressed={isActive}
                    data-testid={`media-export-format-${format}`}
                  >
                    {label}
                  </button>
                )
              })}
            </div>
            <div className="text-xs text-text-muted" data-testid="media-export-hint">
              {t('review:mediaPage.exportHint', {
                defaultValue: 'Exports content, analysis, and key metadata for this item.'
              })}
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                className="rounded border border-border px-3 py-1.5 text-xs text-text hover:bg-surface2"
                onClick={() => setExportModalOpen(false)}
              >
                {t('common:cancel', { defaultValue: 'Cancel' })}
              </button>
              <button
                type="button"
                className="rounded border border-primary bg-primary px-3 py-1.5 text-xs text-white hover:bg-primaryStrong"
                onClick={confirmExportMedia}
                data-testid="media-export-confirm"
              >
                {t('review:mediaPage.exportNow', { defaultValue: 'Export' })}
              </button>
            </div>
          </div>
        </Modal>
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
