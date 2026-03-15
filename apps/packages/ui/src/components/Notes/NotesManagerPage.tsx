import React from 'react'
import type { InputRef } from 'antd'
import { Input, Typography, Select, Button, Modal, Checkbox } from 'antd'
import {
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { bgRequest } from '@/services/background-proxy'
import { useQuery, keepPreviousData, useQueryClient } from '@tanstack/react-query'
import { useServerOnline } from '@/hooks/useServerOnline'
import { useConfirmDanger } from '@/components/Common/confirm-danger'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useDemoMode } from '@/context/demo-mode'
import { useServerCapabilities } from '@/hooks/useServerCapabilities'
import { tldwClient } from '@/services/tldw/TldwApiClient'
import { useAntdMessage } from '@/hooks/useAntdMessage'
import { useStoreMessageOption } from "@/store/option"
import { shallow } from "zustand/shallow"
import { updatePageTitle } from "@/utils/update-page-title"
import { normalizeChatRole } from "@/utils/normalize-chat-role"
import NotesEditorPane from "@/components/Notes/NotesEditorPane"
import NotesSidebar from "@/components/Notes/NotesSidebar"
import NotesGraphModal from "@/components/Notes/NotesGraphModal"
import {
  buildSingleNoteCopyText,
  buildSingleNoteJson,
  buildSingleNoteMarkdown,
  buildSingleNotePrintableHtml,
  type SingleNoteCopyMode,
  type SingleNoteExportFormat
} from "@/components/Notes/export-utils"
import { useNotesKeywords } from "@/components/Notes/hooks/useNotesKeywords"
import type { NoteListItem } from "@/components/Notes/notes-manager-types"
import type { ActiveWikilinkQuery, WikilinkCandidate } from "@/components/Notes/wikilinks"
import {
  buildWikilinkIndex,
  getActiveWikilinkQuery,
  insertWikilinkAtCursor,
  renderContentWithResolvedWikilinks
} from "@/components/Notes/wikilinks"
import { translateMessage } from "@/i18n/translateMessage"
import { formatFileSize } from "@/utils/format"
import { clearSetting, getSetting, setSetting } from "@/services/settings/registry"
import { buildFlashcardsGenerateRoute } from "@/services/tldw/flashcards-generate-handoff"
import { useMobile } from "@/hooks/useMediaQuery"
import {
  LAST_NOTE_ID_SETTING,
  NOTES_NOTEBOOKS_SETTING,
  NOTES_PINNED_IDS_SETTING,
  NOTES_PAGE_SIZE_SETTING,
  NOTES_RECENT_OPENED_SETTING,
  NOTES_TITLE_SUGGEST_STRATEGY_SETTING,
  type NotesNotebookSetting,
  type NotesRecentOpenedEntry,
  type NotesTitleSuggestStrategy
} from "@/services/settings/ui-settings"

import type {
  SaveNoteOptions,
  SaveIndicatorState,
  NotesEditorMode,
  NotesInputMode,
  NotesSortOption,
  KeywordPickerSortMode,
  KeywordFrequencyTone,
  KeywordManagementItem,
  KeywordRenameDraft,
  KeywordMergeDraft,
  MarkdownToolbarAction,
  OfflineDraftEntry,
  OfflineDraftSyncResult,
  RemoteVersionInfo,
  NotesAssistAction,
  EditProvenanceState,
  MonitoringAlertSeverity,
  MonitoringNoticeState,
  ExportFormat,
  ExportProgressState,
  NotesListViewMode,
  MoodboardSummary,
  NotebookFilterOption,
  ImportDuplicateStrategy,
  PendingImportFile,
  NotesImportResponsePayload,
  NotesTitleSettingsResponse,
  NoteTemplateDefinition,
  NotesTocEntry,
  NoteWithKeywords,
  KeywordSyncWarning,
} from './notes-manager-types'
import {
  extractBacklink,
  extractKeywords,
  toNoteVersion,
  toNoteLastModified,
  toKeywordSyncWarning,
  normalizeConversationId,
  toConversationLabel,
  toAttachmentMarkdown,
  normalizeGraphNoteId,
  parseSourceNodeId,
  MIN_SIDEBAR_HEIGHT,
  NOTE_AUTOSAVE_DELAY_MS,
  NOTE_SEARCH_DEBOUNCE_MS,
  LARGE_NOTE_PREVIEW_THRESHOLD,
  LARGE_NOTE_PREVIEW_DELAY_MS,
  LARGE_NOTES_PAGINATION_THRESHOLD,
  TRASH_LOOKUP_PAGE_SIZE,
  TRASH_LOOKUP_MAX_PAGES,
  NOTES_OFFLINE_DRAFT_QUEUE_STORAGE_KEY,
  NOTES_OFFLINE_NEW_DRAFT_KEY,
  NOTES_LIST_REGION_ID,
  NOTES_EDITOR_REGION_ID,
  NOTES_SHORTCUTS_SUMMARY_ID,
  shouldIgnoreGlobalShortcut,
  isWithinRegion,
  isEditorSaveShortcutContext,
  calculateSidebarHeight,
  normalizeOfflineDraftQueue,
  NOTES_TITLE_STRATEGIES,
  NOTE_TEMPLATES,
  toKeywordTestIdSegment,
  normalizeNotebookKeywords,
  normalizeNotebookName,
  normalizeNotebookOptions,
  NOTEBOOK_COLLECTION_PAGE_SIZE,
  NOTEBOOK_COLLECTION_MAX_PAGES,
  normalizeNotebookKeywordsFromServer,
  normalizeNotebookCollectionFromServer,
  normalizeNotebookCollectionsResponse,
  buildNotebookDefaultName,
  stripInlineMarkdownForToc,
  slugifyHeading,
  extractMarkdownHeadings,
  escapeHtml,
  markdownInlineToHtml,
  markdownToWysiwygHtml,
  inlineNodeToMarkdown,
  blockNodeToMarkdown,
  wysiwygHtmlToMarkdown,
  detectImportFormatFromFileName,
  estimateDetectedNotesFromImportContent,
  NOTE_SORT_API_PARAMS,
  NOTE_ASSIST_STOP_WORDS,
  normalizeNotesTitleStrategy,
  deriveAllowedTitleStrategies,
  toSortableTimestamp,
  toSortableTitle,
  sortNoteRows,
  sortNotesByPinnedIds,
  buildSummaryDraft,
  buildOutlineDraft,
  suggestKeywordsDraft,
} from './notes-manager-utils'

const KeywordPickerModal = React.lazy(() => import('@/components/Notes/KeywordPickerModal'))

