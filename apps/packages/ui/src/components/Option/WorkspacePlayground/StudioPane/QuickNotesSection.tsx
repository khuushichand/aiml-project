import React, { useState, useCallback, useRef, useEffect } from "react"
import { useTranslation } from "react-i18next"
import { Input, Button, Modal, message, Tag, Empty, Spin } from "antd"
import {
  Save,
  FolderOpen,
  X,
  Search,
  FileText,
  AlertCircle
} from "lucide-react"
import { useWorkspaceStore } from "@/store/workspace"
import { bgRequest } from "@/services/background-proxy"
import type { AllowedPath } from "@/services/tldw/openapi-guard"

const { TextArea } = Input

interface NoteListItem {
  id: number
  title: string
  content: string
  keywords?: string[]
  version?: number
  created_at?: string
}

interface NotesSearchResponse {
  notes?: NoteListItem[]
  results?: NoteListItem[]
  total?: number
}

/**
 * QuickNotesSection - Enhanced notes editor with load/save functionality
 */
export const QuickNotesSection: React.FC = () => {
  const { t } = useTranslation(["playground", "common"])
  const [messageApi, contextHolder] = message.useMessage()

  // Store state
  const currentNote = useWorkspaceStore((s) => s.currentNote)
  const workspaceTag = useWorkspaceStore((s) => s.workspaceTag)

  // Store actions
  const updateNoteTitle = useWorkspaceStore((s) => s.updateNoteTitle)
  const updateNoteContent = useWorkspaceStore((s) => s.updateNoteContent)
  const updateNoteKeywords = useWorkspaceStore((s) => s.updateNoteKeywords)
  const clearCurrentNote = useWorkspaceStore((s) => s.clearCurrentNote)
  const loadNote = useWorkspaceStore((s) => s.loadNote)

  // Local state
  const [isSaving, setIsSaving] = useState(false)
  const [isLoadModalOpen, setIsLoadModalOpen] = useState(false)
  const [isSearching, setIsSearching] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [notesList, setNotesList] = useState<NoteListItem[]>([])
  const [keywordsInput, setKeywordsInput] = useState("")

  // Parse keywords from input
  const parseKeywords = (input: string): string[] => {
    return input
      .split(",")
      .map((k) => k.trim())
      .filter((k) => k.length > 0)
  }

  // Handle keywords input change
  const handleKeywordsChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setKeywordsInput(e.target.value)
    updateNoteKeywords(parseKeywords(e.target.value))
  }

  // Track if keywords were just loaded from a note (to avoid sync loops)
  const lastLoadedNoteId = useRef<number | undefined>(undefined)

  // Sync keywords input when note is loaded or cleared
  useEffect(() => {
    // Only sync when the note ID changes (load or clear)
    if (currentNote.id !== lastLoadedNoteId.current) {
      lastLoadedNoteId.current = currentNote.id
      if (currentNote.keywords.length > 0) {
        setKeywordsInput(currentNote.keywords.join(", "))
      } else {
        setKeywordsInput("")
      }
    }
  }, [currentNote.id, currentNote.keywords])

  // Debounce timer ref for search
  const searchDebounceRef = useRef<NodeJS.Timeout | null>(null)

  // Search/list notes
  const searchNotes = useCallback(async (query?: string) => {
    setIsSearching(true)
    try {
      let response: NotesSearchResponse
      if (query && query.trim()) {
        response = await bgRequest<NotesSearchResponse>({
          path: `/api/v1/notes/search/?query=${encodeURIComponent(query)}&limit=20` as AllowedPath,
          method: "GET"
        })
      } else {
        response = await bgRequest<NotesSearchResponse>({
          path: "/api/v1/notes/?page=1&results_per_page=20" as AllowedPath,
          method: "GET"
        })
      }
      const notes = response.notes || response.results || []
      setNotesList(notes)
    } catch (error) {
      messageApi.error(
        t("playground:studio.loadNotesError", "Failed to load notes")
      )
      setNotesList([])
    } finally {
      setIsSearching(false)
    }
  }, [messageApi, t])

  // Debounced search for typing
  const debouncedSearch = useCallback((query: string) => {
    if (searchDebounceRef.current) {
      clearTimeout(searchDebounceRef.current)
    }
    searchDebounceRef.current = setTimeout(() => {
      searchNotes(query)
    }, 300)
  }, [searchNotes])

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (searchDebounceRef.current) {
        clearTimeout(searchDebounceRef.current)
      }
    }
  }, [])

  // Open load modal and fetch notes
  const handleOpenLoadModal = () => {
    setIsLoadModalOpen(true)
    setSearchQuery("")
    searchNotes()
  }

  // Handle note selection
  const handleSelectNote = async (note: NoteListItem) => {
    try {
      // Fetch full note details
      const fullNote = await bgRequest<NoteListItem>({
        path: `/api/v1/notes/${note.id}` as AllowedPath,
        method: "GET"
      })
      loadNote({
        id: fullNote.id,
        title: fullNote.title || "",
        content: fullNote.content || "",
        keywords: fullNote.keywords || [],
        version: fullNote.version
      })
      setIsLoadModalOpen(false)
      messageApi.success(
        t("playground:studio.noteLoaded", "Note loaded")
      )
    } catch (error) {
      messageApi.error(
        t("playground:studio.loadNoteError", "Failed to load note")
      )
    }
  }

  // Save note (create or update)
  const handleSave = async () => {
    if (!currentNote.content.trim() && !currentNote.title.trim()) {
      messageApi.warning(
        t("playground:studio.emptyNoteWarning", "Please add some content or a title")
      )
      return
    }

    setIsSaving(true)
    try {
      const payload: Record<string, unknown> = {
        title: currentNote.title || "Untitled Note",
        content: currentNote.content,
        keywords: currentNote.keywords.length > 0 ? currentNote.keywords : undefined
      }

      // Add workspace tag if available
      if (workspaceTag) {
        payload.workspace_tag = workspaceTag
      }

      if (currentNote.id) {
        // Update existing note with version check
        const path = currentNote.version
          ? `/api/v1/notes/${currentNote.id}?expected_version=${currentNote.version}` as AllowedPath
          : `/api/v1/notes/${currentNote.id}` as AllowedPath

        const updated = await bgRequest<NoteListItem>({
          path,
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: payload
        })

        loadNote({
          id: updated.id,
          title: updated.title || "",
          content: updated.content || "",
          keywords: updated.keywords || [],
          version: updated.version
        })
        messageApi.success(
          t("playground:studio.noteUpdated", "Note updated")
        )
      } else {
        // Create new note
        const created = await bgRequest<NoteListItem>({
          path: "/api/v1/notes/" as AllowedPath,
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: payload
        })

        loadNote({
          id: created.id,
          title: created.title || "",
          content: created.content || "",
          keywords: created.keywords || [],
          version: created.version
        })
        messageApi.success(
          t("playground:studio.noteSaved", "Note saved")
        )
      }
    } catch (error: any) {
      // Handle version conflict
      if (error?.message?.includes("version") || error?.status === 409) {
        messageApi.error(
          t("playground:studio.versionConflict", "Note was modified elsewhere. Please reload and try again.")
        )
      } else {
        messageApi.error(
          t("playground:studio.noteSaveError", "Failed to save note")
        )
      }
    } finally {
      setIsSaving(false)
    }
  }

  // Handle clear
  const handleClear = () => {
    if (currentNote.isDirty) {
      Modal.confirm({
        title: t("playground:studio.unsavedChanges", "Unsaved Changes"),
        content: t(
          "playground:studio.unsavedChangesWarning",
          "You have unsaved changes. Are you sure you want to clear?"
        ),
        onOk: () => {
          clearCurrentNote()
          setKeywordsInput("")
        }
      })
    } else {
      clearCurrentNote()
      setKeywordsInput("")
    }
  }

  return (
    <div className="border-t border-border p-4">
      {contextHolder}

      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase text-text-muted">
          {t("playground:studio.quickNotes", "Quick Notes")}
          {currentNote.id && (
            <span className="ml-2 font-normal normal-case text-primary">
              (ID: {currentNote.id})
            </span>
          )}
        </h3>
        <div className="flex items-center gap-1">
          <Button
            type="text"
            size="small"
            icon={<FolderOpen className="h-3.5 w-3.5" />}
            onClick={handleOpenLoadModal}
            title={t("playground:studio.loadNote", "Load note")}
          />
          <Button
            type="text"
            size="small"
            icon={<X className="h-3.5 w-3.5" />}
            onClick={handleClear}
            title={t("common:clear", "Clear")}
            disabled={!currentNote.content && !currentNote.title && !currentNote.id}
          />
        </div>
      </div>

      {/* Title input */}
      <Input
        value={currentNote.title}
        onChange={(e) => updateNoteTitle(e.target.value)}
        placeholder={t("playground:studio.noteTitlePlaceholder", "Note title...")}
        size="small"
        className="mb-2"
      />

      {/* Keywords input */}
      <Input
        value={keywordsInput}
        onChange={handleKeywordsChange}
        placeholder={t("playground:studio.noteKeywordsPlaceholder", "Keywords (comma-separated)...")}
        size="small"
        className="mb-2"
        prefix={
          <span className="text-xs text-text-muted">
            {t("playground:studio.tags", "Tags")}:
          </span>
        }
      />

      {/* Display keywords as tags */}
      {currentNote.keywords.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1">
          {currentNote.keywords.map((kw, idx) => (
            <Tag
              key={idx}
              closable
              onClose={() => {
                const newKeywords = currentNote.keywords.filter((_, i) => i !== idx)
                updateNoteKeywords(newKeywords)
                setKeywordsInput(newKeywords.join(", "))
              }}
              className="text-xs"
            >
              {kw}
            </Tag>
          ))}
        </div>
      )}

      {/* Content textarea */}
      <TextArea
        value={currentNote.content}
        onChange={(e) => updateNoteContent(e.target.value)}
        placeholder={t(
          "playground:studio.notesPlaceholder",
          "Jot down notes, ideas, or observations..."
        )}
        autoSize={{ minRows: 3, maxRows: 8 }}
        className="text-sm"
      />

      {/* Save button */}
      {(currentNote.content.trim() || currentNote.title.trim() || currentNote.isDirty) && (
        <div className="mt-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {currentNote.isDirty && (
              <span className="flex items-center gap-1 text-xs text-warning">
                <AlertCircle className="h-3 w-3" />
                {t("playground:studio.unsaved", "Unsaved")}
              </span>
            )}
          </div>
          <Button
            size="small"
            type="primary"
            icon={<Save className="h-3.5 w-3.5" />}
            onClick={handleSave}
            loading={isSaving}
          >
            {currentNote.id
              ? t("playground:studio.updateNote", "Update")
              : t("playground:studio.saveNote", "Save")}
          </Button>
        </div>
      )}

      {/* Load Note Modal */}
      <Modal
        title={
          <span className="flex items-center gap-2">
            <FolderOpen className="h-4 w-4" />
            {t("playground:studio.loadNoteTitle", "Load Note")}
          </span>
        }
        open={isLoadModalOpen}
        onCancel={() => setIsLoadModalOpen(false)}
        footer={null}
        width={500}
      >
        {/* Search input */}
        <Input
          prefix={<Search className="h-4 w-4 text-text-muted" />}
          placeholder={t("playground:studio.searchNotes", "Search notes...")}
          value={searchQuery}
          onChange={(e) => {
            const value = e.target.value
            setSearchQuery(value)
            // If cleared (empty), search immediately; otherwise debounce
            if (!value) {
              if (searchDebounceRef.current) {
                clearTimeout(searchDebounceRef.current)
              }
              searchNotes("")
            } else {
              debouncedSearch(value)
            }
          }}
          allowClear
          className="mb-4"
        />

        {/* Notes list */}
        <div className="max-h-80 overflow-y-auto">
          {isSearching ? (
            <div className="flex items-center justify-center py-8">
              <Spin />
            </div>
          ) : notesList.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <span className="text-text-muted">
                  {searchQuery
                    ? t("playground:studio.noNotesFound", "No notes found")
                    : t("playground:studio.noNotesYet", "No notes yet")}
                </span>
              }
            />
          ) : (
            <div className="space-y-2">
              {notesList.map((note) => (
                <button
                  key={note.id}
                  type="button"
                  onClick={() => handleSelectNote(note)}
                  className="flex w-full items-start gap-3 rounded-lg border border-border p-3 text-left transition hover:border-primary/50 hover:bg-primary/5"
                >
                  <FileText className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-text">
                      {note.title || "Untitled"}
                    </p>
                    <p className="line-clamp-2 text-xs text-text-muted">
                      {note.content?.slice(0, 100) || "No content"}
                    </p>
                    {note.keywords && note.keywords.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {note.keywords.slice(0, 3).map((kw, idx) => (
                          <Tag key={idx} className="text-xs">
                            {kw}
                          </Tag>
                        ))}
                        {note.keywords.length > 3 && (
                          <span className="text-xs text-text-muted">
                            +{note.keywords.length - 3}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </Modal>
    </div>
  )
}

export default QuickNotesSection
