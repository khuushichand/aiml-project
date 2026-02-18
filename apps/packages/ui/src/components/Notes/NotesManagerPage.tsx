import React from 'react'
import type { InputRef } from 'antd'
import { Input, Typography, Select, Button, Tooltip } from 'antd'
import {
  Plus as PlusIcon,
  Search as SearchIcon,
  ChevronLeft,
  ChevronRight,
  Sparkles as SparklesIcon,
  Bold as BoldIcon,
  Italic as ItalicIcon,
  Heading1 as HeadingIcon,
  List as ListIcon,
  Link2 as LinkIcon,
  Code2 as CodeIcon,
  Paperclip as PaperclipIcon
} from 'lucide-react'
import { bgRequest } from '@/services/background-proxy'
import { useQuery, keepPreviousData, useQueryClient } from '@tanstack/react-query'
import { useServerOnline } from '@/hooks/useServerOnline'
import { useConfirmDanger } from '@/components/Common/confirm-danger'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import FeatureEmptyState from '@/components/Common/FeatureEmptyState'
import { useDemoMode } from '@/context/demo-mode'
import { useServerCapabilities } from '@/hooks/useServerCapabilities'
import { tldwClient } from '@/services/tldw/TldwApiClient'
import { useAntdMessage } from '@/hooks/useAntdMessage'
import { getAllNoteKeywords, searchNoteKeywords } from "@/services/note-keywords"
import { useStoreMessageOption } from "@/store/option"
import { shallow } from "zustand/shallow"
import { updatePageTitle } from "@/utils/update-page-title"
import { normalizeChatRole } from "@/utils/normalize-chat-role"
import { useScrollToServerCard } from "@/hooks/useScrollToServerCard"
import { MarkdownPreview } from "@/components/Common/MarkdownPreview"
import NotesEditorHeader from "@/components/Notes/NotesEditorHeader"
import NotesListPanel from "@/components/Notes/NotesListPanel"
import NotesGraphModal from "@/components/Notes/NotesGraphModal"
import type { NoteListItem } from "@/components/Notes/types"
import type { ActiveWikilinkQuery, WikilinkCandidate } from "@/components/Notes/wikilinks"
import {
  buildWikilinkIndex,
  getActiveWikilinkQuery,
  insertWikilinkAtCursor,
  renderContentWithResolvedWikilinks
} from "@/components/Notes/wikilinks"
import { translateMessage } from "@/i18n/translateMessage"
import { formatFileSize } from "@/utils/format"
import { clearSetting, getSetting } from "@/services/settings/registry"
import { LAST_NOTE_ID_SETTING } from "@/services/settings/ui-settings"

type NoteWithKeywords = {
  metadata?: { keywords?: any[] }
  keywords?: any[]
}

const KeywordPickerModal = React.lazy(() => import('@/components/Notes/KeywordPickerModal'))

const extractBacklink = (note: any) => {
  const meta = note?.metadata || {}
  const backlinks = meta?.backlinks || meta || {}
  const conversation =
    note?.conversation_id ??
    backlinks?.conversation_id ??
    backlinks?.conversationId ??
    meta?.conversation_id ??
    null
  const message =
    note?.message_id ??
    backlinks?.message_id ??
    backlinks?.messageId ??
    meta?.message_id ??
    null
  return {
    conversation_id: conversation != null ? String(conversation) : null,
    message_id: message != null ? String(message) : null
  }
}

const extractKeywords = (note: NoteWithKeywords | any): string[] => {
  const rawKeywords = (Array.isArray(note?.metadata?.keywords)
    ? note.metadata.keywords
    : Array.isArray(note?.keywords)
      ? note.keywords
      : []) as any[]
  return (rawKeywords || [])
    .map((item: any) => {
      const raw =
        item?.keyword ??
        item?.keyword_text ??
        item?.text ??
        item
      return typeof raw === 'string' ? raw : null
    })
    .filter((s): s is string => !!s && s.trim().length > 0)
}

// Extract version from note object. Checks multiple candidate fields in order:
// 1. note.version (primary)
// 2. note.expected_version (fallback)
// 3. note.expectedVersion (camelCase variant)
// 4. note.metadata.* (nested variants)
const toNoteVersion = (note: any): number | null => {
  const candidates = [
    note?.version,
    note?.expected_version,
    note?.expectedVersion,
    note?.metadata?.version,
    note?.metadata?.expected_version,
    note?.metadata?.expectedVersion
  ]
  const validVersions: number[] = []
  for (const candidate of candidates) {
    if (
      typeof candidate === 'number' &&
      Number.isFinite(candidate) &&
      Number.isInteger(candidate) &&
      candidate >= 0
    ) {
      validVersions.push(candidate)
    }
    if (typeof candidate === 'string' && candidate.trim().length > 0) {
      const parsed = Number(candidate)
      if (Number.isFinite(parsed) && Number.isInteger(parsed) && parsed >= 0) {
        validVersions.push(parsed)
      }
    }
  }
  if (validVersions.length > 1) {
    const allSame = validVersions.every((version) => version === validVersions[0])
    if (!allSame) {
      console.warn('[toNoteVersion] Multiple conflicting versions found:', validVersions)
    }
  }
  return validVersions[0] ?? null
}

const toNoteLastModified = (note: any): string | null => {
  const candidates = [
    note?.last_modified,
    note?.updated_at,
    note?.updatedAt,
    note?.lastModified,
    note?.metadata?.last_modified,
    note?.metadata?.updated_at
  ]
  for (const candidate of candidates) {
    if (typeof candidate !== 'string' || candidate.trim().length === 0) continue
    const parsed = new Date(candidate)
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toISOString()
    }
  }
  return null
}

const toAttachmentPlaceholderUrl = (noteId: string | number, fileName: string) =>
  `/api/v1/notes/${encodeURIComponent(String(noteId))}/attachments/${encodeURIComponent(fileName)}`

const toAttachmentMarkdown = (noteId: string | number, file: File) => {
  const escapedName = file.name.replace(/\[/g, '\\[').replace(/\]/g, '\\]')
  const target = toAttachmentPlaceholderUrl(noteId, file.name)
  if ((file.type || '').startsWith('image/')) {
    return `![${escapedName}](${target})`
  }
  return `[${escapedName}](${target})`
}

const normalizeGraphNoteId = (rawId: string | number | null | undefined): string => {
  if (rawId == null) return ''
  const text = String(rawId).trim()
  if (text.startsWith('note:')) return text.slice(5)
  return text
}

// 120px offset accounts for page header and padding
const MIN_SIDEBAR_HEIGHT = 600
const NOTE_AUTOSAVE_DELAY_MS = 5000
const calculateSidebarHeight = () => {
  const vh = typeof window !== 'undefined' ? window.innerHeight : MIN_SIDEBAR_HEIGHT
  return Math.max(MIN_SIDEBAR_HEIGHT, vh - 120)
}

type SaveNoteOptions = {
  showSuccessMessage?: boolean
}

type SaveIndicatorState = 'idle' | 'dirty' | 'saving' | 'saved' | 'error'
type NotesEditorMode = 'edit' | 'split' | 'preview'
type MarkdownToolbarAction = 'bold' | 'italic' | 'heading' | 'list' | 'link' | 'code'
type RemoteVersionInfo = { version: number; lastModified: string | null }

