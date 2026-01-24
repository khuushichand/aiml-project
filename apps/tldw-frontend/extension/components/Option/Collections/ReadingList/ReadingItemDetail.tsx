import React, { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  Button,
  Drawer,
  Empty,
  message,
  Select,
  Spin,
  Tabs,
  Tooltip,
  Input,
  Modal
} from "antd"
import type { TabsProps } from "antd"
import {
  Star,
  ExternalLink,
  Trash2,
  Archive,
  Clock,
  Calendar,
  Globe,
  Sparkles,
  Volume2,
  FileDown,
  Highlighter,
  StickyNote,
  X
} from "lucide-react"
import DOMPurify from "dompurify"
import { useTranslation } from "react-i18next"
import { useCollectionsStore } from "@/store/collections"
import { useTldwApiClient } from "@/hooks/useTldwApiClient"
import type {
  AnchoringStrategy,
  Highlight,
  HighlightColor,
  ReadingStatus
} from "@/types/collections"
import type { ReadingProgress } from "@/services/reading-progress"
import { clearReadingProgress, getReadingProgress, setReadingProgress } from "@/services/reading-progress"
import { StatusBadge } from "../common/StatusBadge"
import { TagSelector } from "../common/TagSelector"
import { HighlightCard } from "../Highlights/HighlightCard"

const { TextArea } = Input

interface ReadingItemDetailProps {
  onRefresh?: () => void
}