const NotesManagerPage: React.FC = () => {
  const { t } = useTranslation(['option', 'common'])
  const [query, setQuery] = React.useState('')
  const [queryInput, setQueryInput] = React.useState('')
  const [searchTipsQuery, setSearchTipsQuery] = React.useState('')
  const [exportProgress, setExportProgress] = React.useState<ExportProgressState | null>(null)
  const [importModalOpen, setImportModalOpen] = React.useState(false)
  const [importSubmitting, setImportSubmitting] = React.useState(false)
  const [importDuplicateStrategy, setImportDuplicateStrategy] =
    React.useState<ImportDuplicateStrategy>('create_copy')
  const [pendingImportFiles, setPendingImportFiles] = React.useState<PendingImportFile[]>([])
  const [page, setPage] = React.useState(1)
  const [pageSize, setPageSize] = React.useState(20)
  const [sortOption, setSortOption] = React.useState<NotesSortOption>('modified_desc')
  const [listMode, setListMode] = React.useState<'active' | 'trash'>('active')
  const [listViewMode, setListViewMode] = React.useState<NotesListViewMode>('list')
  const [moodboards, setMoodboards] = React.useState<MoodboardSummary[]>([])
  const [selectedMoodboardId, setSelectedMoodboardId] = React.useState<number | null>(null)
  const [notebookOptions, setNotebookOptions] = React.useState<NotebookFilterOption[]>([])
  const [selectedNotebookId, setSelectedNotebookId] = React.useState<number | null>(null)
  const [bulkSelectedIds, setBulkSelectedIds] = React.useState<string[]>([])
  const [total, setTotal] = React.useState(0)
  const [selectedId, setSelectedId] = React.useState<string | number | null>(null)
  const [title, setTitle] = React.useState('')
  const [content, setContent] = React.useState('')
  const [loadingDetail, setLoadingDetail] = React.useState(false)
  const [saving, setSaving] = React.useState(false)
  const [saveIndicator, setSaveIndicator] = React.useState<SaveIndicatorState>('idle')
  /* ---- keyword state is now in useNotesKeywords (initialized after deps are ready) ---- */
  const [originalMetadata, setOriginalMetadata] = React.useState<Record<string, any> | null>(null)
  const [selectedVersion, setSelectedVersion] = React.useState<number | null>(null)
  const [selectedLastSavedAt, setSelectedLastSavedAt] = React.useState<string | null>(null)
  const [offlineDraftQueue, setOfflineDraftQueue] = React.useState<Record<string, OfflineDraftEntry>>({})
  const [offlineDraftQueueHydrated, setOfflineDraftQueueHydrated] = React.useState(false)
  const [remoteVersionInfo, setRemoteVersionInfo] = React.useState<RemoteVersionInfo | null>(null)
  const [isDirty, setIsDirty] = React.useState(false)
  const [backlinkConversationId, setBacklinkConversationId] = React.useState<string | null>(null)
  const [conversationLabelById, setConversationLabelById] = React.useState<Record<string, string>>({})
  const [backlinkMessageId, setBacklinkMessageId] = React.useState<string | null>(null)
  const [openingLinkedChat, setOpeningLinkedChat] = React.useState(false)
  const [graphModalOpen, setGraphModalOpen] = React.useState(false)
  const [graphMutationTick, setGraphMutationTick] = React.useState(0)
  const [manualLinkTargetId, setManualLinkTargetId] = React.useState<string | null>(null)
  const [manualLinkSaving, setManualLinkSaving] = React.useState(false)
  const [manualLinkDeletingEdgeId, setManualLinkDeletingEdgeId] = React.useState<string | null>(null)
  const [titleSuggestionLoading, setTitleSuggestionLoading] = React.useState(false)
  const [assistLoadingAction, setAssistLoadingAction] = React.useState<NotesAssistAction | null>(null)
  const [editProvenance, setEditProvenance] = React.useState<EditProvenanceState>({ mode: 'manual' })
  const [monitoringNotice, setMonitoringNotice] = React.useState<MonitoringNoticeState | null>(
    null
  )
  const [recentNotes, setRecentNotes] = React.useState<NotesRecentOpenedEntry[]>([])
  const [pinnedNoteIds, setPinnedNoteIds] = React.useState<string[]>([])
  const [titleSuggestStrategy, setTitleSuggestStrategy] =
    React.useState<NotesTitleSuggestStrategy>('heuristic')
  const [editorMode, setEditorMode] = React.useState<NotesEditorMode>('edit')
  const [editorInputMode, setEditorInputMode] = React.useState<NotesInputMode>('markdown')
  const [wysiwygHtml, setWysiwygHtml] = React.useState<string>('<p><br/></p>')
  const [wysiwygSessionDirty, setWysiwygSessionDirty] = React.useState(false)
  const [editorCursorIndex, setEditorCursorIndex] = React.useState<number | null>(null)
  const [wikilinkSelectionIndex, setWikilinkSelectionIndex] = React.useState(0)
  const [largePreviewReady, setLargePreviewReady] = React.useState(true)
  const searchQueryTimeoutRef = React.useRef<number | null>(null)
  /* keywordSearchTimeoutRef moved to useNotesKeywords */
  const autosaveTimeoutRef = React.useRef<number | null>(null)
  const saveNoteRef = React.useRef<((opts?: { showSuccessMessage?: boolean }) => Promise<void>) | null>(null)
  const pageSizeSettingHydratedRef = React.useRef(false)
  const notebookSettingsHydratedRef = React.useRef(false)
  const bulkSelectionAnchorRef = React.useRef<string | null>(null)
  /* keywordPickerReturnFocusRef, keywordManagerReturnFocusRef, keywordSuggestionReturnFocusRef moved to useNotesKeywords */
  const graphModalReturnFocusRef = React.useRef<HTMLElement | null>(null)
  const contentTextareaRef = React.useRef<HTMLTextAreaElement | null>(null)
  const richEditorRef = React.useRef<HTMLDivElement | null>(null)
  const attachmentInputRef = React.useRef<HTMLInputElement | null>(null)
  const importInputRef = React.useRef<HTMLInputElement | null>(null)
  const markdownBeforeWysiwygRef = React.useRef<string | null>(null)
  const restoredInitialOfflineDraftRef = React.useRef(false)
  const pendingConversationLabelRequestsRef = React.useRef<Set<string>>(new Set())
  const offlineSyncInFlightRef = React.useRef(false)
  const offlineDraftQueueRef = React.useRef<Record<string, OfflineDraftEntry>>({})
  offlineDraftQueueRef.current = offlineDraftQueue
  const isOnline = useServerOnline()
  const isMobileViewport = useMobile()
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

  const capabilityDisabled = !capsLoading && capabilities && !capabilities.hasNotes
  const editorDisabled = Boolean(capabilityDisabled)

  const clearAutosaveTimeout = React.useCallback(() => {
    if (autosaveTimeoutRef.current != null) {
      window.clearTimeout(autosaveTimeoutRef.current)
      autosaveTimeoutRef.current = null
    }
  }, [])

  const clearSearchQueryTimeout = React.useCallback(() => {
    if (searchQueryTimeoutRef.current != null) {
      window.clearTimeout(searchQueryTimeoutRef.current)
      searchQueryTimeoutRef.current = null
    }
  }, [])

  const restoreFocusAfterOverlayClose = React.useCallback((target: HTMLElement | null) => {
    if (!target) return
    window.requestAnimationFrame(() => {
      if (target.isConnected) {
        target.focus()
      }
    })
  }, [])

  const markManualEdit = React.useCallback(() => {
    setEditProvenance((current) => (current.mode === 'manual' ? current : { mode: 'manual' }))
  }, [])

  const markGeneratedEdit = React.useCallback((action: NotesAssistAction) => {
    setEditProvenance({
      mode: 'generated',
      action,
      at: Date.now()
    })
  }, [])

  const selectedNotebook = React.useMemo(
    () =>
      selectedNotebookId == null
        ? null
        : notebookOptions.find((option) => option.id === selectedNotebookId) || null,
    [notebookOptions, selectedNotebookId]
  )
  const notebookKeywordTokens = React.useMemo(
    () =>
      selectedNotebook == null
        ? []
        : selectedNotebook.keywords
            .map((keyword) => String(keyword || '').trim().toLowerCase())
            .filter((keyword) => keyword.length > 0),
    [selectedNotebook]
  )

  const kw = useNotesKeywords({
    isOnline,
    listMode,
    message,
    confirmDanger,
    restoreFocusAfterOverlayClose,
    notebookKeywordTokens,
    queryClient,
    t,
    setPage,
    setIsDirty,
    setSaveIndicator: setSaveIndicator as (state: 'dirty' | 'saving' | 'saved' | 'error' | 'idle') => void,
    setMonitoringNotice,
    markGeneratedEdit,
  })
  const {
    keywordTokens, setKeywordTokens,
    keywordOptions, setKeywordOptions,
    allKeywords, allKeywordsRef,
    keywordNoteCountByKey, setKeywordNoteCountByKey,
    editorKeywords, setEditorKeywords,
    keywordPickerOpen, setKeywordPickerOpen,
    keywordPickerQuery, setKeywordPickerQuery,
    keywordPickerSelection, setKeywordPickerSelection,
    keywordPickerSortMode, setKeywordPickerSortMode,
    recentKeywordHistory,
    keywordManagerOpen,
    keywordManagerLoading,
    keywordManagerQuery, setKeywordManagerQuery,
    keywordManagerItems,
    keywordRenameDraft, setKeywordRenameDraft,
    keywordMergeDraft, setKeywordMergeDraft,
    keywordManagerActionLoading,
    keywordSuggestionOptions, setKeywordSuggestionOptions,
    keywordSuggestionSelection, setKeywordSuggestionSelection,
    keywordPickerReturnFocusRef, keywordManagerReturnFocusRef, keywordSuggestionReturnFocusRef,
    keywordSearchTimeoutRef,
    availableKeywords,
    filteredKeywordPickerOptions, sortedKeywordPickerOptions, recentKeywordPickerOptions,
    maxKeywordNoteCount, getKeywordFrequencyTone, renderKeywordLabelWithFrequency,
    keywordManagerVisibleItems, keywordMergeTargetOptions,
    rememberRecentKeywords,
    loadAllKeywords, loadKeywordManagementItems,
    refreshKeywordDataAfterManagement,
    openKeywordManager, closeKeywordManager, openKeywordManagerFromPicker,
    openKeywordPicker,
    handleKeywordManagerDelete, submitKeywordRename, submitKeywordMerge,
    loadKeywordSuggestions, debouncedLoadKeywordSuggestions,
    closeKeywordSuggestionModal, applySelectedSuggestedKeywords,
    handleKeywordFilterSearch, handleKeywordFilterChange,
  } = kw

  const currentOfflineDraftKey = React.useMemo(() => {
    if (selectedId == null) return NOTES_OFFLINE_NEW_DRAFT_KEY
    return `note:${String(selectedId)}`
  }, [selectedId])

  const buildCurrentOfflineDraft = React.useCallback(
    (
      overrides?: Partial<Pick<OfflineDraftEntry, 'syncState' | 'lastError' | 'updatedAt' | 'baseVersion'>>
    ): OfflineDraftEntry => {
      const nowIso = overrides?.updatedAt || new Date().toISOString()
      return {
        key: currentOfflineDraftKey,
        noteId: selectedId != null ? String(selectedId) : null,
        baseVersion:
          overrides?.baseVersion !== undefined
            ? overrides.baseVersion
            : selectedVersion != null
              ? selectedVersion
              : null,
        title,
        content,
        keywords: [...editorKeywords],
        metadata: originalMetadata ? { ...originalMetadata } : null,
        backlinkConversationId,
        backlinkMessageId,
        updatedAt: nowIso,
        syncState: overrides?.syncState || 'queued',
        lastError: overrides?.lastError ?? null
      }
    },
    [
      backlinkConversationId,
      backlinkMessageId,
      content,
      currentOfflineDraftKey,
      editorKeywords,
      originalMetadata,
      selectedId,
      selectedVersion,
      title
    ]
  )

  const applyOfflineDraftToEditor = React.useCallback((draft: OfflineDraftEntry) => {
    setTitle(String(draft.title || ''))
    setContent(String(draft.content || ''))
    setEditorKeywords(Array.isArray(draft.keywords) ? [...draft.keywords] : [])
    setOriginalMetadata(
      draft.metadata && typeof draft.metadata === 'object'
        ? { ...(draft.metadata as Record<string, any>) }
        : null
    )
    setBacklinkConversationId(draft.backlinkConversationId)
    setBacklinkMessageId(draft.backlinkMessageId)
    if (draft.baseVersion != null) {
      setSelectedVersion(draft.baseVersion)
    }
    setSelectedLastSavedAt(draft.updatedAt)
    setIsDirty(false)
    setSaveIndicator(draft.syncState === 'conflict' || draft.syncState === 'error' ? 'error' : 'saved')
    setEditProvenance({ mode: 'manual' })
    setMonitoringNotice(null)
    setRemoteVersionInfo(null)
    setEditorCursorIndex(null)
    setWikilinkSelectionIndex(0)
    setWysiwygHtml(markdownToWysiwygHtml(String(draft.content || '')))
    setWysiwygSessionDirty(false)
    markdownBeforeWysiwygRef.current = String(draft.content || '')
  }, [])

  const upsertOfflineDraft = React.useCallback(
    (
      overrides?: Partial<Pick<OfflineDraftEntry, 'syncState' | 'lastError' | 'updatedAt' | 'baseVersion'>>
    ) => {
      const nextDraft = buildCurrentOfflineDraft(overrides)
      setOfflineDraftQueue((current) => ({
        ...current,
        [nextDraft.key]: nextDraft
      }))
    },
    [buildCurrentOfflineDraft]
  )

  const removeOfflineDraftByKey = React.useCallback((key: string) => {
    const normalized = String(key || '').trim()
    if (!normalized) return
    setOfflineDraftQueue((current) => {
      if (!current[normalized]) return current
      const next = { ...current }
      delete next[normalized]
      return next
    })
  }, [])

  const queuedOfflineDraftCount = React.useMemo(() => {
    return Object.values(offlineDraftQueue).filter((draft) => {
      return (
        draft.syncState === 'queued' ||
        draft.syncState === 'syncing' ||
        draft.syncState === 'error' ||
        draft.syncState === 'conflict'
      )
    }).length
  }, [offlineDraftQueue])

  const currentOfflineDraft = offlineDraftQueue[currentOfflineDraftKey] || null

  const offlineStatusText = React.useMemo(() => {
    if (!offlineDraftQueueHydrated) return null
    if (!isOnline) {
      if (currentOfflineDraft) {
        return t('option:notesSearch.offlineDraftQueuedStatus', {
          defaultValue: 'Offline: changes stored locally and queued for sync.'
        })
      }
      return t('option:notesSearch.offlineEditingStatus', {
        defaultValue: 'Offline: local draft persistence is active.'
      })
    }
    if (!currentOfflineDraft && queuedOfflineDraftCount <= 0) return null
    if (currentOfflineDraft?.syncState === 'syncing') {
      return t('option:notesSearch.offlineSyncingStatus', {
        defaultValue: 'Syncing queued offline draft...'
      })
    }
    if (currentOfflineDraft?.syncState === 'conflict') {
      return t('option:notesSearch.offlineConflictStatus', {
        defaultValue: 'Offline sync conflict: server has a newer version.'
      })
    }
    if (currentOfflineDraft?.syncState === 'error') {
      return t('option:notesSearch.offlineSyncErrorStatus', {
        defaultValue: 'Queued sync failed. Will retry automatically on reconnect.'
      })
    }
    if (queuedOfflineDraftCount > 0) {
      return t('option:notesSearch.offlineQueuedCountStatus', {
        defaultValue: '{{count}} offline draft(s) pending sync.',
        count: queuedOfflineDraftCount
      })
    }
    return null
  }, [currentOfflineDraft, isOnline, offlineDraftQueueHydrated, queuedOfflineDraftCount, t])

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

  const provenanceSummaryText = React.useMemo(() => {
    if (editProvenance.mode === 'manual') {
      return t('option:notesSearch.provenanceManual', {
        defaultValue: 'Edit source: Manual'
      })
    }
    const actionLabel =
      editProvenance.action === 'summarize'
        ? t('option:notesSearch.assistSummarizeAction', { defaultValue: 'Summarize' })
        : editProvenance.action === 'expand_outline'
          ? t('option:notesSearch.assistExpandOutlineAction', { defaultValue: 'Expand outline' })
          : t('option:notesSearch.assistSuggestKeywordsAction', { defaultValue: 'Suggest keywords' })
    const generatedAt = new Date(editProvenance.at).toLocaleTimeString()
    const generatedPrefix = t('option:notesSearch.provenanceGeneratedPrefix', {
      defaultValue: 'Edit source: Generated'
    })
    return `${generatedPrefix} (${actionLabel} at ${generatedAt})`
  }, [editProvenance, t])

  const monitoringNoticeClasses = React.useMemo(() => {
    if (!monitoringNotice) return ''
    if (monitoringNotice.severity === 'critical') {
      return 'border-danger/50 bg-danger/10 text-danger'
    }
    if (monitoringNotice.severity === 'warning') {
      return 'border-warn/50 bg-warn/10 text-warn'
    }
    return 'border-primary/40 bg-primary/10 text-primary'
  }, [monitoringNotice])

  /* markManualEdit, markGeneratedEdit, keyword hook moved before buildCurrentOfflineDraft */

  const rememberRecentNote = React.useCallback((noteId: string | number, noteTitle: string) => {
    const normalizedId = String(noteId || '').trim()
    const normalizedTitle = String(noteTitle || '').trim()
    if (!normalizedId || !normalizedTitle) return
    setRecentNotes((current) => {
      const next = [
        { id: normalizedId, title: normalizedTitle },
        ...current.filter((entry) => entry.id !== normalizedId)
      ].slice(0, 5)
      void setSetting(NOTES_RECENT_OPENED_SETTING, next)
      return next
    })
  }, [])

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

  const setContentDirty = React.useCallback(
    (
      nextContent: string,
      options?: {
        provenance?: 'manual' | NotesAssistAction
      }
    ) => {
      setContent(nextContent)
      setIsDirty(true)
      setSaveIndicator('dirty')
      setMonitoringNotice(null)
      if (options?.provenance && options.provenance !== 'manual') {
        markGeneratedEdit(options.provenance)
      } else {
        markManualEdit()
      }
    },
    [markGeneratedEdit, markManualEdit]
  )

  const applyMarkdownToolbarAction = React.useCallback(
    (action: MarkdownToolbarAction) => {
      if (editorDisabled) return
      if (editorInputMode === 'wysiwyg') {
        const richEditor = richEditorRef.current
        if (!richEditor) return
        richEditor.focus()
        const execute = (command: string, value?: string) => {
          if (typeof document === 'undefined') return
          if (typeof document.execCommand !== 'function') return
          document.execCommand(command, false, value)
        }

        if (action === 'bold') {
          execute('bold')
        } else if (action === 'italic') {
          execute('italic')
        } else if (action === 'heading') {
          execute('formatBlock', '<h2>')
        } else if (action === 'list') {
          execute('insertUnorderedList')
        } else if (action === 'link') {
          const href =
            typeof window !== 'undefined'
              ? window.prompt('Link URL', 'https://')
              : 'https://'
          const normalizedHref = String(href || '').trim()
          if (!normalizedHref) return
          execute('createLink', normalizedHref)
        } else if (action === 'code') {
          execute('insertText', '`code`')
        }

        const nextHtml = richEditor.innerHTML
        setWysiwygHtml(nextHtml)
        setWysiwygSessionDirty(true)
        const nextMarkdown = wysiwygHtmlToMarkdown(nextHtml)
        setContentDirty(nextMarkdown)
        setEditorCursorIndex(nextMarkdown.length)
        return
      }
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
    [content, editorDisabled, editorInputMode, resizeEditorTextarea, setContentDirty]
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
      const inputElement = event.target
      if (selectedId == null) {
        inputElement.value = ''
        message.warning(
          t('option:notesSearch.attachmentSaveFirstWarning', {
            defaultValue: 'Save this note once before adding attachments.'
          })
        )
        return
      }
      const noteId = String(selectedId)
      const selectedFiles = Array.from(files)
      const textarea = contentTextareaRef.current
      if (!textarea && editorInputMode !== 'wysiwyg') {
        inputElement.value = ''
        return
      }
      void (async () => {
        const uploadedMarkdown: string[] = []
        let failedUploads = 0
        for (const file of selectedFiles) {
          const formData = new FormData()
          formData.append('file', file)
          try {
            const result = await bgRequest<any>({
              path: `/api/v1/notes/${encodeURIComponent(noteId)}/attachments` as any,
              method: 'POST' as any,
              body: formData
            })
            const attachmentUrl = String(result?.url || '').trim()
            if (!attachmentUrl) {
              failedUploads += 1
              continue
            }
            const attachmentName = String(result?.file_name || file.name || '').trim() || file.name
            const attachmentContentType =
              typeof result?.content_type === 'string' ? result.content_type : file.type
            uploadedMarkdown.push(
              toAttachmentMarkdown(attachmentName, attachmentUrl, attachmentContentType)
            )
          } catch {
            failedUploads += 1
          }
        }

        if (uploadedMarkdown.length === 0) {
          message.error(
            t('option:notesSearch.attachmentUploadFailed', {
              defaultValue: 'Attachment upload failed. Please try again.'
            })
          )
          return
        }

        const markdown = uploadedMarkdown.join('\n')
        if (editorInputMode === 'wysiwyg') {
          const nextContent = content.trim().length > 0 ? `${content}\n${markdown}` : markdown
          setContentDirty(nextContent)
          setWysiwygHtml(markdownToWysiwygHtml(nextContent))
          setWysiwygSessionDirty(true)
          window.requestAnimationFrame(() => {
            richEditorRef.current?.focus()
          })
        } else {
          const activeTextarea = contentTextareaRef.current
          if (!activeTextarea) {
            return
          }
          activeTextarea.focus()
          const start = activeTextarea.selectionStart ?? content.length
          const end = activeTextarea.selectionEnd ?? start
          const nextContent = `${content.slice(0, start)}${markdown}${content.slice(end)}`
          setContentDirty(nextContent)
          const cursor = start + markdown.length
          window.requestAnimationFrame(() => {
            const refreshedTextarea = contentTextareaRef.current
            if (!refreshedTextarea) return
            refreshedTextarea.focus()
            refreshedTextarea.setSelectionRange(cursor, cursor)
            setEditorCursorIndex(cursor)
            resizeEditorTextarea()
          })
        }

        if (failedUploads > 0) {
          message.warning(
            t('option:notesSearch.attachmentUploadPartial', {
              defaultValue: 'Uploaded {{uploaded}} attachment(s); {{failed}} failed.',
              uploaded: uploadedMarkdown.length,
              failed: failedUploads
            })
          )
        } else {
          message.success(
            t('option:notesSearch.attachmentUploadSuccess', {
              defaultValue: 'Uploaded {{count}} attachment(s).',
              count: uploadedMarkdown.length
            })
          )
        }
      })().finally(() => {
        inputElement.value = ''
      })
    },
    [content, editorInputMode, message, resizeEditorTextarea, selectedId, setContentDirty, t]
  )

  const effectiveKeywordTokens = React.useMemo(() => {
    const merged = [...keywordTokens, ...notebookKeywordTokens]
    const deduped: string[] = []
    for (const token of merged) {
      const normalized = String(token || '').trim().toLowerCase()
      if (!normalized) continue
      if (deduped.includes(normalized)) continue
      deduped.push(normalized)
    }
    return deduped
  }, [keywordTokens, notebookKeywordTokens])

  const fetchMoodboards = React.useCallback(async (): Promise<MoodboardSummary[]> => {
    const pageLimit = 200
    const maxPages = 50
    const collected: any[] = []
    let offset = 0

    for (let pageIndex = 0; pageIndex < maxPages; pageIndex += 1) {
      const res = await bgRequest<any>({
        path: `/api/v1/notes/moodboards?limit=${pageLimit}&offset=${offset}` as any,
        method: "GET" as any
      })
      const rows = Array.isArray(res?.moodboards)
        ? res.moodboards
        : Array.isArray(res?.items)
          ? res.items
          : Array.isArray(res)
            ? res
            : []

      if (!Array.isArray(rows) || rows.length === 0) break
      collected.push(...rows)

      const paginationTotalRaw = Number(
        res?.total ??
          res?.pagination?.total_items ??
          NaN
      )
      if (Number.isFinite(paginationTotalRaw) && collected.length >= paginationTotalRaw) break
      if (rows.length < pageLimit) break

      offset += pageLimit
    }

    const deduped = new Map<number, any>()
    for (const row of collected) {
      const id = Number(row?.id)
      if (!Number.isFinite(id)) continue
      deduped.set(Math.floor(id), row)
    }

    return Array.from(deduped.values())
      .map((item: any) => {
        const id = Number(item?.id)
        if (!Number.isFinite(id)) return null
        return {
          id: Math.floor(id),
          name: String(item?.name || "").trim() || `Moodboard ${id}`,
          description: item?.description ?? null,
          smart_rule: item?.smart_rule ?? null,
          version:
            typeof item?.version === "number"
              ? item.version
              : Number.isFinite(Number(item?.version))
                ? Number(item.version)
                : undefined,
          last_modified:
            typeof item?.last_modified === "string" ? item.last_modified : undefined
        } as MoodboardSummary
      })
      .filter((item): item is MoodboardSummary => item != null)
  }, [])

  const {
    data: moodboardData,
    isFetching: isMoodboardsFetching,
    refetch: refetchMoodboards
  } = useQuery({
    queryKey: ["notes-moodboards", listMode, listViewMode],
    queryFn: fetchMoodboards,
    enabled: isOnline && listMode === "active" && listViewMode === "moodboard"
  })

  React.useEffect(() => {
    const nextMoodboards = Array.isArray(moodboardData) ? moodboardData : []
    setMoodboards(nextMoodboards)
    if (nextMoodboards.length === 0) {
      setSelectedMoodboardId(null)
      return
    }
    setSelectedMoodboardId((current) => {
      if (current != null && nextMoodboards.some((item) => item.id === current)) return current
      return nextMoodboards[0].id
    })
  }, [moodboardData])

  const selectedMoodboard = React.useMemo(() => {
    if (selectedMoodboardId == null) return null
    return moodboards.find((item) => item.id === selectedMoodboardId) || null
  }, [moodboards, selectedMoodboardId])

  const createMoodboard = React.useCallback(async () => {
    const name = String(window.prompt("Moodboard name") || "").trim()
    if (!name) return
    try {
      const created = await bgRequest<any>({
        path: "/api/v1/notes/moodboards" as any,
        method: "POST" as any,
        body: { name }
      })
      const createdId = Number(created?.id)
      await refetchMoodboards()
      if (Number.isFinite(createdId)) {
        setSelectedMoodboardId(Math.floor(createdId))
      }
      setListViewMode("moodboard")
      setPage(1)
      message.success(`Created moodboard "${name}"`)
    } catch {
      message.error("Could not create moodboard")
    }
  }, [message, refetchMoodboards])

  const renameMoodboard = React.useCallback(async () => {
    if (!selectedMoodboard) {
      message.warning("Select a moodboard first")
      return
    }
    const nextName = String(window.prompt("Rename moodboard", selectedMoodboard.name) || "").trim()
    if (!nextName || nextName === selectedMoodboard.name) return
    const expectedVersion = selectedMoodboard.version ?? 1
    try {
      await bgRequest({
        path: `/api/v1/notes/moodboards/${selectedMoodboard.id}` as any,
        method: "PATCH" as any,
        headers: { "expected-version": String(expectedVersion) } as any,
        body: { name: nextName }
      })
      await refetchMoodboards()
      message.success(`Renamed moodboard to "${nextName}"`)
    } catch {
      message.error("Could not rename moodboard")
    }
  }, [message, refetchMoodboards, selectedMoodboard])

  const deleteMoodboard = React.useCallback(async () => {
    if (!selectedMoodboard) {
      message.warning("Select a moodboard first")
      return
    }
    const ok = await confirmDanger({
      title: "Delete moodboard?",
      content: `Delete "${selectedMoodboard.name}"?`,
      okText: "Delete",
      cancelText: "Cancel"
    })
    if (!ok) return
    const expectedVersion = selectedMoodboard.version ?? 1
    try {
      await bgRequest({
        path: `/api/v1/notes/moodboards/${selectedMoodboard.id}` as any,
        method: "DELETE" as any,
        headers: { "expected-version": String(expectedVersion) } as any
      })
      await refetchMoodboards()
      setPage(1)
      message.success("Moodboard deleted")
    } catch {
      message.error("Could not delete moodboard")
    }
  }, [confirmDanger, message, refetchMoodboards, selectedMoodboard])

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
    params.set('sort_by', NOTE_SORT_API_PARAMS[sortOption].sortBy)
    params.set('sort_order', NOTE_SORT_API_PARAMS[sortOption].sortOrder)
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

    return { items: sortNoteRows(items, sortOption), total }
  }

  const fetchNotes = async (): Promise<NoteListItem[]> => {
    const mapNoteListItem = (n: any): NoteListItem => {
      const links = extractBacklink(n)
      const keywords = extractKeywords(n)
      return {
        id: n?.id,
        title: n?.title,
        content: n?.content ?? n?.content_preview,
        content_preview: n?.content_preview ?? null,
        updated_at: n?.updated_at ?? n?.last_modified ?? n?.lastModified,
        deleted: Boolean(n?.deleted),
        conversation_id: links.conversation_id,
        message_id: links.message_id,
        keywords,
        cover_image_url:
          typeof n?.cover_image_url === 'string' && n.cover_image_url.trim().length > 0
            ? n.cover_image_url
            : null,
        membership_source:
          n?.membership_source === 'manual' ||
          n?.membership_source === 'smart' ||
          n?.membership_source === 'both'
            ? n.membership_source
            : undefined,
        version: toNoteVersion(n) ?? undefined
      }
    }

    if (listMode === 'trash') {
      const params = new URLSearchParams()
      params.set('limit', String(pageSize))
      params.set('offset', String((page - 1) * pageSize))
      params.set('include_keywords', 'true')
      params.set('sort_by', NOTE_SORT_API_PARAMS[sortOption].sortBy)
      params.set('sort_order', NOTE_SORT_API_PARAMS[sortOption].sortOrder)
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
      return sortNoteRows(items, sortOption).map(mapNoteListItem)
    }

    if (listViewMode === 'moodboard') {
      if (selectedMoodboardId == null) {
        setTotal(0)
        return []
      }
      const params = new URLSearchParams()
      params.set('limit', String(pageSize))
      params.set('offset', String((page - 1) * pageSize))
      const res = await bgRequest<any>({
        path: `/api/v1/notes/moodboards/${selectedMoodboardId}/notes?${params.toString()}` as any,
        method: 'GET' as any
      })
      const items = Array.isArray(res?.notes)
        ? res.notes
        : Array.isArray(res?.items)
          ? res.items
          : Array.isArray(res)
            ? res
            : []
      const totalItems =
        Number(
          res?.total ??
            res?.count ??
            res?.pagination?.total_items ??
            items.length ??
            0
        ) || 0
      setTotal(totalItems)
      return items.map(mapNoteListItem)
    }

    const q = query.trim()
    const toks = effectiveKeywordTokens.map((k) => k.toLowerCase())
    // Prefer search when query or keyword filters are present
    if (q || toks.length > 0) {
      const { items, total } = await fetchFilteredNotesRaw(q, toks, page, pageSize)
      setTotal(total)
      return items.map(mapNoteListItem)
    }
    // Browse list with pagination when no filters
    const browsePath =
      (`/api/v1/notes/?page=${page}&results_per_page=${pageSize}` +
        `&sort_by=${NOTE_SORT_API_PARAMS[sortOption].sortBy}` +
        `&sort_order=${NOTE_SORT_API_PARAMS[sortOption].sortOrder}`) as `/${string}`
    const res = await bgRequest<any>({
      path: browsePath,
      method: 'GET' as any
    })
    const items = Array.isArray(res?.items) ? res.items : (Array.isArray(res) ? res : [])
    const pagination = res?.pagination
    setTotal(Number(pagination?.total_items || items.length || 0))
    return sortNoteRows(items, sortOption).map(mapNoteListItem)
  }

  const { data, isFetching, refetch } = useQuery({
    queryKey: [
      'notes',
      listMode,
      listViewMode,
      selectedMoodboardId ?? 'none',
      query,
      page,
      pageSize,
      sortOption,
      selectedNotebookId ?? 'none',
      effectiveKeywordTokens.join('|')
    ],
    queryFn: fetchNotes,
    placeholderData: keepPreviousData,
    enabled: isOnline
  })

  const pinnedNoteIdSet = React.useMemo(() => new Set(pinnedNoteIds), [pinnedNoteIds])
  const visibleNotes = React.useMemo(() => {
    if (!Array.isArray(data)) return []
    if (listMode !== 'active') return data
    if (listViewMode === 'moodboard') return data
    return sortNotesByPinnedIds(data, pinnedNoteIdSet)
  }, [data, listMode, listViewMode, pinnedNoteIdSet])

  const filteredCount = visibleNotes.length
  const moodboardTotalPages = React.useMemo(() => {
    const normalizedPageSize = Math.max(1, Number(pageSize) || 1)
    return Math.max(1, Math.ceil(Math.max(0, Number(total) || 0) / normalizedPageSize))
  }, [pageSize, total])
  const moodboardCanGoPrev = page > 1
  const moodboardCanGoNext = page < moodboardTotalPages
  const moodboardRangeStart = total <= 0 ? 0 : (page - 1) * pageSize + 1
  const moodboardRangeEnd = total <= 0 ? 0 : Math.min(total, page * pageSize)

  React.useEffect(() => {
    if (listMode !== 'active' || listViewMode !== 'moodboard') return
    if (page <= moodboardTotalPages) return
    setPage(moodboardTotalPages)
  }, [listMode, listViewMode, moodboardTotalPages, page])

  const orderedVisibleNoteIds = React.useMemo(
    () => visibleNotes.map((note) => String(note.id)),
    [visibleNotes]
  )
  const bulkSelectedIdSet = React.useMemo(
    () => new Set(bulkSelectedIds),
    [bulkSelectedIds]
  )
  const selectedBulkNotes = React.useMemo(
    () => visibleNotes.filter((note) => bulkSelectedIdSet.has(String(note.id))),
    [bulkSelectedIdSet, visibleNotes]
  )
  const selectedNotePinned =
    selectedId != null && pinnedNoteIdSet.has(String(selectedId))

  const toggleNotePinned = React.useCallback(
    async (id: string | number) => {
      const targetId = String(id || '').trim()
      if (!targetId) return
      const currentlyPinned = pinnedNoteIdSet.has(targetId)
      const nextPinnedIds = currentlyPinned
        ? pinnedNoteIds.filter((entry) => entry !== targetId)
        : [targetId, ...pinnedNoteIds.filter((entry) => entry !== targetId)].slice(0, 500)
      setPinnedNoteIds(nextPinnedIds)
      try {
        await setSetting(NOTES_PINNED_IDS_SETTING, nextPinnedIds)
      } catch {
        // Keep UI state even if persistence fails.
      }
      if (currentlyPinned) {
        message.info('Note unpinned')
      } else {
        message.success('Note pinned to top')
      }
    },
    [message, pinnedNoteIdSet, pinnedNoteIds]
  )
  const showLargeListPaginationHint =
    listMode === 'active' &&
    listViewMode !== 'moodboard' &&
    total >= LARGE_NOTES_PAGINATION_THRESHOLD
  const hasActiveFilters =
    listMode === 'active' &&
    listViewMode !== 'moodboard' &&
    (queryInput.trim().length > 0 || effectiveKeywordTokens.length > 0 || selectedNotebookId != null)
  const activeFilterSummary = React.useMemo(() => {
    if (!hasActiveFilters || listMode !== 'active') return null
    const effectiveQuery = query.trim() || queryInput.trim()
    const details: string[] = []
    if (effectiveQuery) {
      details.push(
        `${t('option:notesSearch.summaryQueryLabel', {
          defaultValue: 'Query'
        })}: "${effectiveQuery}"`
      )
    }
    if (selectedNotebook != null) {
      details.push(
        `${t('option:notesSearch.summaryNotebookLabel', {
          defaultValue: 'Smart collection'
        })}: ${selectedNotebook.name}`
      )
    }
    if (keywordTokens.length > 0) {
      details.push(
        `${t('option:notesSearch.summaryKeywordsLabel', {
          defaultValue: 'Keywords'
        })}: ${keywordTokens.join(', ')}`
      )
    }
    const countText = `${t('option:notesSearch.summaryShowing', {
      defaultValue: 'Showing'
    })} ${filteredCount} ${t('option:notesSearch.summaryOf', {
      defaultValue: 'of'
    })} ${total} ${t('option:notesSearch.summaryNotes', {
      defaultValue: 'notes'
    })}`
    return {
      countText,
      detailsText: details.join(' + ')
    }
  }, [
    filteredCount,
    hasActiveFilters,
    keywordTokens,
    listMode,
    query,
    queryInput,
    selectedNotebook,
    t,
    total
  ])

  const conversationIdsToResolve = React.useMemo(() => {
    const ids = new Set<string>()
    for (const note of visibleNotes) {
      const normalized = normalizeConversationId(note?.conversation_id)
      if (normalized) ids.add(normalized)
    }
    const selectedConversationId = normalizeConversationId(backlinkConversationId)
    if (selectedConversationId) ids.add(selectedConversationId)
    return Array.from(ids)
  }, [backlinkConversationId, visibleNotes])

  const backlinkConversationLabel = React.useMemo(() => {
    const id = normalizeConversationId(backlinkConversationId)
    if (!id) return null
    return conversationLabelById[id] || null
  }, [backlinkConversationId, conversationLabelById])

  const resolveConversationLabels = React.useCallback(
    async (conversationIds: string[]) => {
      const pending = conversationIds.filter((conversationId) => {
        if (!conversationId) return false
        if (conversationLabelById[conversationId]) return false
        if (pendingConversationLabelRequestsRef.current.has(conversationId)) return false
        return true
      })
      if (pending.length === 0) return
      pending.forEach((conversationId) =>
        pendingConversationLabelRequestsRef.current.add(conversationId)
      )

      try {
        await tldwClient.initialize().catch(() => null)
        const settled = await Promise.allSettled(
          pending.map(async (conversationId) => {
            const chat = await tldwClient.getChat(conversationId)
            const label = toConversationLabel(chat)
            return { conversationId, label }
          })
        )
        setConversationLabelById((current) => {
          let next: Record<string, string> | null = null
          for (const result of settled) {
            if (result.status !== 'fulfilled') continue
            const { conversationId, label } = result.value
            if (!label) continue
            if (current[conversationId]) continue
            if (next == null) next = { ...current }
            next[conversationId] = label
          }
          return next ?? current
        })
      } finally {
        pending.forEach((conversationId) =>
          pendingConversationLabelRequestsRef.current.delete(conversationId)
        )
      }
    },
    [conversationLabelById]
  )

  const { data: notesTitleSettings } = useQuery({
    queryKey: ['notes-title-settings'],
    enabled: isOnline,
    staleTime: 5 * 60 * 1000,
    queryFn: async () => {
      try {
        const settings = await bgRequest<NotesTitleSettingsResponse>({
          path: '/api/v1/admin/notes/title-settings' as any,
          method: 'GET' as any
        })
        return settings
      } catch {
        return null
      }
    }
  })

  const allowedTitleStrategies = React.useMemo(
    () => deriveAllowedTitleStrategies(notesTitleSettings),
    [notesTitleSettings]
  )

  const canSwitchTitleStrategy = allowedTitleStrategies.length > 1

  const effectiveTitleSuggestStrategy = React.useMemo<NotesTitleSuggestStrategy>(() => {
    const preferred = normalizeNotesTitleStrategy(titleSuggestStrategy)
    if (preferred && allowedTitleStrategies.includes(preferred)) {
      return preferred
    }
    const fromServer = normalizeNotesTitleStrategy(
      notesTitleSettings?.effective_strategy ?? notesTitleSettings?.default_strategy
    )
    if (fromServer && allowedTitleStrategies.includes(fromServer)) {
      return fromServer
    }
    return allowedTitleStrategies[0] ?? 'heuristic'
  }, [allowedTitleStrategies, notesTitleSettings, titleSuggestStrategy])

  const titleStrategyOptions = React.useMemo(() => {
    return allowedTitleStrategies.map((strategy) => {
      if (strategy === 'llm') {
        return {
          value: strategy,
          label: t('option:notesSearch.titleStrategyLlm', {
            defaultValue: 'LLM (quality)'
          })
        }
      }
      if (strategy === 'llm_fallback') {
        return {
          value: strategy,
          label: t('option:notesSearch.titleStrategyLlmFallback', {
            defaultValue: 'LLM fallback'
          })
        }
      }
      return {
        value: strategy,
        label: t('option:notesSearch.titleStrategyHeuristic', {
          defaultValue: 'Heuristic (fast)'
        })
      }
    })
  }, [allowedTitleStrategies, t])

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
        path: `/api/v1/notes/${noteId}/neighbors?edge_types=manual,wikilink,backlink,source_membership&max_nodes=80&max_edges=200` as any,
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
    const sourceNodeMap = new Map<string, { id: string; label: string }>()
    for (const node of nodes) {
      const nodeType = String(node?.type || '')
      if (!nodeType || nodeType === 'note') {
        const normalizedId = normalizeGraphNoteId(node?.id)
        if (!normalizedId) continue
        noteNodeMap.set(normalizedId, {
          id: normalizedId,
          title: String(node?.label || node?.title || `Note ${normalizedId}`)
        })
        continue
      }
      if (nodeType === 'source') {
        const sourceId = String(node?.id || '').trim()
        if (!sourceId) continue
        sourceNodeMap.set(sourceId, {
          id: sourceId,
          label: String(node?.label || sourceId)
        })
      }
    }

    const relatedIds = new Set<string>()
    const backlinkIds = new Set<string>()
    const sourceIds = new Set<string>()
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
      if (type === 'source_membership') {
        if (source === selectedNormalized && sourceNodeMap.has(target)) {
          sourceIds.add(target)
        }
        if (target === selectedNormalized && sourceNodeMap.has(source)) {
          sourceIds.add(source)
        }
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

    const sourceItems = Array.from(sourceIds)
      .map((id) => {
        const sourceNode = sourceNodeMap.get(id)
        if (!sourceNode) return null
        return {
          id: sourceNode.id,
          label: sourceNode.label
        }
      })
      .filter(
        (item): item is { id: string; label: string } => item != null
      )
      .sort((a, b) => a.label.localeCompare(b.label))

    return {
      related: toItems(relatedIds),
      backlinks: toItems(backlinkIds),
      manualLinks: Array.from(manualLinkByEdgeId.values()).sort((a, b) =>
        a.title.localeCompare(b.title)
      ),
      sources: sourceItems
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
  const tocEntries = React.useMemo(() => extractMarkdownHeadings(content), [content])
  const shouldShowToc = tocEntries.length >= 3

  const usesLargePreviewGuardrails = React.useMemo(
    () =>
      previewContent.trim().length >= LARGE_NOTE_PREVIEW_THRESHOLD &&
      (editorMode === 'preview' || editorMode === 'split'),
    [editorMode, previewContent]
  )

  /* keyword callbacks (availableKeywords .. loadAllKeywords useEffect) moved to useNotesKeywords */

  const handleKeywordPickerCancel = React.useCallback(() => {
    setKeywordPickerOpen(false)
    restoreFocusAfterOverlayClose(keywordPickerReturnFocusRef.current)
  }, [restoreFocusAfterOverlayClose])

  const handleKeywordPickerApply = React.useCallback(() => {
    setKeywordTokens(keywordPickerSelection)
    rememberRecentKeywords(keywordPickerSelection)
    setPage(1)
    setKeywordPickerOpen(false)
    restoreFocusAfterOverlayClose(keywordPickerReturnFocusRef.current)
  }, [keywordPickerSelection, rememberRecentKeywords, restoreFocusAfterOverlayClose])

  const openGraphModal = React.useCallback(() => {
    graphModalReturnFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null
    setGraphModalOpen(true)
  }, [])

  const closeGraphModal = React.useCallback(() => {
    setGraphModalOpen(false)
    restoreFocusAfterOverlayClose(graphModalReturnFocusRef.current)
  }, [restoreFocusAfterOverlayClose])

  const handleKeywordPickerQueryChange = React.useCallback((value: string) => {
    setKeywordPickerQuery(value)
  }, [])

  const handleKeywordPickerSelectionChange = React.useCallback((vals: string[]) => {
    setKeywordPickerSelection(vals)
  }, [])

  const handleKeywordPickerSortModeChange = React.useCallback((mode: KeywordPickerSortMode) => {
    setKeywordPickerSortMode(mode)
  }, [])

  const handleToggleRecentKeyword = React.useCallback((keyword: string) => {
    setKeywordPickerSelection((current) => {
      if (current.includes(keyword)) {
        return current.filter((entry) => entry !== keyword)
      }
      return [...current, keyword]
    })
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
      const loadedTitle = String(d?.title || `Note ${id}`)
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
      setEditProvenance({ mode: 'manual' })
      setMonitoringNotice(null)
      setRemoteVersionInfo(null)
      setEditorCursorIndex(0)
      setWikilinkSelectionIndex(0)
      setWysiwygHtml(markdownToWysiwygHtml(String(d?.content || '')))
      setWysiwygSessionDirty(false)
      markdownBeforeWysiwygRef.current = String(d?.content || '')
      rememberRecentNote(id, loadedTitle)
      const queuedDraft = offlineDraftQueueRef.current[`note:${String(id)}`]
      if (queuedDraft) {
        applyOfflineDraftToEditor(queuedDraft)
      }
    } catch {
      message.error('Failed to load note')
    } finally { setLoadingDetail(false) }
  }, [applyOfflineDraftToEditor, message, rememberRecentNote])

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
    setEditProvenance({ mode: 'manual' })
    setMonitoringNotice(null)
    setRemoteVersionInfo(null)
    setEditorCursorIndex(null)
    setWikilinkSelectionIndex(0)
    setWysiwygHtml('<p><br/></p>')
    setWysiwygSessionDirty(false)
    markdownBeforeWysiwygRef.current = null
  }, [])

  const confirmDiscardIfDirty = React.useCallback(async () => {
    if (!isDirty) return true
    // Auto-save instead of discarding
    if (!saving && (content.trim() || title.trim()) && saveNoteRef.current) {
      try {
        await saveNoteRef.current({ showSuccessMessage: false })
        return true
      } catch {
        // Save failed — fall through to confirmation dialog
      }
    }
    const ok = await confirmDanger({
      title: t('option:notesSearch.unsavedChangesTitle', { defaultValue: 'Save changes?' }),
      content: t('option:notesSearch.unsavedChangesContent', {
        defaultValue: 'Your changes could not be saved automatically. What would you like to do?'
      }),
      okText: t('option:notesSearch.discardChanges', { defaultValue: 'Discard' }),
      cancelText: t('common:cancel', { defaultValue: 'Cancel' })
    })
    return ok
  }, [confirmDanger, content, isDirty, saving, t, title])

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
        setQueryInput('')
        setKeywordTokens([])
        setSelectedNotebookId(null)
        setListViewMode('list')
      }
    },
    [confirmDiscardIfDirty, listMode, resetEditor]
  )

  const handleNewNote = React.useCallback(async (templateId?: string) => {
    const ok = await confirmDiscardIfDirty()
    if (!ok) return
    if (listMode !== 'active') setListMode('active')
    if (isMobileViewport) setMobileSidebarOpen(false)
    resetEditor()
    const template = NOTE_TEMPLATES.find((entry) => entry.id === templateId)
    if (template) {
      setTitle(template.title)
      setContent(template.content)
      setIsDirty(true)
      setSaveIndicator('dirty')
      message.success(`Applied template: ${template.label}`)
    }
    setTimeout(() => {
      titleInputRef.current?.focus()
    }, 0)
  }, [confirmDiscardIfDirty, isMobileViewport, listMode, message, resetEditor])

  const duplicateSelectedNote = React.useCallback(async () => {
    if (editorDisabled) return
    const hasDraft = title.trim().length > 0 || content.trim().length > 0
    if (!hasDraft) {
      message.warning('Add a title or content before duplicating.')
      return
    }

    if (listMode !== 'active') setListMode('active')
    if (isMobileViewport) setMobileSidebarOpen(false)
    const baseTitle = title.trim() || (selectedId != null ? `Note ${selectedId}` : 'Untitled note')
    const duplicateTitle = /\(copy\)$/i.test(baseTitle) ? baseTitle : `${baseTitle} (Copy)`
    const duplicateContent = content
    const duplicateKeywords = [...editorKeywords]

    resetEditor()
    setTitle(duplicateTitle)
    setContent(duplicateContent)
    setEditorKeywords(duplicateKeywords)
    setIsDirty(true)
    setSaveIndicator('dirty')
    message.success('Created duplicate draft. Save to keep it.')
    setTimeout(() => {
      titleInputRef.current?.focus()
    }, 0)
  }, [
    content,
    editorDisabled,
    editorKeywords,
    isMobileViewport,
    listMode,
    message,
    resetEditor,
    selectedId,
    title
  ])

  const handleSelectNote = React.useCallback(
    async (id: string | number) => {
      const ok = await confirmDiscardIfDirty()
      if (!ok) return
      await loadDetail(id)
      if (isMobileViewport) {
        setMobileSidebarOpen(false)
      }
    },
    [confirmDiscardIfDirty, isMobileViewport, loadDetail]
  )

  const clearBulkSelection = React.useCallback(() => {
    setBulkSelectedIds([])
    bulkSelectionAnchorRef.current = null
  }, [])

  const handleToggleBulkSelection = React.useCallback(
    (id: string | number, checked: boolean, shiftKey: boolean) => {
      if (listMode !== 'active') return
      const targetId = String(id)
      setBulkSelectedIds((current) => {
        const next = new Set(current)
        const anchorId = bulkSelectionAnchorRef.current
        const canApplyRange =
          shiftKey &&
          !!anchorId &&
          orderedVisibleNoteIds.includes(anchorId) &&
          orderedVisibleNoteIds.includes(targetId)

        if (canApplyRange && anchorId) {
          const start = orderedVisibleNoteIds.indexOf(anchorId)
          const end = orderedVisibleNoteIds.indexOf(targetId)
          const [minIndex, maxIndex] = start <= end ? [start, end] : [end, start]
          const rangeIds = orderedVisibleNoteIds.slice(minIndex, maxIndex + 1)
          for (const rangeId of rangeIds) {
            if (checked) next.add(rangeId)
            else next.delete(rangeId)
          }
        } else {
          if (checked) next.add(targetId)
          else next.delete(targetId)
        }

        bulkSelectionAnchorRef.current = targetId
        return orderedVisibleNoteIds.filter((visibleId) => next.has(visibleId))
      })
    },
    [listMode, orderedVisibleNoteIds]
  )

  const enterWysiwygMode = React.useCallback(() => {
    markdownBeforeWysiwygRef.current = content
    setWysiwygHtml(markdownToWysiwygHtml(content))
    setWysiwygSessionDirty(false)
    setEditorInputMode('wysiwyg')
    setEditorCursorIndex(null)
  }, [content])

  const exitWysiwygMode = React.useCallback(() => {
    const originalMarkdown = markdownBeforeWysiwygRef.current
    if (!wysiwygSessionDirty && originalMarkdown != null && originalMarkdown !== content) {
      setContent(originalMarkdown)
    }
    markdownBeforeWysiwygRef.current = null
    setEditorInputMode('markdown')
    setWysiwygSessionDirty(false)
  }, [content, wysiwygSessionDirty])

  const handleEditorInputModeChange = React.useCallback(
    (nextMode: NotesInputMode) => {
      if (nextMode === editorInputMode) return
      if (nextMode === 'wysiwyg') {
        enterWysiwygMode()
        return
      }
      exitWysiwygMode()
      window.requestAnimationFrame(() => {
        const textarea = contentTextareaRef.current
        if (!textarea) return
        textarea.focus()
        const cursor = Math.min(content.length, textarea.selectionStart ?? content.length)
        textarea.setSelectionRange(cursor, cursor)
        setEditorCursorIndex(cursor)
      })
    },
    [content, editorInputMode, enterWysiwygMode, exitWysiwygMode]
  )

  const handleWysiwygInput = React.useCallback(
    (event: React.FormEvent<HTMLDivElement>) => {
      const nextHtml = event.currentTarget.innerHTML
      setWysiwygHtml(nextHtml)
      setWysiwygSessionDirty(true)
      const nextMarkdown = wysiwygHtmlToMarkdown(nextHtml)
      setContentDirty(nextMarkdown)
      setEditorCursorIndex(nextMarkdown.length)
    },
    [setContentDirty]
  )

  const handleWysiwygPaste = React.useCallback((event: React.ClipboardEvent<HTMLDivElement>) => {
    if (editorDisabled) return
    const plain = event.clipboardData.getData('text/plain')
    if (!plain) return
    event.preventDefault()
    if (typeof document !== 'undefined' && typeof document.execCommand === 'function') {
      document.execCommand('insertText', false, plain)
    }
  }, [editorDisabled])

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

  const handleTocJump = React.useCallback(
    (entry: NotesTocEntry) => {
      if (editorInputMode === 'wysiwyg') {
        const richEditor = richEditorRef.current
        if (!richEditor) return
        const headingMatch = Array.from(
          richEditor.querySelectorAll<HTMLElement>('[data-md-slug]')
        ).find((element) => element.getAttribute('data-md-slug') === entry.id)
        if (headingMatch) {
          headingMatch.scrollIntoView({ block: 'center', behavior: 'smooth' })
          const range = document.createRange()
          range.selectNodeContents(headingMatch)
          range.collapse(true)
          const selection = window.getSelection()
          selection?.removeAllRanges()
          selection?.addRange(range)
        }
        richEditor.focus()
        return
      }

      const focusAtOffset = () => {
        const textarea = contentTextareaRef.current
        if (!textarea) return
        const cursor = Math.max(0, Math.min(entry.offset, content.length))
        textarea.focus()
        textarea.setSelectionRange(cursor, cursor)
        setEditorCursorIndex(cursor)
      }

      if (editorMode === 'preview') {
        setEditorMode('split')
        window.requestAnimationFrame(() => {
          window.requestAnimationFrame(focusAtOffset)
        })
        return
      }
      window.requestAnimationFrame(focusAtOffset)
    },
    [content.length, editorInputMode, editorMode]
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
          title_strategy: effectiveTitleSuggestStrategy
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
      setMonitoringNotice(null)
    } catch (error: any) {
      message.error(String(error?.message || 'Could not generate title'))
    } finally {
      setTitleSuggestionLoading(false)
    }
  }, [
    confirmDanger,
    content,
    editorDisabled,
    effectiveTitleSuggestStrategy,
    message,
    t,
    titleSuggestionLoading
  ])

  /* closeKeywordSuggestionModal, applySelectedSuggestedKeywords moved to useNotesKeywords */

  const runAssistAction = React.useCallback(
    async (action: NotesAssistAction) => {
      if (editorDisabled || assistLoadingAction) return
      const sourceContent = content.trim()
      if (!sourceContent) {
        message.warning(
          t('option:notesSearch.assistEmptyContentWarning', {
            defaultValue: 'Write some content before using assist actions.'
          })
        )
        return
      }

      setAssistLoadingAction(action)
      try {
        if (action === 'suggest_keywords') {
          const suggestedKeywords = suggestKeywordsDraft(sourceContent, editorKeywords)
          if (suggestedKeywords.length === 0) {
            message.warning(
              t('option:notesSearch.assistKeywordsNoResult', {
                defaultValue: 'No additional keyword suggestions were found.'
              })
            )
            return
          }
          keywordSuggestionReturnFocusRef.current =
            document.activeElement instanceof HTMLElement ? document.activeElement : null
          setKeywordSuggestionOptions(suggestedKeywords)
          setKeywordSuggestionSelection(suggestedKeywords)
          return
        }

        const generatedContent =
          action === 'summarize'
            ? buildSummaryDraft(sourceContent)
            : buildOutlineDraft(sourceContent)
        if (!generatedContent.trim()) {
          message.warning(
            t('option:notesSearch.assistNoResult', {
              defaultValue: 'No assist output was generated.'
            })
          )
          return
        }

        const apply = await confirmDanger({
          title:
            action === 'summarize'
              ? t('option:notesSearch.assistSummaryApplyTitle', {
                  defaultValue: 'Apply generated summary?'
                })
              : t('option:notesSearch.assistOutlineApplyTitle', {
                  defaultValue: 'Apply expanded outline?'
                }),
          content: generatedContent,
          okText: t('option:notesSearch.assistApplyAction', {
            defaultValue: 'Apply'
          }),
          cancelText: t('option:notesSearch.assistKeepCurrentAction', {
            defaultValue: 'Keep current'
          })
        })
        if (!apply) return
        setContentDirty(generatedContent, { provenance: action })
        message.success(
          action === 'summarize'
            ? t('option:notesSearch.assistSummaryApplied', {
                defaultValue: 'Applied generated summary.'
              })
            : t('option:notesSearch.assistOutlineApplied', {
                defaultValue: 'Applied expanded outline.'
              })
        )
      } catch (error: any) {
        message.error(String(error?.message || 'Assist action failed'))
      } finally {
        setAssistLoadingAction(null)
      }
    },
    [
      assistLoadingAction,
      confirmDanger,
      content,
      editorDisabled,
      editorKeywords,
      message,
      setContentDirty,
      t
    ]
  )

  const handleGenerateFlashcardsFromNote = React.useCallback(() => {
    const sourceText = content.trim()
    if (!sourceText) {
      message.warning(
        t("option:notesSearch.generateFlashcardsEmpty", {
          defaultValue: "Add note content before generating flashcards."
        })
      )
      return
    }

    navigate(
      buildFlashcardsGenerateRoute({
        text: sourceText,
        sourceType: "note",
        sourceId: selectedId != null ? String(selectedId) : undefined,
        sourceTitle: title.trim() || undefined,
        conversationId: backlinkConversationId || undefined,
        messageId: backlinkMessageId || undefined
      })
    )
  }, [
    backlinkConversationId,
    backlinkMessageId,
    content,
    message,
    navigate,
    selectedId,
    t,
    title
  ])

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

  const loadMonitoringNoticeForSavedNote = React.useCallback(
    async (
      noteId: string | number,
      source: 'notes.create' | 'notes.update',
      saveStartedAtMs: number
    ) => {
      try {
        const params = new URLSearchParams()
        params.set('source', source)
        params.set('unread_only', 'true')
        params.set('limit', '50')
        const response = await bgRequest<any>({
          path: `/api/v1/monitoring/alerts?${params.toString()}` as any,
          method: 'GET' as any
        })
        const items = Array.isArray(response?.items) ? response.items : []
        const noteIdText = String(noteId)
        const minCreatedAtMs = saveStartedAtMs - 5000
        const matchedAlert = items.find((item: any) => {
          if (String(item?.source_id || '') !== noteIdText) return false
          const createdAtMs = Date.parse(String(item?.created_at || ''))
          if (Number.isFinite(createdAtMs) && createdAtMs < minCreatedAtMs) return false
          return true
        })
        if (!matchedAlert) return

        const severityRaw = String(matchedAlert?.rule_severity || 'info').toLowerCase()
        const severity: MonitoringAlertSeverity =
          severityRaw === 'critical'
            ? 'critical'
            : severityRaw === 'warning'
              ? 'warning'
              : 'info'

        const titleCopy =
          severity === 'critical'
            ? t('option:notesSearch.monitoringAlertCriticalTitle', {
                defaultValue: 'Sensitive-topic alert detected'
              })
            : severity === 'warning'
              ? t('option:notesSearch.monitoringAlertWarningTitle', {
                  defaultValue: 'Monitoring warning detected'
                })
              : t('option:notesSearch.monitoringAlertInfoTitle', {
                  defaultValue: 'Monitored topic detected'
                })

        const guidanceCopy = t('option:notesSearch.monitoringAlertGuidance', {
          defaultValue:
            'Review this note for sensitive material before sharing. You can edit and save again.'
        })

        setMonitoringNotice({
          severity,
          title: titleCopy,
          guidance: guidanceCopy
        })
      } catch {
        // Endpoint may be disabled or permission-gated; do not interrupt save flow.
      }
    },
    [t]
  )

  const showKeywordSyncWarning = React.useCallback(
    (warning: KeywordSyncWarning, action: 'created' | 'updated') => {
      if (warning.failedCount <= 0) return
      const keywordSuffix =
        warning.failedKeywords.length > 0 ? ` (${warning.failedKeywords.join(', ')})` : ''
      message.warning(
        `Note ${action}, but ${warning.failedCount} keyword${
          warning.failedCount === 1 ? '' : 's'
        } failed to attach${keywordSuffix}.`
      )
    },
    [message]
  )

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
      if (!isOnline) {
        const queuedAt = new Date().toISOString()
        upsertOfflineDraft({
          syncState: 'queued',
          lastError: null,
          updatedAt: queuedAt
        })
        setIsDirty(false)
        setSaveIndicator('saved')
        setSelectedLastSavedAt(queuedAt)
        if (showSuccessMessage) {
          message.info(
            t('option:notesSearch.offlineSavedLocally', {
              defaultValue: 'Saved locally. Sync will resume when connection returns.'
            })
          )
        }
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
      setMonitoringNotice(null)
      const saveStartedAtMs = Date.now()
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
          const createdKeywordWarning = toKeywordSyncWarning(created)
          const createdVersion = toNoteVersion(created)
          const createdLastSaved = toNoteLastModified(created)
          if (showSuccessMessage) {
            message.success('Note created')
          }
          if (createdKeywordWarning) {
            showKeywordSyncWarning(createdKeywordWarning, 'created')
          }
          setIsDirty(false)
          setSaveIndicator('saved')
          setRemoteVersionInfo(null)
          removeOfflineDraftByKey(currentOfflineDraftKey)
          if (createdVersion != null) setSelectedVersion(createdVersion)
          if (createdLastSaved) setSelectedLastSavedAt(createdLastSaved)
          await refetch()
          if (created?.id != null) {
            await loadDetail(created.id)
            void loadMonitoringNoticeForSavedNote(created.id, 'notes.create', saveStartedAtMs)
          }
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
          const updatedKeywordWarning = toKeywordSyncWarning(updated)
          const updatedVersion = toNoteVersion(updated)
          const updatedLastSaved = toNoteLastModified(updated)
          if (showSuccessMessage) {
            message.success('Note updated')
          }
          if (updatedKeywordWarning) {
            showKeywordSyncWarning(updatedKeywordWarning, 'updated')
          }
          setIsDirty(false)
          setSaveIndicator('saved')
          setRemoteVersionInfo(null)
          removeOfflineDraftByKey(currentOfflineDraftKey)
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
          if (selectedId != null) {
            void loadMonitoringNoticeForSavedNote(selectedId, 'notes.update', saveStartedAtMs)
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
      isOnline,
      loadDetail,
      loadMonitoringNoticeForSavedNote,
      message,
      originalMetadata,
      currentOfflineDraftKey,
      refetch,
      removeOfflineDraftByKey,
      remoteVersionInfo,
      saving,
      selectedId,
      setSelectedLastSavedAt,
      selectedVersion,
      showKeywordSyncWarning,
      t,
      title,
      upsertOfflineDraft
    ]
  )

  // Keep ref in sync so confirmDiscardIfDirty can call saveNote without TDZ
  saveNoteRef.current = saveNote

  const syncOfflineDraftEntry = React.useCallback(
    async (draft: OfflineDraftEntry): Promise<OfflineDraftSyncResult> => {
      const metadata: Record<string, any> = {
        ...(draft.metadata || {}),
        keywords: draft.keywords
      }
      if (draft.backlinkConversationId) metadata.conversation_id = draft.backlinkConversationId
      if (draft.backlinkMessageId) metadata.message_id = draft.backlinkMessageId
      const payload: Record<string, any> = {
        title: draft.title || undefined,
        content: draft.content,
        metadata,
        keywords: draft.keywords
      }
      if (draft.backlinkConversationId) payload.conversation_id = draft.backlinkConversationId
      if (draft.backlinkMessageId) payload.message_id = draft.backlinkMessageId

      try {
        if (!draft.noteId) {
          const created = await bgRequest<any>({
            path: '/api/v1/notes/' as any,
            method: 'POST' as any,
            headers: { 'Content-Type': 'application/json' },
            body: payload
          })
          const createdId = String(created?.id || '').trim()
          if (!createdId) {
            return {
              status: 'error',
              key: draft.key,
              message: 'Queued create sync did not return a note id.'
            }
          }
          return {
            status: 'synced',
            key: draft.key,
            noteId: createdId,
            version: toNoteVersion(created),
            lastSavedAt: toNoteLastModified(created)
          }
        }

        const encodedId = encodeURIComponent(String(draft.noteId))
        const remote = await bgRequest<any>({
          path: `/api/v1/notes/${encodedId}` as any,
          method: 'GET' as any
        })
        const remoteVersion = toNoteVersion(remote)
        if (
          draft.baseVersion != null &&
          remoteVersion != null &&
          remoteVersion > draft.baseVersion
        ) {
          return {
            status: 'conflict',
            key: draft.key,
            message: `Remote version advanced from ${draft.baseVersion} to ${remoteVersion}.`
          }
        }
        const expectedVersion = draft.baseVersion ?? remoteVersion
        if (expectedVersion == null) {
          return {
            status: 'error',
            key: draft.key,
            message: 'Missing expected version for queued sync.'
          }
        }

        const updated = await bgRequest<any>({
          path: `/api/v1/notes/${encodedId}?expected_version=${encodeURIComponent(
            String(expectedVersion)
          )}` as any,
          method: 'PUT' as any,
          headers: { 'Content-Type': 'application/json' },
          body: payload
        })

        return {
          status: 'synced',
          key: draft.key,
          noteId: String(draft.noteId),
          version: toNoteVersion(updated),
          lastSavedAt: toNoteLastModified(updated)
        }
      } catch (error: any) {
        if (isVersionConflictError(error)) {
          return {
            status: 'conflict',
            key: draft.key,
            message: String(error?.message || 'Server version conflict while syncing queued draft.')
          }
        }
        return {
          status: 'error',
          key: draft.key,
          message: String(error?.message || 'Queued sync failed.')
        }
      }
    },
    [isVersionConflictError]
  )

  const syncOfflineDraftQueue = React.useCallback(async () => {
    if (!isOnline) return
    if (offlineSyncInFlightRef.current) return
    const queuedEntries = Object.values(offlineDraftQueueRef.current)
      .filter((entry) => entry.syncState !== 'conflict')
      .sort((a, b) => new Date(a.updatedAt).getTime() - new Date(b.updatedAt).getTime())
    if (queuedEntries.length === 0) return

    offlineSyncInFlightRef.current = true
    let successfulSyncs = 0
    try {
      for (const queuedEntry of queuedEntries) {
        setOfflineDraftQueue((current) => {
          const existing = current[queuedEntry.key]
          if (!existing) return current
          return {
            ...current,
            [queuedEntry.key]: {
              ...existing,
              syncState: 'syncing',
              lastError: null
            }
          }
        })

        const latestEntry = offlineDraftQueueRef.current[queuedEntry.key] || queuedEntry
        const syncResult = await syncOfflineDraftEntry(latestEntry)
        if (syncResult.status === 'synced' && syncResult.noteId) {
          successfulSyncs += 1
          setOfflineDraftQueue((current) => {
            if (!current[syncResult.key]) return current
            const next = { ...current }
            delete next[syncResult.key]
            return next
          })
          if (selectedId == null && syncResult.key === NOTES_OFFLINE_NEW_DRAFT_KEY) {
            await loadDetail(syncResult.noteId)
          } else if (
            selectedId != null &&
            syncResult.noteId &&
            String(selectedId) === String(syncResult.noteId)
          ) {
            if (syncResult.version != null) {
              setSelectedVersion(syncResult.version)
            }
            setSelectedLastSavedAt(syncResult.lastSavedAt || new Date().toISOString())
            setSaveIndicator('saved')
          }
          continue
        }

        if (syncResult.status === 'conflict') {
          setOfflineDraftQueue((current) => {
            const existing = current[syncResult.key]
            if (!existing) return current
            return {
              ...current,
              [syncResult.key]: {
                ...existing,
                syncState: 'conflict',
                lastError: syncResult.message
              }
            }
          })
          if (syncResult.key === currentOfflineDraftKey) {
            setSaveIndicator('error')
          }
          continue
        }

        if (syncResult.status === 'error') {
          setOfflineDraftQueue((current) => {
            const existing = current[syncResult.key]
            if (!existing) return current
            return {
              ...current,
              [syncResult.key]: {
                ...existing,
                syncState: 'error',
                lastError: syncResult.message
              }
            }
          })
        }
      }
    } finally {
      offlineSyncInFlightRef.current = false
    }

    if (successfulSyncs > 0) {
      void refetch()
      message.success(
        t('option:notesSearch.offlineSyncCompleteToast', {
          defaultValue: 'Synced {{count}} queued offline draft(s).',
          count: successfulSyncs
        })
      )
    }
  }, [
    currentOfflineDraftKey,
    isOnline,
    loadDetail,
    message,
    refetch,
    selectedId,
    syncOfflineDraftEntry,
    t
  ])

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

  const getExpectedVersionForNoteId = React.useCallback(
    async (noteId: string): Promise<number | null> => {
      if (selectedId != null && String(selectedId) === noteId && selectedVersion != null) {
        return selectedVersion
      }
      if (Array.isArray(data)) {
        const match = data.find((note) => String(note.id) === noteId)
        if (typeof match?.version === 'number' && Number.isFinite(match.version)) {
          return match.version
        }
      }
      try {
        const detail = await bgRequest<any>({
          path: `/api/v1/notes/${encodeURIComponent(noteId)}` as any,
          method: 'GET' as any
        })
        return toNoteVersion(detail)
      } catch {
        return null
      }
    },
    [data, selectedId, selectedVersion]
  )

  const lookupDeletedNoteVersion = React.useCallback(async (noteId: string) => {
    if (listMode === 'trash' && Array.isArray(data)) {
      const existing = data.find((note) => String(note.id) === noteId)
      if (existing?.version != null) {
        return Number(existing.version)
      }
    }
    try {
      let offset = 0
      let pagesChecked = 0

      while (pagesChecked < TRASH_LOOKUP_MAX_PAGES) {
        const res = await bgRequest<any>({
          path: `/api/v1/notes/trash?limit=${TRASH_LOOKUP_PAGE_SIZE}&offset=${offset}` as any,
          method: 'GET' as any
        })
        const items = Array.isArray(res?.items) ? res.items : Array.isArray(res) ? res : []
        const match = items.find((item: any) => String(item?.id) === noteId)
        const version = toNoteVersion(match)
        if (version != null) return version
        if (items.length === 0) break

        const paginationTotalRaw =
          res && typeof res === 'object' ? Number((res as any)?.pagination?.total_items) : NaN
        const hasPaginationTotal = Number.isFinite(paginationTotalRaw)

        offset += items.length
        pagesChecked += 1

        if (hasPaginationTotal && offset >= paginationTotalRaw) break
        if (items.length < TRASH_LOOKUP_PAGE_SIZE) break
      }
      return null
    } catch {
      return null
    }
  }, [data, listMode])

  const showDeleteUndoToast = React.useCallback(
    (noteId: string) => {
      const toastKey = `notes-delete-${noteId}`
      const handleUndo = async () => {
        if (typeof (message as any).destroy === 'function') {
          ;(message as any).destroy(toastKey)
        }
        try {
          const resolvedVersion = await lookupDeletedNoteVersion(noteId)
          if (resolvedVersion == null) {
            message.warning('Undo unavailable. Open Trash to restore this note.')
            return
          }
          await bgRequest<any>({
            path: `/api/v1/notes/${encodeURIComponent(noteId)}/restore?expected_version=${encodeURIComponent(
              String(resolvedVersion)
            )}` as any,
            method: 'POST' as any
          })
          message.success('Note restored')
          setListMode('active')
          setPage(1)
          await refetch()
          await loadDetail(noteId)
        } catch {
          message.warning('Undo failed. Open Trash to restore this note manually.')
        }
      }

      if (typeof (message as any).open === 'function') {
        ;(message as any).open({
          key: toastKey,
          duration: 10,
          content: (
            <span className="inline-flex items-center gap-2">
              <span>Note deleted</span>
              <Button
                type="link"
                size="small"
                className="!px-0"
                onClick={() => {
                  void handleUndo()
                }}
                data-testid={`notes-delete-undo-${noteId.replace(/[^a-z0-9_-]/gi, '_')}`}
              >
                Undo
              </Button>
            </span>
          )
        })
        return
      }

      message.success('Note deleted')
    },
    [bgRequest, loadDetail, lookupDeletedNoteVersion, message, refetch]
  )

  const countInboundDeleteReferences = React.useCallback(async (noteId: string) => {
    try {
      const encodedId = encodeURIComponent(noteId)
      const graph = await bgRequest<any>({
        path: `/api/v1/notes/${encodedId}/neighbors?edge_types=manual,wikilink,backlink&max_nodes=120&max_edges=240` as any,
        method: 'GET' as any
      })
      const edges = Array.isArray(graph?.edges) ? graph.edges : []
      const inbound = new Set<string>()
      for (const edge of edges) {
        const source = normalizeGraphNoteId(edge?.source)
        const target = normalizeGraphNoteId(edge?.target)
        if (!source || !target || source === target) continue
        const type = String(edge?.type || '').toLowerCase()
        const directed = Boolean(edge?.directed)
        if (type === 'wikilink' && target === noteId) {
          inbound.add(source)
          continue
        }
        if (type === 'backlink' && source === noteId) {
          inbound.add(target)
          continue
        }
        if (type === 'manual' && directed && target === noteId) {
          inbound.add(source)
        }
      }
      return inbound.size
    } catch {
      return 0
    }
  }, [])

  const deleteNote = async (id?: string | number | null) => {
    const target = id ?? selectedId
    if (target == null) { message.warning('No note selected'); return }
    const targetId = String(target)
    const inboundReferenceCount = await countInboundDeleteReferences(targetId)
    const warningSuffix =
      inboundReferenceCount > 0
        ? `\n\nThis note is referenced by ${inboundReferenceCount} other note${
            inboundReferenceCount === 1 ? '' : 's'
          }. Deleting it will break those links.`
        : ''
    const ok = await confirmDanger({
      title: 'Please confirm',
      content: `Delete this note?${warningSuffix}`,
      okText: 'Delete',
      cancelText: 'Cancel'
    })
    if (!ok) return
    try {
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
      showDeleteUndoToast(targetId)
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

  const exportSelectedBulk = React.useCallback(() => {
    if (selectedBulkNotes.length === 0) {
      message.info('No selected notes to export')
      return
    }
    const md = selectedBulkNotes
      .map((note, index) => `### ${note.title || `Note ${note.id ?? index + 1}`}\n\n${String(note.content || '')}`)
      .join('\n\n---\n\n')
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `notes-selected-export.md`
    anchor.click()
    URL.revokeObjectURL(url)
    message.success(
      translateMessage(
        t,
        'option:notesSearch.bulkExportSuccess',
        'Exported {{count}} selected notes',
        { count: selectedBulkNotes.length }
      )
    )
  }, [message, selectedBulkNotes, t])

  const deleteSelectedBulk = React.useCallback(async () => {
    if (selectedBulkNotes.length === 0) {
      message.info('No selected notes to delete')
      return
    }
    const okToLeave = await confirmDiscardIfDirty()
    if (!okToLeave) return
    const confirmed = await confirmDanger({
      title: 'Delete selected notes?',
      content: `Delete ${selectedBulkNotes.length} selected notes? This moves them to trash.`,
      okText: 'Delete selected',
      cancelText: 'Cancel'
    })
    if (!confirmed) return

    let deleted = 0
    let failed = 0
    const deletedIds = new Set<string>()

    for (const note of selectedBulkNotes) {
      const noteId = String(note.id)
      const expectedVersion = await getExpectedVersionForNoteId(noteId)
      if (expectedVersion == null) {
        failed += 1
        continue
      }
      try {
        await bgRequest<any>({
          path: `/api/v1/notes/${encodeURIComponent(noteId)}?expected_version=${encodeURIComponent(
            String(expectedVersion)
          )}` as any,
          method: 'DELETE' as any,
          headers: {
            'expected-version': String(expectedVersion)
          }
        })
        deleted += 1
        deletedIds.add(noteId)
      } catch {
        failed += 1
      }
    }

    if (deleted > 0) {
      message.success(`Deleted ${deleted} selected note${deleted === 1 ? '' : 's'}`)
      if (selectedId != null && deletedIds.has(String(selectedId))) {
        resetEditor()
      }
      setBulkSelectedIds((current) => current.filter((id) => !deletedIds.has(id)))
      await refetch()
    }
    if (failed > 0) {
      message.warning(`${failed} selected note${failed === 1 ? '' : 's'} failed to delete`)
    }
  }, [
    confirmDanger,
    confirmDiscardIfDirty,
    getExpectedVersionForNoteId,
    message,
    refetch,
    resetEditor,
    selectedBulkNotes,
    selectedId
  ])

  const assignKeywordsToSelectedBulk = React.useCallback(async () => {
    if (selectedBulkNotes.length === 0) {
      message.info('No selected notes to update')
      return
    }
    const okToLeave = await confirmDiscardIfDirty()
    if (!okToLeave) return
    const suggested = keywordTokens.join(', ')
    const rawInput = window.prompt(
      'Assign keywords to selected notes (comma-separated):',
      suggested
    )
    if (rawInput == null) return
    const keywords = rawInput
      .split(',')
      .map((entry) => entry.trim())
      .filter(Boolean)
    if (keywords.length === 0) {
      message.warning('Enter at least one keyword to assign')
      return
    }

    const confirmed = await confirmDanger({
      title: 'Apply keywords to selected notes?',
      content: `Apply ${keywords.join(', ')} to ${selectedBulkNotes.length} selected notes?`,
      okText: 'Apply keywords',
      cancelText: 'Cancel'
    })
    if (!confirmed) return

    let updated = 0
    let failed = 0
    for (const note of selectedBulkNotes) {
      const noteId = String(note.id)
      const expectedVersion = await getExpectedVersionForNoteId(noteId)
      if (expectedVersion == null) {
        failed += 1
        continue
      }
      try {
        await bgRequest<any>({
          path: `/api/v1/notes/${encodeURIComponent(noteId)}?expected_version=${encodeURIComponent(
            String(expectedVersion)
          )}` as any,
          method: 'PATCH' as any,
          headers: {
            'Content-Type': 'application/json',
            'expected-version': String(expectedVersion)
          },
          body: {
            keywords
          }
        })
        updated += 1
      } catch {
        failed += 1
      }
    }

    if (updated > 0) {
      message.success(`Updated keywords on ${updated} selected note${updated === 1 ? '' : 's'}`)
      await refetch()
      if (selectedId != null && selectedBulkNotes.some((note) => String(note.id) === String(selectedId))) {
        await loadDetail(selectedId)
      }
    }
    if (failed > 0) {
      message.warning(`${failed} selected note${failed === 1 ? '' : 's'} failed keyword update`)
    }
  }, [
    confirmDanger,
    confirmDiscardIfDirty,
    getExpectedVersionForNoteId,
    keywordTokens,
    loadDetail,
    message,
    refetch,
    selectedBulkNotes,
    selectedId
  ])

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
      const resolvedLabel = toConversationLabel(chat)
      if (resolvedLabel) {
        setConversationLabelById((current) =>
          current[backlinkConversationId]
            ? current
            : {
                ...current,
                [backlinkConversationId]: resolvedLabel
              }
        )
      }
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

  const openLinkedSource = React.useCallback(
    (sourceId: string, sourceLabel: string) => {
      const parsed = parseSourceNodeId(sourceId)
      const externalRef = parsed?.externalRef || null
      if (externalRef && /^https?:\/\//i.test(externalRef)) {
        if (typeof window !== 'undefined') {
          window.open(externalRef, '_blank', 'noopener,noreferrer')
        }
        return
      }
      if (externalRef) {
        navigate(`/media?id=${encodeURIComponent(externalRef)}`)
        return
      }
      navigate('/media')
      message.info(
        t('option:notesSearch.sourceNavigationFallback', {
          defaultValue: 'Opened media library for source "{{label}}".',
          label: sourceLabel
        })
      )
    },
    [message, navigate, t]
  )

  const copySelected = async (mode: SingleNoteCopyMode = 'content') => {
    const payload = buildSingleNoteCopyText(
      {
        id: selectedId,
        title,
        content,
        keywords: editorKeywords
      },
      mode
    )
    try {
      await navigator.clipboard.writeText(payload)
      message.success(mode === 'markdown' ? 'Copied as Markdown' : 'Copied')
    } catch { message.error('Copy failed') }
  }

  const printSelected = React.useCallback(() => {
    if (typeof window === 'undefined') {
      message.error('Print is not available in this environment')
      return
    }
    const printWindow = window.open('', '_blank', 'noopener,noreferrer,width=1024,height=768')
    if (!printWindow) {
      message.error('Unable to open print view. Please allow pop-ups and try again.')
      return
    }

    const printableHtml = buildSingleNotePrintableHtml({
      id: selectedId,
      title,
      content,
      keywords: editorKeywords
    })

    printWindow.document.open()
    printWindow.document.write(printableHtml)
    printWindow.document.close()
    printWindow.focus()
    printWindow.print()

    message.success('Opened print view. Use Save as PDF in your browser to export PDF.')
  }, [content, editorKeywords, message, selectedId, title])

  const exportSelected = (format: SingleNoteExportFormat = 'md') => {
    if (format === 'print') {
      printSelected()
      return
    }
    const name = (title || `note-${selectedId ?? 'new'}`).replace(/[^a-z0-9-_]+/gi, '-')
    const fileContent =
      format === 'json'
        ? buildSingleNoteJson({
            id: selectedId,
            title,
            content,
            keywords: editorKeywords
          })
        : buildSingleNoteMarkdown({
            id: selectedId,
            title,
            content,
            keywords: editorKeywords
          })
    const blob = new Blob([fileContent], {
      type:
        format === 'json'
          ? 'application/json;charset=utf-8'
          : 'text/markdown;charset=utf-8'
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${name}.${format === 'json' ? 'json' : 'md'}`
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

  const clearImportSelection = React.useCallback(() => {
    setPendingImportFiles([])
    if (importInputRef.current) {
      importInputRef.current.value = ''
    }
  }, [])

  const openImportPicker = React.useCallback(() => {
    if (!isOnline || listMode !== 'active') return
    importInputRef.current?.click()
  }, [isOnline, listMode])

  const handleImportInputChange = React.useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFiles = Array.from(event.target.files || [])
      if (selectedFiles.length === 0) {
        return
      }
      const loaded = await Promise.all(
        selectedFiles.map(async (file): Promise<PendingImportFile> => {
          const content = await file.text()
          const format = detectImportFormatFromFileName(file.name)
          const detectedNotes = estimateDetectedNotesFromImportContent(format, content)
          const parseError =
            format === 'json' && detectedNotes === 0
              ? 'Could not parse notes from this JSON file.'
              : null
          return {
            fileName: file.name,
            format,
            content,
            detectedNotes,
            parseError
          }
        })
      )
      setPendingImportFiles(loaded)
      setImportModalOpen(true)
    },
    []
  )

  const closeImportModal = React.useCallback(() => {
    setImportModalOpen(false)
    clearImportSelection()
  }, [clearImportSelection])

  const confirmImport = React.useCallback(async () => {
    if (pendingImportFiles.length === 0) {
      message.warning('Select at least one import file')
      return
    }
    const importItems = pendingImportFiles
      .filter((entry) => entry.content.trim().length > 0)
      .map((entry) => ({
        file_name: entry.fileName,
        format: entry.format,
        content: entry.content
      }))
    if (importItems.length === 0) {
      message.warning('Selected files are empty')
      return
    }

    setImportSubmitting(true)
    try {
      const response = await bgRequest<NotesImportResponsePayload>({
        path: '/api/v1/notes/import' as any,
        method: 'POST' as any,
        headers: { 'Content-Type': 'application/json' },
        body: {
          duplicate_strategy: importDuplicateStrategy,
          items: importItems
        }
      })

      const createdCount = Number(response?.created_count || 0)
      const updatedCount = Number(response?.updated_count || 0)
      const skippedCount = Number(response?.skipped_count || 0)
      const failedCount = Number(response?.failed_count || 0)

      if (failedCount > 0 || skippedCount > 0) {
        message.warning(
          `Import completed with partial results: ${createdCount} created, ${updatedCount} updated, ${skippedCount} skipped, ${failedCount} failed.`
        )
      } else {
        message.success(`Imported ${createdCount + updatedCount} note${createdCount + updatedCount === 1 ? '' : 's'}.`)
      }

      closeImportModal()
      await refetch()
    } catch (error: any) {
      message.error(String(error?.message || 'Import failed'))
    } finally {
      setImportSubmitting(false)
    }
  }, [
    closeImportModal,
    importDuplicateStrategy,
    message,
    pendingImportFiles,
    refetch
  ])

  const MAX_EXPORT_PAGES = 1000
  const EXPORT_PREFLIGHT_NOTE_THRESHOLD = MAX_EXPORT_PAGES * 100

  const gatherAllMatching = async (
    format: ExportFormat
  ): Promise<{ arr: NoteListItem[]; limitReached: boolean; failedBatches: number }> => {
    const arr: NoteListItem[] = []
    let limitReached = false
    let failedBatches = 0
    let fetchedPages = 0
    const q = query.trim()
    const toks = effectiveKeywordTokens.map((k) => k.toLowerCase())
    const updateProgress = () => {
      setExportProgress({
        format,
        fetchedNotes: arr.length,
        fetchedPages,
        failedBatches
      })
    }

    setExportProgress({
      format,
      fetchedNotes: 0,
      fetchedPages: 0,
      failedBatches: 0
    })

    if (q || toks.length > 0) {
      // Fetch all matching notes in chunks using server-side filtering
      let p = 1
      const ps = 100
      while (p <= MAX_EXPORT_PAGES) {
        let items: any[] = []
        try {
          const result = await fetchFilteredNotesRaw(q, toks, p, ps)
          items = result.items
        } catch {
          failedBatches += 1
          updateProgress()
          break
        }
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
        fetchedPages += 1
        updateProgress()
        if (items.length < ps) break
        p++
      }
      if (p > MAX_EXPORT_PAGES) limitReached = true
    } else {
      // Iterate pages (chunk by 100)
      let p = 1
      const ps = 100
      while (p <= MAX_EXPORT_PAGES) {
        let res: any
        try {
          res = await bgRequest<any>({
            path: `/api/v1/notes/?page=${p}&results_per_page=${ps}` as any,
            method: 'GET' as any
          })
        } catch {
          failedBatches += 1
          updateProgress()
          break
        }
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
        if (items.length > 0) {
          fetchedPages += 1
          updateProgress()
        }
        const pagination = res?.pagination
        const totalPages = Number(pagination?.total_pages || (items.length < ps ? p : p + 1))
        if (p >= totalPages || items.length === 0) break
        p++
      }
      if (p > MAX_EXPORT_PAGES) limitReached = true
    }
    return { arr, limitReached, failedBatches }
  }

  const maybeConfirmExportPreflight = React.useCallback(
    async (format: ExportFormat): Promise<boolean> => {
      if (listMode !== 'active') return true
      const estimatedScope = Math.max(total, filteredCount)
      if (estimatedScope < EXPORT_PREFLIGHT_NOTE_THRESHOLD) return true
      const scopeText = hasActiveFilters
        ? 'current search/filter scope'
        : 'all active notes'
      return confirmDanger({
        title: `Large ${format.toUpperCase()} export`,
        content:
          `This export is estimated to include about ${estimatedScope.toLocaleString()} notes from ${scopeText}. ` +
          'It may take a while and can return partial results if some batches fail. Continue?',
        okText: 'Start export',
        cancelText: 'Cancel'
      })
    },
    [confirmDanger, filteredCount, hasActiveFilters, listMode, total]
  )

  const maybeWarnExportLimits = React.useCallback(
    (arrLength: number, limitReached: boolean, failedBatches: number) => {
      if (limitReached) {
        message.warning(`Export limited to ${arrLength} notes. Some notes may be excluded.`)
      }
      if (failedBatches > 0) {
        message.warning(
          `Export completed with partial data. ${failedBatches} batch${
            failedBatches === 1 ? '' : 'es'
          } failed.`
        )
      }
    },
    [message]
  )

  const exportAll = async () => {
    try {
      const allowed = await maybeConfirmExportPreflight('md')
      if (!allowed) return
      const { arr, limitReached, failedBatches } = await gatherAllMatching('md')
      if (arr.length === 0) {
        message.info('No notes to export')
        return
      }
      maybeWarnExportLimits(arr.length, limitReached, failedBatches)
      const md = arr
        .map((n, idx) => `### ${n.title || `Note ${n.id ?? idx + 1}`}\n\n${String(n.content || '')}`)
        .join('\n\n---\n\n')
      const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `notes-export.md`
      a.click()
      URL.revokeObjectURL(url)
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
    } finally {
      setExportProgress(null)
    }
  }

  const exportAllCSV = async () => {
    try {
      const allowed = await maybeConfirmExportPreflight('csv')
      if (!allowed) return
      const { arr, limitReached, failedBatches } = await gatherAllMatching('csv')
      if (!arr.length) { message.info('No notes to export'); return }
      maybeWarnExportLimits(arr.length, limitReached, failedBatches)
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
    } finally {
      setExportProgress(null)
    }
  }

  const exportAllJSON = async () => {
    try {
      const allowed = await maybeConfirmExportPreflight('json')
      if (!allowed) return
      const { arr, limitReached, failedBatches } = await gatherAllMatching('json')
      if (!arr.length) { message.info('No notes to export'); return }
      maybeWarnExportLimits(arr.length, limitReached, failedBatches)
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
    } finally {
      setExportProgress(null)
    }
  }

  /* loadKeywordSuggestions, debouncedLoadKeywordSuggestions, handleKeywordFilterSearch, handleKeywordFilterChange moved to useNotesKeywords */

  const fetchServerNotebooks = React.useCallback(async (): Promise<NotebookFilterOption[]> => {
    const merged: NotebookFilterOption[] = []
    const seenIds = new Set<number>()
    let offset = 0
    for (let pageIndex = 0; pageIndex < NOTEBOOK_COLLECTION_MAX_PAGES; pageIndex += 1) {
      const params = new URLSearchParams()
      params.set('limit', String(NOTEBOOK_COLLECTION_PAGE_SIZE))
      params.set('offset', String(offset))
      params.set('include_keywords', 'true')
      const response = await bgRequest<any>({
        path: `/api/v1/notes/collections?${params.toString()}` as any,
        method: 'GET' as any
      })
      const pageItems = normalizeNotebookCollectionsResponse(response)
      for (const notebook of pageItems) {
        if (seenIds.has(notebook.id)) continue
        seenIds.add(notebook.id)
        merged.push(notebook)
      }
      const totalHint = Number(
        (response as any)?.total ??
          (response as any)?.pagination?.total_items ??
          NaN
      )
      if (pageItems.length < NOTEBOOK_COLLECTION_PAGE_SIZE) break
      if (Number.isFinite(totalHint) && merged.length >= totalHint) break
      offset += NOTEBOOK_COLLECTION_PAGE_SIZE
    }
    return normalizeNotebookOptions(merged)
  }, [])

  const upsertNotebookOnServer = React.useCallback(
    async ({
      notebookName,
      keywords,
      existingNotebookId
    }: {
      notebookName: string
      keywords: string[]
      existingNotebookId?: number | null
    }): Promise<NotebookFilterOption | null> => {
      const payload = {
        name: notebookName,
        parent_id: null,
        keywords: normalizeNotebookKeywords(keywords)
      }

      if (existingNotebookId != null) {
        try {
          const updated = await bgRequest<any>({
            path: `/api/v1/notes/collections/${existingNotebookId}` as any,
            method: 'PATCH' as any,
            body: payload as any
          })
          const normalizedUpdated = normalizeNotebookCollectionFromServer(updated)
          if (normalizedUpdated) return normalizedUpdated
        } catch {
          // Fall back to create for local IDs that do not exist server-side.
        }
      }

      const created = await bgRequest<any>({
        path: '/api/v1/notes/collections' as any,
        method: 'POST' as any,
        body: payload as any
      })
      return normalizeNotebookCollectionFromServer(created)
    },
    []
  )

  const deleteNotebookOnServer = React.useCallback(async (notebookId: number) => {
    await bgRequest<any>({
      path: `/api/v1/notes/collections/${notebookId}` as any,
      method: 'DELETE' as any
    })
  }, [])

  const migrateLocalNotebooksToServer = React.useCallback(
    async (localNotebooks: NotebookFilterOption[]): Promise<NotebookFilterOption[]> => {
      const normalizedLocal = normalizeNotebookOptions(localNotebooks)
      if (normalizedLocal.length === 0) return []
      for (const notebook of normalizedLocal) {
        try {
          await upsertNotebookOnServer({
            notebookName: notebook.name,
            keywords: notebook.keywords,
            existingNotebookId: notebook.id
          })
        } catch {
          // Continue best-effort migration for remaining notebooks.
        }
      }
      const fetched = await fetchServerNotebooks()
      return fetched.length > 0 ? fetched : normalizedLocal
    },
    [fetchServerNotebooks, upsertNotebookOnServer]
  )

  const createNotebookFromCurrentKeywords = React.useCallback(async () => {
    const normalizedKeywords = normalizeNotebookKeywords(keywordTokens)
    if (normalizedKeywords.length === 0) {
      message.info('Select at least one keyword before saving a notebook.')
      return
    }
    if (typeof window === 'undefined') return

    const defaultName = buildNotebookDefaultName(normalizedKeywords)
    const rawName = window.prompt('Smart collection name', defaultName)
    if (rawName == null) return

    const notebookName = normalizeNotebookName(rawName)
    if (!notebookName) {
      message.warning('Smart collection name cannot be empty.')
      return
    }

    const normalizedCurrent = normalizeNotebookOptions(notebookOptions)
    const existing = normalizedCurrent.find(
      (entry) => entry.name.toLowerCase() === notebookName.toLowerCase()
    )
    let selectedNotebookAfterSave: NotebookFilterOption | null = null
    if (existing) {
      const updatedOptions = normalizeNotebookOptions(
        normalizedCurrent.map((entry) =>
          entry.id === existing.id
            ? {
                ...entry,
                name: notebookName,
                keywords: normalizedKeywords
              }
            : entry
        )
      )
      setNotebookOptions(updatedOptions)
      selectedNotebookAfterSave = updatedOptions.find((entry) => entry.id === existing.id) || null
      setSelectedNotebookId(existing.id)
    } else {
      const nextId =
        normalizedCurrent.reduce((maxId, entry) => Math.max(maxId, entry.id), 0) + 1
      const createdLocal = { id: nextId, name: notebookName, keywords: normalizedKeywords }
      const nextOptions = normalizeNotebookOptions([
        ...normalizedCurrent,
        createdLocal
      ])
      setNotebookOptions(nextOptions)
      selectedNotebookAfterSave = nextOptions.find((entry) => entry.id === nextId) || null
      setSelectedNotebookId(nextId)
    }
    setKeywordTokens([])
    setPage(1)
    message.success(`Saved smart collection "${notebookName}"`)

    if (isOnline && selectedNotebookAfterSave) {
      try {
        const persisted = await upsertNotebookOnServer({
          notebookName: selectedNotebookAfterSave.name,
          keywords: selectedNotebookAfterSave.keywords,
          existingNotebookId: selectedNotebookAfterSave.id
        })
        if (persisted) {
          setNotebookOptions((current) =>
            normalizeNotebookOptions(
              current.map((entry) =>
                entry.id === selectedNotebookAfterSave?.id
                  ? persisted
                  : entry
              )
            )
          )
          setSelectedNotebookId(persisted.id)
        }
      } catch {
        message.warning('Saved locally, but failed to sync notebook to server.')
      }
    }
  }, [isOnline, keywordTokens, message, notebookOptions, upsertNotebookOnServer])

  const removeSelectedNotebook = React.useCallback(async () => {
    if (selectedNotebookId == null) return
    const notebookToRemove =
      notebookOptions.find((entry) => entry.id === selectedNotebookId) || null
    if (!notebookToRemove) {
      setSelectedNotebookId(null)
      return
    }
    const ok = await confirmDanger({
      title: 'Remove notebook?',
      content: `Remove "${notebookToRemove.name}" from notebook filters? This does not delete any notes.`,
      okText: 'Remove',
      cancelText: 'Cancel'
    })
    if (!ok) return
    setNotebookOptions((current) =>
      current.filter((entry) => entry.id !== notebookToRemove.id)
    )
    setSelectedNotebookId(null)
    setPage(1)
    message.success(`Removed notebook "${notebookToRemove.name}"`)
    if (isOnline) {
      try {
        await deleteNotebookOnServer(notebookToRemove.id)
      } catch {
        message.warning('Removed locally, but failed to remove notebook on server.')
      }
    }
  }, [confirmDanger, deleteNotebookOnServer, isOnline, message, notebookOptions, selectedNotebookId])

  const handleClearFilters = React.useCallback(() => {
    setQuery('')
    setQueryInput('')
    setKeywordTokens([])
    setSelectedNotebookId(null)
    setPage(1)
  }, [])

  React.useEffect(() => {
    if (
      listMode === 'active' &&
      (queryInput.trim().length > 0 ||
        effectiveKeywordTokens.length > 0 ||
        selectedNotebookId != null)
    ) {
      return
    }
  }, [effectiveKeywordTokens.length, listMode, queryInput, selectedNotebookId])

  React.useEffect(() => {
    if (queryInput === query) return
    if (typeof window === 'undefined') {
      setQuery(queryInput)
      setPage(1)
      return
    }
    clearSearchQueryTimeout()
    searchQueryTimeoutRef.current = window.setTimeout(() => {
      setQuery(queryInput)
      setPage(1)
      searchQueryTimeoutRef.current = null
    }, NOTE_SEARCH_DEBOUNCE_MS)
    return () => {
      clearSearchQueryTimeout()
    }
  }, [clearSearchQueryTimeout, query, queryInput])

  React.useEffect(() => {
    if (!usesLargePreviewGuardrails) {
      setLargePreviewReady(true)
      return
    }
    setLargePreviewReady(false)
    if (typeof window === 'undefined') {
      setLargePreviewReady(true)
      return
    }
    const timeoutId = window.setTimeout(() => {
      setLargePreviewReady(true)
    }, LARGE_NOTE_PREVIEW_DELAY_MS)
    return () => {
      window.clearTimeout(timeoutId)
    }
  }, [previewContent, usesLargePreviewGuardrails])

  React.useEffect(() => {
    if (!isOnline) return
    if (conversationIdsToResolve.length === 0) return
    void resolveConversationLabels(conversationIdsToResolve)
  }, [conversationIdsToResolve, isOnline, resolveConversationLabels])

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
      if (!isEditorSaveShortcutContext(event.target)) return
      event.preventDefault()
      if (editorDisabled) return
      void saveNote()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [editorDisabled, saveNote])

  React.useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return
      if (event.key !== '?') return
      if (event.metaKey || event.ctrlKey || event.altKey) return
      if (shouldIgnoreGlobalShortcut(event.target)) return
      event.preventDefault()
      setShortcutHelpOpen(true)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

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
      clearSearchQueryTimeout()
      if (keywordSearchTimeoutRef.current != null) {
        clearTimeout(keywordSearchTimeoutRef.current)
      }
      clearAutosaveTimeout()
    }
  }, [clearAutosaveTimeout, clearSearchQueryTimeout])

  React.useEffect(() => {
    // When selecting a different note, default back to edit mode so users can start typing immediately.
    setEditorMode('edit')
    setManualLinkTargetId(null)
    setRemoteVersionInfo(null)
    setEditorCursorIndex(null)
    setWikilinkSelectionIndex(0)
    setWysiwygSessionDirty(false)
  }, [selectedId])

  React.useEffect(() => {
    if (selectedId == null) {
      setGraphModalOpen(false)
    }
  }, [selectedId])

  React.useEffect(() => {
    if (listMode !== 'active') {
      setBulkSelectedIds([])
      bulkSelectionAnchorRef.current = null
      return
    }
    if (orderedVisibleNoteIds.length === 0) {
      setBulkSelectedIds([])
      bulkSelectionAnchorRef.current = null
      return
    }
    setBulkSelectedIds((current) => {
      const visibleSet = new Set(orderedVisibleNoteIds)
      const filtered = current.filter((id) => visibleSet.has(id))
      const unchanged =
        filtered.length === current.length &&
        filtered.every((id, index) => id === current[index])
      return unchanged ? current : filtered
    })
    if (
      bulkSelectionAnchorRef.current &&
      !orderedVisibleNoteIds.includes(bulkSelectionAnchorRef.current)
    ) {
      bulkSelectionAnchorRef.current = null
    }
  }, [listMode, orderedVisibleNoteIds])

  React.useEffect(() => {
    if (editorInputMode !== 'wysiwyg') return
    if (wysiwygSessionDirty) return
    setWysiwygHtml(markdownToWysiwygHtml(content))
  }, [content, editorInputMode, wysiwygSessionDirty])

  React.useEffect(() => {
    resizeEditorTextarea()
  }, [content, editorInputMode, editorMode, resizeEditorTextarea])

  React.useEffect(() => {
    if (typeof window === 'undefined') return
    const onResize = () => resizeEditorTextarea()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [resizeEditorTextarea])

  React.useEffect(() => {
    if (typeof window === 'undefined') {
      setOfflineDraftQueueHydrated(true)
      return
    }
    try {
      const raw = window.localStorage.getItem(NOTES_OFFLINE_DRAFT_QUEUE_STORAGE_KEY)
      if (!raw) {
        setOfflineDraftQueue({})
        return
      }
      const parsed = JSON.parse(raw)
      setOfflineDraftQueue(normalizeOfflineDraftQueue(parsed))
    } catch {
      setOfflineDraftQueue({})
    } finally {
      setOfflineDraftQueueHydrated(true)
    }
  }, [])

  React.useEffect(() => {
    if (!offlineDraftQueueHydrated) return
    if (typeof window === 'undefined') return
    try {
      window.localStorage.setItem(
        NOTES_OFFLINE_DRAFT_QUEUE_STORAGE_KEY,
        JSON.stringify(offlineDraftQueue)
      )
    } catch {
      // Ignore localStorage quota/transient persistence failures.
    }
  }, [offlineDraftQueue, offlineDraftQueueHydrated])

  React.useEffect(() => {
    if (!offlineDraftQueueHydrated) return
    if (restoredInitialOfflineDraftRef.current) return
    if (selectedId != null) return
    if (title.trim().length > 0 || content.trim().length > 0 || editorKeywords.length > 0) return
    const draft = offlineDraftQueue[NOTES_OFFLINE_NEW_DRAFT_KEY]
    if (!draft) return
    restoredInitialOfflineDraftRef.current = true
    applyOfflineDraftToEditor(draft)
  }, [
    applyOfflineDraftToEditor,
    content,
    editorKeywords,
    offlineDraftQueue,
    offlineDraftQueueHydrated,
    selectedId,
    title
  ])

  React.useEffect(() => {
    if (!offlineDraftQueueHydrated) return
    if (isOnline) return
    if (editorDisabled) return
    if (!isDirty) return
    if (!content.trim() && !title.trim() && editorKeywords.length === 0) return
    const timeoutId = window.setTimeout(() => {
      upsertOfflineDraft({
        syncState: 'queued',
        lastError: null
      })
    }, 250)
    return () => {
      window.clearTimeout(timeoutId)
    }
  }, [
    content,
    editorDisabled,
    editorKeywords,
    isDirty,
    isOnline,
    offlineDraftQueueHydrated,
    title,
    upsertOfflineDraft
  ])

  React.useEffect(() => {
    if (!offlineDraftQueueHydrated) return
    if (!isOnline) return
    void syncOfflineDraftQueue()
  }, [isOnline, offlineDraftQueueHydrated, syncOfflineDraftQueue])

  React.useEffect(() => {
    let cancelled = false
    void (async () => {
      const savedStrategy = await getSetting(NOTES_TITLE_SUGGEST_STRATEGY_SETTING)
      if (cancelled) return
      const normalized = normalizeNotesTitleStrategy(savedStrategy)
      if (!normalized) return
      setTitleSuggestStrategy(normalized)
    })()
    return () => {
      cancelled = true
    }
  }, [])

  React.useEffect(() => {
    let cancelled = false
    void (async () => {
      const savedRecent = await getSetting(NOTES_RECENT_OPENED_SETTING)
      if (cancelled) return
      if (!Array.isArray(savedRecent)) return
      setRecentNotes(savedRecent)
    })()
    return () => {
      cancelled = true
    }
  }, [])

  React.useEffect(() => {
    let cancelled = false
    void (async () => {
      const savedPinned = await getSetting(NOTES_PINNED_IDS_SETTING)
      if (cancelled) return
      if (!Array.isArray(savedPinned)) return
      const normalized = savedPinned
        .map((entry) => String(entry || '').trim())
        .filter((entry) => entry.length > 0)
        .filter((entry, index, arr) => arr.indexOf(entry) === index)
        .slice(0, 500)
      setPinnedNoteIds(normalized)
    })()
    return () => {
      cancelled = true
    }
  }, [])

  React.useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const savedNotebooks = await getSetting(NOTES_NOTEBOOKS_SETTING)
        if (cancelled) return
        const localNotebooks = normalizeNotebookOptions(savedNotebooks)
        if (!isOnline) {
          setNotebookOptions(localNotebooks)
          return
        }
        try {
          const serverNotebooks = await fetchServerNotebooks()
          if (cancelled) return
          if (serverNotebooks.length > 0) {
            setNotebookOptions(serverNotebooks)
            return
          }
          if (localNotebooks.length > 0) {
            const migrated = await migrateLocalNotebooksToServer(localNotebooks)
            if (cancelled) return
            setNotebookOptions(migrated)
            return
          }
          setNotebookOptions([])
        } catch {
          if (cancelled) return
          setNotebookOptions(localNotebooks)
        }
      } finally {
        if (!cancelled) {
          notebookSettingsHydratedRef.current = true
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [fetchServerNotebooks, isOnline, migrateLocalNotebooksToServer])

  React.useEffect(() => {
    if (!notebookSettingsHydratedRef.current) return
    void setSetting(NOTES_NOTEBOOKS_SETTING, normalizeNotebookOptions(notebookOptions))
  }, [notebookOptions])

  React.useEffect(() => {
    if (selectedNotebookId == null) return
    if (notebookOptions.some((entry) => entry.id === selectedNotebookId)) return
    setSelectedNotebookId(null)
  }, [notebookOptions, selectedNotebookId])

  React.useEffect(() => {
    let cancelled = false
    void (async () => {
      const savedPageSize = await getSetting(NOTES_PAGE_SIZE_SETTING)
      if (cancelled) return
      if (typeof savedPageSize === 'number' && [20, 50, 100].includes(savedPageSize)) {
        setPageSize(savedPageSize)
      }
      pageSizeSettingHydratedRef.current = true
    })()
    return () => {
      cancelled = true
    }
  }, [])

  React.useEffect(() => {
    if (!pageSizeSettingHydratedRef.current) return
    void setSetting(NOTES_PAGE_SIZE_SETTING, pageSize)
  }, [pageSize])

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
  const [mobileSidebarOpen, setMobileSidebarOpen] = React.useState(false)
  const [shortcutHelpOpen, setShortcutHelpOpen] = React.useState(false)
  const desktopSidebarCollapsedRef = React.useRef(false)

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

  React.useEffect(() => {
    if (!isMobileViewport) {
      desktopSidebarCollapsedRef.current = sidebarCollapsed
    }
  }, [isMobileViewport, sidebarCollapsed])

  React.useEffect(() => {
    if (isMobileViewport) {
      setSidebarCollapsed(true)
      setMobileSidebarOpen(false)
      return
    }
    setMobileSidebarOpen(false)
    setSidebarCollapsed(desktopSidebarCollapsedRef.current)
  }, [isMobileViewport])

  const searchableTips = React.useMemo(
    () => [
      {
        id: 'phrase',
        text: t('option:notesSearch.searchTipPhrase', {
          defaultValue: 'Use quotes for phrases, e.g. "project roadmap".'
        })
      },
      {
        id: 'prefix',
        text: t('option:notesSearch.searchTipPrefix', {
          defaultValue: 'Use prefix terms (like analy*) for broader matches.'
        })
      },
      {
        id: 'and',
        text: t('option:notesSearch.searchTipAnd', {
          defaultValue: 'Text query + selected keywords are combined with AND.'
        })
      },
      {
        id: 'in-note',
        text: t('option:notesSearch.searchTipInNote', {
          defaultValue: 'To find text inside the open note, use browser Ctrl/Cmd+F.'
        })
      }
    ],
    [t]
  )

  const filteredSearchTips = React.useMemo(() => {
    const queryLower = searchTipsQuery.trim().toLowerCase()
    if (!queryLower) return searchableTips
    return searchableTips.filter((tip) => tip.text.toLowerCase().includes(queryLower))
  }, [searchTipsQuery, searchableTips])

  const searchTipsContent = React.useMemo(
    () => (
      <div className="max-w-[300px] space-y-2 text-xs text-text">
        <Input
          size="small"
          allowClear
          placeholder={t('option:notesSearch.searchTipsFilterPlaceholder', {
            defaultValue: 'Filter tips...'
          })}
          value={searchTipsQuery}
          onChange={(event) => setSearchTipsQuery(event.target.value)}
          data-testid="notes-search-tips-filter"
        />
        <div className="space-y-1">
          {filteredSearchTips.length === 0 ? (
            <Typography.Text
              type="secondary"
              className="block text-[11px] text-text-muted"
              data-testid="notes-search-tips-empty"
            >
              {t('option:notesSearch.searchTipsEmpty', {
                defaultValue: 'No matching tips.'
              })}
            </Typography.Text>
          ) : (
            filteredSearchTips.map((tip) => (
              <div key={tip.id} data-testid={`notes-search-tip-${tip.id}`}>
                {tip.text}
              </div>
            ))
          )}
        </div>
      </div>
    ),
    [filteredSearchTips, searchTipsQuery, t]
  )

  const timelineSections = React.useMemo(() => {
    if (listMode !== 'active') return [] as Array<{
      key: string
      label: string
      notes: NoteListItem[]
    }>

    const bucketMap = new Map<string, NoteListItem[]>()
    for (const note of visibleNotes) {
      const rawTimestamp = toSortableTimestamp(note.updated_at)
      if (rawTimestamp <= 0) {
        const fallback = bucketMap.get('unknown') || []
        fallback.push(note)
        bucketMap.set('unknown', fallback)
        continue
      }
      const parsed = new Date(rawTimestamp)
      const key = `${parsed.getUTCFullYear()}-${String(parsed.getUTCMonth() + 1).padStart(2, '0')}`
      const bucket = bucketMap.get(key) || []
      bucket.push(note)
      bucketMap.set(key, bucket)
    }

    const orderedKeys = Array.from(bucketMap.keys()).sort((a, b) => {
      if (a === 'unknown') return 1
      if (b === 'unknown') return -1
      return b.localeCompare(a)
    })

    return orderedKeys.map((key) => {
      const notesForKey = bucketMap.get(key) || []
      notesForKey.sort((a, b) => toSortableTimestamp(b.updated_at) - toSortableTimestamp(a.updated_at))
      if (key === 'unknown') {
        return {
          key,
          label: t('option:notesSearch.timelineUnknownDate', {
            defaultValue: 'Unknown date'
          }),
          notes: notesForKey
        }
      }
      const monthLabel = `${key}-01T00:00:00.000Z`
      const parsed = new Date(monthLabel)
      const label = Number.isNaN(parsed.getTime())
        ? key
        : parsed.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
      return {
        key,
        label,
        notes: notesForKey
      }
    })
  }, [listMode, t, visibleNotes])

  const handleSkipLinkActivate = React.useCallback(
    (targetId: string) => (event: React.MouseEvent<HTMLAnchorElement>) => {
      event.preventDefault()
      const sidebarHidden = isMobileViewport ? !mobileSidebarOpen : sidebarCollapsed
      if (targetId === NOTES_LIST_REGION_ID && sidebarHidden) {
        if (isMobileViewport) {
          setMobileSidebarOpen(true)
        } else {
          setSidebarCollapsed(false)
        }
      }
      window.requestAnimationFrame(() => {
        const target = document.getElementById(targetId) as HTMLElement | null
        if (!target) return
        target.focus()
        if (typeof window !== 'undefined') {
          window.location.hash = targetId
        }
      })
    },
    [isMobileViewport, mobileSidebarOpen, sidebarCollapsed]
  )

  return (
    <div className="relative flex h-full w-full bg-bg p-2 sm:p-4 mt-16">
      <a
        href={`#${NOTES_LIST_REGION_ID}`}
        onClick={handleSkipLinkActivate(NOTES_LIST_REGION_ID)}
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:border focus:border-border focus:bg-surface focus:px-3 focus:py-2 focus:text-sm focus:text-text focus:shadow"
      >
        {t('option:notesSearch.skipToNotesList', {
          defaultValue: 'Skip to notes list'
        })}
      </a>
      <a
        href={`#${NOTES_EDITOR_REGION_ID}`}
        onClick={handleSkipLinkActivate(NOTES_EDITOR_REGION_ID)}
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-12 focus:z-50 focus:rounded-md focus:border focus:border-border focus:bg-surface focus:px-3 focus:py-2 focus:text-sm focus:text-text focus:shadow"
      >
        {t('option:notesSearch.skipToEditor', {
          defaultValue: 'Skip to editor'
        })}
      </a>
      <p id={NOTES_SHORTCUTS_SUMMARY_ID} className="sr-only">
        {t('option:notesSearch.shortcutSummaryText', {
          defaultValue:
            'Keyboard shortcuts: Ctrl or Command plus S to save, question mark to open keyboard shortcuts help, Escape to close dialogs.'
        })}
      </p>
      {isMobileViewport && mobileSidebarOpen && (
        <button
          type="button"
          aria-label={t('option:notesSearch.closeMobileSidebar', {
            defaultValue: 'Close notes list'
          })}
          data-testid="notes-mobile-sidebar-backdrop"
          className="absolute inset-0 z-30 bg-black/35"
          onClick={() => setMobileSidebarOpen(false)}
        />
      )}
      {/* Collapsible Sidebar */}
      <NotesSidebar
        isMobileViewport={isMobileViewport}
        mobileSidebarOpen={mobileSidebarOpen}
        sidebarCollapsed={sidebarCollapsed}
        sidebarHeight={sidebarHeight}
        listMode={listMode}
        listViewMode={listViewMode}
        page={page}
        pageSize={pageSize}
        total={total}
        sortOption={sortOption}
        selectedId={selectedId}
        visibleNotes={visibleNotes}
        filteredCount={filteredCount}
        timelineSections={timelineSections}
        recentNotes={recentNotes}
        pinnedNoteIds={pinnedNoteIds}
        pinnedNoteIdSet={pinnedNoteIdSet}
        queryInput={queryInput}
        hasActiveFilters={hasActiveFilters}
        activeFilterSummary={activeFilterSummary}
        keywordTokens={keywordTokens}
        keywordOptions={keywordOptions}
        availableKeywords={availableKeywords}
        notebookOptions={notebookOptions}
        selectedNotebookId={selectedNotebookId}
        selectedNotebook={selectedNotebook}
        moodboards={moodboards}
        selectedMoodboardId={selectedMoodboardId}
        selectedMoodboard={selectedMoodboard}
        isMoodboardsFetching={isMoodboardsFetching}
        moodboardTotalPages={moodboardTotalPages}
        moodboardCanGoPrev={moodboardCanGoPrev}
        moodboardCanGoNext={moodboardCanGoNext}
        moodboardRangeStart={moodboardRangeStart}
        moodboardRangeEnd={moodboardRangeEnd}
        bulkSelectedIds={bulkSelectedIds}
        searchTipsContent={searchTipsContent}
        query={query}
        isFetching={isFetching}
        isOnline={isOnline}
        demoEnabled={demoEnabled}
        capsLoading={capsLoading}
        capabilities={capabilities || null}
        queuedOfflineDraftCount={queuedOfflineDraftCount}
        showLargeListPaginationHint={showLargeListPaginationHint}
        conversationLabelById={conversationLabelById}
        importSubmitting={importSubmitting}
        exportProgress={exportProgress}
        setMobileSidebarOpen={setMobileSidebarOpen}
        setListViewMode={setListViewMode}
        setPage={setPage}
        setPageSize={setPageSize}
        setSortOption={setSortOption}
        setQueryInput={setQueryInput}
        setSelectedMoodboardId={setSelectedMoodboardId}
        setSelectedNotebookId={setSelectedNotebookId}
        setSearchTipsQuery={setSearchTipsQuery}
        handleNewNote={handleNewNote}
        switchListMode={switchListMode}
        handleSelectNote={handleSelectNote}
        handleClearFilters={handleClearFilters}
        handleKeywordFilterSearch={handleKeywordFilterSearch}
        handleKeywordFilterChange={handleKeywordFilterChange}
        handleToggleBulkSelection={handleToggleBulkSelection}
        clearSearchQueryTimeout={clearSearchQueryTimeout}
        setQuery={setQuery}
        openKeywordPicker={openKeywordPicker}
        createNotebookFromCurrentKeywords={createNotebookFromCurrentKeywords}
        removeSelectedNotebook={removeSelectedNotebook}
        createMoodboard={createMoodboard}
        renameMoodboard={renameMoodboard}
        deleteMoodboard={deleteMoodboard}
        clearBulkSelection={clearBulkSelection}
        exportSelectedBulk={exportSelectedBulk}
        assignKeywordsToSelectedBulk={assignKeywordsToSelectedBulk}
        deleteSelectedBulk={deleteSelectedBulk}
        toggleNotePinned={toggleNotePinned}
        restoreNote={restoreNote}
        exportAll={exportAll}
        exportAllCSV={exportAllCSV}
        exportAllJSON={exportAllJSON}
        openImportPicker={openImportPicker}
        resetEditor={resetEditor}
        renderKeywordLabelWithFrequency={renderKeywordLabelWithFrequency}
        onOpenSettings={() => navigate('/settings/tldw')}
        onOpenHealth={() => navigate('/settings/health')}
      />

      {/* Collapse Button - Simple style like Media page */}
      {!isMobileViewport && (
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
          data-testid="notes-desktop-sidebar-toggle"
        >
          <div className="flex items-center justify-center w-full h-full">
            {sidebarCollapsed ? (
              <ChevronRight className="w-4 h-4 text-text-subtle group-hover:text-text" />
            ) : (
              <ChevronLeft className="w-4 h-4 text-text-subtle group-hover:text-text" />
            )}
          </div>
        </button>
      )}

      {/* Editor Panel */}
      <NotesEditorPane
        isMobileViewport={isMobileViewport}
        setMobileSidebarOpen={setMobileSidebarOpen}
        selectedId={selectedId}
        title={title}
        content={content}
        editorDisabled={editorDisabled}
        isDirty={isDirty}
        isOnline={isOnline}
        loadingDetail={loadingDetail}
        saving={saving}
        backlinkConversationId={backlinkConversationId}
        backlinkConversationLabel={backlinkConversationLabel}
        backlinkMessageId={backlinkMessageId}
        noteRelations={noteRelations}
        noteNeighborsLoading={noteNeighborsLoading}
        noteNeighborsError={noteNeighborsError}
        selectedNotePinned={selectedNotePinned}
        editorMode={editorMode}
        editorInputMode={editorInputMode}
        openingLinkedChat={openingLinkedChat}
        editorKeywords={editorKeywords}
        keywordOptions={keywordOptions}
        saveIndicator={saveIndicator}
        saveIndicatorText={saveIndicatorText}
        selectedLastSavedAt={selectedLastSavedAt}
        offlineStatusText={offlineStatusText}
        currentOfflineDraft={currentOfflineDraft}
        remoteVersionInfo={remoteVersionInfo}
        monitoringNotice={monitoringNotice}
        monitoringNoticeClasses={monitoringNoticeClasses}
        titleSuggestionLoading={titleSuggestionLoading}
        canSwitchTitleStrategy={canSwitchTitleStrategy}
        effectiveTitleSuggestStrategy={effectiveTitleSuggestStrategy}
        titleStrategyOptions={titleStrategyOptions}
        setTitleSuggestStrategy={setTitleSuggestStrategy}
        manualLinkTargetId={manualLinkTargetId}
        setManualLinkTargetId={setManualLinkTargetId}
        manualLinkSaving={manualLinkSaving}
        manualLinkOptions={manualLinkOptions}
        manualLinkDeletingEdgeId={manualLinkDeletingEdgeId}
        assistLoadingAction={assistLoadingAction}
        shouldShowToc={shouldShowToc}
        tocEntries={tocEntries}
        previewContent={previewContent}
        usesLargePreviewGuardrails={usesLargePreviewGuardrails}
        largePreviewReady={largePreviewReady}
        wysiwygHtml={wysiwygHtml}
        activeWikilinkQuery={activeWikilinkQuery}
        wikilinkSuggestions={wikilinkSuggestions}
        wikilinkSuggestionDisplayCounts={wikilinkSuggestionDisplayCounts}
        wikilinkSelectionIndex={wikilinkSelectionIndex}
        metricSummaryText={metricSummaryText}
        revisionSummaryText={revisionSummaryText}
        provenanceSummaryText={provenanceSummaryText}
        queuedOfflineDraftCount={queuedOfflineDraftCount}
        titleInputRef={titleInputRef}
        contentTextareaRef={contentTextareaRef}
        richEditorRef={richEditorRef}
        attachmentInputRef={attachmentInputRef}
        setTitle={setTitle}
        setIsDirty={setIsDirty}
        setSaveIndicator={setSaveIndicator}
        setMonitoringNotice={setMonitoringNotice}
        setEditorMode={setEditorMode}
        setEditorKeywords={setEditorKeywords}
        setEditorCursorIndex={setEditorCursorIndex}
        setShortcutHelpOpen={setShortcutHelpOpen}
        markManualEdit={markManualEdit}
        suggestTitle={suggestTitle}
        openLinkedConversation={openLinkedConversation}
        openLinkedSource={openLinkedSource}
        handleNewNote={handleNewNote}
        duplicateSelectedNote={duplicateSelectedNote}
        toggleNotePinned={toggleNotePinned}
        copySelected={copySelected}
        handleGenerateFlashcardsFromNote={handleGenerateFlashcardsFromNote}
        exportSelected={exportSelected}
        saveNote={saveNote}
        deleteNote={deleteNote}
        handleSelectNote={handleSelectNote}
        openGraphModal={openGraphModal}
        createManualLink={createManualLink}
        removeManualLink={removeManualLink}
        debouncedLoadKeywordSuggestions={debouncedLoadKeywordSuggestions}
        renderKeywordLabelWithFrequency={renderKeywordLabelWithFrequency}
        handleEditorInputModeChange={handleEditorInputModeChange}
        applyMarkdownToolbarAction={applyMarkdownToolbarAction}
        openAttachmentPicker={openAttachmentPicker}
        handleAttachmentInputChange={handleAttachmentInputChange}
        runAssistAction={runAssistAction}
        handleTocJump={handleTocJump}
        handlePreviewLinkClick={handlePreviewLinkClick}
        handleWysiwygInput={handleWysiwygInput}
        handleWysiwygPaste={handleWysiwygPaste}
        handleEditorChange={handleEditorChange}
        handleEditorKeyDown={handleEditorKeyDown}
        handleEditorSelectionUpdate={handleEditorSelectionUpdate}
        applyWikilinkSuggestion={applyWikilinkSuggestion}
      />
      <Modal
        open={keywordSuggestionOptions.length > 0}
        onCancel={closeKeywordSuggestionModal}
        onOk={applySelectedSuggestedKeywords}
        okText={t('option:notesSearch.assistKeywordsApplySelectedAction', {
          defaultValue: 'Apply selected'
        })}
        cancelText={t('common:cancel', { defaultValue: 'Cancel' })}
        destroyOnHidden
        title={t('option:notesSearch.assistKeywordsReviewTitle', {
          defaultValue: 'Review suggested keywords'
        })}
      >
        <div className="space-y-3" data-testid="notes-assist-keyword-suggestions-modal">
          <Typography.Text type="secondary" className="block text-xs text-text-muted">
            {t('option:notesSearch.assistKeywordsReviewHelp', {
              defaultValue: 'Select which suggested keywords to add to this note.'
            })}
          </Typography.Text>
          <div className="flex items-center gap-2">
            <Button
              size="small"
              onClick={() => setKeywordSuggestionSelection([...keywordSuggestionOptions])}
              disabled={keywordSuggestionOptions.length === 0}
              data-testid="notes-assist-keyword-select-all"
            >
              {t('option:notesSearch.keywordPickerSelectAll', {
                defaultValue: 'Select all'
              })}
            </Button>
            <Button
              size="small"
              onClick={() => setKeywordSuggestionSelection([])}
              disabled={keywordSuggestionSelection.length === 0}
              data-testid="notes-assist-keyword-clear-all"
            >
              {t('option:notesSearch.keywordPickerClear', {
                defaultValue: 'Clear'
              })}
            </Button>
          </div>
          <Checkbox.Group
            value={keywordSuggestionSelection}
            onChange={(values) => setKeywordSuggestionSelection((values as string[]).map(String))}
            className="w-full"
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 rounded-lg border border-border bg-surface2 p-3">
              {keywordSuggestionOptions.map((keyword) => (
                <Checkbox
                  key={`assist-keyword-${keyword}`}
                  value={keyword}
                  data-testid={`notes-assist-keyword-option-${toKeywordTestIdSegment(keyword)}`}
                >
                  {renderKeywordLabelWithFrequency(keyword, {
                    includeCount: true,
                    testIdPrefix: 'notes-assist-keyword-label'
                  })}
                </Checkbox>
              ))}
            </div>
          </Checkbox.Group>
        </div>
      </Modal>
      {keywordPickerOpen && (
        <React.Suspense fallback={null}>
          <KeywordPickerModal
            open={keywordPickerOpen}
            availableKeywords={availableKeywords}
            filteredKeywordPickerOptions={sortedKeywordPickerOptions}
            recentKeywordPickerOptions={recentKeywordPickerOptions}
            keywordNoteCountByKey={keywordNoteCountByKey}
            sortMode={keywordPickerSortMode}
            keywordPickerQuery={keywordPickerQuery}
            keywordPickerSelection={keywordPickerSelection}
            onCancel={handleKeywordPickerCancel}
            onApply={handleKeywordPickerApply}
            onSortModeChange={handleKeywordPickerSortModeChange}
            onToggleRecentKeyword={handleToggleRecentKeyword}
            onQueryChange={handleKeywordPickerQueryChange}
            onSelectionChange={handleKeywordPickerSelectionChange}
            onSelectAll={handleKeywordPickerSelectAll}
            onClear={handleKeywordPickerClear}
            onOpenManager={openKeywordManagerFromPicker}
            managerDisabled={!isOnline}
            t={t}
          />
        </React.Suspense>
      )}
      <Modal
        open={keywordManagerOpen}
        onCancel={closeKeywordManager}
        title={t('option:notesSearch.keywordManagerTitle', {
          defaultValue: 'Manage keywords'
        })}
        destroyOnHidden
        footer={[
          <Button key="close" onClick={closeKeywordManager}>
            {t('common:close', { defaultValue: 'Close' })}
          </Button>
        ]}
      >
        <div className="space-y-3" data-testid="notes-keyword-manager-modal">
          <Typography.Text type="secondary" className="block text-xs text-text-muted">
            {t('option:notesSearch.keywordManagerHelp', {
              defaultValue: 'Rename, merge, or delete keywords from one place.'
            })}
          </Typography.Text>
          <Input
            allowClear
            value={keywordManagerQuery}
            onChange={(event) => setKeywordManagerQuery(event.target.value)}
            placeholder={t('option:notesSearch.keywordManagerSearchPlaceholder', {
              defaultValue: 'Filter keywords'
            })}
            data-testid="notes-keyword-manager-search"
          />
          <div className="max-h-80 overflow-auto rounded-lg border border-border bg-surface2 p-2">
            {keywordManagerLoading ? (
              <Typography.Text type="secondary" className="text-xs text-text-muted">
                {t('option:notesSearch.keywordManagerLoading', {
                  defaultValue: 'Loading keywords...'
                })}
              </Typography.Text>
            ) : keywordManagerVisibleItems.length === 0 ? (
              <Typography.Text type="secondary" className="text-xs text-text-muted">
                {t('option:notesSearch.keywordManagerEmpty', {
                  defaultValue: 'No keywords found.'
                })}
              </Typography.Text>
            ) : (
              <div className="space-y-2">
                {keywordManagerVisibleItems.map((item) => (
                  <div
                    key={`manager-${item.id}`}
                    className="rounded border border-border bg-surface px-2 py-2"
                    data-testid={`notes-keyword-manager-item-${item.id}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <div className="truncate text-sm text-text">{item.keyword}</div>
                        <div className="text-[11px] text-text-muted">
                          {t('option:notesSearch.keywordManagerUsage', {
                            defaultValue: '{{count}} linked notes',
                            count: item.noteCount
                          })}
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-1">
                        <Button
                          size="small"
                          onClick={() =>
                            setKeywordRenameDraft({
                              id: item.id,
                              currentKeyword: item.keyword,
                              expectedVersion: item.version,
                              nextKeyword: item.keyword
                            })
                          }
                          disabled={keywordManagerActionLoading}
                          data-testid={`notes-keyword-manager-rename-${item.id}`}
                        >
                          {t('option:notesSearch.keywordManagerRenameAction', {
                            defaultValue: 'Rename'
                          })}
                        </Button>
                        <Button
                          size="small"
                          onClick={() =>
                            setKeywordMergeDraft({
                              source: item,
                              targetKeywordId: null
                            })
                          }
                          disabled={keywordManagerActionLoading}
                          data-testid={`notes-keyword-manager-merge-${item.id}`}
                        >
                          {t('option:notesSearch.keywordManagerMergeAction', {
                            defaultValue: 'Merge'
                          })}
                        </Button>
                        <Button
                          size="small"
                          danger
                          onClick={() => {
                            void handleKeywordManagerDelete(item)
                          }}
                          disabled={keywordManagerActionLoading}
                          data-testid={`notes-keyword-manager-delete-${item.id}`}
                        >
                          {t('option:notesSearch.keywordManagerDeleteAction', {
                            defaultValue: 'Delete'
                          })}
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </Modal>
      <Modal
        open={keywordRenameDraft != null}
        onCancel={() => setKeywordRenameDraft(null)}
        onOk={() => {
          void submitKeywordRename()
        }}
        okText={t('option:notesSearch.keywordManagerRenameAction', {
          defaultValue: 'Rename'
        })}
        cancelText={t('common:cancel', { defaultValue: 'Cancel' })}
        confirmLoading={keywordManagerActionLoading}
        destroyOnHidden
        title={t('option:notesSearch.keywordManagerRenameTitle', {
          defaultValue: 'Rename keyword'
        })}
      >
        <div className="space-y-2">
          <Typography.Text type="secondary" className="block text-xs text-text-muted">
            {t('option:notesSearch.keywordManagerRenameHelp', {
              defaultValue: 'Choose a new name for this keyword.'
            })}
          </Typography.Text>
          <Input
            autoFocus
            value={keywordRenameDraft?.nextKeyword ?? ''}
            onChange={(event) =>
              setKeywordRenameDraft((current) =>
                current
                  ? {
                      ...current,
                      nextKeyword: event.target.value
                    }
                  : current
              )
            }
            data-testid="notes-keyword-manager-rename-input"
          />
        </div>
      </Modal>
      <Modal
        open={keywordMergeDraft != null}
        onCancel={() => setKeywordMergeDraft(null)}
        onOk={() => {
          void submitKeywordMerge()
        }}
        okText={t('option:notesSearch.keywordManagerMergeAction', {
          defaultValue: 'Merge'
        })}
        cancelText={t('common:cancel', { defaultValue: 'Cancel' })}
        confirmLoading={keywordManagerActionLoading}
        destroyOnHidden
        title={t('option:notesSearch.keywordManagerMergeTitle', {
          defaultValue: 'Merge keyword'
        })}
      >
        <div className="space-y-2">
          <Typography.Text type="secondary" className="block text-xs text-text-muted">
            {t('option:notesSearch.keywordManagerMergeHelp', {
              defaultValue:
                'Move all links from the source keyword to the selected target keyword.'
            })}
          </Typography.Text>
          <div className="text-xs text-text-muted">
            {t('option:notesSearch.keywordManagerMergeSourceLabel', {
              defaultValue: 'Source'
            })}
            :{' '}
            <span className="font-medium text-text">
              {keywordMergeDraft?.source.keyword ?? ''}
            </span>
          </div>
          <select
            className="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-text"
            value={keywordMergeDraft?.targetKeywordId ?? ''}
            onChange={(event) => {
              const parsed = Number(event.target.value)
              setKeywordMergeDraft((current) =>
                current
                  ? {
                      ...current,
                      targetKeywordId:
                        Number.isFinite(parsed) && parsed > 0 ? parsed : null
                    }
                  : current
              )
            }}
            data-testid="notes-keyword-manager-merge-target"
          >
            <option value="">
              {t('option:notesSearch.keywordManagerMergeTargetPlaceholder', {
                defaultValue: 'Select target keyword'
              })}
            </option>
            {keywordMergeTargetOptions.map((item) => (
              <option key={`keyword-merge-target-${item.id}`} value={item.id}>
                {item.keyword} ({item.noteCount})
              </option>
            ))}
          </select>
        </div>
      </Modal>
      <input
        ref={importInputRef}
        type="file"
        multiple
        accept=".json,.md,.markdown,application/json,text/markdown,text/plain"
        className="hidden"
        data-testid="notes-import-input"
        onChange={(event) => {
          void handleImportInputChange(event)
        }}
      />
      <Modal
        open={importModalOpen}
        onCancel={closeImportModal}
        onOk={() => {
          void confirmImport()
        }}
        okText={t('option:notesSearch.importConfirmAction', {
          defaultValue: 'Import notes'
        })}
        cancelText={t('common:cancel', { defaultValue: 'Cancel' })}
        confirmLoading={importSubmitting}
        destroyOnHidden
        title={t('option:notesSearch.importModalTitle', {
          defaultValue: 'Import notes'
        })}
      >
        <div className="space-y-3" data-testid="notes-import-modal">
          <Typography.Text type="secondary" className="block text-xs text-text-muted">
            {t('option:notesSearch.importModalHelp', {
              defaultValue:
                'Upload JSON exports or markdown files. Choose how to handle imported IDs that already exist.'
            })}
          </Typography.Text>
          <div className="space-y-1">
            <label htmlFor="notes-import-strategy" className="text-xs font-medium text-text">
              {t('option:notesSearch.importDuplicateStrategyLabel', {
                defaultValue: 'Duplicate handling'
              })}
            </label>
            <select
              id="notes-import-strategy"
              className="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-text"
              value={importDuplicateStrategy}
              onChange={(event) => setImportDuplicateStrategy(event.target.value as ImportDuplicateStrategy)}
              data-testid="notes-import-duplicate-strategy"
            >
              <option value="create_copy">
                {t('option:notesSearch.importDuplicateCreateCopy', {
                  defaultValue: 'Create copy'
                })}
              </option>
              <option value="skip">
                {t('option:notesSearch.importDuplicateSkip', {
                  defaultValue: 'Skip duplicate IDs'
                })}
              </option>
              <option value="overwrite">
                {t('option:notesSearch.importDuplicateOverwrite', {
                  defaultValue: 'Overwrite duplicate IDs'
                })}
              </option>
            </select>
          </div>
          <div
            className="rounded border border-border bg-surface2 px-2 py-2 text-xs text-text-muted"
            data-testid="notes-import-preview-summary"
          >
            {`Files: ${pendingImportFiles.length} · Estimated notes: ${pendingImportFiles.reduce(
              (sum, item) => sum + item.detectedNotes,
              0
            )}`}
          </div>
          <div className="max-h-56 space-y-2 overflow-y-auto pr-1">
            {pendingImportFiles.map((file) => (
              <div
                key={`import-file-${file.fileName}`}
                className="rounded border border-border bg-surface px-2 py-2"
                data-testid={`notes-import-file-${file.fileName.toLowerCase().replace(/[^a-z0-9_-]/g, '_')}`}
              >
                <div className="truncate text-sm text-text">{file.fileName}</div>
                <div className="text-[11px] text-text-muted">
                  {`${file.format.toUpperCase()} · ${file.detectedNotes} note${
                    file.detectedNotes === 1 ? '' : 's'
                  } detected`}
                </div>
                {file.parseError && (
                  <div className="mt-1 text-[11px] text-warn">{file.parseError}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      </Modal>
      <NotesGraphModal
        open={graphModalOpen}
        noteId={selectedId}
        refreshToken={graphMutationTick}
        onClose={closeGraphModal}
        onOpenNote={(noteId) => {
          void handleSelectNote(noteId)
        }}
      />
      <Modal
        open={shortcutHelpOpen}
        onCancel={() => setShortcutHelpOpen(false)}
        footer={null}
        title={t('option:notesSearch.shortcutHelpTitle', {
          defaultValue: 'Keyboard shortcuts'
        })}
        destroyOnHidden
      >
        <div className="space-y-2 text-sm text-text" data-testid="notes-shortcuts-modal">
          <div>
            <strong>Ctrl/Cmd + S</strong>:{' '}
            {t('option:notesSearch.shortcutSaveDescription', {
              defaultValue: 'Save the current note.'
            })}
          </div>
          <div>
            <strong>?</strong>:{' '}
            {t('option:notesSearch.shortcutOpenHelpDescription', {
              defaultValue: 'Open keyboard shortcut help.'
            })}
          </div>
          <div>
            <strong>Esc</strong>:{' '}
            {t('option:notesSearch.shortcutCloseDialogDescription', {
              defaultValue: 'Close the current dialog.'
            })}
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default NotesManagerPage