const NotesManagerPage: React.FC = () => {
  const { t } = useTranslation(['option', 'common'])
  const [query, setQuery] = React.useState('')
  const [page, setPage] = React.useState(1)
  const [pageSize, setPageSize] = React.useState(20)
  const [listMode, setListMode] = React.useState<'active' | 'trash'>('active')
  const [total, setTotal] = React.useState(0)
  const [selectedId, setSelectedId] = React.useState<string | number | null>(null)
  const [title, setTitle] = React.useState('')
  const [content, setContent] = React.useState('')
  const [loadingDetail, setLoadingDetail] = React.useState(false)
  const [saving, setSaving] = React.useState(false)
  const [saveIndicator, setSaveIndicator] = React.useState<SaveIndicatorState>('idle')
  const [keywordTokens, setKeywordTokens] = React.useState<string[]>([])
  const [keywordOptions, setKeywordOptions] = React.useState<string[]>([])
  const [allKeywords, setAllKeywords] = React.useState<string[]>([])
  const allKeywordsRef = React.useRef<string[]>([])
  allKeywordsRef.current = allKeywords
  const [keywordPickerOpen, setKeywordPickerOpen] = React.useState(false)
  const [keywordPickerQuery, setKeywordPickerQuery] = React.useState('')
  const [keywordPickerSelection, setKeywordPickerSelection] = React.useState<string[]>([])
  const [editorKeywords, setEditorKeywords] = React.useState<string[]>([])
  const [originalMetadata, setOriginalMetadata] = React.useState<Record<string, any> | null>(null)
  const [selectedVersion, setSelectedVersion] = React.useState<number | null>(null)
  const [selectedLastSavedAt, setSelectedLastSavedAt] = React.useState<string | null>(null)
  const [remoteVersionInfo, setRemoteVersionInfo] = React.useState<RemoteVersionInfo | null>(null)
  const [isDirty, setIsDirty] = React.useState(false)
  const [backlinkConversationId, setBacklinkConversationId] = React.useState<string | null>(null)
  const [backlinkMessageId, setBacklinkMessageId] = React.useState<string | null>(null)
  const [openingLinkedChat, setOpeningLinkedChat] = React.useState(false)
  const [graphModalOpen, setGraphModalOpen] = React.useState(false)
  const [graphMutationTick, setGraphMutationTick] = React.useState(0)
  const [manualLinkTargetId, setManualLinkTargetId] = React.useState<string | null>(null)
  const [manualLinkSaving, setManualLinkSaving] = React.useState(false)
  const [manualLinkDeletingEdgeId, setManualLinkDeletingEdgeId] = React.useState<string | null>(null)
  const [titleSuggestionLoading, setTitleSuggestionLoading] = React.useState(false)
  const [editorMode, setEditorMode] = React.useState<NotesEditorMode>('edit')
  const [editorCursorIndex, setEditorCursorIndex] = React.useState<number | null>(null)
  const [wikilinkSelectionIndex, setWikilinkSelectionIndex] = React.useState(0)
  const keywordSearchTimeoutRef = React.useRef<number | null>(null)
  const autosaveTimeoutRef = React.useRef<number | null>(null)
  const contentTextareaRef = React.useRef<HTMLTextAreaElement | null>(null)
  const attachmentInputRef = React.useRef<HTMLInputElement | null>(null)
  const isOnline = useServerOnline()
  const { demoEnabled } = useDemoMode()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { capabilities, loading: capsLoading } = useServerCapabilities()
  const titleInputRef = React.useRef<InputRef | null>(null)
  const message = useAntdMessage()
  const confirmDanger = useConfirmDanger()
  const {
    setHistory,
    setMessages,
    setHistoryId,
    setServerChatId,
    setServerChatState,
    setServerChatTopic,
    setServerChatClusterId,
    setServerChatSource,
    setServerChatExternalRef
  } = useStoreMessageOption(
    (state) => ({
      setHistory: state.setHistory,
      setMessages: state.setMessages,
      setHistoryId: state.setHistoryId,
      setServerChatId: state.setServerChatId,
      setServerChatState: state.setServerChatState,
      setServerChatTopic: state.setServerChatTopic,
      setServerChatClusterId: state.setServerChatClusterId,
      setServerChatSource: state.setServerChatSource,
      setServerChatExternalRef: state.setServerChatExternalRef
    }),
    shallow
  )

  const editorDisabled = !isOnline || (!capsLoading && capabilities && !capabilities.hasNotes)

  const clearAutosaveTimeout = React.useCallback(() => {
    if (autosaveTimeoutRef.current != null) {
      window.clearTimeout(autosaveTimeoutRef.current)
      autosaveTimeoutRef.current = null
    }
  }, [])

  const saveIndicatorText = React.useMemo(() => {
    if (saveIndicator === 'saving') {
      return t('option:notesSearch.saving', { defaultValue: 'Saving...' })
    }
    if (saveIndicator === 'error') {
      return t('option:notesSearch.autosaveFailed', {
        defaultValue: 'Autosave failed. Press Save to retry.'
      })
    }
    if (saveIndicator === 'saved' && !isDirty) {
      return t('option:notesSearch.saved', { defaultValue: 'All changes saved' })
    }
    return null
  }, [isDirty, saveIndicator, t])

  const editorMetrics = React.useMemo(() => {
    const chars = content.length
    const words = content.trim().length > 0 ? content.trim().split(/\s+/).filter(Boolean).length : 0
    const readingTimeMinutes = words === 0 ? 0 : Math.max(1, Math.ceil(words / 200))
    return { chars, words, readingTimeMinutes }
  }, [content])

  const metricSummaryText = React.useMemo(() => {
    const wordLabel = editorMetrics.words === 1 ? 'word' : 'words'
    const charLabel = editorMetrics.chars === 1 ? 'char' : 'chars'
    const readLabel = editorMetrics.readingTimeMinutes === 1 ? 'min read' : 'mins read'
    return `${editorMetrics.words} ${wordLabel} · ${editorMetrics.chars} ${charLabel} · ${editorMetrics.readingTimeMinutes} ${readLabel}`
  }, [editorMetrics])

  const revisionSummaryText = React.useMemo(() => {
    const versionText =
      selectedVersion != null
        ? `${t('option:notesSearch.versionMetadata', {
            defaultValue: 'Version'
          })} ${selectedVersion}`
        : t('option:notesSearch.versionMetadataPending', {
            defaultValue: 'Version pending'
          })

    const lastSavedText = selectedLastSavedAt
      ? `${t('option:notesSearch.lastSavedMetadata', {
          defaultValue: 'Last saved'
        })} ${new Date(selectedLastSavedAt).toLocaleString()}`
      : t('option:notesSearch.lastSavedMetadataPending', {
          defaultValue: 'Not saved yet'
        })

    return `${versionText} · ${lastSavedText}`
  }, [selectedLastSavedAt, selectedVersion, t])

  const resizeEditorTextarea = React.useCallback(() => {
    const textarea = contentTextareaRef.current
    if (!textarea) return
    textarea.style.height = 'auto'
    const viewportHeight = typeof window !== 'undefined' ? window.innerHeight : 900
    const maxHeight = Math.max(
      280,
      Math.floor(viewportHeight * (editorMode === 'split' ? 0.42 : 0.62))
    )
    const minHeight = editorMode === 'split' ? 220 : 280
    const nextHeight = Math.min(Math.max(textarea.scrollHeight, minHeight), maxHeight)
    textarea.style.height = `${nextHeight}px`
    textarea.style.overflowY = textarea.scrollHeight > maxHeight ? 'auto' : 'hidden'
  }, [editorMode])

  const setContentDirty = React.useCallback((nextContent: string) => {
    setContent(nextContent)
    setIsDirty(true)
    setSaveIndicator('dirty')
  }, [])

  const applyMarkdownToolbarAction = React.useCallback(
    (action: MarkdownToolbarAction) => {
      if (editorDisabled) return
      const textarea = contentTextareaRef.current
      if (!textarea) return

      textarea.focus()
      const start = textarea.selectionStart ?? 0
      const end = textarea.selectionEnd ?? start
      const selected = content.slice(start, end)

      let replacement = selected
      let nextSelectionStart = start
      let nextSelectionEnd = end

      if (action === 'bold') {
        const inner = selected || 'bold text'
        replacement = `**${inner}**`
        nextSelectionStart = start + 2
        nextSelectionEnd = nextSelectionStart + inner.length
      } else if (action === 'italic') {
        const inner = selected || 'italic text'
        replacement = `*${inner}*`
        nextSelectionStart = start + 1
        nextSelectionEnd = nextSelectionStart + inner.length
      } else if (action === 'code') {
        const inner = selected || 'code'
        replacement = `\`${inner}\``
        nextSelectionStart = start + 1
        nextSelectionEnd = nextSelectionStart + inner.length
      } else if (action === 'heading') {
        if (selected) {
          replacement = selected
            .split('\n')
            .map((line) => (line.startsWith('#') ? line : `# ${line}`))
            .join('\n')
          nextSelectionStart = start
          nextSelectionEnd = start + replacement.length
        } else {
          replacement = '# Heading'
          nextSelectionStart = start + 2
          nextSelectionEnd = start + replacement.length
        }
      } else if (action === 'list') {
        if (selected) {
          replacement = selected
            .split('\n')
            .map((line) => {
              const trimmed = line.trim()
              if (!trimmed) return line
              if (trimmed.startsWith('- ')) return line
              return line.replace(trimmed, `- ${trimmed}`)
            })
            .join('\n')
          nextSelectionStart = start
          nextSelectionEnd = start + replacement.length
        } else {
          replacement = '- List item'
          nextSelectionStart = start + 2
          nextSelectionEnd = start + replacement.length
        }
      } else if (action === 'link') {
        const text = selected || 'link text'
        const url = 'https://'
        replacement = `[${text}](${url})`
        const urlStart = start + replacement.indexOf(url)
        nextSelectionStart = urlStart
        nextSelectionEnd = urlStart + url.length
      }

      const nextContent = `${content.slice(0, start)}${replacement}${content.slice(end)}`
      setContentDirty(nextContent)

      window.requestAnimationFrame(() => {
        const activeTextarea = contentTextareaRef.current
        if (!activeTextarea) return
        activeTextarea.focus()
        activeTextarea.setSelectionRange(nextSelectionStart, nextSelectionEnd)
        setEditorCursorIndex(nextSelectionEnd)
        resizeEditorTextarea()
      })
    },
    [content, editorDisabled, resizeEditorTextarea, setContentDirty]
  )

  const openAttachmentPicker = React.useCallback(() => {
    if (editorDisabled) return
    if (selectedId == null) {
      message.warning(
        t('option:notesSearch.attachmentSaveFirstWarning', {
          defaultValue: 'Save this note once before adding attachments.'
        })
      )
      return
    }
    attachmentInputRef.current?.click()
  }, [editorDisabled, message, selectedId, t])

  const handleAttachmentInputChange = React.useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const files = event.target.files
      if (!files || files.length === 0) return
      if (selectedId == null) {
        event.target.value = ''
        message.warning(
          t('option:notesSearch.attachmentSaveFirstWarning', {
            defaultValue: 'Save this note once before adding attachments.'
          })
        )
        return
      }

      const textarea = contentTextareaRef.current
      if (!textarea) {
        event.target.value = ''
        return
      }

      textarea.focus()
      const start = textarea.selectionStart ?? content.length
      const end = textarea.selectionEnd ?? start
      const markdown = Array.from(files)
        .map((file) => toAttachmentMarkdown(selectedId, file))
        .join('\n')
      const nextContent = `${content.slice(0, start)}${markdown}${content.slice(end)}`
      setContentDirty(nextContent)

      const cursor = start + markdown.length
      window.requestAnimationFrame(() => {
        const activeTextarea = contentTextareaRef.current
        if (!activeTextarea) return
        activeTextarea.focus()
        activeTextarea.setSelectionRange(cursor, cursor)
        setEditorCursorIndex(cursor)
        resizeEditorTextarea()
      })

      message.info(
        t('option:notesSearch.attachmentPlaceholderInserted', {
          defaultValue:
            'Inserted attachment placeholder links. Pending API contract: POST /api/v1/notes/{id}/attachments'
        })
      )
      event.target.value = ''
    },
    [content, message, resizeEditorTextarea, selectedId, setContentDirty, t]
  )

  const fetchFilteredNotesRaw = async (
    q: string,
    toks: string[],
    page: number,
    pageSize: number
  ): Promise<{ items: any[]; total: number }> => {
    const qstr = q.trim()
    if (!qstr && toks.length === 0) {
      return { items: [], total: 0 }
    }

    const params = new URLSearchParams()
    if (qstr) params.set('query', qstr)
    params.set('limit', String(pageSize))
    params.set('offset', String((page - 1) * pageSize))
    params.set('include_keywords', 'true')
    toks.forEach((tok) => {
      const v = tok.trim()
      if (v.length > 0) {
        params.append('tokens', v)
      }
    })

    const abs = await bgRequest<any>({
      path: `/api/v1/notes/search/?${params.toString()}` as any,
      method: 'GET' as any
    })

    let items: any[] = []
    let total = 0

    if (Array.isArray(abs)) {
      items = abs
      total = abs.length
    } else if (abs && typeof abs === 'object') {
      if (Array.isArray((abs as any).items)) {
        items = (abs as any).items
      }
      const pagination = (abs as any).pagination
      if (pagination && typeof pagination.total_items === 'number') {
        total = Number(pagination.total_items)
      } else if (Array.isArray((abs as any).items)) {
        total = (abs as any).items.length
      }
    }

    return { items, total }
  }

  const fetchNotes = async (): Promise<NoteListItem[]> => {
    const mapNoteListItem = (n: any): NoteListItem => {
      const links = extractBacklink(n)
      const keywords = extractKeywords(n)
      return {
        id: n?.id,
        title: n?.title,
        content: n?.content,
        updated_at: n?.updated_at ?? n?.last_modified ?? n?.lastModified,
        deleted: Boolean(n?.deleted),
        conversation_id: links.conversation_id,
        message_id: links.message_id,
        keywords,
        version: toNoteVersion(n) ?? undefined
      }
    }

    if (listMode === 'trash') {
      const params = new URLSearchParams()
      params.set('limit', String(pageSize))
      params.set('offset', String((page - 1) * pageSize))
      params.set('include_keywords', 'true')
      const res = await bgRequest<any>({
        path: `/api/v1/notes/trash?${params.toString()}` as any,
        method: 'GET' as any
      })
      const items = Array.isArray(res?.items) ? res.items : (Array.isArray(res) ? res : [])
      const totalItems =
        Number(
          res?.total ??
            res?.pagination?.total_items ??
            res?.count ??
            items.length ??
            0
        ) || 0
      setTotal(totalItems)
      return items.map(mapNoteListItem)
    }

    const q = query.trim()
    const toks = keywordTokens.map((k) => k.toLowerCase())
    // Prefer search when query or keyword filters are present
    if (q || toks.length > 0) {
      const { items, total } = await fetchFilteredNotesRaw(q, toks, page, pageSize)
      setTotal(total)
      return items.map(mapNoteListItem)
    }
    // Browse list with pagination when no filters
    const res = await bgRequest<any>({ path: `/api/v1/notes/?page=${page}&results_per_page=${pageSize}` as any, method: 'GET' as any })
    const items = Array.isArray(res?.items) ? res.items : (Array.isArray(res) ? res : [])
    const pagination = res?.pagination
    setTotal(Number(pagination?.total_items || items.length || 0))
    return items.map(mapNoteListItem)
  }

  const { data, isFetching, refetch } = useQuery({
    queryKey: ['notes', listMode, query, page, pageSize, keywordTokens.join('|')],
    queryFn: fetchNotes,
    placeholderData: keepPreviousData,
    enabled: isOnline
  })

  const filteredCount = Array.isArray(data) ? data.length : 0
  const hasActiveFilters = listMode === 'active' && (query.trim().length > 0 || keywordTokens.length > 0)

  const {
    data: noteNeighborsData,
    isLoading: noteNeighborsLoading,
    isError: noteNeighborsError
  } = useQuery({
    queryKey: ['note-graph-neighbors', selectedId, graphMutationTick],
    enabled: isOnline && selectedId != null,
    queryFn: async () => {
      const noteId = encodeURIComponent(String(selectedId))
      const graph = await bgRequest<any>({
        path: `/api/v1/notes/${noteId}/neighbors?edge_types=manual,wikilink,backlink&max_nodes=80&max_edges=200` as any,
        method: 'GET' as any
      })
      return graph
    }
  })

  const noteRelations = React.useMemo(() => {
    const selectedNormalized = normalizeGraphNoteId(selectedId)
    const nodes = Array.isArray(noteNeighborsData?.nodes) ? noteNeighborsData.nodes : []
    const edges = Array.isArray(noteNeighborsData?.edges) ? noteNeighborsData.edges : []

    const noteNodeMap = new Map<string, { id: string; title: string }>()
    for (const node of nodes) {
      const nodeType = String(node?.type || '')
      if (nodeType && nodeType !== 'note') continue
      const normalizedId = normalizeGraphNoteId(node?.id)
      if (!normalizedId) continue
      noteNodeMap.set(normalizedId, {
        id: normalizedId,
        title: String(node?.label || node?.title || `Note ${normalizedId}`)
      })
    }

    const relatedIds = new Set<string>()
    const backlinkIds = new Set<string>()
    const manualLinkByEdgeId = new Map<
      string,
      { edgeId: string; noteId: string; title: string; directed: boolean; outgoing: boolean }
    >()

    for (const edge of edges) {
      const source = normalizeGraphNoteId(edge?.source)
      const target = normalizeGraphNoteId(edge?.target)
      if (!source || !target || source === target) continue

      if (source === selectedNormalized) relatedIds.add(target)
      if (target === selectedNormalized) relatedIds.add(source)

      const type = String(edge?.type || '').toLowerCase()
      const directed = Boolean(edge?.directed)
      if (type === 'wikilink' && target === selectedNormalized) {
        backlinkIds.add(source)
      }
      if (type === 'backlink' && source === selectedNormalized) {
        backlinkIds.add(target)
      }
      if (type === 'manual' && directed && target === selectedNormalized) {
        backlinkIds.add(source)
      }
      if (type === 'manual') {
        const touchesSelected = source === selectedNormalized || target === selectedNormalized
        if (!touchesSelected) continue
        const counterpartId = source === selectedNormalized ? target : source
        if (!counterpartId) continue
        const edgeId = String(edge?.id || '')
        if (!edgeId) continue
        const node = noteNodeMap.get(counterpartId)
        manualLinkByEdgeId.set(edgeId, {
          edgeId,
          noteId: counterpartId,
          title: node?.title || `Note ${counterpartId}`,
          directed,
          outgoing: source === selectedNormalized
        })
      }
    }

    for (const normalizedId of noteNodeMap.keys()) {
      if (normalizedId !== selectedNormalized) {
        relatedIds.add(normalizedId)
      }
    }

    const toItems = (ids: Set<string>) =>
      Array.from(ids)
        .filter((id) => id !== selectedNormalized)
        .map((id) => {
          const node = noteNodeMap.get(id)
          return {
            id,
            title: node?.title || `Note ${id}`
          }
        })
        .sort((a, b) => a.title.localeCompare(b.title))

    return {
      related: toItems(relatedIds),
      backlinks: toItems(backlinkIds),
      manualLinks: Array.from(manualLinkByEdgeId.values()).sort((a, b) =>
        a.title.localeCompare(b.title)
      )
    }
  }, [noteNeighborsData, selectedId])

  const manualLinkOptions = React.useMemo(() => {
    const selectedNormalized = normalizeGraphNoteId(selectedId)
    const seen = new Set<string>()
    const options: Array<{ value: string; label: string }> = []
    const append = (id: string, title: string) => {
      const normalized = normalizeGraphNoteId(id)
      if (!normalized || normalized === selectedNormalized) return
      if (seen.has(normalized)) return
      seen.add(normalized)
      options.push({
        value: normalized,
        label: title || `Note ${normalized}`
      })
    }
    if (Array.isArray(data)) {
      for (const item of data) {
        append(String(item.id), String(item.title || `Note ${item.id}`))
      }
    }
    for (const item of noteRelations.related) {
      append(item.id, item.title)
    }
    for (const item of noteRelations.backlinks) {
      append(item.id, item.title)
    }
    return options.sort((a, b) => a.label.localeCompare(b.label))
  }, [data, noteRelations.backlinks, noteRelations.related, selectedId])

  const wikilinkCandidates = React.useMemo(() => {
    const seen = new Set<string>()
    const candidates: WikilinkCandidate[] = []

    const append = (id: string | number, candidateTitle: string) => {
      const normalizedId = normalizeGraphNoteId(id)
      const normalizedTitle = String(candidateTitle || '').trim()
      if (!normalizedId || !normalizedTitle) return
      const dedupeKey = `${normalizedId}::${normalizedTitle.toLowerCase()}`
      if (seen.has(dedupeKey)) return
      seen.add(dedupeKey)
      candidates.push({ id: normalizedId, title: normalizedTitle })
    }

    if (selectedId != null) {
      append(selectedId, title || `Note ${selectedId}`)
    }

    if (Array.isArray(data)) {
      for (const note of data) {
        append(String(note.id), String(note.title || `Note ${note.id}`))
      }
    }

    for (const note of noteRelations.related) {
      append(note.id, note.title)
    }
    for (const note of noteRelations.backlinks) {
      append(note.id, note.title)
    }
    for (const link of noteRelations.manualLinks) {
      append(link.noteId, link.title)
    }

    return candidates.sort((a, b) => a.title.localeCompare(b.title) || a.id.localeCompare(b.id))
  }, [data, noteRelations.backlinks, noteRelations.manualLinks, noteRelations.related, selectedId, title])

  const wikilinkIndex = React.useMemo(
    () => buildWikilinkIndex(wikilinkCandidates),
    [wikilinkCandidates]
  )

  const activeWikilinkQuery = React.useMemo<ActiveWikilinkQuery | null>(() => {
    if (editorDisabled) return null
    if (editorCursorIndex == null) return null
    return getActiveWikilinkQuery(content, editorCursorIndex)
  }, [content, editorCursorIndex, editorDisabled])

  const wikilinkSuggestions = React.useMemo(() => {
    if (!activeWikilinkQuery) return [] as WikilinkCandidate[]
    const queryLower = activeWikilinkQuery.query.trim().toLowerCase()
    const selectedNormalized = normalizeGraphNoteId(selectedId)
    const filtered = wikilinkCandidates.filter((candidate) => {
      if (!candidate.title) return false
      if (selectedNormalized && candidate.id === selectedNormalized) return false
      if (!queryLower) return true
      return candidate.title.toLowerCase().includes(queryLower)
    })
    return filtered
      .sort((a, b) => {
        const aTitle = a.title.toLowerCase()
        const bTitle = b.title.toLowerCase()
        const aStarts = queryLower.length > 0 && aTitle.startsWith(queryLower)
        const bStarts = queryLower.length > 0 && bTitle.startsWith(queryLower)
        if (aStarts !== bStarts) return aStarts ? -1 : 1
        return a.title.localeCompare(b.title) || a.id.localeCompare(b.id)
      })
      .slice(0, 8)
  }, [activeWikilinkQuery, selectedId, wikilinkCandidates])

  const wikilinkSuggestionDisplayCounts = React.useMemo(() => {
    const counts = new Map<string, number>()
    for (const candidate of wikilinkSuggestions) {
      const key = candidate.title.toLowerCase()
      counts.set(key, (counts.get(key) || 0) + 1)
    }
    return counts
  }, [wikilinkSuggestions])

  const previewContent = React.useMemo(
    () => renderContentWithResolvedWikilinks(content, wikilinkIndex),
    [content, wikilinkIndex]
  )

  const availableKeywords = React.useMemo(() => {
    const base = allKeywords.length ? allKeywords : keywordOptions
    const seen = new Set<string>()
    const out: string[] = []
    const add = (value: string) => {
      const text = String(value || '').trim()
      if (!text) return
      const key = text.toLowerCase()
      if (seen.has(key)) return
      seen.add(key)
      out.push(text)
    }
    base.forEach(add)
    keywordTokens.forEach(add)
    return out
  }, [allKeywords, keywordOptions, keywordTokens])

  const filteredKeywordPickerOptions = React.useMemo(() => {
    const q = keywordPickerQuery.trim().toLowerCase()
    if (!q) return availableKeywords
    return availableKeywords.filter((kw) => kw.toLowerCase().includes(q))
  }, [availableKeywords, keywordPickerQuery])

  const loadAllKeywords = React.useCallback(async () => {
    // Cached for session; add a refresh/TTL if keyword updates become frequent.
    if (allKeywordsRef.current.length > 0) return
    try {
      const arr = await getAllNoteKeywords()
      setAllKeywords(arr)
      setKeywordOptions(arr)
    } catch {
      console.debug('[NotesManagerPage] Keyword suggestions load failed')
    }
  }, [])

  const openKeywordPicker = React.useCallback(() => {
    setKeywordPickerQuery('')
    setKeywordPickerSelection(keywordTokens)
    setKeywordPickerOpen(true)
    void loadAllKeywords()
  }, [keywordTokens, loadAllKeywords])

  const handleKeywordPickerCancel = React.useCallback(() => {
    setKeywordPickerOpen(false)
  }, [])

  const handleKeywordPickerApply = React.useCallback(() => {
    setKeywordTokens(keywordPickerSelection)
    setPage(1)
    setKeywordPickerOpen(false)
  }, [keywordPickerSelection])

  const handleKeywordPickerQueryChange = React.useCallback((value: string) => {
    setKeywordPickerQuery(value)
  }, [])

  const handleKeywordPickerSelectionChange = React.useCallback((vals: string[]) => {
    setKeywordPickerSelection(vals)
  }, [])

  const handleKeywordPickerSelectAll = React.useCallback(() => {
    setKeywordPickerSelection(availableKeywords)
  }, [availableKeywords])

  const handleKeywordPickerClear = React.useCallback(() => {
    setKeywordPickerSelection([])
  }, [])

  const loadDetail = React.useCallback(async (id: string | number) => {
    setLoadingDetail(true)
    try {
      const d = await bgRequest<any>({ path: `/api/v1/notes/${id}` as any, method: 'GET' as any })
      setSelectedId(id)
      setTitle(String(d?.title || ''))
      setContent(String(d?.content || ''))
      setEditorKeywords(extractKeywords(d))
      setSelectedVersion(toNoteVersion(d))
      setSelectedLastSavedAt(toNoteLastModified(d))
      const rawMeta = d && typeof d === "object" ? (d as any).metadata : null
      setOriginalMetadata(
        rawMeta && typeof rawMeta === "object" ? { ...(rawMeta as Record<string, any>) } : null
      )
      const links = extractBacklink(d)
      setBacklinkConversationId(links.conversation_id)
      setBacklinkMessageId(links.message_id)
      setIsDirty(false)
      setSaveIndicator('idle')
      setRemoteVersionInfo(null)
      setEditorCursorIndex(0)
      setWikilinkSelectionIndex(0)
    } catch {
      message.error('Failed to load note')
    } finally { setLoadingDetail(false) }
  }, [message])

  const resetEditor = React.useCallback(() => {
    setSelectedId(null)
    setTitle('')
    setContent('')
    setEditorKeywords([])
    setOriginalMetadata(null)
    setSelectedVersion(null)
    setSelectedLastSavedAt(null)
    setBacklinkConversationId(null)
    setBacklinkMessageId(null)
    setIsDirty(false)
    setSaveIndicator('idle')
    setRemoteVersionInfo(null)
    setEditorCursorIndex(null)
    setWikilinkSelectionIndex(0)
  }, [])

  const confirmDiscardIfDirty = React.useCallback(async () => {
    if (!isDirty) return true
    const ok = await confirmDanger({
      title: 'Discard changes?',
      content: 'You have unsaved changes. Discard them?',
      okText: 'Discard',
      cancelText: 'Cancel'
    })
    return ok
  }, [isDirty])

  const switchListMode = React.useCallback(
    async (nextMode: 'active' | 'trash') => {
      if (nextMode === listMode) return
      const ok = await confirmDiscardIfDirty()
      if (!ok) return
      resetEditor()
      setListMode(nextMode)
      setPage(1)
      if (nextMode === 'trash') {
        setQuery('')
        setKeywordTokens([])
      }
    },
    [confirmDiscardIfDirty, listMode, resetEditor]
  )

  const handleNewNote = React.useCallback(async () => {
    const ok = await confirmDiscardIfDirty()
    if (!ok) return
    if (listMode !== 'active') setListMode('active')
    resetEditor()
    setTimeout(() => {
      titleInputRef.current?.focus()
    }, 0)
  }, [confirmDiscardIfDirty, listMode, resetEditor])

  const handleSelectNote = React.useCallback(
    async (id: string | number) => {
      const ok = await confirmDiscardIfDirty()
      if (!ok) return
      await loadDetail(id)
    },
    [confirmDiscardIfDirty, loadDetail]
  )

  const handleEditorChange = React.useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      const nextContent = event.target.value
      setContentDirty(nextContent)
      setEditorCursorIndex(event.target.selectionStart ?? nextContent.length)
    },
    [setContentDirty]
  )

  const handleEditorSelectionUpdate = React.useCallback(
    (event: React.SyntheticEvent<HTMLTextAreaElement>) => {
      const target = event.currentTarget
      setEditorCursorIndex(target.selectionStart ?? target.value.length)
    },
    []
  )

  const applyWikilinkSuggestion = React.useCallback(
    (candidate: WikilinkCandidate) => {
      if (!activeWikilinkQuery) return
      const next = insertWikilinkAtCursor(content, activeWikilinkQuery, candidate.title)
      setContentDirty(next.content)
      setEditorCursorIndex(next.cursor)
      setWikilinkSelectionIndex(0)
      window.requestAnimationFrame(() => {
        const textarea = contentTextareaRef.current
        if (!textarea) return
        textarea.focus()
        textarea.setSelectionRange(next.cursor, next.cursor)
        resizeEditorTextarea()
      })
    },
    [activeWikilinkQuery, content, resizeEditorTextarea, setContentDirty]
  )

  const handleEditorKeyDown = React.useCallback(
    (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (!activeWikilinkQuery || wikilinkSuggestions.length === 0) return
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        setWikilinkSelectionIndex((current) => (current + 1) % wikilinkSuggestions.length)
        return
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault()
        setWikilinkSelectionIndex((current) =>
          current === 0 ? wikilinkSuggestions.length - 1 : current - 1
        )
        return
      }
      if (event.key === 'Enter' || event.key === 'Tab') {
        event.preventDefault()
        const candidate =
          wikilinkSuggestions[Math.max(0, Math.min(wikilinkSelectionIndex, wikilinkSuggestions.length - 1))]
        if (!candidate) return
        applyWikilinkSuggestion(candidate)
        return
      }
      if (event.key === 'Escape') {
        event.preventDefault()
        const closeCursor = activeWikilinkQuery.start
        setEditorCursorIndex(closeCursor)
        window.requestAnimationFrame(() => {
          const textarea = contentTextareaRef.current
          if (!textarea) return
          textarea.focus()
          textarea.setSelectionRange(closeCursor, closeCursor)
        })
      }
    },
    [activeWikilinkQuery, applyWikilinkSuggestion, wikilinkSelectionIndex, wikilinkSuggestions]
  )

  const handlePreviewLinkClick = React.useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      const target = event.target as HTMLElement | null
      if (!target) return
      const anchor = target.closest('a')
      if (!(anchor instanceof HTMLAnchorElement)) return
      const href = String(anchor.getAttribute('href') || '')
      if (!href.startsWith('note://')) return
      event.preventDefault()
      const noteId = decodeURIComponent(href.slice('note://'.length))
      if (!noteId) return
      void handleSelectNote(noteId)
    },
    [handleSelectNote]
  )

  const suggestTitle = React.useCallback(async () => {
    if (editorDisabled || titleSuggestionLoading) return
    const sourceContent = content.trim()
    if (!sourceContent) {
      message.warning(
        t('option:notesSearch.titleSuggestEmptyContent', {
          defaultValue: 'Write some note content before generating a title.'
        })
      )
      return
    }

    setTitleSuggestionLoading(true)
    try {
      const response = await bgRequest<any>({
        path: '/api/v1/notes/title/suggest' as any,
        method: 'POST' as any,
        headers: { 'Content-Type': 'application/json' },
        body: {
          content: sourceContent,
          title_strategy: 'heuristic'
        }
      })
      const suggested = String(response?.title || '').trim()
      if (!suggested) {
        message.warning(
          t('option:notesSearch.titleSuggestNoResult', {
            defaultValue: 'No title suggestion was returned.'
          })
        )
        return
      }
      const apply = await confirmDanger({
        title: t('option:notesSearch.titleSuggestApplyTitle', {
          defaultValue: 'Apply suggested title?'
        }),
        content: suggested,
        okText: t('option:notesSearch.titleSuggestApplyAction', {
          defaultValue: 'Apply'
        }),
        cancelText: t('option:notesSearch.titleSuggestKeepCurrentAction', {
          defaultValue: 'Keep current'
        })
      })
      if (!apply) return
      setTitle(suggested)
      setIsDirty(true)
      setSaveIndicator('dirty')
    } catch (error: any) {
      message.error(String(error?.message || 'Could not generate title'))
    } finally {
      setTitleSuggestionLoading(false)
    }
  }, [confirmDanger, content, editorDisabled, message, t, titleSuggestionLoading])

  const createManualLink = React.useCallback(async () => {
    if (manualLinkSaving) return
    if (selectedId == null || !manualLinkTargetId) return
    const fromId = normalizeGraphNoteId(selectedId)
    const toId = normalizeGraphNoteId(manualLinkTargetId)
    if (!fromId || !toId) return
    if (fromId === toId) {
      message.warning('Cannot link a note to itself')
      return
    }
    setManualLinkSaving(true)
    try {
      await bgRequest<any>({
        path: `/api/v1/notes/${encodeURIComponent(fromId)}/links` as any,
        method: 'POST' as any,
        headers: { 'Content-Type': 'application/json' },
        body: {
          to_note_id: toId,
          directed: false,
          weight: 1.0
        }
      })
      message.success('Manual link created')
      setManualLinkTargetId(null)
      setGraphMutationTick((current) => current + 1)
    } catch (error: any) {
      const status = Number(error?.status ?? error?.response?.status)
      if (status === 409) {
        message.warning('Manual link already exists')
      } else {
        message.error(String(error?.message || 'Could not create manual link'))
      }
    } finally {
      setManualLinkSaving(false)
    }
  }, [manualLinkSaving, manualLinkTargetId, message, selectedId])

  const removeManualLink = React.useCallback(
    async (edgeId: string) => {
      if (!edgeId || manualLinkDeletingEdgeId) return
      const ok = await confirmDanger({
        title: 'Remove link?',
        content: 'This removes the manual relationship between these notes.',
        okText: 'Remove',
        cancelText: 'Cancel'
      })
      if (!ok) return
      setManualLinkDeletingEdgeId(edgeId)
      try {
        await bgRequest<any>({
          path: `/api/v1/notes/links/${encodeURIComponent(edgeId)}` as any,
          method: 'DELETE' as any
        })
        message.success('Manual link removed')
        setGraphMutationTick((current) => current + 1)
      } catch (error: any) {
        message.error(String(error?.message || 'Could not remove manual link'))
      } finally {
        setManualLinkDeletingEdgeId(null)
      }
    },
    [confirmDanger, manualLinkDeletingEdgeId, message]
  )

  const isVersionConflictError = (error: any) => {
    const msg = String(error?.message || '')
    const lower = msg.toLowerCase()
    const status = error?.status ?? error?.response?.status
    return (
      status === 409 ||
      lower.includes('expected-version') ||
      lower.includes('expected_version') ||
      lower.includes('version mismatch')
    )
  }

  const handleVersionConflict = (noteId?: string | number | null) => {
    message.error({
      content: (
        <span
          className="inline-flex items-center gap-2"
          role="alert"
          aria-live="assertive"
          aria-atomic="true"
          tabIndex={0}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault()
              void reloadNotes(noteId)
            }
          }}
        >
          <span>This note changed on the server.</span>
          <Button
            type="link"
            size="small"
            onClick={() => void reloadNotes(noteId)}
            aria-label="Reload notes"
          >
            Reload notes
          </Button>
        </span>
      ),
      duration: 6
    })
  }

  const saveNote = React.useCallback(
    async ({ showSuccessMessage = true }: SaveNoteOptions = {}) => {
      if (saving) return
      if (!content.trim() && !title.trim()) {
        if (showSuccessMessage) {
          message.warning('Nothing to save')
        }
        setSaveIndicator('idle')
        return
      }
      if (
        selectedId != null &&
        selectedVersion != null &&
        remoteVersionInfo &&
        remoteVersionInfo.version > selectedVersion
      ) {
        const proceed = await confirmDanger({
          title: 'Remote changes detected',
          content:
            `This note changed in another tab or session (local v${selectedVersion}, remote v${remoteVersionInfo.version}). ` +
            'Saving now may cause a conflict. Continue anyway?',
          okText: 'Save anyway',
          cancelText: 'Cancel'
        })
        if (!proceed) {
          return
        }
      }
      setSaving(true)
      setSaveIndicator('saving')
      try {
        const metadata: Record<string, any> = {
          ...(originalMetadata || {}),
          keywords: editorKeywords
        }
        if (backlinkConversationId) metadata.conversation_id = backlinkConversationId
        if (backlinkMessageId) metadata.message_id = backlinkMessageId
        const payload: Record<string, any> = {
          title: title || undefined,
          content,
          metadata,
          keywords: editorKeywords
        }
        if (backlinkConversationId) payload.conversation_id = backlinkConversationId
        if (backlinkMessageId) payload.message_id = backlinkMessageId
        if (selectedId == null) {
          const created = await bgRequest<any>({
            path: '/api/v1/notes/' as any,
            method: 'POST' as any,
            headers: { 'Content-Type': 'application/json' },
            body: payload
          })
          const createdVersion = toNoteVersion(created)
          const createdLastSaved = toNoteLastModified(created)
          if (showSuccessMessage) {
            message.success('Note created')
          }
          setIsDirty(false)
          setSaveIndicator('saved')
          setRemoteVersionInfo(null)
          if (createdVersion != null) setSelectedVersion(createdVersion)
          if (createdLastSaved) setSelectedLastSavedAt(createdLastSaved)
          await refetch()
          if (created?.id != null) await loadDetail(created.id)
        } else {
          let expectedVersion = selectedVersion
          if (expectedVersion == null) {
            try {
              const latest = await bgRequest<any>({
                path: `/api/v1/notes/${selectedId}` as any,
                method: 'GET' as any
              })
              expectedVersion = toNoteVersion(latest)
            } catch (e: any) {
              setSaveIndicator('error')
              if (showSuccessMessage) {
                message.error(e?.message || 'Save failed')
              }
              return
            }
          }
          if (expectedVersion == null) {
            setSaveIndicator('error')
            if (showSuccessMessage) {
              message.error('Missing version; reload and try again')
            }
            return
          }
          const updated = await bgRequest<any>({
            path: `/api/v1/notes/${selectedId}?expected_version=${encodeURIComponent(
              String(expectedVersion)
            )}` as any,
            method: 'PUT' as any,
            headers: { 'Content-Type': 'application/json' },
            body: payload
          })
          const updatedVersion = toNoteVersion(updated)
          const updatedLastSaved = toNoteLastModified(updated)
          if (showSuccessMessage) {
            message.success('Note updated')
          }
          setIsDirty(false)
          setSaveIndicator('saved')
          setRemoteVersionInfo(null)
          await refetch()
          if (updatedVersion != null) {
            setSelectedVersion(updatedVersion)
          } else if (selectedId != null) {
            try {
              const latest = await bgRequest<any>({
                path: `/api/v1/notes/${selectedId}` as any,
                method: 'GET' as any
              })
              setSelectedVersion(toNoteVersion(latest))
            } catch (err) {
              console.debug('[NotesManagerPage] Version refresh after save failed:', err)
            }
          }
          if (updatedLastSaved) {
            setSelectedLastSavedAt(updatedLastSaved)
          } else {
            setSelectedLastSavedAt(new Date().toISOString())
          }
        }
      } catch (e: any) {
        setSaveIndicator('error')
        if (isVersionConflictError(e)) {
          if (showSuccessMessage) {
            handleVersionConflict(selectedId)
          }
        } else if (showSuccessMessage) {
          message.error(String(e?.message || '') || 'Operation failed')
        }
      } finally {
        setSaving(false)
      }
    },
    [
      backlinkConversationId,
      backlinkMessageId,
      confirmDanger,
      content,
      editorKeywords,
      handleVersionConflict,
      isVersionConflictError,
      loadDetail,
      message,
      originalMetadata,
      refetch,
      remoteVersionInfo,
      saving,
      selectedId,
      setSelectedLastSavedAt,
      selectedVersion,
      title
    ]
  )

  const reloadNotes = async (noteId?: string | number | null) => {
    await refetch()
    const target = noteId ?? selectedId
    if (target == null) return
    try {
      const detail = await bgRequest<any>({ path: `/api/v1/notes/${target}` as any, method: 'GET' as any })
      const version = toNoteVersion(detail)
      if (version != null) setSelectedVersion(version)
      setSelectedLastSavedAt(toNoteLastModified(detail))
      setRemoteVersionInfo(null)
    } catch {
      // Ignore refresh errors for reload action; list refresh already happened.
    }
  }

  const checkSelectedNoteFreshness = React.useCallback(async () => {
    if (!isOnline || listMode !== 'active') return
    if (selectedId == null || selectedVersion == null) return
    if (saving) return
    try {
      const detail = await bgRequest<any>({
        path: `/api/v1/notes/${selectedId}` as any,
        method: 'GET' as any
      })
      const remoteVersion = toNoteVersion(detail)
      if (remoteVersion != null && remoteVersion > selectedVersion) {
        setRemoteVersionInfo({
          version: remoteVersion,
          lastModified: toNoteLastModified(detail)
        })
      } else {
        setRemoteVersionInfo(null)
      }
    } catch {
      // Ignore transient freshness-check failures.
    }
  }, [isOnline, listMode, saving, selectedId, selectedVersion])

  const deleteNote = async (id?: string | number | null) => {
    const target = id ?? selectedId
    if (target == null) { message.warning('No note selected'); return }
    const ok = await confirmDanger({ title: 'Please confirm', content: 'Delete this note?', okText: 'Delete', cancelText: 'Cancel' })
    if (!ok) return
    try {
      const targetId = String(target)
      let expectedVersion: number | null = null
      if (selectedId != null && String(selectedId) === targetId) {
        expectedVersion = selectedVersion
      }
      if (expectedVersion == null && Array.isArray(data)) {
        const match = data.find((note) => String(note.id) === targetId)
        if (typeof match?.version === 'number') expectedVersion = match.version
      }
      if (expectedVersion == null) {
        try {
          const detail = await bgRequest<any>({ path: `/api/v1/notes/${target}` as any, method: 'GET' as any })
          expectedVersion = toNoteVersion(detail)
        } catch (e: any) {
          message.error(e?.message || 'Could not verify note version')
          return
        }
      }
      if (expectedVersion == null) {
        message.error('Missing version; reload and try again')
        return
      }
      await bgRequest<any>({
        path: `/api/v1/notes/${target}?expected_version=${encodeURIComponent(
          String(expectedVersion)
        )}` as any,
        method: 'DELETE' as any,
        headers: {
          "expected-version": String(expectedVersion)
        }
      })
      message.success('Note deleted')
      if (selectedId != null && String(selectedId) === targetId) resetEditor()
      await refetch()
    } catch (e: any) {
      if (isVersionConflictError(e)) {
        handleVersionConflict(target)
      } else {
        message.error(String(e?.message || '') || 'Operation failed')
      }
    }
  }

  const restoreNote = async (id: string | number, version?: number) => {
    const target = String(id)
    let expectedVersion: number | null =
      typeof version === 'number' && Number.isFinite(version) ? version : null

    if (expectedVersion == null && Array.isArray(data)) {
      const match = data.find((note) => String(note.id) === target)
      if (typeof match?.version === 'number') expectedVersion = match.version
    }
    if (expectedVersion == null) {
      message.error('Missing version; reload trash and try again')
      return
    }

    try {
      const restored = await bgRequest<any>({
        path: `/api/v1/notes/${encodeURIComponent(target)}/restore?expected_version=${encodeURIComponent(
          String(expectedVersion)
        )}` as any,
        method: 'POST' as any
      })
      message.success('Note restored')
      setListMode('active')
      setPage(1)
      await refetch()
      const restoredId = String(restored?.id || target)
      await loadDetail(restoredId)
    } catch (error: any) {
      if (isVersionConflictError(error)) {
        message.error('Restore conflict. Refresh trash and retry.')
      } else {
        message.error(String(error?.message || 'Could not restore note'))
      }
    }
  }

  const openLinkedConversation = async () => {
    // Check for unsaved changes before navigating
    const okToLeave = await confirmDiscardIfDirty()
    if (!okToLeave) return

    if (!backlinkConversationId) {
      message.warning(
        t("option:notesSearch.noLinkedConversation", {
          defaultValue: "No linked conversation to open."
        })
      )
      return
    }
    try {
      setOpeningLinkedChat(true)
      await tldwClient.initialize().catch(() => null)
      const chat = await tldwClient.getChat(backlinkConversationId)
      setHistoryId(null)
      setServerChatId(String(backlinkConversationId))
      setServerChatState(
        (chat as any)?.state ??
          (chat as any)?.conversation_state ??
          "in-progress"
      )
      setServerChatTopic((chat as any)?.topic_label ?? null)
      setServerChatClusterId((chat as any)?.cluster_id ?? null)
      setServerChatSource((chat as any)?.source ?? null)
      setServerChatExternalRef((chat as any)?.external_ref ?? null)
      let assistantName = "Assistant"
      if ((chat as any)?.character_id != null) {
        try {
          const c = await tldwClient.getCharacter((chat as any)?.character_id)
          assistantName =
            c?.name || c?.title || c?.slug || assistantName
        } catch {}
      }

      const messages = await tldwClient.listChatMessages(
        backlinkConversationId,
        { include_deleted: "false" } as any
      )
      const historyArr = messages.map((m) => ({
        role: normalizeChatRole(m.role),
        content: m.content
      }))
      const mappedMessages = messages.map((m) => {
        const createdAt = Date.parse(m.created_at)
        const normalizedRole = normalizeChatRole(m.role)
        return {
          createdAt: Number.isNaN(createdAt) ? undefined : createdAt,
          isBot: normalizedRole === "assistant",
          role: normalizedRole,
          name:
            normalizedRole === "assistant"
              ? assistantName
              : normalizedRole === "system"
                ? "System"
                : "You",
          message: m.content,
          sources: [],
          images: [],
          serverMessageId: m.id,
          serverMessageVersion: m.version
        }
      })
      setHistory(historyArr)
      setMessages(mappedMessages)
      updatePageTitle((chat as any)?.title || "")
      navigate("/")
      setTimeout(() => {
        try {
          window.dispatchEvent(new CustomEvent("tldw:focus-composer"))
        } catch {}
      }, 0)
    } catch (e: any) {
      message.error(
        e?.message ||
          t("option:notesSearch.openConversationError", {
            defaultValue: "Failed to open linked conversation."
          })
      )
    } finally {
      setOpeningLinkedChat(false)
    }
  }

  const copySelected = async () => {
    try {
      await navigator.clipboard.writeText(content || '')
      message.success('Copied')
    } catch { message.error('Copy failed') }
  }

  const exportSelected = () => {
    const name = (title || `note-${selectedId ?? 'new'}`).replace(/[^a-z0-9-_]+/gi, '-')
    const md = title ? `# ${title}\n\n${content || ''}` : (content || '')
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${name}.md`
    a.click()
    URL.revokeObjectURL(url)
    // Show file size in success message (KB/MB)
    const sizeDisplay = formatFileSize(blob.size)
    message.success(
      translateMessage(
        t,
        'option:notesSearch.exportNoteSuccess',
        'Exported ({{size}})',
        { size: sizeDisplay }
      )
    )
  }

  const MAX_EXPORT_PAGES = 1000

  const exportAll = async () => {
    try {
      let arr: NoteListItem[] = []
      let limitReached = false
      const q = query.trim()
      const toks = keywordTokens.map((k) => k.toLowerCase())
      if (q || toks.length > 0) {
        // Fetch all matching notes in chunks using server-side filtering
        let p = 1
        const ps = 100
        while (p <= MAX_EXPORT_PAGES) {
          const { items } = await fetchFilteredNotesRaw(q, toks, p, ps)
          if (!items.length) break
          arr.push(
            ...items.map((n: any) => ({
              id: n?.id,
              title: n?.title,
              content: n?.content
            }))
          )
          if (items.length < ps) break
          p++
        }
        if (p > MAX_EXPORT_PAGES) limitReached = true
      } else {
        // Iterate pages (chunk by 100)
        let p = 1
        const ps = 100
        while (p <= MAX_EXPORT_PAGES) {
          const res = await bgRequest<any>({ path: `/api/v1/notes/?page=${p}&results_per_page=${ps}` as any, method: 'GET' as any })
          const items = Array.isArray(res?.items) ? res.items : (Array.isArray(res) ? res : [])
          arr.push(...items.map((n: any) => ({ id: n?.id, title: n?.title, content: n?.content })))
          const pagination = res?.pagination
          const totalPages = Number(pagination?.total_pages || (items.length < ps ? p : p + 1))
          if (p >= totalPages || items.length === 0) break
          p++
        }
        if (p > MAX_EXPORT_PAGES) limitReached = true
      }
      if (arr.length === 0) { message.info('No notes to export'); return }
      if (limitReached) {
        message.warning(`Export limited to ${arr.length} notes. Some notes may be excluded.`)
      }
      const md = arr.map((n, idx) => `### ${n.title || `Note ${n.id ?? idx+1}`}\n\n${String(n.content || '')}`).join("\n\n---\n\n")
      const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `notes-export.md`
      a.click()
      URL.revokeObjectURL(url)
      // Format file size for success message
      const sizeDisplay = formatFileSize(blob.size)
      message.success(
        translateMessage(
          t,
          'option:notesSearch.exportSuccess',
          'Exported {{count}} notes ({{size}})',
          { count: arr.length, size: sizeDisplay }
        )
      )
    } catch (e: any) {
      message.error(e?.message || 'Export failed')
    }
  }

  const gatherAllMatching = async (): Promise<{ arr: NoteListItem[]; limitReached: boolean }> => {
    const arr: NoteListItem[] = []
    let limitReached = false
    const q = query.trim()
    const toks = keywordTokens.map((k) => k.toLowerCase())
    if (q || toks.length > 0) {
      // Fetch all matching notes in chunks using server-side filtering
      let p = 1
      const ps = 100
      while (p <= MAX_EXPORT_PAGES) {
        const { items } = await fetchFilteredNotesRaw(q, toks, p, ps)
        if (!items.length) break
        arr.push(
          ...items.map((n: any) => ({
            id: n?.id,
            title: n?.title,
            content: n?.content,
            updated_at: n?.updated_at,
            keywords: extractKeywords(n)
          }))
        )
        if (items.length < ps) break
        p++
      }
      if (p > MAX_EXPORT_PAGES) limitReached = true
    } else {
      // Iterate pages (chunk by 100)
      let p = 1
      const ps = 100
      while (p <= MAX_EXPORT_PAGES) {
        const res = await bgRequest<any>({ path: `/api/v1/notes/?page=${p}&results_per_page=${ps}` as any, method: 'GET' as any })
        const items = Array.isArray(res?.items) ? res.items : (Array.isArray(res) ? res : [])
        arr.push(
          ...items.map((n: any) => ({
            id: n?.id,
            title: n?.title,
            content: n?.content,
            updated_at: n?.updated_at,
            keywords: extractKeywords(n)
          }))
        )
        const pagination = res?.pagination
        const totalPages = Number(pagination?.total_pages || (items.length < ps ? p : p + 1))
        if (p >= totalPages || items.length === 0) break
        p++
      }
      if (p > MAX_EXPORT_PAGES) limitReached = true
    }
    return { arr, limitReached }
  }

  const exportAllCSV = async () => {
    try {
      const { arr, limitReached } = await gatherAllMatching()
      if (!arr.length) { message.info('No notes to export'); return }
      if (limitReached) {
        message.warning(`Export limited to ${arr.length} notes. Some notes may be excluded.`)
      }
      const escape = (s: any) => '"' + String(s ?? '').replace(/"/g, '""') + '"'
      const header = ['id','title','content','updated_at','keywords']
      const rows = [
        header.join(','),
        ...arr.map((n) =>
          [
            n.id,
            n.title || '',
            (n.content || '').replace(/\r?\n/g, '\\n'),
            n.updated_at || '',
            (n.keywords || []).join('; ')
          ]
            .map(escape)
            .join(',')
        )
      ]
      const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `notes-export.csv`
      a.click()
      URL.revokeObjectURL(url)
      const sizeDisplay = formatFileSize(blob.size)
      message.success(
        translateMessage(
          t,
          'option:notesSearch.exportCsvSuccess',
          'Exported {{count}} notes as CSV ({{size}})',
          { count: arr.length, size: sizeDisplay }
        )
      )
    } catch (e: any) {
      message.error(e?.message || 'Export failed')
    }
  }

  const exportAllJSON = async () => {
    try {
      const { arr, limitReached } = await gatherAllMatching()
      if (!arr.length) { message.info('No notes to export'); return }
      if (limitReached) {
        message.warning(`Export limited to ${arr.length} notes. Some notes may be excluded.`)
      }
      const blob = new Blob([JSON.stringify(arr, null, 2)], { type: 'application/json;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `notes-export.json`
      a.click()
      URL.revokeObjectURL(url)
      const sizeDisplay = formatFileSize(blob.size)
      message.success(
        translateMessage(
          t,
          'option:notesSearch.exportJsonSuccess',
          'Exported {{count}} notes as JSON ({{size}})',
          { count: arr.length, size: sizeDisplay }
        )
      )
    } catch (e: any) {
      message.error(e?.message || 'Export failed')
    }
  }

  const loadKeywordSuggestions = React.useCallback(async (text?: string) => {
    try {
      if (text && text.trim().length > 0) {
        const arr = await searchNoteKeywords(text, 10)
        setKeywordOptions(arr)
      } else if (allKeywords.length > 0) {
        setKeywordOptions(allKeywords)
      } else {
        setKeywordOptions([])
      }
    } catch {
      // Keyword load failed - feature will use empty suggestions
      console.debug('[NotesManagerPage] Keyword suggestions load failed')
    }
  }, [allKeywords])

  const debouncedLoadKeywordSuggestions = React.useCallback(
    (text?: string) => {
      if (typeof window === 'undefined') {
        void loadKeywordSuggestions(text)
        return
      }
      if (keywordSearchTimeoutRef.current != null) {
        window.clearTimeout(keywordSearchTimeoutRef.current)
      }
      keywordSearchTimeoutRef.current = window.setTimeout(() => {
        void loadKeywordSuggestions(text)
      }, 300)
    },
    [loadKeywordSuggestions]
  )

  const handleKeywordFilterSearch = React.useCallback(
    (text: string) => {
      if (isOnline) void debouncedLoadKeywordSuggestions(text)
    },
    [debouncedLoadKeywordSuggestions, isOnline]
  )

  const handleKeywordFilterChange = React.useCallback(
    (vals: string[] | string) => {
      setKeywordTokens(Array.isArray(vals) ? vals : [vals])
      setPage(1)
    },
    []
  )

  const handleClearFilters = React.useCallback(() => {
    setQuery('')
    setKeywordTokens([])
    setPage(1)
  }, [])

  React.useEffect(() => {
    setWikilinkSelectionIndex(0)
  }, [activeWikilinkQuery?.start, activeWikilinkQuery?.query])

  React.useEffect(() => {
    if (wikilinkSuggestions.length === 0) return
    if (wikilinkSelectionIndex < wikilinkSuggestions.length) return
    setWikilinkSelectionIndex(0)
  }, [wikilinkSelectionIndex, wikilinkSuggestions.length])

  React.useEffect(() => {
    if (listMode !== 'active') {
      setRemoteVersionInfo(null)
      return
    }
    if (selectedId == null || selectedVersion == null) return
    let cancelled = false
    const runCheck = async () => {
      if (cancelled) return
      await checkSelectedNoteFreshness()
    }
    void runCheck()
    const intervalId = window.setInterval(() => {
      void runCheck()
    }, 30_000)
    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [checkSelectedNoteFreshness, listMode, selectedId, selectedVersion])

  React.useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (!isDirty) return
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [isDirty])

  React.useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const lowered = event.key.toLowerCase()
      const hasModifier = event.ctrlKey || event.metaKey
      if (!hasModifier || lowered !== 's' || event.altKey) return
      event.preventDefault()
      if (editorDisabled) return
      void saveNote()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [editorDisabled, saveNote])

  React.useEffect(() => {
    if (!isDirty || editorDisabled || saving) {
      clearAutosaveTimeout()
      return
    }
    if (!content.trim() && !title.trim()) {
      clearAutosaveTimeout()
      return
    }
    clearAutosaveTimeout()
    autosaveTimeoutRef.current = window.setTimeout(() => {
      void saveNote({ showSuccessMessage: false })
    }, NOTE_AUTOSAVE_DELAY_MS)
    return () => {
      clearAutosaveTimeout()
    }
  }, [clearAutosaveTimeout, content, editorDisabled, isDirty, saveNote, saving, title])

  React.useEffect(() => {
    return () => {
      if (keywordSearchTimeoutRef.current != null) {
        clearTimeout(keywordSearchTimeoutRef.current)
      }
      clearAutosaveTimeout()
    }
  }, [clearAutosaveTimeout])

  React.useEffect(() => {
    // When selecting a different note, default back to edit mode so users can start typing immediately.
    setEditorMode('edit')
    setManualLinkTargetId(null)
    setRemoteVersionInfo(null)
    setEditorCursorIndex(null)
    setWikilinkSelectionIndex(0)
  }, [selectedId])

  React.useEffect(() => {
    if (selectedId == null) {
      setGraphModalOpen(false)
    }
  }, [selectedId])

  React.useEffect(() => {
    resizeEditorTextarea()
  }, [content, editorMode, resizeEditorTextarea])

  React.useEffect(() => {
    if (typeof window === 'undefined') return
    const onResize = () => resizeEditorTextarea()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [resizeEditorTextarea])

  // Deep-link support: if tldw:lastNoteId is set (e.g., from omni-search),
  // automatically load that note once when the list is available.
  const [pendingNoteId, setPendingNoteId] = React.useState<string | null>(null)

  React.useEffect(() => {
    let cancelled = false
    void (async () => {
      const lastNoteId = await getSetting(LAST_NOTE_ID_SETTING)
      if (!cancelled && lastNoteId) {
        setPendingNoteId(lastNoteId)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  React.useEffect(() => {
    if (!isOnline) return
    if (listMode !== 'active') return
    if (!pendingNoteId) return
    if (!Array.isArray(data)) return
    if (selectedId != null) return

    ;(async () => {
      await handleSelectNote(pendingNoteId)
      setPendingNoteId(null)
      void clearSetting(LAST_NOTE_ID_SETTING)
    })()
  }, [data, handleSelectNote, isOnline, listMode, pendingNoteId, selectedId])

  const [sidebarCollapsed, setSidebarCollapsed] = React.useState(false)

  const [sidebarHeight, setSidebarHeight] = React.useState(calculateSidebarHeight())

  React.useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    const handleResize = () => {
      setSidebarHeight(calculateSidebarHeight())
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  return (
    <div className="flex h-full w-full bg-bg p-4 mt-16">
      {/* Collapsible Sidebar */}
      <div
        className={`flex-shrink-0 transition-all duration-300 ease-in-out ${
          sidebarCollapsed ? 'w-0 overflow-hidden' : 'w-[380px]'
        }`}
        style={{ minHeight: `${MIN_SIDEBAR_HEIGHT}px`, height: `${sidebarHeight}px` }}
      >
        <div className="flex h-full flex-col overflow-hidden rounded-lg border border-border bg-surface">
          {/* Toolbar Section */}
          <div className="flex-shrink-0 border-b border-border p-4 bg-surface">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs uppercase tracking-[0.16em] text-text-muted">
                {t('option:notesSearch.headerLabel', { defaultValue: 'Notes' })}
                <span className="ml-2 text-text-subtle">
                  {hasActiveFilters && filteredCount > 0 && total > 0
                    ? t('option:notesSearch.headerCount', {
                        defaultValue: '{{visible}} of {{total}}',
                        visible: filteredCount,
                        total
                      })
                    : t('option:notesSearch.headerCountFallback', {
                        defaultValue: '{{total}} total',
                        total
                      })}
                </span>
              </div>
              <Tooltip
                title={t('option:notesSearch.newTooltip', {
                  defaultValue: 'Create a new note'
                })}
              >
                <Button
                  type="text"
                  shape="circle"
                  onClick={() => void handleNewNote()}
                  className="flex items-center justify-center"
                  icon={(<PlusIcon className="w-4 h-4" />) as any}
                  aria-label={t('option:notesSearch.new', {
                    defaultValue: 'New note'
                  })}
                />
              </Tooltip>
            </div>
	            <div className="space-y-2">
	              <div className="grid grid-cols-2 gap-2">
	                <Button
	                  size="small"
	                  type={listMode === 'active' ? 'primary' : 'default'}
	                  onClick={() => {
	                    void switchListMode('active')
	                  }}
	                  data-testid="notes-mode-active"
	                >
	                  {t('option:notesSearch.modeActive', {
	                    defaultValue: 'Notes'
	                  })}
	                </Button>
	                <Button
	                  size="small"
	                  type={listMode === 'trash' ? 'primary' : 'default'}
	                  onClick={() => {
	                    void switchListMode('trash')
	                  }}
	                  data-testid="notes-mode-trash"
	                >
	                  {t('option:notesSearch.modeTrash', {
	                    defaultValue: 'Trash'
	                  })}
	                </Button>
	              </div>
	              {listMode === 'active' ? (
	                <>
	                  <Input
	                    allowClear
	                    placeholder={t('option:notesSearch.placeholder', {
	                      defaultValue: 'Search notes...'
	                    })}
	                    prefix={(<SearchIcon className="w-4 h-4 text-text-subtle" />) as any}
	                    value={query}
	                    onChange={(e) => {
	                      setQuery(e.target.value)
	                      setPage(1)
	                    }}
	                    onPressEnter={() => {
	                      setPage(1)
	                    }}
	                  />
	                  <Select
	                    mode="tags"
	                    allowClear
	                    placeholder={t('option:notesSearch.keywordsPlaceholder', {
	                      defaultValue: 'Filter by keyword'
	                    })}
	                    className="w-full"
	                    value={keywordTokens}
	                    onSearch={handleKeywordFilterSearch}
	                    onChange={handleKeywordFilterChange}
	                    options={keywordOptions.map((k) => ({ label: k, value: k }))}
	                  />
	                  <div className="flex items-center justify-between gap-2">
	                    <Button
	                      size="small"
	                      onClick={openKeywordPicker}
	                      disabled={!isOnline}
	                      className="text-xs"
	                    >
	                      {t('option:notesSearch.keywordsBrowse', {
	                        defaultValue: 'Browse keywords'
	                      })}
	                    </Button>
	                    {availableKeywords.length > 0 && (
	                      <Typography.Text
	                        type="secondary"
	                        className="text-[11px] text-text-muted"
	                      >
	                        {t('option:notesSearch.keywordsBrowseCount', {
	                          defaultValue: '{{count}} available',
	                          count: availableKeywords.length
	                        })}
	                      </Typography.Text>
	                    )}
	                  </div>
	                  {hasActiveFilters && (
	                    <Button
	                      size="small"
	                      onClick={handleClearFilters}
	                      className="w-full text-xs"
	                    >
	                      {t('option:notesSearch.clear', {
	                        defaultValue: 'Clear search & filters'
	                      })}
	                    </Button>
	                  )}
	                </>
	              ) : (
	                <Typography.Text
	                  type="secondary"
	                  className="text-[11px] text-text-muted block"
	                >
	                  {t('option:notesSearch.trashHelpText', {
	                    defaultValue: 'Restore notes from trash to edit them again.'
	                  })}
	                </Typography.Text>
	              )}
	            </div>
	          </div>

          {/* Notes List Section */}
          <div className="flex-1 overflow-y-auto">
	            <NotesListPanel
	              listMode={listMode}
	              isOnline={isOnline}
	              isFetching={isFetching}
	              demoEnabled={demoEnabled}
              capsLoading={capsLoading}
              capabilities={capabilities || null}
              notes={Array.isArray(data) ? data : undefined}
              total={total}
              page={page}
              pageSize={pageSize}
              selectedId={selectedId}
              onSelectNote={(id) => {
                void handleSelectNote(id)
              }}
	              onChangePage={(nextPage, nextPageSize) => {
	                setPage(nextPage)
	                setPageSize(nextPageSize)
	              }}
	              onResetEditor={() => {
	                if (listMode === 'trash') {
	                  void switchListMode('active')
	                  return
	                }
	                resetEditor()
	              }}
	              onOpenSettings={() => navigate('/settings/tldw')}
	              onOpenHealth={() => navigate('/settings/health')}
	              onRestoreNote={(id, version) => {
	                void restoreNote(id, version)
	              }}
	              onExportAllMd={() => {
	                void exportAll()
	              }}
              onExportAllCsv={() => {
                void exportAllCSV()
              }}
              onExportAllJson={() => {
                void exportAllJSON()
              }}
            />
          </div>
        </div>
      </div>

      {/* Collapse Button - Simple style like Media page */}
      <button
        onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
        className="relative w-6 bg-surface border-y border-r border-border hover:bg-surface2 flex items-center justify-center group transition-colors rounded-r-lg"
        style={{ minHeight: `${MIN_SIDEBAR_HEIGHT}px`, height: `${sidebarHeight}px` }}
        aria-label={
          sidebarCollapsed
            ? t('option:notesSearch.expandSidebar', {
                defaultValue: 'Expand sidebar'
              })
            : t('option:notesSearch.collapseSidebar', {
                defaultValue: 'Collapse sidebar'
              })
        }
      >
        <div className="flex items-center justify-center w-full h-full">
          {sidebarCollapsed ? (
            <ChevronRight className="w-4 h-4 text-text-subtle group-hover:text-text" />
          ) : (
            <ChevronLeft className="w-4 h-4 text-text-subtle group-hover:text-text" />
          )}
        </div>
      </button>

      {/* Editor Panel */}
      <div
        className="flex-1 flex flex-col overflow-hidden rounded-lg border border-border bg-surface ml-4"
        aria-disabled={editorDisabled}
      >
        <NotesEditorHeader
          title={title}
          selectedId={selectedId}
          backlinkConversationId={backlinkConversationId}
          backlinkMessageId={backlinkMessageId}
          editorDisabled={editorDisabled}
          openingLinkedChat={openingLinkedChat}
          editorMode={editorMode}
          hasContent={content.trim().length > 0}
          canSave={
            !editorDisabled &&
            (title.trim().length > 0 || content.trim().length > 0)
          }
          canExport={Boolean(title || content)}
          isSaving={saving}
          canDelete={!editorDisabled && selectedId != null}
          isDirty={isDirty}
          onOpenLinkedConversation={() => {
            void openLinkedConversation()
          }}
          onNewNote={() => {
            void handleNewNote()
          }}
          onChangeEditorMode={(nextMode) => {
            setEditorMode(nextMode)
          }}
          onCopy={() => {
            void copySelected()
          }}
          onExport={exportSelected}
          onSave={() => {
            void saveNote()
          }}
          onDelete={() => {
            void deleteNote()
          }}
        />
        <div className="flex-1 flex flex-col px-4 py-3 overflow-auto">
          <div className="flex items-center gap-2">
            <Input
              placeholder={t('option:notesSearch.titlePlaceholder', {
                defaultValue: 'Title'
              })}
              value={title}
              onChange={(e) => {
                setTitle(e.target.value)
                setIsDirty(true)
                setSaveIndicator('dirty')
              }}
              disabled={editorDisabled}
              ref={titleInputRef}
              className="bg-transparent hover:bg-surface2 focus:bg-surface2 transition-colors"
            />
            <Tooltip
              title={t('option:notesSearch.generateTitleTooltip', {
                defaultValue: 'Generate title from content'
              })}
            >
              <Button
                size="small"
                onClick={() => {
                  void suggestTitle()
                }}
                disabled={editorDisabled || content.trim().length === 0}
                loading={titleSuggestionLoading}
                icon={(<SparklesIcon className="w-4 h-4" />) as any}
                aria-label={t('option:notesSearch.generateTitleTooltip', {
                  defaultValue: 'Generate title from content'
                })}
                data-testid="notes-generate-title-button"
              >
                {t('option:notesSearch.generateTitleAction', {
                  defaultValue: 'Generate title'
                })}
              </Button>
            </Tooltip>
          </div>
          <div className="mt-3">
            <Select
              mode="tags"
              allowClear
              placeholder={t('option:notesSearch.keywordsEditorPlaceholder', {
                defaultValue: 'Keywords (tags)'
              })}
              data-testid="notes-keywords-editor"
              className="w-full"
              value={editorKeywords}
              onSearch={(txt) => {
                if (isOnline) void debouncedLoadKeywordSuggestions(txt)
              }}
              onChange={(vals) => {
                setEditorKeywords(vals as string[])
                setIsDirty(true)
                setSaveIndicator('dirty')
              }}
              options={keywordOptions.map((k) => ({ label: k, value: k }))}
              disabled={editorDisabled}
            />
            <Typography.Text
              type="secondary"
              className="block text-[11px] mt-1 text-text-muted"
            >
              {t('option:notesSearch.tagsHelp', {
                defaultValue:
                  'Keywords help you find this note using the keyword filter on the left.'
              })}
            </Typography.Text>
            {saveIndicatorText && (
              <Typography.Text
                type={saveIndicator === 'error' ? 'danger' : 'secondary'}
                className="block text-[11px] mt-1 text-text-muted"
                aria-live="polite"
              >
                {saveIndicatorText}
              </Typography.Text>
            )}
            {remoteVersionInfo && (
              <div
                className="mt-2 rounded border border-warn/50 bg-warn/10 px-2 py-1 text-[12px] text-warn"
                role="status"
                data-testid="notes-stale-version-warning"
              >
                <span>
                  {t('option:notesSearch.staleVersionWarning', {
                    defaultValue:
                      'A newer version is available on the server (v{{version}}).',
                    version: remoteVersionInfo.version
                  })}
                </span>
                <Button
                  type="link"
                  size="small"
                  className="!px-1"
                  onClick={() => {
                    if (selectedId == null) return
                    void handleSelectNote(selectedId)
                  }}
                  data-testid="notes-stale-version-reload"
                >
                  {t('option:notesSearch.reloadNoteAction', {
                    defaultValue: 'Reload note'
                  })}
                </Button>
              </div>
            )}
          </div>
          {selectedId != null && (
            <div
              className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-2"
              data-testid="notes-graph-relation-panels"
            >
              <div className="rounded-lg border border-border bg-surface2 p-3">
                <Typography.Text
                  className="text-[11px] uppercase tracking-[0.08em] text-text-muted"
                  data-testid="notes-related-heading"
                >
                  {t('option:notesSearch.relatedNotesHeading', {
                    defaultValue: 'Related notes'
                  })}
                </Typography.Text>
                <Button
                  size="small"
                  className="mt-2"
                  onClick={() => setGraphModalOpen(true)}
                  data-testid="notes-open-graph-view"
                >
                  {t('option:notesSearch.graphOpenButton', {
                    defaultValue: 'Open graph view'
                  })}
                </Button>
                <div className="mt-2 flex items-center gap-2">
                  <select
                    className="flex-1 rounded border border-border bg-surface px-2 py-1 text-sm text-text"
                    value={manualLinkTargetId ?? ''}
                    onChange={(event) => {
                      const value = event.target.value
                      setManualLinkTargetId(value || null)
                    }}
                    disabled={manualLinkSaving || editorDisabled || manualLinkOptions.length === 0}
                    data-testid="notes-manual-link-target-select"
                  >
                    <option value="">
                      {t('option:notesSearch.manualLinkTargetPlaceholder', {
                        defaultValue: 'Select a note to link'
                      })}
                    </option>
                    {manualLinkOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  <Button
                    size="small"
                    type="primary"
                    onClick={() => {
                      void createManualLink()
                    }}
                    disabled={!manualLinkTargetId || editorDisabled}
                    loading={manualLinkSaving}
                    data-testid="notes-manual-link-add"
                  >
                    {t('option:notesSearch.manualLinkAdd', {
                      defaultValue: 'Add link'
                    })}
                  </Button>
                </div>
                <Typography.Text
                  type="secondary"
                  className="block mt-2 text-[11px] text-text-muted"
                >
                  {t('option:notesSearch.manualLinksHeading', {
                    defaultValue: 'Manual links'
                  })}
                </Typography.Text>
                {noteRelations.manualLinks.length === 0 ? (
                  <Typography.Text
                    type="secondary"
                    className="block mt-1 text-[12px] text-text-muted"
                    data-testid="notes-manual-links-empty"
                  >
                    {t('option:notesSearch.manualLinksEmpty', {
                      defaultValue: 'No manual links yet.'
                    })}
                  </Typography.Text>
                ) : (
                  <div className="mt-1 flex flex-wrap gap-1.5" data-testid="notes-manual-links-list">
                    {noteRelations.manualLinks.map((link) => (
                      <div
                        key={link.edgeId}
                        className="inline-flex items-center gap-1 rounded border border-border bg-surface px-2 py-1"
                      >
                        <button
                          type="button"
                          className="text-xs text-text hover:underline"
                          onClick={() => {
                            void handleSelectNote(link.noteId)
                          }}
                        >
                          {link.title}
                        </button>
                        <button
                          type="button"
                          className="text-xs text-danger hover:underline"
                          onClick={() => {
                            void removeManualLink(link.edgeId)
                          }}
                          disabled={manualLinkDeletingEdgeId === link.edgeId}
                          aria-label={t('option:notesSearch.manualLinkRemoveAria', {
                            defaultValue: `Remove manual link ${link.title}`
                          })}
                          data-testid={`notes-manual-link-remove-${link.edgeId.replace(/[^a-z0-9_-]/gi, '_')}`}
                        >
                          {manualLinkDeletingEdgeId === link.edgeId
                            ? t('option:notesSearch.manualLinkRemoving', {
                                defaultValue: 'Removing...'
                              })
                            : t('option:notesSearch.manualLinkRemove', {
                                defaultValue: 'Remove'
                              })}
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                {noteNeighborsLoading ? (
                  <Typography.Text
                    type="secondary"
                    className="block mt-2 text-[12px] text-text-muted"
                  >
                    {t('option:notesSearch.relatedNotesLoading', {
                      defaultValue: 'Loading related notes...'
                    })}
                  </Typography.Text>
                ) : noteNeighborsError ? (
                  <Typography.Text
                    type="danger"
                    className="block mt-2 text-[12px]"
                    data-testid="notes-related-error"
                  >
                    {t('option:notesSearch.relatedNotesError', {
                      defaultValue: 'Could not load related notes.'
                    })}
                  </Typography.Text>
                ) : noteRelations.related.length === 0 ? (
                  <Typography.Text
                    type="secondary"
                    className="block mt-2 text-[12px] text-text-muted"
                    data-testid="notes-related-empty"
                  >
                    {t('option:notesSearch.relatedNotesEmpty', {
                      defaultValue: 'No related notes yet.'
                    })}
                  </Typography.Text>
                ) : (
                  <div className="mt-2 flex flex-wrap gap-1.5" data-testid="notes-related-list">
                    {noteRelations.related.map((note) => (
                      <button
                        key={`related-${note.id}`}
                        type="button"
                        className="rounded border border-border bg-surface px-2 py-1 text-left text-xs text-text hover:bg-surface3"
                        onClick={() => {
                          void handleSelectNote(note.id)
                        }}
                      >
                        {note.title}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div className="rounded-lg border border-border bg-surface2 p-3">
                <Typography.Text
                  className="text-[11px] uppercase tracking-[0.08em] text-text-muted"
                  data-testid="notes-backlinks-heading"
                >
                  {t('option:notesSearch.backlinksHeading', {
                    defaultValue: 'Backlinks'
                  })}
                </Typography.Text>
                {noteNeighborsLoading ? (
                  <Typography.Text
                    type="secondary"
                    className="block mt-2 text-[12px] text-text-muted"
                  >
                    {t('option:notesSearch.backlinksLoading', {
                      defaultValue: 'Loading backlinks...'
                    })}
                  </Typography.Text>
                ) : noteNeighborsError ? (
                  <Typography.Text
                    type="danger"
                    className="block mt-2 text-[12px]"
                    data-testid="notes-backlinks-error"
                  >
                    {t('option:notesSearch.backlinksError', {
                      defaultValue: 'Could not load backlinks.'
                    })}
                  </Typography.Text>
                ) : noteRelations.backlinks.length === 0 ? (
                  <Typography.Text
                    type="secondary"
                    className="block mt-2 text-[12px] text-text-muted"
                    data-testid="notes-backlinks-empty"
                  >
                    {t('option:notesSearch.backlinksEmpty', {
                      defaultValue: 'No backlinks yet.'
                    })}
                  </Typography.Text>
                ) : (
                  <div className="mt-2 flex flex-wrap gap-1.5" data-testid="notes-backlinks-list">
                    {noteRelations.backlinks.map((note) => (
                      <button
                        key={`backlink-${note.id}`}
                        type="button"
                        className="rounded border border-border bg-surface px-2 py-1 text-left text-xs text-text hover:bg-surface3"
                        onClick={() => {
                          void handleSelectNote(note.id)
                        }}
                      >
                        {note.title}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
          {editorMode !== 'preview' && (
            <div className="mt-3 flex items-center flex-wrap gap-1 rounded-lg border border-border bg-surface2 p-2">
              <Typography.Text
                type="secondary"
                className="text-[11px] mr-1 uppercase tracking-[0.08em]"
              >
                {t('option:notesSearch.formattingLabel', {
                  defaultValue: 'Formatting'
                })}
              </Typography.Text>
              <Tooltip title={t('option:notesSearch.toolbarBoldTooltip', { defaultValue: 'Bold' })}>
                <Button
                  size="small"
                  type="text"
                  icon={(<BoldIcon className="w-4 h-4" />) as any}
                  onClick={() => applyMarkdownToolbarAction('bold')}
                  disabled={editorDisabled}
                  aria-label={t('option:notesSearch.toolbarBoldTooltip', { defaultValue: 'Bold' })}
                  data-testid="notes-toolbar-bold"
                />
              </Tooltip>
              <Tooltip title={t('option:notesSearch.toolbarItalicTooltip', { defaultValue: 'Italic' })}>
                <Button
                  size="small"
                  type="text"
                  icon={(<ItalicIcon className="w-4 h-4" />) as any}
                  onClick={() => applyMarkdownToolbarAction('italic')}
                  disabled={editorDisabled}
                  aria-label={t('option:notesSearch.toolbarItalicTooltip', { defaultValue: 'Italic' })}
                  data-testid="notes-toolbar-italic"
                />
              </Tooltip>
              <Tooltip title={t('option:notesSearch.toolbarHeadingTooltip', { defaultValue: 'Heading' })}>
                <Button
                  size="small"
                  type="text"
                  icon={(<HeadingIcon className="w-4 h-4" />) as any}
                  onClick={() => applyMarkdownToolbarAction('heading')}
                  disabled={editorDisabled}
                  aria-label={t('option:notesSearch.toolbarHeadingTooltip', { defaultValue: 'Heading' })}
                  data-testid="notes-toolbar-heading"
                />
              </Tooltip>
              <Tooltip title={t('option:notesSearch.toolbarListTooltip', { defaultValue: 'List' })}>
                <Button
                  size="small"
                  type="text"
                  icon={(<ListIcon className="w-4 h-4" />) as any}
                  onClick={() => applyMarkdownToolbarAction('list')}
                  disabled={editorDisabled}
                  aria-label={t('option:notesSearch.toolbarListTooltip', { defaultValue: 'List' })}
                  data-testid="notes-toolbar-list"
                />
              </Tooltip>
              <Tooltip title={t('option:notesSearch.toolbarLinkTooltip', { defaultValue: 'Link' })}>
                <Button
                  size="small"
                  type="text"
                  icon={(<LinkIcon className="w-4 h-4" />) as any}
                  onClick={() => applyMarkdownToolbarAction('link')}
                  disabled={editorDisabled}
                  aria-label={t('option:notesSearch.toolbarLinkTooltip', { defaultValue: 'Link' })}
                  data-testid="notes-toolbar-link"
                />
              </Tooltip>
              <Tooltip title={t('option:notesSearch.toolbarAttachmentTooltip', { defaultValue: 'Attachment' })}>
                <Button
                  size="small"
                  type="text"
                  icon={(<PaperclipIcon className="w-4 h-4" />) as any}
                  onClick={openAttachmentPicker}
                  disabled={editorDisabled}
                  aria-label={t('option:notesSearch.toolbarAttachmentTooltip', { defaultValue: 'Attachment' })}
                  data-testid="notes-toolbar-attachment"
                />
              </Tooltip>
              <Tooltip title={t('option:notesSearch.toolbarCodeTooltip', { defaultValue: 'Code' })}>
                <Button
                  size="small"
                  type="text"
                  icon={(<CodeIcon className="w-4 h-4" />) as any}
                  onClick={() => applyMarkdownToolbarAction('code')}
                  disabled={editorDisabled}
                  aria-label={t('option:notesSearch.toolbarCodeTooltip', { defaultValue: 'Code' })}
                  data-testid="notes-toolbar-code"
                />
              </Tooltip>
              <input
                ref={attachmentInputRef}
                type="file"
                multiple
                className="hidden"
                onChange={handleAttachmentInputChange}
                data-testid="notes-attachment-input"
              />
            </div>
          )}
          <div className="mt-2 flex-1 min-h-0">
            {editorMode === 'preview' ? (
              content.trim().length > 0 ? (
                <div className="h-full flex flex-col">
                  <Typography.Text
                    type="secondary"
                    className="block text-[11px] mb-2 text-text-muted"
                  >
                    {t('option:notesSearch.previewTitle', {
                      defaultValue: 'Preview (Markdown + LaTeX)'
                    })}
                  </Typography.Text>
                  <div
                    className="w-full flex-1 text-sm p-4 rounded-lg border border-border bg-surface2 overflow-auto"
                    onClick={handlePreviewLinkClick}
                    data-testid="notes-preview-surface"
                  >
                    <MarkdownPreview content={previewContent} size="sm" />
                  </div>
                </div>
              ) : (
                <Typography.Text
                  type="secondary"
                  className="block text-[11px] mt-1 text-text-muted"
                >
                  {t('option:notesSearch.emptyPreview', {
                    defaultValue:
                      'Start typing to see a live preview of your note.'
                  })}
                </Typography.Text>
              )
            ) : editorMode === 'split' ? (
              <div className="grid h-full min-h-0 grid-cols-1 gap-3 lg:grid-cols-2">
                <div className="flex min-h-0 flex-col">
                  <Typography.Text
                    type="secondary"
                    className="block text-[11px] mb-2 text-text-muted"
                  >
                    {t('option:notesSearch.editModeLabel', {
                      defaultValue: 'Edit'
                    })}
                  </Typography.Text>
                  <textarea
                    ref={contentTextareaRef}
                    className="w-full min-h-[220px] text-sm p-4 rounded-lg border border-border bg-surface2 text-text resize-none leading-relaxed focus:outline-none focus:ring-2 focus:ring-focus"
                    value={content}
                    onChange={handleEditorChange}
                    onKeyDown={handleEditorKeyDown}
                    onSelect={handleEditorSelectionUpdate}
                    onClick={handleEditorSelectionUpdate}
                    onKeyUp={handleEditorSelectionUpdate}
                    onFocus={handleEditorSelectionUpdate}
                    onBlur={() => setEditorCursorIndex(null)}
                    placeholder={t('option:notesSearch.editorPlaceholder', {
                      defaultValue: 'Write your note here... (Markdown supported)'
                    })}
                    readOnly={editorDisabled}
                    aria-label={t('option:notesSearch.editorAriaLabel', {
                      defaultValue: 'Note content'
                    })}
                  />
                  {activeWikilinkQuery && wikilinkSuggestions.length > 0 && (
                    <div
                      className="mt-2 rounded-lg border border-border bg-surface p-1"
                      role="listbox"
                      aria-label={t('option:notesSearch.wikilinkSuggestionsLabel', {
                        defaultValue: 'Wikilink suggestions'
                      })}
                      data-testid="notes-wikilink-suggestions"
                    >
                      {wikilinkSuggestions.map((candidate, index) => {
                        const duplicateCount =
                          wikilinkSuggestionDisplayCounts.get(candidate.title.toLowerCase()) || 0
                        const label =
                          duplicateCount > 1 ? `${candidate.title} (${candidate.id})` : candidate.title
                        return (
                          <button
                            key={`${candidate.id}-${candidate.title}`}
                            type="button"
                            className={`block w-full rounded px-2 py-1 text-left text-xs ${
                              index === wikilinkSelectionIndex
                                ? 'bg-surface2 text-text'
                                : 'text-text-muted hover:bg-surface2 hover:text-text'
                            }`}
                            aria-selected={index === wikilinkSelectionIndex}
                            onMouseDown={(event) => {
                              event.preventDefault()
                              applyWikilinkSuggestion(candidate)
                            }}
                            data-testid={`notes-wikilink-suggestion-${candidate.id.replace(/[^a-z0-9_-]/gi, '_')}`}
                          >
                            {label}
                          </button>
                        )
                      })}
                    </div>
                  )}
                  <Typography.Text
                    type="secondary"
                    className="block text-[11px] mt-1 text-text-muted"
                  >
                    {t('option:notesSearch.editorSupportHint', {
                      defaultValue: 'Markdown + LaTeX supported'
                    })}
                  </Typography.Text>
                </div>
                <div className="flex min-h-0 flex-col">
                  {content.trim().length > 0 ? (
                    <>
                      <Typography.Text
                        type="secondary"
                        className="block text-[11px] mb-2 text-text-muted"
                      >
                        {t('option:notesSearch.previewTitle', {
                          defaultValue: 'Preview (Markdown + LaTeX)'
                        })}
                      </Typography.Text>
                      <div
                        className="w-full flex-1 text-sm p-4 rounded-lg border border-border bg-surface2 overflow-auto"
                        onClick={handlePreviewLinkClick}
                        data-testid="notes-split-preview-surface"
                      >
                        <MarkdownPreview content={previewContent} size="sm" />
                      </div>
                    </>
                  ) : (
                    <Typography.Text
                      type="secondary"
                      className="block text-[11px] mt-1 text-text-muted"
                    >
                      {t('option:notesSearch.emptyPreview', {
                        defaultValue:
                          'Start typing to see a live preview of your note.'
                      })}
                    </Typography.Text>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex h-full min-h-0 flex-col">
                <textarea
                  ref={contentTextareaRef}
                  className="w-full min-h-[280px] text-sm p-4 rounded-lg border border-border bg-surface2 text-text resize-none leading-relaxed focus:outline-none focus:ring-2 focus:ring-focus"
                  value={content}
                  onChange={handleEditorChange}
                  onKeyDown={handleEditorKeyDown}
                  onSelect={handleEditorSelectionUpdate}
                  onClick={handleEditorSelectionUpdate}
                  onKeyUp={handleEditorSelectionUpdate}
                  onFocus={handleEditorSelectionUpdate}
                  onBlur={() => setEditorCursorIndex(null)}
                  placeholder={t('option:notesSearch.editorPlaceholder', {
                    defaultValue: 'Write your note here... (Markdown supported)'
                  })}
                  readOnly={editorDisabled}
                  aria-label={t('option:notesSearch.editorAriaLabel', {
                    defaultValue: 'Note content'
                  })}
                />
                {activeWikilinkQuery && wikilinkSuggestions.length > 0 && (
                  <div
                    className="mt-2 rounded-lg border border-border bg-surface p-1"
                    role="listbox"
                    aria-label={t('option:notesSearch.wikilinkSuggestionsLabel', {
                      defaultValue: 'Wikilink suggestions'
                    })}
                    data-testid="notes-wikilink-suggestions"
                  >
                    {wikilinkSuggestions.map((candidate, index) => {
                      const duplicateCount =
                        wikilinkSuggestionDisplayCounts.get(candidate.title.toLowerCase()) || 0
                      const label =
                        duplicateCount > 1 ? `${candidate.title} (${candidate.id})` : candidate.title
                      return (
                        <button
                          key={`${candidate.id}-${candidate.title}`}
                          type="button"
                          className={`block w-full rounded px-2 py-1 text-left text-xs ${
                            index === wikilinkSelectionIndex
                              ? 'bg-surface2 text-text'
                              : 'text-text-muted hover:bg-surface2 hover:text-text'
                          }`}
                          aria-selected={index === wikilinkSelectionIndex}
                          onMouseDown={(event) => {
                            event.preventDefault()
                            applyWikilinkSuggestion(candidate)
                          }}
                          data-testid={`notes-wikilink-suggestion-${candidate.id.replace(/[^a-z0-9_-]/gi, '_')}`}
                        >
                          {label}
                        </button>
                      )
                    })}
                  </div>
                )}
                <Typography.Text
                  type="secondary"
                  className="block text-[11px] mt-1 text-text-muted"
                >
                  {t('option:notesSearch.editorSupportHint', {
                    defaultValue: 'Markdown + LaTeX supported'
                  })}
                </Typography.Text>
              </div>
            )}
          </div>
          <div className="mt-2 border-t border-border pt-2">
            <Typography.Text
              type="secondary"
              className="text-[11px] text-text-muted"
              data-testid="notes-editor-metrics"
            >
              {metricSummaryText}
            </Typography.Text>
            <Typography.Text
              type="secondary"
              className="block text-[11px] text-text-muted mt-1"
              data-testid="notes-editor-revision-meta"
            >
              {revisionSummaryText}
            </Typography.Text>
          </div>
        </div>
      </div>
      {keywordPickerOpen && (
        <React.Suspense fallback={null}>
          <KeywordPickerModal
            open={keywordPickerOpen}
            availableKeywords={availableKeywords}
            filteredKeywordPickerOptions={filteredKeywordPickerOptions}
            keywordPickerQuery={keywordPickerQuery}
            keywordPickerSelection={keywordPickerSelection}
            onCancel={handleKeywordPickerCancel}
            onApply={handleKeywordPickerApply}
            onQueryChange={handleKeywordPickerQueryChange}
            onSelectionChange={handleKeywordPickerSelectionChange}
            onSelectAll={handleKeywordPickerSelectAll}
            onClear={handleKeywordPickerClear}
            t={t}
          />
        </React.Suspense>
      )}
      <NotesGraphModal
        open={graphModalOpen}
        noteId={selectedId}
        refreshToken={graphMutationTick}
        onClose={() => setGraphModalOpen(false)}
        onOpenNote={(noteId) => {
          void handleSelectNote(noteId)
        }}
      />
    </div>
  )
}

export default NotesManagerPage