export const ReadingItemDetail: React.FC<ReadingItemDetailProps> = ({
  onRefresh
}) => {
  const { t } = useTranslation(["collections", "common"])
  const api = useTldwApiClient()

  const selectedItemId = useCollectionsStore((s) => s.selectedItemId)
  const currentItem = useCollectionsStore((s) => s.currentItem)
  const currentItemLoading = useCollectionsStore((s) => s.currentItemLoading)
  const itemDetailOpen = useCollectionsStore((s) => s.itemDetailOpen)

  const setCurrentItem = useCollectionsStore((s) => s.setCurrentItem)
  const setCurrentItemLoading = useCollectionsStore((s) => s.setCurrentItemLoading)
  const closeItemDetail = useCollectionsStore((s) => s.closeItemDetail)
  const updateItemInList = useCollectionsStore((s) => s.updateItemInList)
  const removeItem = useCollectionsStore((s) => s.removeItem)
  const addHighlight = useCollectionsStore((s) => s.addHighlight)
  const removeHighlight = useCollectionsStore((s) => s.removeHighlight)
  const openHighlightEditor = useCollectionsStore((s) => s.openHighlightEditor)
  const highlightEditorOpen = useCollectionsStore((s) => s.highlightEditorOpen)
  const editingHighlight = useCollectionsStore((s) => s.editingHighlight)

  const [actionLoading, setActionLoading] = useState(false)
  const [summarizing, setSummarizing] = useState(false)
  const [generatingTts, setGeneratingTts] = useState(false)
  const [editingNotes, setEditingNotes] = useState(false)
  const [notesValue, setNotesValue] = useState("")
  const [notesDirty, setNotesDirty] = useState(false)
  const [notesSaving, setNotesSaving] = useState(false)
  const [notesSaveError, setNotesSaveError] = useState<string | null>(null)
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [itemHighlights, setItemHighlights] = useState<Highlight[]>([])
  const [itemHighlightsLoading, setItemHighlightsLoading] = useState(false)
  const [itemHighlightsError, setItemHighlightsError] = useState<string | null>(null)
  const [highlightQuote, setHighlightQuote] = useState("")
  const [highlightNote, setHighlightNote] = useState("")
  const [highlightColor, setHighlightColor] = useState<HighlightColor>("yellow")
  const [highlightStartOffset, setHighlightStartOffset] = useState<number | null>(null)
  const [highlightEndOffset, setHighlightEndOffset] = useState<number | null>(null)
  const [highlightAnchorStrategy, setHighlightAnchorStrategy] =
    useState<AnchoringStrategy>("fuzzy_quote")
  const [selectionHighlight, setSelectionHighlight] = useState<{
    quote: string
    startOffset: number
    endOffset: number
  } | null>(null)
  const [highlightSaving, setHighlightSaving] = useState(false)
  const [highlightDeleteOpen, setHighlightDeleteOpen] = useState(false)
  const [highlightDeleteId, setHighlightDeleteId] = useState<string | null>(null)
  const [highlightDeleteLoading, setHighlightDeleteLoading] = useState(false)
  const [activeTabKey, setActiveTabKey] = useState("content")
  const [progressPercent, setProgressPercent] = useState<number | null>(null)
  const lastEditedItemId = useRef<string | null>(null)
  const contentRef = useRef<HTMLDivElement | null>(null)
  const scrollContainerRef = useRef<HTMLDivElement | null>(null)
  const notesSaveTokenRef = useRef(0)
  const progressSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastProgressRef = useRef<ReadingProgress | null>(null)
  const lastSavedProgressRef = useRef<string | null>(null)
  const lastRestoredItemRef = useRef<string | null>(null)

  // Fetch item details
  useEffect(() => {
    if (!selectedItemId || !itemDetailOpen) return

    const fetchItem = async () => {
      setCurrentItemLoading(true)
      try {
        const item = await api.getReadingItem(selectedItemId)
        setCurrentItem(item)
        setNotesValue(item.notes || "")
        setEditingNotes(false)
        setNotesDirty(false)
        setNotesSaveError(null)
      } catch (error: any) {
        message.error(error?.message || "Failed to load article details")
        closeItemDetail()
      } finally {
        setCurrentItemLoading(false)
      }
    }

    fetchItem()
  }, [
    selectedItemId,
    itemDetailOpen,
    api,
    setCurrentItem,
    setCurrentItemLoading,
    closeItemDetail
  ])

  const clearSelection = useCallback(() => {
    setSelectionHighlight(null)
    setHighlightStartOffset(null)
    setHighlightEndOffset(null)
    setHighlightAnchorStrategy("fuzzy_quote")
    try {
      const selection = window.getSelection()
      selection?.removeAllRanges()
    } catch (error) {
      // Ignore selection reset failures (non-critical).
    }
  }, [])

  useEffect(() => {
    if (!itemDetailOpen || !currentItem?.id) {
      clearSelection()
    }
  }, [itemDetailOpen, currentItem?.id, clearSelection])

  const fetchItemHighlights = useCallback(async () => {
    if (!selectedItemId || !itemDetailOpen) return
    setItemHighlightsLoading(true)
    setItemHighlightsError(null)
    try {
      const highlights = await api.getHighlights(selectedItemId)
      const enriched = highlights.map((highlight: any) => ({
        ...highlight,
        item_title: highlight.item_title || currentItem?.title
      }))
      setItemHighlights(enriched)
    } catch (error: any) {
      const errorMsg = error?.message || "Failed to load highlights"
      setItemHighlightsError(errorMsg)
    } finally {
      setItemHighlightsLoading(false)
    }
  }, [api, selectedItemId, itemDetailOpen, currentItem?.title])

  useEffect(() => {
    fetchItemHighlights()
  }, [fetchItemHighlights])

  useEffect(() => {
    if (highlightEditorOpen && editingHighlight?.item_id) {
      lastEditedItemId.current = String(editingHighlight.item_id)
    }
  }, [highlightEditorOpen, editingHighlight])

  useEffect(() => {
    if (!highlightEditorOpen && lastEditedItemId.current) {
      if (currentItem?.id === lastEditedItemId.current) {
        fetchItemHighlights()
      }
      lastEditedItemId.current = null
    }
  }, [highlightEditorOpen, currentItem?.id, fetchItemHighlights])

  const handleStartEditingNotes = useCallback(() => {
    setEditingNotes(true)
    setNotesSaveError(null)
  }, [])

  const handleToggleFavorite = useCallback(async () => {
    if (!currentItem) return
    setActionLoading(true)
    try {
      await api.updateReadingItem(currentItem.id, {
        favorite: !currentItem.favorite
      })
      const updated = { ...currentItem, favorite: !currentItem.favorite }
      setCurrentItem(updated)
      updateItemInList(currentItem.id, { favorite: updated.favorite })
    } catch (error: any) {
      message.error(error?.message || "Failed to update favorite status")
    } finally {
      setActionLoading(false)
    }
  }, [api, currentItem, setCurrentItem, updateItemInList])

  const handleStatusChange = useCallback(
    async (newStatus: ReadingStatus) => {
      if (!currentItem) return
      setActionLoading(true)
      try {
        await api.updateReadingItem(currentItem.id, { status: newStatus })
        const updated = { ...currentItem, status: newStatus }
        setCurrentItem(updated)
        updateItemInList(currentItem.id, { status: newStatus })
        message.success(
          t("collections:reading.statusUpdated", "Status updated to {{status}}", {
            status: newStatus
          })
        )
        if (newStatus === "read" || newStatus === "archived") {
          if (progressSaveTimerRef.current) {
            clearTimeout(progressSaveTimerRef.current)
            progressSaveTimerRef.current = null
          }
          try {
            await clearReadingProgress(currentItem.id)
          } catch {}
          lastSavedProgressRef.current = null
          lastProgressRef.current = null
          setProgressPercent(0)
        }
      } catch (error: any) {
        message.error(error?.message || "Failed to update status")
      } finally {
        setActionLoading(false)
      }
    },
    [api, currentItem, setCurrentItem, updateItemInList, t]
  )

  const handleTagsChange = useCallback(
    async (tags: string[]) => {
      if (!currentItem) return
      try {
        await api.updateReadingItem(currentItem.id, { tags })
        const updated = { ...currentItem, tags }
        setCurrentItem(updated)
        updateItemInList(currentItem.id, { tags })
      } catch (error: any) {
        message.error(error?.message || "Failed to update tags")
      }
    },
    [api, currentItem, setCurrentItem, updateItemInList]
  )

  const handleSaveNotes = useCallback(async () => {
    if (!currentItem) return
    setNotesSaving(true)
    setNotesSaveError(null)
    const token = ++notesSaveTokenRef.current
    try {
      await api.updateReadingItem(currentItem.id, { notes: notesValue })
      if (notesSaveTokenRef.current !== token) return
      const updated = { ...currentItem, notes: notesValue }
      setCurrentItem(updated)
      updateItemInList(currentItem.id, { notes: notesValue })
      setNotesDirty(false)
      setEditingNotes(false)
      message.success(t("collections:reading.notesSaved", "Notes saved"))
    } catch (error: any) {
      if (notesSaveTokenRef.current !== token) return
      setNotesSaveError(error?.message || "Failed to save notes")
      message.error(error?.message || "Failed to save notes")
    } finally {
      if (notesSaveTokenRef.current === token) {
        setNotesSaving(false)
      }
    }
  }, [api, currentItem, notesValue, setCurrentItem, updateItemInList, t])

  const handleCancelNotes = useCallback(() => {
    notesSaveTokenRef.current += 1
    setEditingNotes(false)
    setNotesValue(currentItem?.notes || "")
    setNotesDirty(false)
    setNotesSaveError(null)
    setNotesSaving(false)
  }, [currentItem?.notes])

  useEffect(() => {
    if (!editingNotes || !currentItem) return
    const baseNotes = currentItem.notes || ""
    const dirty = notesValue !== baseNotes
    setNotesDirty(dirty)
    if (!dirty) return

    const token = ++notesSaveTokenRef.current
    setNotesSaveError(null)
    const timer = window.setTimeout(async () => {
      if (notesSaveTokenRef.current !== token) return
      setNotesSaving(true)
      try {
        await api.updateReadingItem(currentItem.id, { notes: notesValue })
        if (notesSaveTokenRef.current !== token) return
        const updated = { ...currentItem, notes: notesValue }
        setCurrentItem(updated)
        updateItemInList(currentItem.id, { notes: notesValue })
        setNotesDirty(false)
      } catch (error: any) {
        if (notesSaveTokenRef.current !== token) return
        setNotesSaveError(error?.message || "Failed to save notes")
      } finally {
        if (notesSaveTokenRef.current === token) {
          setNotesSaving(false)
        }
      }
    }, 800)

    return () => window.clearTimeout(timer)
  }, [editingNotes, notesValue, currentItem, api, setCurrentItem, updateItemInList])

  const handleSummarize = useCallback(async () => {
    if (!currentItem) return
    setSummarizing(true)
    try {
      const result = await api.summarizeReadingItem(currentItem.id)
      const updated = { ...currentItem, summary: result.summary }
      setCurrentItem(updated)
      message.success(t("collections:reading.summarized", "Summary generated"))
    } catch (error: any) {
      message.error(error?.message || "Failed to generate summary")
    } finally {
      setSummarizing(false)
    }
  }, [api, currentItem, setCurrentItem, t])

  const handleGenerateTts = useCallback(async () => {
    if (!currentItem) return
    setGeneratingTts(true)
    try {
      const result = await api.generateReadingItemTts(currentItem.id)
      const updated = { ...currentItem, tts_audio_url: result.audio_url }
      setCurrentItem(updated)
      message.success(t("collections:reading.ttsGenerated", "Audio generated"))
    } catch (error: any) {
      message.error(error?.message || "Failed to generate audio")
    } finally {
      setGeneratingTts(false)
    }
  }, [api, currentItem, setCurrentItem, t])

  const computeProgress = useCallback((): ReadingProgress | null => {
    const container = scrollContainerRef.current
    if (!container) return null
    const maxScroll = container.scrollHeight - container.clientHeight
    const scrollTop = container.scrollTop
    const percent = maxScroll > 0 ? (scrollTop / maxScroll) * 100 : 100
    return {
      percent: Math.min(100, Math.max(0, percent)),
      scrollTop: Math.max(0, scrollTop),
      scrollHeight: Math.max(0, container.scrollHeight),
      clientHeight: Math.max(0, container.clientHeight)
    }
  }, [])

  const persistProgress = useCallback(
    async (progress: ReadingProgress) => {
      if (!currentItem?.id) return
      const serialized = JSON.stringify(progress)
      if (serialized === lastSavedProgressRef.current) return
      await setReadingProgress(currentItem.id, progress)
      lastSavedProgressRef.current = serialized
    },
    [currentItem?.id]
  )

  const scheduleProgressSave = useCallback(
    (progress: ReadingProgress) => {
      if (progressSaveTimerRef.current) {
        clearTimeout(progressSaveTimerRef.current)
      }
      progressSaveTimerRef.current = setTimeout(() => {
        void persistProgress(progress)
      }, 350)
    },
    [persistProgress]
  )

  const flushProgressSave = useCallback(() => {
    if (progressSaveTimerRef.current) {
      clearTimeout(progressSaveTimerRef.current)
      progressSaveTimerRef.current = null
    }
    if (lastProgressRef.current) {
      void persistProgress(lastProgressRef.current)
    }
  }, [persistProgress])

  const handleClose = useCallback(() => {
    flushProgressSave()
    closeItemDetail()
    setEditingNotes(false)
    setNotesDirty(false)
    setNotesSaveError(null)
    setNotesSaving(false)
  }, [closeItemDetail, flushProgressSave])

  const handleDelete = useCallback(async () => {
    if (!currentItem) return
    setActionLoading(true)
    try {
      await api.deleteReadingItem(currentItem.id, { hard: true })
      await clearReadingProgress(currentItem.id)
      removeItem(currentItem.id)
      message.success(t("collections:reading.deleted", "Article deleted"))
      handleClose()
      onRefresh?.()
    } catch (error: any) {
      message.error(error?.message || "Failed to delete article")
    } finally {
      setActionLoading(false)
      setDeleteModalOpen(false)
    }
  }, [api, currentItem, removeItem, handleClose, onRefresh, t])

  const handleContentScroll = useCallback(() => {
    if (activeTabKey !== "content") return
    const progress = computeProgress()
    if (!progress) return
    lastProgressRef.current = progress
    setProgressPercent(progress.percent)
    scheduleProgressSave(progress)
  }, [activeTabKey, computeProgress, scheduleProgressSave])

  const restoreScrollPosition = useCallback(async () => {
    if (!currentItem?.id) return
    const container = scrollContainerRef.current
    if (!container) return
    const saved = await getReadingProgress(currentItem.id)
    if (!saved) {
      setProgressPercent(0)
      return
    }
    const maxScroll = container.scrollHeight - container.clientHeight
    if (maxScroll <= 0) {
      container.scrollTop = 0
      setProgressPercent(100)
      return
    }
    let targetScrollTop = saved.scrollTop
    if (saved.scrollHeight > 0 && Math.abs(saved.scrollHeight - container.scrollHeight) > 5) {
      targetScrollTop = Math.round((saved.percent / 100) * maxScroll)
    }
    container.scrollTop = Math.min(Math.max(0, targetScrollTop), maxScroll)
    setProgressPercent(saved.percent)
  }, [currentItem?.id])

  const handleClearProgress = useCallback(async () => {
    if (!currentItem?.id) return
    if (progressSaveTimerRef.current) {
      clearTimeout(progressSaveTimerRef.current)
      progressSaveTimerRef.current = null
    }
    await clearReadingProgress(currentItem.id)
    lastSavedProgressRef.current = null
    lastProgressRef.current = null
    const container = scrollContainerRef.current
    if (container) {
      container.scrollTop = 0
    }
    setProgressPercent(0)
    message.success(t("collections:reading.progressCleared", "Progress reset"))
  }, [currentItem?.id, t])

  useEffect(() => {
    if (!itemDetailOpen) {
      lastRestoredItemRef.current = null
      setProgressPercent(null)
    }
  }, [itemDetailOpen])

  useEffect(() => {
    lastSavedProgressRef.current = null
    lastProgressRef.current = null
  }, [currentItem?.id])

  useEffect(() => {
    if (!itemDetailOpen || !currentItem?.id || activeTabKey !== "content") return
    if (lastRestoredItemRef.current === currentItem.id) return
    lastRestoredItemRef.current = currentItem.id
    let cancelled = false

    const restore = async () => {
      await new Promise<void>((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
      })
      if (cancelled) return
      await restoreScrollPosition()
      if (cancelled) return
      const progress = computeProgress()
      if (progress) {
        lastProgressRef.current = progress
        setProgressPercent(progress.percent)
      }
    }

    void restore()
    return () => {
      cancelled = true
    }
  }, [itemDetailOpen, currentItem?.id, activeTabKey, restoreScrollPosition, computeProgress])

  useEffect(() => {
    if (activeTabKey !== "content") return
    handleContentScroll()
  }, [activeTabKey, handleContentScroll])

  useEffect(() => {
    return () => {
      if (progressSaveTimerRef.current) {
        clearTimeout(progressSaveTimerRef.current)
      }
    }
  }, [])

  const captureSelection = useCallback(() => {
    const container = contentRef.current
    if (!container) return
    const selection = window.getSelection()
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
      if (selectionHighlight) {
        setSelectionHighlight(null)
      }
      return
    }
    const range = selection.getRangeAt(0)
    if (!container.contains(range.startContainer) || !container.contains(range.endContainer)) {
      return
    }
    const quote = selection.toString().trim()
    if (!quote) return

    const computeOffset = (node: Node, offset: number) => {
      const preRange = document.createRange()
      preRange.selectNodeContents(container)
      preRange.setEnd(node, offset)
      return preRange.toString().length
    }

    const startOffset = computeOffset(range.startContainer, range.startOffset)
    const endOffset = computeOffset(range.endContainer, range.endOffset)
    if (endOffset <= startOffset) return

    const selectionPayload = { quote, startOffset, endOffset }
    setSelectionHighlight(selectionPayload)
    if (!highlightQuote) {
      setHighlightQuote(quote)
      setHighlightStartOffset(startOffset)
      setHighlightEndOffset(endOffset)
      setHighlightAnchorStrategy("fuzzy_quote")
    }
  }, [highlightQuote, selectionHighlight])

  const handleHighlightQuoteChange = useCallback(
    (value: string) => {
      setHighlightQuote(value)
      if (selectionHighlight && value !== selectionHighlight.quote) {
        setHighlightStartOffset(null)
        setHighlightEndOffset(null)
        setHighlightAnchorStrategy("fuzzy_quote")
      }
    },
    [selectionHighlight]
  )

  const handleCreateHighlight = useCallback(async () => {
    if (!currentItem) return
    const quote = highlightQuote.trim()
    if (!quote) {
      message.warning(
        t("collections:highlights.quoteRequired", "Please enter the highlight text")
      )
      return
    }
    setHighlightSaving(true)
    try {
      const created = await api.createHighlight({
        item_id: currentItem.id,
        quote,
        note: highlightNote.trim() || undefined,
        color: highlightColor,
        start_offset: highlightStartOffset ?? undefined,
        end_offset: highlightEndOffset ?? undefined,
        anchor_strategy: highlightAnchorStrategy
      })
      const normalized = created.item_title
        ? created
        : { ...created, item_title: currentItem.title }
      setItemHighlights((prev) => [normalized, ...prev])
      addHighlight(normalized)
      setHighlightQuote("")
      setHighlightNote("")
      setHighlightStartOffset(null)
      setHighlightEndOffset(null)
      setHighlightAnchorStrategy("fuzzy_quote")
      clearSelection()
      message.success(t("collections:highlights.created", "Highlight created"))
    } catch (error: any) {
      message.error(error?.message || "Failed to create highlight")
    } finally {
      setHighlightSaving(false)
    }
  }, [
    api,
    currentItem,
    highlightQuote,
    highlightNote,
    highlightColor,
    highlightStartOffset,
    highlightEndOffset,
    highlightAnchorStrategy,
    clearSelection,
    addHighlight,
    t
  ])

  const applySelectionToHighlight = useCallback(() => {
    if (!selectionHighlight) return
    setHighlightQuote(selectionHighlight.quote)
    setHighlightStartOffset(selectionHighlight.startOffset)
    setHighlightEndOffset(selectionHighlight.endOffset)
    setHighlightAnchorStrategy("fuzzy_quote")
  }, [selectionHighlight])

  const handleHighlightDeleteClick = useCallback((id: string) => {
    setHighlightDeleteId(id)
    setHighlightDeleteOpen(true)
  }, [])

  const handleHighlightDeleteConfirm = useCallback(async () => {
    if (!highlightDeleteId) return
    setHighlightDeleteLoading(true)
    try {
      await api.deleteHighlight(highlightDeleteId)
      setItemHighlights((prev) => prev.filter((h) => h.id !== highlightDeleteId))
      removeHighlight(highlightDeleteId)
      message.success(t("collections:highlights.deleted", "Highlight deleted"))
      setHighlightDeleteOpen(false)
      setHighlightDeleteId(null)
    } catch (error: any) {
      message.error(error?.message || "Failed to delete highlight")
    } finally {
      setHighlightDeleteLoading(false)
    }
  }, [api, highlightDeleteId, removeHighlight, t])

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString(undefined, {
      year: "numeric",
      month: "long",
      day: "numeric"
    })
  }

  const sanitizedHtml = useMemo(() => {
    if (!currentItem?.clean_html) return ""
    return DOMPurify.sanitize(currentItem.clean_html, { USE_PROFILES: { html: true } })
  }, [currentItem?.clean_html])

  const tabItems: TabsProps["items"] = [
    {
      key: "content",
      label: (
        <span className="flex items-center gap-1">
          <Globe className="h-4 w-4" />
          {t("collections:reading.tabs.content", "Content")}
        </span>
      ),
      children: (
        <div className="prose prose-sm dark:prose-invert max-w-none">
          {currentItem?.clean_html ? (
            <div
              ref={contentRef}
              onMouseUp={captureSelection}
              onKeyUp={captureSelection}
              onTouchEnd={captureSelection}
              dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
            />
          ) : currentItem?.text ? (
            <pre
              ref={contentRef}
              onMouseUp={captureSelection}
              onKeyUp={captureSelection}
              onTouchEnd={captureSelection}
              className="whitespace-pre-wrap text-sm text-zinc-700 dark:text-zinc-200"
            >
              {currentItem.text}
            </pre>
          ) : (
            <p className="text-zinc-500">
              {t("collections:reading.noContent", "Content not available")}
            </p>
          )}
          {selectionHighlight && (
            <div className="mt-3 flex flex-wrap items-center gap-2 rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
              <span>{t("collections:highlights.selectionCaptured", "Selection captured")}</span>
              <Button size="small" type="link" onClick={applySelectionToHighlight}>
                {t("collections:highlights.useSelection", "Use selection")}
              </Button>
              <Button size="small" type="text" onClick={clearSelection}>
                {t("common:clear", "Clear")}
              </Button>
            </div>
          )}
        </div>
      )
    },
    {
      key: "summary",
      label: (
        <span className="flex items-center gap-1">
          <Sparkles className="h-4 w-4" />
          {t("collections:reading.tabs.summary", "Summary")}
        </span>
      ),
      children: (
        <div className="space-y-4">
          {currentItem?.summary ? (
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <p>{currentItem.summary}</p>
            </div>
          ) : (
            <div className="text-center py-8">
              <Sparkles className="h-8 w-8 mx-auto text-zinc-400 mb-2" />
              <p className="text-zinc-500 mb-4">
                {t("collections:reading.noSummary", "No summary yet")}
              </p>
              <Button
                type="primary"
                icon={<Sparkles className="h-4 w-4" />}
                onClick={handleSummarize}
                loading={summarizing}
              >
                {t("collections:reading.generateSummary", "Generate Summary")}
              </Button>
            </div>
          )}
        </div>
      )
    },
    {
      key: "highlights",
      label: (
        <span className="flex items-center gap-1">
          <Highlighter className="h-4 w-4" />
          {t("collections:reading.tabs.highlights", "Highlights")}
        </span>
      ),
      children: (
        <div className="space-y-4">
          <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-sm font-medium text-zinc-600 dark:text-zinc-300">
                  {t("collections:highlights.quoteLabel", "Quote")}
                </label>
                <TextArea
                  rows={3}
                  value={highlightQuote}
                  onChange={(e) => handleHighlightQuoteChange(e.target.value)}
                  placeholder={t(
                    "collections:highlights.quotePlaceholder",
                    "Paste the highlighted text..."
                  )}
                  aria-label={t("collections:highlights.quoteLabel", "Quote")}
                />
                {selectionHighlight && (
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
                    <span>
                      {t("collections:highlights.selectionCaptured", "Selection captured")}
                    </span>
                    <Button size="small" type="link" onClick={applySelectionToHighlight}>
                      {t("collections:highlights.useSelection", "Use selection")}
                    </Button>
                    <Button size="small" type="text" onClick={clearSelection}>
                      {t("common:clear", "Clear")}
                    </Button>
                  </div>
                )}
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-zinc-600 dark:text-zinc-300">
                  {t("collections:highlights.noteLabel", "Note (optional)")}
                </label>
                <TextArea
                  rows={2}
                  value={highlightNote}
                  onChange={(e) => setHighlightNote(e.target.value)}
                  placeholder={t(
                    "collections:highlights.notePlaceholder",
                    "Add context or why this matters..."
                  )}
                  aria-label={t("collections:highlights.noteLabel", "Note (optional)")}
                />
              </div>
              <div className="flex items-center gap-3">
                <Select
                  value={highlightColor}
                  onChange={(value) => setHighlightColor(value as HighlightColor)}
                  options={[
                    { value: "yellow", label: t("collections:colors.yellow", "Yellow") },
                    { value: "green", label: t("collections:colors.green", "Green") },
                    { value: "blue", label: t("collections:colors.blue", "Blue") },
                    { value: "pink", label: t("collections:colors.pink", "Pink") },
                    { value: "purple", label: t("collections:colors.purple", "Purple") }
                  ]}
                  className="w-32"
                  size="small"
                />
                <Button
                  type="primary"
                  icon={<Highlighter className="h-4 w-4" />}
                  onClick={handleCreateHighlight}
                  loading={highlightSaving}
                >
                  {t("collections:highlights.add", "Add Highlight")}
                </Button>
              </div>
            </div>
          </div>

          {itemHighlightsLoading ? (
            <div className="flex items-center justify-center py-6">
              <Spin size="large" />
            </div>
          ) : itemHighlightsError ? (
            <Empty
              description={itemHighlightsError}
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            >
              <Button onClick={fetchItemHighlights}>{t("common:retry", "Retry")}</Button>
            </Empty>
          ) : itemHighlights.length === 0 ? (
            <Empty
              description={t(
                "collections:highlights.emptyForItem",
                "No highlights for this article yet"
              )}
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          ) : (
            <div className="space-y-3">
              {itemHighlights.map((highlight) => (
                <HighlightCard
                  key={highlight.id}
                  highlight={highlight}
                  onDelete={handleHighlightDeleteClick}
                  onEdit={openHighlightEditor}
                />
              ))}
            </div>
          )}
        </div>
      )
    },
    {
      key: "notes",
      label: (
        <span className="flex items-center gap-1">
          <StickyNote className="h-4 w-4" />
          {t("collections:reading.tabs.notes", "Notes")}
        </span>
      ),
      children: (
        <div className="space-y-4">
          {editingNotes ? (
            <>
              <TextArea
                value={notesValue}
                onChange={(e) => setNotesValue(e.target.value)}
                rows={6}
                placeholder={t("collections:reading.notesPlaceholder", "Add your notes...")}
              />
              <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-zinc-500 dark:text-zinc-400">
                <div>
                  {notesSaveError
                    ? t("collections:reading.notesSaveFailed", notesSaveError)
                    : notesSaving
                      ? t("collections:reading.notesSaving", "Saving...")
                      : notesDirty
                        ? t("collections:reading.notesDirty", "Unsaved changes")
                        : t("collections:reading.notesSaved", "All changes saved")}
                </div>
                <div className="flex items-center gap-2">
                  <Button onClick={handleCancelNotes}>
                  {t("common:cancel", "Cancel")}
                </Button>
                  <Button type="primary" onClick={handleSaveNotes} loading={notesSaving}>
                  {t("common:save", "Save")}
                </Button>
                </div>
              </div>
            </>
          ) : (
            <>
              {currentItem?.notes ? (
                <div className="prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap">
                  {currentItem.notes}
                </div>
              ) : (
                <p className="text-zinc-500">
                  {t("collections:reading.noNotes", "No notes yet")}
                </p>
              )}
              <Button onClick={handleStartEditingNotes}>
                {currentItem?.notes
                  ? t("collections:reading.editNotes", "Edit Notes")
                  : t("collections:reading.addNotes", "Add Notes")}
              </Button>
            </>
          )}
        </div>
      )
    }
  ]

  return (
    <>
      <Drawer
        title={null}
        open={itemDetailOpen}
        onClose={handleClose}
        width={640}
        className="reading-item-detail-drawer"
        styles={{ body: { padding: 0 } }}
      >
        {currentItemLoading ? (
          <div className="flex items-center justify-center py-12">
            <Spin size="large" />
          </div>
        ) : currentItem ? (
          <div className="flex flex-col h-full">
            {/* Header */}
            <div className="border-b border-zinc-200 p-4 dark:border-zinc-700">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
                    {currentItem.title}
                  </h2>
                  <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-zinc-500 dark:text-zinc-400">
                    {currentItem.domain && (
                      <a
                        href={currentItem.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 hover:text-blue-500"
                      >
                        <Globe className="h-3 w-3" />
                        {currentItem.domain}
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                    {currentItem.published_at && (
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {formatDate(currentItem.published_at)}
                      </span>
                    )}
                    {currentItem.reading_time_minutes && (
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {t("collections:reading.readingTime", "{{count}} min read", {
                          count: currentItem.reading_time_minutes
                        })}
                      </span>
                    )}
                  </div>
                </div>
                <Button
                  type="text"
                  icon={<X className="h-5 w-5" />}
                  onClick={handleClose}
                />
              </div>

              {/* Status & Tags Row */}
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Select
                  value={currentItem.status}
                  onChange={handleStatusChange}
                  options={[
                    { value: "saved", label: t("collections:status.saved", "Saved") },
                    { value: "reading", label: t("collections:status.reading", "Reading") },
                    { value: "read", label: t("collections:status.read", "Read") },
                    { value: "archived", label: t("collections:status.archived", "Archived") }
                  ]}
                  size="small"
                  className="w-28"
                  loading={actionLoading}
                />

                <Tooltip
                  title={
                    currentItem.favorite
                      ? t("collections:reading.unfavorite", "Unfavorite")
                      : t("collections:reading.favorite", "Favorite")
                  }
                >
                  <Button
                    type={currentItem.favorite ? "primary" : "default"}
                    size="small"
                    icon={
                      <Star
                        className={`h-4 w-4 ${currentItem.favorite ? "fill-current" : ""}`}
                      />
                    }
                    onClick={handleToggleFavorite}
                    loading={actionLoading}
                  />
                </Tooltip>

                <div className="flex-1">
                  <TagSelector
                    tags={currentItem.tags}
                    onChange={handleTagsChange}
                    placeholder={t("collections:reading.addTag", "Add tag...")}
                  />
                </div>
              </div>

              {progressPercent !== null && (
                <div className="mt-3">
                  <div className="flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400">
                    <span>
                      {t("collections:reading.progressLabel", "Progress")}
                    </span>
                    <span>{Math.round(progressPercent)}%</span>
                  </div>
                  <div className="mt-1 h-1.5 w-full rounded-full bg-zinc-200 dark:bg-zinc-700">
                    <div
                      className="h-1.5 rounded-full bg-emerald-500 transition-all"
                      style={{ width: `${Math.min(100, Math.max(0, progressPercent))}%` }}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Content Tabs */}
            <div
              ref={scrollContainerRef}
              className="flex-1 overflow-auto p-4"
              onScroll={handleContentScroll}
            >
              <Tabs
                items={tabItems}
                activeKey={activeTabKey}
                onChange={setActiveTabKey}
              />
            </div>

            {/* Footer Actions */}
            <div className="border-t border-zinc-200 p-4 dark:border-zinc-700">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Button
                    icon={<Sparkles className="h-4 w-4" />}
                    onClick={handleSummarize}
                    loading={summarizing}
                  >
                    {t("collections:reading.summarize", "Summarize")}
                  </Button>
                  <Button
                    icon={<Volume2 className="h-4 w-4" />}
                    onClick={handleGenerateTts}
                    loading={generatingTts}
                  >
                    {t("collections:reading.generateTts", "Generate Audio")}
                  </Button>
                  {currentItem.tts_audio_url && (
                    <Button
                      icon={<FileDown className="h-4 w-4" />}
                      href={currentItem.tts_audio_url}
                      target="_blank"
                    >
                      {t("collections:reading.downloadAudio", "Download Audio")}
                    </Button>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Button onClick={handleClearProgress}>
                    {t("collections:reading.clearProgress", "Clear progress")}
                  </Button>
                  <Button
                    danger
                    icon={<Trash2 className="h-4 w-4" />}
                    onClick={() => setDeleteModalOpen(true)}
                  >
                    {t("common:delete", "Delete")}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </Drawer>

      {/* Delete Confirmation Modal */}
      <Modal
        title={t("collections:reading.deleteConfirm.title", "Delete Article")}
        open={deleteModalOpen}
        onCancel={() => setDeleteModalOpen(false)}
        onOk={handleDelete}
        okText={t("common:delete", "Delete")}
        okButtonProps={{ danger: true, loading: actionLoading }}
        cancelText={t("common:cancel", "Cancel")}
      >
        <p>
          {t(
            "collections:reading.deleteConfirm.message",
            "Are you sure you want to delete this article? This action cannot be undone."
          )}
        </p>
      </Modal>

      <Modal
        title={t("collections:highlights.deleteConfirm.title", "Delete Highlight")}
        open={highlightDeleteOpen}
        onCancel={() => setHighlightDeleteOpen(false)}
        onOk={handleHighlightDeleteConfirm}
        okText={t("common:delete", "Delete")}
        okButtonProps={{ danger: true, loading: highlightDeleteLoading }}
        cancelText={t("common:cancel", "Cancel")}
      >
        <p>
          {t(
            "collections:highlights.deleteConfirm.message",
            "Are you sure you want to delete this highlight?"
          )}
        </p>
      </Modal>
    </>
  )
}
