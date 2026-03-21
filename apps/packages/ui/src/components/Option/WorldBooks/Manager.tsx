import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button, Form, Input, InputNumber, Modal, Skeleton, Switch, Table, Tooltip, Tag, Select, Descriptions, Empty, Popover, Divider, Drawer, Checkbox, Grid, Progress, Upload, Dropdown } from "antd"
import React from "react"
import { useConfirmDanger } from "@/components/Common/confirm-danger"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { Pen, Trash2, BookOpen, Link2, Download, BarChart3, Copy, List, MoreHorizontal, Upload as UploadIcon, HelpCircle } from "lucide-react"
import { useServerOnline } from "@/hooks/useServerOnline"
import FeatureEmptyState from "../../Common/FeatureEmptyState"
import { useTranslation } from "react-i18next"
import { useAntdNotification } from "@/hooks/useAntdNotification"
import { useUndoNotification } from "@/hooks/useUndoNotification"
import {
  WORLD_BOOK_FORM_DEFAULTS,
  buildWorldBookMutationErrorMessage,
  getWorldBookStarterTemplate,
  isWorldBookVersionConflictError,
  toWorldBookFormValues
} from "./worldBookFormUtils"
import {
  formatWorldBookLastModified,
  UNKNOWN_LAST_MODIFIED_LABEL
} from "./worldBookListUtils"
import {
  getWorldBookImportFormatLabel,
  WORLD_BOOK_IMPORT_MERGE_HELP_TEXT,
} from "./worldBookInteropUtils"
import {
  getBudgetUtilizationBand,
  getBudgetUtilizationColor,
  getBudgetUtilizationPercent,
  getTokenEstimatorNote
} from "./worldBookStatsUtils"
import {
  buildGlobalWorldBookStatistics,
  type GlobalWorldBookStatistics
} from "./worldBookGlobalStatsUtils"
import { useWorldBookFiltering } from "./hooks/useWorldBookFiltering"
import { useWorldBookBulkActions } from "./hooks/useWorldBookBulkActions"
import { useWorldBookImportExport } from "./hooks/useWorldBookImportExport"
import { useWorldBookTestMatching } from "./hooks/useWorldBookTestMatching"
import { WorldBookForm } from "./WorldBookForm"
import { WorldBookTestMatchingModal } from "./WorldBookTestMatchingModal"
import {
  WorldBookEntryManager as EntryManager,
  type EntryFilterPreset,
  DEFAULT_ENTRY_FILTER_PRESET
} from "./WorldBookEntryManager"
import {
  ATTACHMENT_MATRIX_CHARACTER_THRESHOLD,
  ATTACHMENT_LIST_PAGE_SIZE,
  ATTACHMENT_FEEDBACK_DURATION_MS,
  ATTACHMENT_PULSE_DURATION_MS,
  MODAL_BODY_SCROLL_STYLE,
  LOREBOOK_DEBUG_ENTRYPOINT_HREF,
  ACCESSIBLE_SWITCH_TEXT_PROPS,
  type EditWorldBookConflictState,
} from "./worldBookManagerUtils"

export { WorldBookForm } from "./WorldBookForm"

export const WorldBooksManager: React.FC = () => {
  const isOnline = useServerOnline()
  const { t } = useTranslation(["option"])
  const screens = Grid.useBreakpoint()
  const qc = useQueryClient()
  const notification = useAntdNotification()
  const { showUndoNotification } = useUndoNotification()
  const [open, setOpen] = React.useState(false)
  const [openEdit, setOpenEdit] = React.useState(false)
  const [openEntries, setOpenEntries] = React.useState<
    null | { id: number; name: string; entryCount?: number; tokenBudget?: number }
  >(null)
  const [openAttach, setOpenAttach] = React.useState<null | number>(null)
  const [editId, setEditId] = React.useState<number | null>(null)
  const [editExpectedVersion, setEditExpectedVersion] = React.useState<number | null>(null)
  const [editConflict, setEditConflict] = React.useState<EditWorldBookConflictState | null>(null)
  const [openMatrix, setOpenMatrix] = React.useState(false)
  const [attachmentsHydrationRequested, setAttachmentsHydrationRequested] = React.useState(false)
  const [openGlobalStats, setOpenGlobalStats] = React.useState(false)
  const [statsFor, setStatsFor] = React.useState<any | null>(null)
  const [statsLoadingId, setStatsLoadingId] = React.useState<number | null>(null)
  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()
  const [entryForm] = Form.useForm()
  const [attachForm] = Form.useForm()
  const importFormatHelpContentId = React.useId()
  const importErrorDetailsContentId = React.useId()
  const importPreviewEntriesContentId = React.useId()
  const confirmDanger = useConfirmDanger()
  const entriesFocusReturnRef = React.useRef<HTMLElement | null>(null)
  const matrixFocusReturnRef = React.useRef<HTMLElement | null>(null)
  const matrixBaselineKeysRef = React.useRef<Set<string>>(new Set())
  const matrixPulseTimersRef = React.useRef<Record<string, any>>({})
  const matrixFeedbackTimerRef = React.useRef<any>(null)
  const [matrixPending, setMatrixPending] = React.useState<Record<string, boolean>>({})
  const [matrixSessionDeltas, setMatrixSessionDeltas] = React.useState<
    Record<string, "attached" | "detached">
  >({})
  const [matrixSuccessPulse, setMatrixSuccessPulse] = React.useState<Record<string, boolean>>({})
  const [matrixMetaPopoverOpenKey, setMatrixMetaPopoverOpenKey] = React.useState<string | null>(null)
  const [matrixMetaDrafts, setMatrixMetaDrafts] = React.useState<
    Record<string, { enabled: boolean; priority: number }>
  >({})
  const [matrixFeedback, setMatrixFeedback] = React.useState<{
    kind: "success" | "error"
    message: string
  } | null>(null)
  const [matrixBookFilter, setMatrixBookFilter] = React.useState('')
  const [matrixCharacterFilter, setMatrixCharacterFilter] = React.useState('')
  const [matrixListPage, setMatrixListPage] = React.useState(1)
  const [entryFilterPreset, setEntryFilterPreset] = React.useState<EntryFilterPreset>(
    DEFAULT_ENTRY_FILTER_PRESET
  )

  const getActiveFocusableElement = React.useCallback((): HTMLElement | null => {
    if (typeof document === "undefined") return null
    const activeElement = document.activeElement
    return activeElement instanceof HTMLElement ? activeElement : null
  }, [])

  const restoreFocusToElement = React.useCallback((target: HTMLElement | null) => {
    if (!target) return
    window.setTimeout(() => {
      if (!target.isConnected) return
      if (target instanceof HTMLButtonElement && target.disabled) return
      if (target instanceof HTMLInputElement && target.disabled) return
      target.focus()
    }, 0)
  }, [])

  const { data, status } = useQuery({
    queryKey: ['tldw:listWorldBooks'],
    queryFn: async () => {
      await tldwClient.initialize()
      const res = await tldwClient.listWorldBooks(false)
      return res?.world_books || []
    },
    enabled: isOnline
  })

  const { data: worldBookRuntimeConfig } = useQuery({
    queryKey: ["tldw:worldBookRuntimeConfig"],
    queryFn: async () => {
      await tldwClient.initialize()
      return await tldwClient.getWorldBookRuntimeConfig()
    },
    enabled: isOnline
  })

  const { data: characters } = useQuery({
    queryKey: ['tldw:listCharactersForWB'],
    queryFn: async () => {
      await tldwClient.initialize()
      return await tldwClient.listCharacters()
    },
    enabled: isOnline
  })

  const { data: attachmentsByBook, isLoading: attachmentsLoading } = useQuery({
    queryKey: ['tldw:worldBookAttachments', (characters || []).map((c: any) => c.id).join(',')],
    queryFn: async () => {
      if (!characters || characters.length === 0) return {}
      await tldwClient.initialize()
      const results: Array<{ character: any; books: any[] }> = []
      for (const character of characters || []) {
        try {
          const books = await tldwClient.listCharacterWorldBooks(character.id)
          results.push({ character, books: books || [] })
        } catch {
          results.push({ character, books: [] })
        }
      }
      const map: Record<number, any[]> = {}
      results.forEach(({ character, books }) => {
        (books || []).forEach((b: any) => {
          const wid = b.world_book_id ?? b.id
          if (!map[wid]) map[wid] = []
          map[wid].push({
            id: character.id,
            name: character.name,
            attachment_enabled: b.attachment_enabled,
            attachment_priority: b.attachment_priority
          })
        })
      })
      return map
    },
    enabled: isOnline && attachmentsHydrationRequested && !!characters && characters.length > 0
  })

  const requestAttachmentHydration = React.useCallback(() => {
    setAttachmentsHydrationRequested(true)
  }, [])

  const maxRecursiveDepth =
    typeof worldBookRuntimeConfig?.max_recursive_depth === "number" &&
    Number.isFinite(worldBookRuntimeConfig.max_recursive_depth)
      ? worldBookRuntimeConfig.max_recursive_depth
      : 10

  const activeCharacterIds = React.useMemo(() => {
    const ids = new Set<number>()
    ;(characters || []).forEach((character: any) => {
      const id = Number(character?.id)
      if (Number.isFinite(id) && id > 0) ids.add(id)
    })
    return ids
  }, [characters])

  const reconciledAttachmentsByBook = React.useMemo(() => {
    const source = attachmentsByBook as Record<number, any[]> | undefined
    if (!source || typeof source !== "object") return {}

    const next: Record<number, any[]> = {}
    Object.entries(source).forEach(([worldBookIdRaw, attachedCharacters]) => {
      const worldBookId = Number(worldBookIdRaw)
      if (!Number.isFinite(worldBookId) || worldBookId <= 0) return
      const list = Array.isArray(attachedCharacters) ? attachedCharacters : []
      const filtered = list.filter((character: any) => {
        const characterId = Number(character?.id)
        if (!Number.isFinite(characterId) || characterId <= 0) return false
        if (activeCharacterIds.size === 0) return true
        return activeCharacterIds.has(characterId)
      })
      if (filtered.length > 0) next[worldBookId] = filtered
    })
    return next
  }, [activeCharacterIds, attachmentsByBook])

  const globalStatsQuerySignature = React.useMemo(
    () =>
      ((data || []) as any[])
        .map((book: any) => `${book?.id}:${book?.last_modified || ""}`)
        .join("|"),
    [data]
  )

  const {
    data: globalStats,
    status: globalStatsStatus,
    isFetching: globalStatsFetching
  } = useQuery<GlobalWorldBookStatistics>({
    queryKey: ["tldw:worldBookGlobalStatistics", globalStatsQuerySignature],
    queryFn: async () => {
      await tldwClient.initialize()
      const books = Array.isArray(data) ? (data as any[]) : []
      const entriesByBook: Record<number, unknown> = {}
      await Promise.all(
        books.map(async (book: any) => {
          const worldBookId = Number(book?.id)
          if (!Number.isFinite(worldBookId) || worldBookId <= 0) return
          const response = await tldwClient.listWorldBookEntries(worldBookId, false)
          entriesByBook[worldBookId] = Array.isArray(response?.entries) ? response.entries : []
        })
      )
      return buildGlobalWorldBookStatistics(books, entriesByBook)
    },
    enabled: isOnline && openGlobalStats && Array.isArray(data) && data.length > 0
  })

  const quickAttachWorldBookName = React.useMemo(() => {
    if (!openAttach) return null
    const match = ((data || []) as any[]).find(
      (book: any) => Number(book?.id) === Number(openAttach)
    )
    return match?.name || null
  }, [data, openAttach])

  const getAttachedCharacters = React.useCallback(
    (worldBookId: number) => reconciledAttachmentsByBook[worldBookId] || [],
    [reconciledAttachmentsByBook]
  )

  const { mutate: createWB, isPending: creating } = useMutation({
    mutationFn: async (values: any) => {
      const templateKey =
        typeof values?.template_key === "string" ? values.template_key : undefined
      const payload = { ...(values || {}) }
      delete payload.template_key

      const created = await tldwClient.createWorldBook(payload)
      const template = getWorldBookStarterTemplate(templateKey)
      const createdId = Number(created?.id)

      if (template && Number.isFinite(createdId) && createdId > 0) {
        for (const entry of template.entries) {
          await tldwClient.addWorldBookEntry(createdId, {
            keywords: entry.keywords,
            content: entry.content,
            priority: typeof entry.priority === "number" ? entry.priority : 0,
            enabled: typeof entry.enabled === "boolean" ? entry.enabled : true,
            case_sensitive: !!entry.case_sensitive,
            regex_match: !!entry.regex_match,
            whole_word_match:
              typeof entry.whole_word_match === "boolean"
                ? entry.whole_word_match
                : true,
            appendable: !!entry.appendable
          })
        }
      }

      return created
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tldw:listWorldBooks'] }); setOpen(false); createForm.resetFields() },
    onError: (e: any, values: any) =>
      notification.error({
        message: "Error",
        description: buildWorldBookMutationErrorMessage(e, {
          attemptedName: values?.name,
          fallback: "Failed to create world book"
        })
      })
  })
  const { mutate: updateWB, isPending: updating } = useMutation({
    mutationFn: (values: any) => {
      if (editId == null) return Promise.resolve(null)
      if (typeof editExpectedVersion === "number") {
        return tldwClient.updateWorldBook(editId, values, {
          expectedVersion: editExpectedVersion
        })
      }
      return tldwClient.updateWorldBook(editId, values)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tldw:listWorldBooks'] })
      setOpenEdit(false)
      editForm.resetFields()
      setEditId(null)
      setEditExpectedVersion(null)
      setEditConflict(null)
    },
    onError: (e: any, values: any) => {
      const description = buildWorldBookMutationErrorMessage(e, {
        attemptedName: values?.name,
        fallback: "Failed to update world book"
      })
      notification.error({
        message: "Error",
        description
      })
      if (isWorldBookVersionConflictError(e)) {
        setEditConflict({
          attemptedValues: { ...(values || {}) },
          message: description
        })
        void qc.invalidateQueries({ queryKey: ["tldw:listWorldBooks"] })
      }
    }
  })
  const { mutate: deleteWB, isPending: deleting } = useMutation({
    mutationFn: (id: number) => tldwClient.deleteWorldBook(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tldw:listWorldBooks'] }) },
    onError: (e: any) => notification.error({ message: 'Error', description: e?.message || 'Failed to delete world book' })
  })
  const { mutate: doImport, isPending: importing } = useMutation({
    mutationFn: (payload: any) => tldwClient.importWorldBook(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tldw:listWorldBooks'] })
      resetImportAfterSuccess()
    },
    onError: (e: any) => notification.error({ message: 'Error', description: e?.message || 'Failed to import world book' })
  })

  const { mutateAsync: attachWB, isPending: attaching } = useMutation({
    mutationFn: ({
      characterId,
      worldBookId,
      enabled,
      priority
    }: {
      characterId: number
      worldBookId: number
      enabled?: boolean
      priority?: number
    }) => {
      const hasEnabled = typeof enabled === "boolean"
      const hasPriority = typeof priority === "number" && Number.isFinite(priority)
      if (hasEnabled || hasPriority) {
        return tldwClient.attachWorldBookToCharacter(characterId, worldBookId, {
          ...(hasEnabled ? { enabled } : {}),
          ...(hasPriority ? { priority } : {})
        })
      }
      return tldwClient.attachWorldBookToCharacter(characterId, worldBookId)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tldw:worldBookAttachments'] })
    },
    onError: (e: any) => notification.error({ message: 'Error', description: e?.message || 'Failed to attach world book' })
  })

  const { mutateAsync: detachWB } = useMutation({
    mutationFn: ({ characterId, worldBookId }: { characterId: number; worldBookId: number }) =>
      tldwClient.detachWorldBookFromCharacter(characterId, worldBookId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tldw:worldBookAttachments'] })
    },
    onError: (e: any) => notification.error({ message: 'Error', description: e?.message || 'Failed to detach world book' })
  })

  const [detachingFor, setDetachingFor] = React.useState<{ characterId: number; worldBookId: number } | null>(null)

  const renderAttachedCell = (record: any) => {
    if (!attachmentsHydrationRequested) {
      return <Tag color="default">Open to load</Tag>
    }
    if (attachmentsLoading) return <span className="text-text-muted">Loading…</span>
    const attached = getAttachedCharacters(record.id)
    if (!attached || attached.length === 0) {
      return <Tag color="gold">Unattached</Tag>
    }

    const buildCharacterWorkspaceHref = (characterId: number | string) => {
      const params = new URLSearchParams()
      params.set("from", "world-books")
      params.set("focusCharacterId", String(characterId))
      params.set("focusWorldBookId", String(record.id))
      return `/characters?${params.toString()}`
    }

    return (
      <Popover
        trigger="click"
        title="Attached Characters"
        content={
          <div className="space-y-2">
            {attached.map((c: any) => (
              <div key={c.id} className="flex items-center justify-between gap-2">
                <a
                  href={buildCharacterWorkspaceHref(c.id)}
                  className="text-sm text-primary hover:underline"
                  aria-label={`Open character ${c.name || `Character ${c.id}`}`}
                >
                  {c.name || `Character ${c.id}`}
                </a>
                <Button
                  size="small"
                  danger
                  loading={detachingFor?.characterId === c.id && detachingFor?.worldBookId === record.id}
                  onClick={async (e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    setDetachingFor({ characterId: c.id, worldBookId: record.id })
                    try {
                      await detachWB({ characterId: c.id, worldBookId: record.id })
                      notification.success({ message: 'Detached' })
                    } finally {
                      setDetachingFor(null)
                    }
                  }}
                >
                  Detach
                </Button>
              </div>
            ))}
          </div>
        }
      >
        <Button
          type="link"
          size="small"
          className="px-0"
          aria-label={`View attached characters for ${record?.name || "world book"} (${attached.length})`}
        >
          {attached.length} {attached.length === 1 ? "character" : "characters"}
        </Button>
      </Popover>
    )
  }

  const renderLastModifiedCell = (value: unknown) => {
    const formatted = formatWorldBookLastModified(value)
    if (!formatted.timestamp) {
      return <span className="text-text-muted">{UNKNOWN_LAST_MODIFIED_LABEL}</span>
    }
    return (
      <Tooltip title={formatted.absolute}>
        <span>{formatted.relative}</span>
      </Tooltip>
    )
  }

  const renderBudgetCell = (value: unknown) => {
    if (typeof value !== "number" || !Number.isFinite(value)) {
      return <span className="text-text-muted">—</span>
    }
    return <span>{value.toLocaleString()} tok</span>
  }

  const attachmentKeyFor = React.useCallback((worldBookId: number, characterId: number) => {
    return `${worldBookId}:${characterId}`
  }, [])

  const applyMatrixFeedback = React.useCallback((kind: "success" | "error", message: string) => {
    if (matrixFeedbackTimerRef.current) {
      clearTimeout(matrixFeedbackTimerRef.current)
    }
    setMatrixFeedback({ kind, message })
    matrixFeedbackTimerRef.current = setTimeout(() => {
      setMatrixFeedback((current) => (current?.message === message ? null : current))
      matrixFeedbackTimerRef.current = null
    }, ATTACHMENT_FEEDBACK_DURATION_MS)
  }, [])

  const initializeMatrixSession = React.useCallback(() => {
    const baseline = new Set<string>()
    const source = reconciledAttachmentsByBook as Record<string, any> | undefined
    if (source && typeof source === "object") {
      Object.entries(source).forEach(([worldBookIdRaw, attachedCharacters]) => {
        const worldBookId = Number(worldBookIdRaw)
        if (!Number.isFinite(worldBookId) || worldBookId <= 0) return
        const list = Array.isArray(attachedCharacters) ? attachedCharacters : []
        list.forEach((character: any) => {
          const characterId = Number(character?.id)
          if (!Number.isFinite(characterId) || characterId <= 0) return
          baseline.add(attachmentKeyFor(worldBookId, characterId))
        })
      })
    }

    matrixBaselineKeysRef.current = baseline
    Object.values(matrixPulseTimersRef.current).forEach((timerId) => clearTimeout(timerId))
    matrixPulseTimersRef.current = {}
    if (matrixFeedbackTimerRef.current) {
      clearTimeout(matrixFeedbackTimerRef.current)
      matrixFeedbackTimerRef.current = null
    }
    setMatrixSessionDeltas({})
    setMatrixSuccessPulse({})
    setMatrixMetaDrafts({})
    setMatrixMetaPopoverOpenKey(null)
    setMatrixFeedback(null)
  }, [attachmentKeyFor, reconciledAttachmentsByBook])

  const handleOpenMatrix = React.useCallback(() => {
    matrixFocusReturnRef.current = getActiveFocusableElement()
    requestAttachmentHydration()
    initializeMatrixSession()
    setOpenMatrix(true)
  }, [getActiveFocusableElement, initializeMatrixSession, requestAttachmentHydration])

  const handleCloseMatrix = React.useCallback(() => {
    const focusTarget = matrixFocusReturnRef.current
    matrixFocusReturnRef.current = null
    setOpenMatrix(false)
    initializeMatrixSession()
    restoreFocusToElement(focusTarget)
  }, [initializeMatrixSession, restoreFocusToElement])

  const openFullMatrixFromQuickAttach = React.useCallback(() => {
    setOpenAttach(null)
    handleOpenMatrix()
  }, [handleOpenMatrix])

  const isAttached = React.useCallback((worldBookId: number, characterId: number) => {
    const attached = getAttachedCharacters(worldBookId)
    return attached.some((c: any) => c.id === characterId)
  }, [getAttachedCharacters])

  const getAttachmentMetadata = React.useCallback(
    (worldBookId: number, characterId: number) => {
      const attached = getAttachedCharacters(worldBookId).find(
        (character: any) => Number(character?.id) === characterId
      )
      return {
        enabled:
          typeof attached?.attachment_enabled === "boolean"
            ? attached.attachment_enabled
            : true,
        priority:
          typeof attached?.attachment_priority === "number" &&
          Number.isFinite(attached.attachment_priority)
            ? attached.attachment_priority
            : 0
      }
    },
    [getAttachedCharacters]
  )

  const handleMatrixToggle = async (worldBookId: number, characterId: number, next: boolean) => {
    const key = attachmentKeyFor(worldBookId, characterId)
    if (matrixPending[key]) return
    setMatrixPending((prev) => ({ ...prev, [key]: true }))
    try {
      if (next) {
        await attachWB({ characterId, worldBookId })
      } else {
        await detachWB({ characterId, worldBookId })
      }

      const baselineHadAttachment = matrixBaselineKeysRef.current.has(key)
      if (baselineHadAttachment === next) {
        setMatrixSessionDeltas((prev) => {
          const copy = { ...prev }
          delete copy[key]
          return copy
        })
      } else {
        setMatrixSessionDeltas((prev) => ({
          ...prev,
          [key]: next ? "attached" : "detached"
        }))
      }

      const worldBookName =
        ((data || []) as any[]).find((book: any) => Number(book?.id) === worldBookId)?.name ||
        `World Book ${worldBookId}`
      const characterName =
        ((characters || []) as any[]).find((character: any) => Number(character?.id) === characterId)
          ?.name || `Character ${characterId}`
      applyMatrixFeedback(
        "success",
        `${next ? "Attached" : "Detached"} ${characterName} ${next ? "to" : "from"} ${worldBookName}.`
      )

      if (matrixPulseTimersRef.current[key]) {
        clearTimeout(matrixPulseTimersRef.current[key])
      }
      setMatrixSuccessPulse((prev) => ({ ...prev, [key]: true }))
      matrixPulseTimersRef.current[key] = setTimeout(() => {
        setMatrixSuccessPulse((prev) => {
          const copy = { ...prev }
          delete copy[key]
          return copy
        })
        delete matrixPulseTimersRef.current[key]
      }, ATTACHMENT_PULSE_DURATION_MS)
    } catch (error: any) {
      const worldBookName =
        ((data || []) as any[]).find((book: any) => Number(book?.id) === worldBookId)?.name ||
        `World Book ${worldBookId}`
      const characterName =
        ((characters || []) as any[]).find((character: any) => Number(character?.id) === characterId)
          ?.name || `Character ${characterId}`
      const errorDetails = String(error?.message || "Unknown error")
      applyMatrixFeedback(
        "error",
        `Could not ${next ? "attach" : "detach"} ${characterName} ${next ? "to" : "from"} ${worldBookName}. Changes were reverted. ${errorDetails}`
      )
    } finally {
      setMatrixPending((prev) => {
        const copy = { ...prev }
        delete copy[key]
        return copy
      })
    }
  }

  const openMatrixMetadataEditor = React.useCallback(
    (worldBookId: number, characterId: number) => {
      const key = attachmentKeyFor(worldBookId, characterId)
      const defaults = getAttachmentMetadata(worldBookId, characterId)
      setMatrixMetaDrafts((prev) => ({
        ...prev,
        [key]:
          prev[key] || {
            enabled: defaults.enabled,
            priority: defaults.priority
          }
      }))
      setMatrixMetaPopoverOpenKey(key)
    },
    [attachmentKeyFor, getAttachmentMetadata]
  )

  const updateMatrixMetadataDraft = React.useCallback(
    (
      worldBookId: number,
      characterId: number,
      patch: Partial<{ enabled: boolean; priority: number }>
    ) => {
      const key = attachmentKeyFor(worldBookId, characterId)
      setMatrixMetaDrafts((prev) => {
        const baseline = prev[key] || getAttachmentMetadata(worldBookId, characterId)
        return {
          ...prev,
          [key]: {
            enabled:
              typeof patch.enabled === "boolean" ? patch.enabled : baseline.enabled,
            priority:
              typeof patch.priority === "number" && Number.isFinite(patch.priority)
                ? patch.priority
                : baseline.priority
          }
        }
      })
    },
    [attachmentKeyFor, getAttachmentMetadata]
  )

  const saveMatrixMetadata = React.useCallback(
    async (worldBookId: number, characterId: number) => {
      const key = attachmentKeyFor(worldBookId, characterId)
      if (matrixPending[key]) return

      const draft = matrixMetaDrafts[key] || getAttachmentMetadata(worldBookId, characterId)
      const nextPriority = Number.isFinite(draft.priority) ? draft.priority : 0
      setMatrixPending((prev) => ({ ...prev, [key]: true }))
      try {
        await attachWB({
          characterId,
          worldBookId,
          enabled: draft.enabled,
          priority: nextPriority
        })

        const worldBookName =
          ((data || []) as any[]).find((book: any) => Number(book?.id) === worldBookId)?.name ||
          `World Book ${worldBookId}`
        const characterName =
          ((characters || []) as any[]).find(
            (character: any) => Number(character?.id) === characterId
          )?.name || `Character ${characterId}`
        applyMatrixFeedback(
          "success",
          `Updated attachment settings for ${characterName} in ${worldBookName}.`
        )
        setMatrixMetaPopoverOpenKey(null)
      } catch (error: any) {
        const worldBookName =
          ((data || []) as any[]).find((book: any) => Number(book?.id) === worldBookId)?.name ||
          `World Book ${worldBookId}`
        const characterName =
          ((characters || []) as any[]).find(
            (character: any) => Number(character?.id) === characterId
          )?.name || `Character ${characterId}`
        const errorDetails = String(error?.message || "Unknown error")
        applyMatrixFeedback(
          "error",
          `Could not update attachment settings for ${characterName} in ${worldBookName}. ${errorDetails}`
        )
      } finally {
        setMatrixPending((prev) => {
          const copy = { ...prev }
          delete copy[key]
          return copy
        })
      }
    },
    [
      attachmentKeyFor,
      attachWB,
      characters,
      data,
      getAttachmentMetadata,
      matrixMetaDrafts,
      matrixPending,
      applyMatrixFeedback
    ]
  )

  const normalizeCharacterIds = React.useCallback((values: Array<number | string>) => {
    return Array.from(
      new Set(
        values
          .map((value) => Number(value))
          .filter((id) => Number.isFinite(id) && id > 0)
      )
    )
  }, [])

  const filteredBooks = React.useMemo(() => {
    const q = matrixBookFilter.trim().toLowerCase()
    if (!q) return data || []
    return (data || []).filter((b: any) => (b.name || '').toLowerCase().includes(q))
  }, [data, matrixBookFilter])

  const filteredCharacters = React.useMemo(() => {
    const q = matrixCharacterFilter.trim().toLowerCase()
    if (!q) return characters || []
    return (characters || []).filter((c: any) => (c.name || '').toLowerCase().includes(q))
  }, [characters, matrixCharacterFilter])

  const useAttachmentListView = !screens.md || filteredCharacters.length > ATTACHMENT_MATRIX_CHARACTER_THRESHOLD

  const focusMatrixCheckboxAt = React.useCallback((rowIndex: number, colIndex: number) => {
    if (typeof document === "undefined") return false
    const selector =
      `input[data-matrix-checkbox="true"]` +
      `[data-matrix-row-index="${rowIndex}"]` +
      `[data-matrix-col-index="${colIndex}"]`
    const target = document.querySelector<HTMLInputElement>(selector)
    if (!target) return false
    target.focus()
    return true
  }, [])

  const handleMatrixCellKeyDown = React.useCallback(
    (
      event: React.KeyboardEvent<HTMLElement>,
      rowIndex: number,
      colIndex: number
    ) => {
      if (useAttachmentListView) return

      const maxRow = filteredBooks.length - 1
      const maxCol = filteredCharacters.length - 1
      if (maxRow < 0 || maxCol < 0) return

      let nextRow = rowIndex
      let nextCol = colIndex

      switch (event.key) {
        case "ArrowLeft":
          nextCol = Math.max(0, colIndex - 1)
          break
        case "ArrowRight":
          nextCol = Math.min(maxCol, colIndex + 1)
          break
        case "ArrowUp":
          nextRow = Math.max(0, rowIndex - 1)
          break
        case "ArrowDown":
          nextRow = Math.min(maxRow, rowIndex + 1)
          break
        case "Home":
          nextCol = 0
          break
        case "End":
          nextCol = maxCol
          break
        default:
          return
      }

      if (nextRow === rowIndex && nextCol === colIndex) return
      event.preventDefault()
      void focusMatrixCheckboxAt(nextRow, nextCol)
    },
    [filteredBooks.length, filteredCharacters.length, focusMatrixCheckboxAt, useAttachmentListView]
  )

  React.useEffect(() => {
    setMatrixListPage(1)
  }, [matrixBookFilter, matrixCharacterFilter, useAttachmentListView])

  const handleListAttachmentChange = React.useCallback(
    async (worldBookId: number, nextValues: Array<number | string>) => {
      const nextIds = normalizeCharacterIds(nextValues)
      const currentIds = normalizeCharacterIds(
        getAttachedCharacters(worldBookId).map((character: any) => character?.id)
      )
      const nextSet = new Set(nextIds)
      const currentSet = new Set(currentIds)

      const attachIds = nextIds.filter((id) => !currentSet.has(id))
      const detachIds = currentIds.filter((id) => !nextSet.has(id))
      if (attachIds.length === 0 && detachIds.length === 0) return

      await Promise.all([
        ...attachIds.map((id) => handleMatrixToggle(worldBookId, id, true)),
        ...detachIds.map((id) => handleMatrixToggle(worldBookId, id, false))
      ])
    },
    [getAttachedCharacters, handleMatrixToggle, normalizeCharacterIds]
  )

  // --- Hooks ---

  const filtering = useWorldBookFiltering({
    data,
    reconciledAttachmentsByBook,
    attachmentsLoading,
  })
  const {
    listSearch, setListSearch,
    enabledFilter, setEnabledFilter,
    attachmentFilter, setAttachmentFilter,
    selectedWorldBookKeys, setSelectedWorldBookKeys,
    tableSort,
    filteredWorldBooks,
    hasActiveListFilters,
    clearListFilters,
    handleTableSortChange,
  } = filtering

  const bulkActions = useWorldBookBulkActions({
    data,
    qc,
    notification,
    confirmDanger,
    showUndoNotification,
    deleteWB,
    deleting,
    attachmentsLoading,
    getAttachedCharacters,
    selectedWorldBookKeys,
    setSelectedWorldBookKeys,
  })
  const {
    bulkWorldBookAction,
    pendingDeleteIds,
    cancelPendingWorldBookDeletes,
    requestDeleteWorldBook,
    handleBulkWorldBookAction,
  } = bulkActions

  const importExport = useWorldBookImportExport({
    data,
    qc,
    notification,
    selectedWorldBookKeys,
  })
  const {
    openImport,
    importFormatHelpOpen, setImportFormatHelpOpen,
    importErrorDetailsOpen, setImportErrorDetailsOpen,
    importPreviewEntriesOpen, setImportPreviewEntriesOpen,
    mergeOnConflict, setMergeOnConflict,
    importPreview,
    importPayload,
    importError,
    importErrorDetails,
    importFileName,
    exportingId,
    bulkExportMode,
    duplicatingId,
    exportSingleWorldBook,
    exportWorldBookBundle,
    duplicateWorldBook,
    handleImportUpload,
    openImportModal,
    closeImportModal,
    resetImportAfterSuccess,
  } = importExport

  const testMatching = useWorldBookTestMatching()
  const {
    openTestMatching,
    testMatchingWorldBookId,
    openTestMatchingModal,
    closeTestMatchingModal,
  } = testMatching

  // --- End Hooks ---

  const handleCloseCreate = async () => {
    if (createForm.isFieldsTouched()) {
      const ok = await confirmDanger({
        title: "Discard changes?",
        content: "You have unsaved changes. Are you sure you want to close?",
        okText: "Discard",
        cancelText: "Keep editing"
      })
      if (!ok) return
    }
    setOpen(false)
    createForm.resetFields()
  }

  const handleCloseEdit = async () => {
    if (editForm.isFieldsTouched()) {
      const ok = await confirmDanger({
        title: "Discard changes?",
        content: "You have unsaved changes. Are you sure you want to close?",
        okText: "Discard",
        cancelText: "Keep editing"
      })
      if (!ok) return
    }
    setOpenEdit(false)
    editForm.resetFields()
    setEditId(null)
    setEditExpectedVersion(null)
    setEditConflict(null)
  }

  const handleCloseEntries = async () => {
    if (entryForm.isFieldsTouched()) {
      const ok = await confirmDanger({
        title: "Discard changes?",
        content: "You have unsaved changes in the entry form. Are you sure you want to close?",
        okText: "Discard",
        cancelText: "Keep editing"
      })
      if (!ok) return
    }
    const focusTarget = entriesFocusReturnRef.current
    entriesFocusReturnRef.current = null
    setOpenEntries(null)
    entryForm.resetFields()
    restoreFocusToElement(focusTarget)
  }

  const openEntriesWithPreset = React.useCallback(
    (
      book: { id: number; name: string; entryCount?: number; tokenBudget?: number },
      preset: EntryFilterPreset = DEFAULT_ENTRY_FILTER_PRESET
    ) => {
      entriesFocusReturnRef.current = getActiveFocusableElement()
      setEntryFilterPreset({ ...DEFAULT_ENTRY_FILTER_PRESET, ...(preset || {}) })
      setOpenEntries({
        id: book.id,
        name: book.name,
        entryCount: book.entryCount,
        tokenBudget: book.tokenBudget
      })
    },
    [getActiveFocusableElement]
  )

  const openEntriesFromStats = React.useCallback(
    (preset: EntryFilterPreset) => {
      const worldBookId = Number(statsFor?.world_book_id)
      if (!Number.isFinite(worldBookId) || worldBookId <= 0) return
      const worldBookName = String(statsFor?.name || `World Book ${worldBookId}`)
      const entryCount =
        typeof statsFor?.total_entries === "number" ? statsFor.total_entries : undefined
      const tokenBudget =
        typeof statsFor?.token_budget === "number" ? statsFor.token_budget : undefined
      entriesFocusReturnRef.current = getActiveFocusableElement()
      setEntryFilterPreset({ ...DEFAULT_ENTRY_FILTER_PRESET, ...(preset || {}) })
      setStatsFor(null)
      setOpenEntries({ id: worldBookId, name: worldBookName, entryCount, tokenBudget })
    },
    [getActiveFocusableElement, statsFor]
  )

  const openEntriesFromGlobalStats = React.useCallback(
    (worldBookId: number, keyword?: string) => {
      const source = ((data || []) as any[]).find(
        (book: any) => Number(book?.id) === Number(worldBookId)
      )
      if (!source) return
      entriesFocusReturnRef.current = getActiveFocusableElement()
      setOpenGlobalStats(false)
      setEntryFilterPreset({
        ...DEFAULT_ENTRY_FILTER_PRESET,
        searchText: String(keyword || "").trim()
      })
      setOpenEntries({
        id: Number(source.id),
        name: String(source.name || `World Book ${source.id}`),
        entryCount: typeof source.entry_count === "number" ? source.entry_count : undefined,
        tokenBudget: typeof source.token_budget === "number" ? source.token_budget : undefined
      })
    },
    [data, getActiveFocusableElement]
  )

  const latestEditRecord = React.useMemo(
    () =>
      ((data || []) as any[]).find(
        (book: any) => Number(book?.id) === Number(editId)
      ) || null,
    [data, editId]
  )
  const latestEditVersion =
    typeof latestEditRecord?.version === "number" ? latestEditRecord.version : null

  const handleLoadLatestEditValues = React.useCallback(() => {
    if (!latestEditRecord) return
    editForm.setFieldsValue(toWorldBookFormValues(latestEditRecord))
    setEditExpectedVersion(
      typeof latestEditRecord.version === "number" ? latestEditRecord.version : null
    )
    setEditConflict(null)
    notification.info({
      message: "Latest values loaded",
      description: "Review the refreshed values, reapply any local edits, then save again."
    })
  }, [editForm, latestEditRecord, notification])

  const handleReapplyEditDraft = React.useCallback(() => {
    if (!latestEditRecord || !editConflict) return
    editForm.setFieldsValue({
      ...toWorldBookFormValues(latestEditRecord),
      ...editConflict.attemptedValues
    })
    setEditExpectedVersion(
      typeof latestEditRecord.version === "number" ? latestEditRecord.version : null
    )
    setEditConflict(null)
    notification.info({
      message: "Edits reapplied",
      description: "Your unsaved edits were merged onto the latest version. Save to retry."
    })
  }, [editConflict, editForm, latestEditRecord, notification])

  React.useEffect(() => {
    return () => {
      Object.values(matrixPulseTimersRef.current).forEach((t) => clearTimeout(t))
      matrixPulseTimersRef.current = {}
      if (matrixFeedbackTimerRef.current) {
        clearTimeout(matrixFeedbackTimerRef.current)
        matrixFeedbackTimerRef.current = null
      }
    }
  }, [])

  const openEditWorldBook = (record: any) => {
    setEditId(record.id)
    setEditExpectedVersion(
      typeof record?.version === "number" ? record.version : null
    )
    setEditConflict(null)
    editForm.setFieldsValue(toWorldBookFormValues(record))
    setOpenEdit(true)
  }

  const openWorldBookStatistics = async (record: any) => {
    setStatsLoadingId(record.id)
    try {
      const stats = await tldwClient.worldBookStatistics(record.id)
      setStatsFor(stats)
    } catch (error: any) {
      notification.error({ message: "Stats failed", description: error?.message })
    } finally {
      setStatsLoadingId(null)
    }
  }

  const renderDesktopWorldBookActions = (record: any) => (
    <div className="flex gap-2">
      <Tooltip title="Edit">
        <Button
          type="text"
          size="small"
          aria-label="Edit world book"
          icon={<Pen className="w-4 h-4" />}
          onClick={() => openEditWorldBook(record)}
        />
      </Tooltip>
      <Tooltip title="Manage Entries">
        <Button
          type="text"
          size="small"
          aria-label="Manage entries"
          icon={<List className="w-4 h-4" />}
          onClick={() =>
            openEntriesWithPreset(
              {
                id: record.id,
                name: record.name,
                entryCount: record.entry_count,
                tokenBudget: record.token_budget
              },
              DEFAULT_ENTRY_FILTER_PRESET
            )
          }
        />
      </Tooltip>
      <Tooltip title="Duplicate World Book">
        <Button
          type="text"
          size="small"
          aria-label="Duplicate world book"
          icon={<Copy className="w-4 h-4" />}
          loading={duplicatingId === record.id}
          onClick={() => void duplicateWorldBook(record)}
        />
      </Tooltip>
      <Tooltip title="Quick Attach Characters">
        <Button
          type="text"
          size="small"
          aria-label="Quick attach characters"
          icon={<Link2 className="w-4 h-4" />}
          onClick={() => {
            requestAttachmentHydration()
            setOpenAttach(record.id)
          }}
        />
      </Tooltip>
      <Tooltip title="Export JSON">
        <Button
          type="text"
          size="small"
          aria-label="Export world book"
          icon={<Download className="w-4 h-4" />}
          loading={exportingId === record.id}
          onClick={() => void exportSingleWorldBook(record)}
        />
      </Tooltip>
      <Tooltip title="Statistics">
        <Button
          type="text"
          size="small"
          aria-label="View world book statistics"
          icon={<BarChart3 className="w-4 h-4" />}
          loading={statsLoadingId === record.id}
          onClick={() => void openWorldBookStatistics(record)}
        />
      </Tooltip>
      <Tooltip title="Delete">
        <Button
          type="text"
          size="small"
          danger
          aria-label="Delete world book"
          icon={<Trash2 className="w-4 h-4" />}
          disabled={deleting || pendingDeleteIds.includes(record.id)}
          onClick={() => void requestDeleteWorldBook(record)}
        />
      </Tooltip>
    </div>
  )

  const renderMobileWorldBookActions = (record: any) => {
    const menuItems = [
      {
        key: "entries",
        label: "Manage Entries",
        onClick: () =>
          openEntriesWithPreset(
            {
              id: record.id,
              name: record.name,
              entryCount: record.entry_count,
              tokenBudget: record.token_budget
            },
            DEFAULT_ENTRY_FILTER_PRESET
          )
      },
      {
        key: "edit",
        label: "Edit",
        onClick: () => openEditWorldBook(record)
      },
      {
        key: "duplicate",
        label: "Duplicate",
        onClick: () => void duplicateWorldBook(record)
      },
      {
        key: "attach",
        label: "Quick Attach Characters",
        onClick: () => {
          requestAttachmentHydration()
          setOpenAttach(record.id)
        }
      },
      {
        key: "export",
        label: "Export JSON",
        onClick: () => void exportSingleWorldBook(record)
      },
      {
        key: "stats",
        label: "Statistics",
        onClick: () => void openWorldBookStatistics(record)
      },
      {
        key: "delete",
        label: "Delete",
        danger: true,
        onClick: () => void requestDeleteWorldBook(record)
      }
    ]

    return (
      <Dropdown menu={{ items: menuItems }} trigger={["click"]} placement="bottomRight">
        <Button
          size="middle"
          type="default"
          aria-label={`More actions for ${record?.name || "world book"}`}
          icon={<MoreHorizontal className="w-4 h-4" />}
        />
      </Dropdown>
    )
  }

  const columns = [
    { title: "", key: "icon", width: 40, render: () => <BookOpen className="w-4 h-4" /> },
    {
      title: "Name",
      dataIndex: "name",
      key: "name",
      sorter: (a: any, b: any) => String(a?.name || "").localeCompare(String(b?.name || "")),
      sortOrder: tableSort.field === "name" ? tableSort.order : null,
      render: (value: string, record: any) => (
        <div className="flex flex-wrap items-center gap-2">
          <span>{value}</span>
          {pendingDeleteIds.includes(Number(record?.id)) && (
            <Tag color="orange">Pending delete</Tag>
          )}
        </div>
      )
    },
    ...(screens.md
      ? [
          {
            title: "Description",
            dataIndex: "description",
            key: "description",
            render: (v: string) => <span className="line-clamp-1">{v}</span>
          },
          {
            title: "Attached To",
            key: "attached_to",
            render: (_: any, record: any) => renderAttachedCell(record)
          },
          {
            title: "Budget",
            dataIndex: "token_budget",
            key: "token_budget",
            render: (v: unknown) => renderBudgetCell(v)
          }
        ]
      : []),
    {
      title: "Last Modified",
      dataIndex: "last_modified",
      key: "last_modified",
      render: (v: unknown) => renderLastModifiedCell(v)
    },
    {
      title: "Enabled",
      dataIndex: "enabled",
      key: "enabled",
      sorter: (a: any, b: any) => Number(Boolean(a?.enabled)) - Number(Boolean(b?.enabled)),
      sortOrder: tableSort.field === "enabled" ? tableSort.order : null,
      render: (v: boolean) => (v ? <Tag color="green">Enabled</Tag> : <Tag color="volcano">Disabled</Tag>)
    },
    {
      title: "Entries",
      dataIndex: "entry_count",
      key: "entry_count",
      sorter: (a: any, b: any) => Number(a?.entry_count || 0) - Number(b?.entry_count || 0),
      sortOrder: tableSort.field === "entry_count" ? tableSort.order : null
    },
    {
      title: "Actions",
      key: "actions",
      render: (_: any, record: any) =>
        screens.md
          ? renderDesktopWorldBookActions(record)
          : renderMobileWorldBookActions(record)
    }
  ]

  if (!isOnline) {
    return (
      <FeatureEmptyState
        title={t("option:worldBooksEmpty.offlineTitle", {
          defaultValue: "World Books are offline"
        })}
        description={t("option:worldBooksEmpty.offlineDescription", {
          defaultValue:
            "Connect to your tldw server from the main settings page to view and edit World Books."
        })}
      />
    )
  }

  return (
    <div className="space-y-4" data-testid="world-books-manager">
      <div
        className="flex flex-wrap items-center justify-between gap-2"
        data-testid="world-books-toolbar"
      >
        <div className="flex flex-wrap items-center gap-2">
          <Input
            allowClear
            placeholder="Search world books…"
            aria-label="Search world books"
            data-testid="world-books-search-input"
            value={listSearch}
            onChange={(e) => setListSearch(e.target.value)}
            className="w-full min-w-[220px] md:w-72"
          />
          <Select
            value={enabledFilter}
            onChange={(value) => setEnabledFilter(value)}
            aria-label="Filter by enabled status"
            data-testid="world-books-enabled-filter"
            className="w-40"
            options={[
              { label: "All statuses", value: "all" },
              { label: "Enabled", value: "enabled" },
              { label: "Disabled", value: "disabled" }
            ]}
          />
          <Select
            value={attachmentFilter}
            onChange={(value) => {
              if (value !== "all") {
                requestAttachmentHydration()
              }
              setAttachmentFilter(value)
            }}
            aria-label="Filter by attachment state"
            data-testid="world-books-attachment-filter"
            className="w-44"
            options={[
              { label: "All attachments", value: "all" },
              { label: "Has attachments", value: "attached" },
              { label: "Unattached only", value: "unattached" }
            ]}
          />
        </div>
        <div className="flex items-center gap-2">
          <Button aria-label="Open relationship matrix" onClick={handleOpenMatrix}>
            Relationship Matrix
          </Button>
          <Button
            aria-label="Open global statistics modal"
            loading={openGlobalStats && globalStatsFetching}
            disabled={!Array.isArray(data) || data.length === 0}
            onClick={() => setOpenGlobalStats(true)}
          >
            Global Statistics
          </Button>
          <Button
            aria-label="Open test matching modal"
            disabled={!Array.isArray(data) || data.length === 0}
            onClick={() => openTestMatchingModal()}
          >
            Test Matching
          </Button>
          <Button
            aria-label="Export all world books"
            loading={bulkExportMode === "all"}
            disabled={!Array.isArray(data) || data.length === 0}
            onClick={() => void exportWorldBookBundle("all")}
          >
            Export All
          </Button>
          <Button
            aria-label="Open world book import modal"
            data-testid="world-books-import-button"
            onClick={openImportModal}
          >
            Import
          </Button>
          <Button
            type="primary"
            data-testid="world-books-new-button"
            onClick={() => setOpen(true)}
          >
            New World Book
          </Button>
        </div>
      </div>
      <div className="rounded border border-border bg-surface-secondary px-3 py-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-text-muted">
            Need runtime injection diagnostics in a live chat turn?
          </p>
          <a
            href={LOREBOOK_DEBUG_ENTRYPOINT_HREF}
            className="text-xs text-primary hover:underline"
            aria-label="Open chat lorebook debug panel from world books"
          >
            Open Chat Debug Panel
          </a>
        </div>
      </div>
      {pendingDeleteIds.length > 0 && (
        <div
          data-testid="world-book-pending-delete-banner"
          className="rounded border border-amber-300 bg-amber-50 px-3 py-2"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-sm text-amber-800">
                <strong>{pendingDeleteIds.length}</strong>{" "}
                {pendingDeleteIds.length === 1 ? "world book" : "world books"} pending deletion.
              </p>
              <p className="text-xs text-amber-700">
                Timers run only in this tab. Refreshing or navigating away cancels pending deletions.
              </p>
            </div>
            <Button
              size="small"
              onClick={cancelPendingWorldBookDeletes}
              aria-label="Cancel pending world book deletions"
            >
              Cancel pending
            </Button>
          </div>
        </div>
      )}
      {selectedWorldBookKeys.length > 0 && (
        <div className="rounded border border-border bg-surface-secondary px-3 py-2 flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm">
            <strong>{selectedWorldBookKeys.length}</strong> selected
          </span>
          <div className="flex items-center gap-2">
            <Button
              size="small"
              loading={bulkExportMode === "selected"}
              onClick={() => void exportWorldBookBundle("selected")}
            >
              Export selected
            </Button>
            <Button
              size="small"
              loading={bulkWorldBookAction === "enable"}
              onClick={() => void handleBulkWorldBookAction("enable")}
            >
              Enable
            </Button>
            <Button
              size="small"
              loading={bulkWorldBookAction === "disable"}
              onClick={() => void handleBulkWorldBookAction("disable")}
            >
              Disable
            </Button>
            <Button
              size="small"
              danger
              loading={bulkWorldBookAction === "delete"}
              onClick={() => void handleBulkWorldBookAction("delete")}
            >
              Delete
            </Button>
          </div>
        </div>
      )}
      {status === 'pending' && <Skeleton active paragraph={{ rows: 6 }} />}
      {status === 'success' && (
        <Table
          data-testid="world-books-table"
          rowKey={(r: any) => r.id}
          dataSource={filteredWorldBooks}
          columns={columns as any}
          rowSelection={{
            selectedRowKeys: selectedWorldBookKeys,
            onChange: (keys) => setSelectedWorldBookKeys(keys)
          }}
          expandable={{
            expandRowByClick: true,
            rowExpandable: (record: any) => Number(record?.entry_count || 0) > 0,
            expandedRowRender: (record: any) => (
              <WorldBookEntryPreview
                worldBookId={record.id}
                entryCount={Number(record?.entry_count || 0)}
              />
            )
          }}
          locale={{
            emptyText: (Array.isArray(data) && data.length === 0 && !hasActiveListFilters) ? (
              <div className="py-6 text-center space-y-2">
                <p className="font-medium">No world books yet</p>
                <p className="text-sm text-text-muted">
                  World books store reusable lore and context snippets that can be injected into chats.
                </p>
                <Button type="primary" onClick={() => setOpen(true)}>
                  Create your first world book
                </Button>
              </div>
            ) : (
              <div className="py-4 text-center space-y-2">
                <p className="text-sm text-text-muted">No world books match the current filters.</p>
                {hasActiveListFilters && (
                  <Button size="small" onClick={clearListFilters}>
                    Clear filters
                  </Button>
                )}
              </div>
            )
          }}
          onChange={handleTableSortChange}
          rowClassName={(record: any) => (record?.enabled === false ? "opacity-75" : "")}
        />
      )}

      <Modal
        title="Create World Book"
        open={open}
        onCancel={handleCloseCreate}
        footer={null}
        styles={{ body: MODAL_BODY_SCROLL_STYLE }}
      >
        <WorldBookForm
          mode="create"
          form={createForm}
          worldBooks={(data || []) as any[]}
          submitting={creating}
          maxRecursiveDepth={maxRecursiveDepth}
          onSubmit={createWB}
        />
      </Modal>

      <Modal
        title="Import World Book (JSON)"
        open={openImport}
        onCancel={closeImportModal}
        footer={null}
        styles={{ body: MODAL_BODY_SCROLL_STYLE }}
      >
        <div className="space-y-3">
          <details
            className="rounded border border-border px-3 py-2"
            open={importFormatHelpOpen}
            onToggle={(event) => {
              const nextOpen = (event.currentTarget as HTMLDetailsElement).open
              setImportFormatHelpOpen(nextOpen)
            }}
          >
            <summary
              className="cursor-pointer text-sm font-medium"
              aria-expanded={importFormatHelpOpen}
              aria-controls={importFormatHelpContentId}
            >
              Format help
            </summary>
            <div id={importFormatHelpContentId} className="mt-2 space-y-2 text-xs text-text-muted">
              <p>Expected tldw JSON shape:</p>
              <pre className="overflow-auto rounded bg-surface-secondary p-2 text-[11px] leading-5 text-text">
{`{
  "world_book": { "name": "My Lorebook", "description": "...", "scan_depth": 3, "token_budget": 500 },
  "entries": [{ "keywords": ["keyword"], "content": "Lore content" }]
}`}
              </pre>
              <p>
                Required fields: <code>world_book.name</code>, at least one
                <code> entries[]</code> item, and each entry needs
                <code> keywords[]</code> + <code>content</code>.
              </p>
              <p>Also supported: SillyTavern and Kobold export formats.</p>
            </div>
          </details>
          <Upload
            data-testid="world-book-import-upload"
            accept=".json,application/json"
            maxCount={1}
            showUploadList={false}
            beforeUpload={(file) => {
              void handleImportUpload(file as File)
              return false
            }}
          >
            <Button icon={<UploadIcon className="h-4 w-4" />} aria-label="Import world book JSON file">
              Choose JSON file
            </Button>
          </Upload>
          <label className="inline-flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={mergeOnConflict}
              onChange={(ev) => setMergeOnConflict(ev.target.checked)}
            />
            Merge on conflict
            <Tooltip title={WORLD_BOOK_IMPORT_MERGE_HELP_TEXT}>
              <HelpCircle
                role="img"
                aria-label="Merge on conflict help"
                className="h-4 w-4 text-text-muted cursor-help"
              />
            </Tooltip>
          </label>
          {importFileName && <p className="text-xs text-text-muted">Selected: {importFileName}</p>}
          {importError && <p className="text-sm text-danger">{importError}</p>}
          {importError && importErrorDetails && (
            <details
              className="rounded border border-border px-3 py-2 text-xs text-text-muted"
              data-testid="import-error-details"
              open={importErrorDetailsOpen}
              onToggle={(event) => {
                const nextOpen = (event.currentTarget as HTMLDetailsElement).open
                setImportErrorDetailsOpen(nextOpen)
              }}
            >
              <summary
                className="cursor-pointer font-medium"
                aria-expanded={importErrorDetailsOpen}
                aria-controls={importErrorDetailsContentId}
              >
                More details
              </summary>
              <pre
                id={importErrorDetailsContentId}
                className="mt-2 whitespace-pre-wrap break-words text-[11px] leading-5 text-text-muted"
              >
                {importErrorDetails}
              </pre>
            </details>
          )}
          {importPreview && !importError && (
            <div className="p-3 rounded bg-surface-secondary text-sm space-y-1">
              <p><strong>Will import:</strong> {importPreview.name}</p>
              <p><strong>Entries:</strong> {importPreview.entryCount}</p>
              {importPreview.format && (
                <p><strong>Detected format:</strong> {getWorldBookImportFormatLabel(importPreview.format)}</p>
              )}
              {importPreview.settings && (
                <div className="pt-1 space-y-1">
                  <p><strong>Settings:</strong></p>
                  <p>Scan depth: {importPreview.settings.scanDepth ?? "Default"}</p>
                  <p>Token budget: {importPreview.settings.tokenBudget ?? "Default"}</p>
                  <p>
                    Recursive scanning:{" "}
                    {typeof importPreview.settings.recursiveScanning === "boolean"
                      ? importPreview.settings.recursiveScanning ? "Enabled" : "Disabled"
                      : "Default"}
                  </p>
                  <p>
                    World book enabled:{" "}
                    {typeof importPreview.settings.enabled === "boolean"
                      ? importPreview.settings.enabled ? "Enabled" : "Disabled"
                      : "Default"}
                  </p>
                </div>
              )}
              {(importPreview.previewEntries || []).length > 0 && (
                <details
                  className="pt-1"
                  data-testid="import-preview-entries"
                  open={importPreviewEntriesOpen}
                  onToggle={(event) => {
                    const nextOpen = (event.currentTarget as HTMLDetailsElement).open
                    setImportPreviewEntriesOpen(nextOpen)
                  }}
                >
                  <summary
                    className="cursor-pointer text-sm font-medium"
                    aria-expanded={importPreviewEntriesOpen}
                    aria-controls={importPreviewEntriesContentId}
                  >
                    Preview first {importPreview.previewEntries?.length} entries
                  </summary>
                  <div id={importPreviewEntriesContentId} className="mt-2 space-y-2">
                    {(importPreview.previewEntries || []).map((entry, index) => (
                      <div
                        key={`${index}-${entry.keywords.join(",")}`}
                        className="rounded border border-border px-2 py-1"
                        data-testid={`import-preview-entry-${index + 1}`}
                      >
                        <div className="flex flex-wrap gap-1 mb-1">
                          {(entry.keywords || []).slice(0, 5).map((keyword) => (
                            <Tag key={`${index}-${keyword}`}>{keyword}</Tag>
                          ))}
                        </div>
                        <p className="text-xs text-text-muted break-words">
                          {entry.contentPreview || "(No content preview)"}
                        </p>
                      </div>
                    ))}
                    {importPreview.entryCount > (importPreview.previewEntries || []).length && (
                      <p className="text-xs text-text-muted">
                        Showing first {(importPreview.previewEntries || []).length} of{" "}
                        {importPreview.entryCount} entries.
                      </p>
                    )}
                  </div>
                </details>
              )}
              {importPreview.conflict && (
                <p className="text-warning">
                  Name conflict detected. Enable "Merge on conflict" to append imported entries to the existing world book.
                </p>
              )}
              {(importPreview.warnings || []).length > 0 && (
                <div className="space-y-1">
                  <p className="font-medium">Conversion warnings:</p>
                  {(importPreview.warnings || []).slice(0, 5).map((warning, index) => (
                    <p key={`${warning}-${index}`} className="text-xs text-warning">- {warning}</p>
                  ))}
                </div>
              )}
            </div>
          )}
          <Button
            type="primary"
            className="w-full"
            loading={importing}
            disabled={!importPayload || !!importError}
            onClick={() => {
              if (!importPayload) return
              doImport({ ...importPayload, merge_on_conflict: mergeOnConflict })
            }}
          >
            Import
          </Button>
        </div>
      </Modal>

      <Modal
        title="World Book Statistics"
        open={!!statsFor}
        onCancel={() => setStatsFor(null)}
        footer={null}
        styles={{ body: MODAL_BODY_SCROLL_STYLE }}
      >
        {statsFor && (
          <div className="space-y-2">
            {(() => {
              const worldBookId = Number(statsFor.world_book_id)
              const matchingBook = ((data || []) as any[]).find(
                (book: any) => Number(book?.id) === worldBookId
              )
              const tokenBudget =
                typeof statsFor?.token_budget === "number"
                  ? statsFor.token_budget
                  : matchingBook?.token_budget
              const utilizationPercent = getBudgetUtilizationPercent(
                statsFor.estimated_tokens,
                tokenBudget
              )
              const utilizationBand = getBudgetUtilizationBand(utilizationPercent)
              const utilizationColor = getBudgetUtilizationColor(utilizationBand)
              const estimatorNote = getTokenEstimatorNote(statsFor)

              return (
                <>
                  <p className="text-xs text-text-muted">
                    {estimatorNote}
                  </p>
                  <p className="text-xs text-text-muted">
                    Tip: Click linked metrics to open the entries drawer with matching filters.
                  </p>
                  <Descriptions size="small" bordered column={1}>
                    <Descriptions.Item label="ID">{statsFor.world_book_id}</Descriptions.Item>
                    <Descriptions.Item label="Name">{statsFor.name}</Descriptions.Item>
                    <Descriptions.Item label="Total Entries">{statsFor.total_entries}</Descriptions.Item>
                    <Descriptions.Item label="Enabled Entries">
                      {Number(statsFor.enabled_entries || 0) > 0 ? (
                        <Button
                          type="link"
                          size="small"
                          className="px-0"
                          aria-label="Open enabled entries"
                          onClick={() =>
                            openEntriesFromStats({
                              enabledFilter: "enabled",
                              matchFilter: "all",
                              searchText: ""
                            })
                          }
                        >
                          {statsFor.enabled_entries}
                        </Button>
                      ) : (
                        statsFor.enabled_entries
                      )}
                    </Descriptions.Item>
                    <Descriptions.Item label="Disabled Entries">
                      {Number(statsFor.disabled_entries || 0) > 0 ? (
                        <Button
                          type="link"
                          size="small"
                          className="px-0"
                          aria-label="Open disabled entries"
                          onClick={() =>
                            openEntriesFromStats({
                              enabledFilter: "disabled",
                              matchFilter: "all",
                              searchText: ""
                            })
                          }
                        >
                          {statsFor.disabled_entries}
                        </Button>
                      ) : (
                        statsFor.disabled_entries
                      )}
                    </Descriptions.Item>
                    <Descriptions.Item label="Total Keywords">{statsFor.total_keywords}</Descriptions.Item>
                    <Descriptions.Item label="Regex Entries">
                      {Number(statsFor.regex_entries || 0) > 0 ? (
                        <Button
                          type="link"
                          size="small"
                          className="px-0"
                          aria-label="Open regex entries"
                          onClick={() =>
                            openEntriesFromStats({
                              enabledFilter: "all",
                              matchFilter: "regex",
                              searchText: ""
                            })
                          }
                        >
                          {statsFor.regex_entries}
                        </Button>
                      ) : (
                        statsFor.regex_entries
                      )}
                    </Descriptions.Item>
                    <Descriptions.Item label="Case Sensitive Entries">{statsFor.case_sensitive_entries}</Descriptions.Item>
                    <Descriptions.Item label="Average Priority">{statsFor.average_priority}</Descriptions.Item>
                    <Descriptions.Item label="Total Content Length">{statsFor.total_content_length}</Descriptions.Item>
                    <Descriptions.Item label="Estimated Tokens">{statsFor.estimated_tokens}</Descriptions.Item>
                    <Descriptions.Item label="Token Budget">
                      {typeof tokenBudget === "number" && Number.isFinite(tokenBudget)
                        ? tokenBudget
                        : <span className="text-text-muted">Not configured</span>}
                    </Descriptions.Item>
                    <Descriptions.Item label="Budget Utilization">
                      {typeof utilizationPercent === "number" ? (
                        <div className="space-y-1">
                          <p>
                            {statsFor.estimated_tokens}/{tokenBudget} ({utilizationPercent.toFixed(1)}%)
                          </p>
                          <Progress
                            percent={Math.min(utilizationPercent, 100)}
                            status={utilizationPercent > 100 ? "exception" : "normal"}
                            strokeColor={utilizationColor}
                            size="small"
                          />
                          {utilizationPercent > 100 && (
                            <div className="space-y-0.5">
                              <p className="text-xs text-danger">
                                Estimated token usage exceeds the configured budget.
                              </p>
                              <p className="text-xs text-text-muted">
                                Reduce entry content or increase token budget.
                              </p>
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className="text-text-muted">Budget unavailable</span>
                      )}
                    </Descriptions.Item>
                  </Descriptions>
                </>
              )
            })()}
          </div>
        )}
      </Modal>

      <Modal
        title="Global World Book Statistics"
        open={openGlobalStats}
        onCancel={() => setOpenGlobalStats(false)}
        footer={null}
        width={780}
        styles={{ body: MODAL_BODY_SCROLL_STYLE }}
      >
        {globalStatsStatus === "pending" && (
          <Skeleton active paragraph={{ rows: 8 }} />
        )}
        {globalStatsStatus === "success" && globalStats && (() => {
          const utilizationPercent = getBudgetUtilizationPercent(
            globalStats.totalEstimatedTokens,
            globalStats.totalTokenBudget
          )
          const utilizationBand = getBudgetUtilizationBand(utilizationPercent)
          const utilizationColor = getBudgetUtilizationColor(utilizationBand)

          return (
            <div className="space-y-3">
              <Descriptions size="small" bordered column={1}>
                <Descriptions.Item label="Total World Books">
                  {globalStats.totalBooks}
                </Descriptions.Item>
                <Descriptions.Item label="Total Entries">
                  {globalStats.totalEntries}
                </Descriptions.Item>
                <Descriptions.Item label="Total Keywords">
                  {globalStats.totalKeywords}
                </Descriptions.Item>
                <Descriptions.Item label="Estimated Tokens">
                  {globalStats.totalEstimatedTokens}
                </Descriptions.Item>
                <Descriptions.Item label="Aggregate Token Budget">
                  {globalStats.totalTokenBudget > 0
                    ? globalStats.totalTokenBudget
                    : <span className="text-text-muted">Not configured</span>}
                </Descriptions.Item>
                <Descriptions.Item label="Budget Utilization">
                  {typeof utilizationPercent === "number" ? (
                    <div className="space-y-1">
                      <p>
                        {globalStats.totalEstimatedTokens}/{globalStats.totalTokenBudget} ({utilizationPercent.toFixed(1)}%)
                      </p>
                      <Progress
                        percent={Math.min(utilizationPercent, 100)}
                        status={utilizationPercent > 100 ? "exception" : "normal"}
                        strokeColor={utilizationColor}
                        size="small"
                      />
                      {utilizationPercent > 100 && (
                        <div className="space-y-0.5">
                          <p className="text-xs text-danger">
                            Estimated token usage exceeds the configured budget.
                          </p>
                          <p className="text-xs text-text-muted">
                            Reduce entry content or increase token budget.
                          </p>
                        </div>
                      )}
                    </div>
                  ) : (
                    <span className="text-text-muted">Budget unavailable</span>
                  )}
                </Descriptions.Item>
                <Descriptions.Item label="Shared Keywords Across Books">
                  {globalStats.sharedKeywordCount}
                </Descriptions.Item>
                <Descriptions.Item label="Cross-book Keyword Conflicts">
                  {globalStats.conflictKeywordCount}
                </Descriptions.Item>
              </Descriptions>

              <Divider className="my-2" />

              <div className="space-y-2">
                <p className="text-xs text-text-muted">
                  Click a book under a keyword conflict to open entries filtered by that keyword.
                </p>
                {globalStats.conflicts.length === 0 ? (
                  <p className="text-sm text-text-muted">No cross-book keyword conflicts detected.</p>
                ) : (
                  <div className="space-y-2 max-h-72 overflow-auto pr-1">
                    {globalStats.conflicts.slice(0, 20).map((conflict) => (
                      <div
                        key={`${conflict.keyword}-${conflict.occurrenceCount}`}
                        className="rounded border border-border px-3 py-2"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <Tag color="volcano">{conflict.keyword}</Tag>
                          <span className="text-xs text-text-muted">
                            {conflict.affectedBooks.length} books, {conflict.variantCount} content variants
                          </span>
                        </div>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {conflict.affectedBooks.map((book) => (
                            <Button
                              key={`${conflict.keyword}-${book.id}`}
                              type="link"
                              size="small"
                              className="px-0"
                              aria-label={`Open conflict keyword ${conflict.keyword} in ${book.name}`}
                              onClick={() => openEntriesFromGlobalStats(book.id, conflict.keyword)}
                            >
                              {book.name}
                            </Button>
                          ))}
                        </div>
                      </div>
                    ))}
                    {globalStats.conflicts.length > 20 && (
                      <p className="text-xs text-text-muted">
                        Showing first 20 conflicts of {globalStats.conflicts.length}.
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>
          )
        })()}
      </Modal>

      <WorldBookTestMatchingModal
        open={openTestMatching}
        onClose={closeTestMatchingModal}
        worldBooks={Array.isArray(data) ? (data as any[]) : []}
        initialWorldBookId={testMatchingWorldBookId}
      />

      <Modal
        title="Edit World Book"
        open={openEdit}
        onCancel={handleCloseEdit}
        footer={null}
        styles={{ body: MODAL_BODY_SCROLL_STYLE }}
      >
        {editConflict && (
          <div
            data-testid="world-book-edit-conflict"
            className="mb-3 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800"
          >
            <p>{editConflict.message}</p>
            <p className="mt-1 text-xs text-amber-700">
              Reload the latest version and then reapply your edits before saving again.
              {latestEditVersion != null ? ` Latest version: ${latestEditVersion}.` : ""}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button
                size="small"
                onClick={handleLoadLatestEditValues}
                disabled={!latestEditRecord}
              >
                Load latest values
              </Button>
              <Button
                size="small"
                onClick={handleReapplyEditDraft}
                disabled={!latestEditRecord}
              >
                Reapply my edits
              </Button>
            </div>
          </div>
        )}
        <WorldBookForm
          mode="edit"
          form={editForm}
          worldBooks={(data || []) as any[]}
          submitting={updating}
          currentWorldBookId={editId}
          maxRecursiveDepth={maxRecursiveDepth}
          onSubmit={updateWB}
        />
      </Modal>

      <Drawer
        title={(
          <div className="space-y-1">
            <div className="text-xs text-text-muted">World Books &gt; {openEntries?.name || ''} &gt; Entries</div>
            <div className="font-semibold">Entries: {openEntries?.name || ''}</div>
          </div>
        )}
        placement="right"
        size={screens.md ? "60vw" : "100%"}
        open={!!openEntries}
        onClose={handleCloseEntries}
        destroyOnHidden
      >
        {openEntries && (
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Tag color="blue">Editing: {openEntries.name}</Tag>
              <Tag>Entries: {openEntries.entryCount ?? '—'}</Tag>
              <Tag>Attached: {getAttachedCharacters(openEntries.id).length}</Tag>
              {typeof openEntries.tokenBudget === "number" && (
                <Tag>Budget: {openEntries.tokenBudget}</Tag>
              )}
            </div>
            <Button
              size="small"
              aria-label="Test keywords for this world book"
              onClick={() => openTestMatchingModal(openEntries.id)}
            >
              Test Keywords
            </Button>
          </div>
        )}
        <EntryManager
          worldBookId={openEntries?.id!}
          worldBookName={openEntries?.name}
          tokenBudget={openEntries?.tokenBudget}
          worldBooks={(data || []) as any[]}
          entryFilterPreset={entryFilterPreset}
          form={entryForm}
        />
      </Drawer>

      <Modal
        title="World Book ↔ Character Matrix"
        open={openMatrix}
        onCancel={handleCloseMatrix}
        footer={null}
        width="90vw"
        styles={{ body: MODAL_BODY_SCROLL_STYLE }}
      >
        <div className="text-sm text-text-muted mb-3">
          Toggle checkboxes to attach or detach world books from characters.
        </div>
        {matrixFeedback && (
          <div
            role="status"
            aria-live="polite"
            className={`mb-3 rounded border px-2 py-1 text-xs ${
              matrixFeedback.kind === "success"
                ? "border-blue-300 bg-blue-50 text-blue-700"
                : "border-rose-300 bg-rose-50 text-rose-700"
            }`}
          >
            {matrixFeedback.message}
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <Input
            placeholder="Filter world books…"
            value={matrixBookFilter}
            onChange={(e) => setMatrixBookFilter(e.target.value)}
            allowClear
            className="max-w-xs"
          />
          <Input
            placeholder="Filter characters…"
            value={matrixCharacterFilter}
            onChange={(e) => setMatrixCharacterFilter(e.target.value)}
            allowClear
            className="max-w-xs"
          />
          <Button
            size="small"
            onClick={() => {
              setMatrixBookFilter('')
              setMatrixCharacterFilter('')
            }}
            disabled={!matrixBookFilter && !matrixCharacterFilter}
          >
            Clear filters
          </Button>
        </div>
        {filteredCharacters.length === 0 && (
          <Empty description="No characters match this filter" />
        )}
        <div className="text-xs text-text-muted mb-2" aria-live="polite">
          {useAttachmentListView
            ? `List view active (${filteredCharacters.length} characters).`
            : `Matrix view active (${filteredCharacters.length} characters).`}
        </div>
        {useAttachmentListView ? (
          <div className="border border-border rounded">
            <Table
              size="small"
              rowKey={(r: any) => r.id}
              dataSource={filteredBooks}
              pagination={{
                current: matrixListPage,
                pageSize: ATTACHMENT_LIST_PAGE_SIZE,
                total: filteredBooks.length,
                onChange: (page) => setMatrixListPage(page),
                showSizeChanger: false
              }}
              columns={[
                {
                  title: "World Book",
                  dataIndex: "name",
                  key: "name",
                  width: 220
                },
                {
                  title: "Attached Characters",
                  key: "attached_characters",
                  render: (_: any, record: any) => {
                    const attachedIds = normalizeCharacterIds(
                      getAttachedCharacters(record.id).map((character: any) => character?.id)
                    )
                    const rowDeltaStates = (filteredCharacters || [])
                      .map((character: any) => matrixSessionDeltas[attachmentKeyFor(record.id, character.id)])
                      .filter(
                        (value): value is "attached" | "detached" =>
                          value === "attached" || value === "detached"
                      )
                    const attachedDeltaCount = rowDeltaStates.filter(
                      (value) => value === "attached"
                    ).length
                    const detachedDeltaCount = rowDeltaStates.filter(
                      (value) => value === "detached"
                    ).length
                    const rowPending = filteredCharacters.some(
                      (character: any) => matrixPending[attachmentKeyFor(record.id, character.id)]
                    )
                    return (
                      <div className="space-y-1">
                        <Select
                          mode="multiple"
                          allowClear
                          showSearch
                          optionFilterProp="label"
                          aria-label={`Attachment selector for ${record?.name || "world book"}`}
                          placeholder="Select characters"
                          className="w-full"
                          value={attachedIds}
                          options={(filteredCharacters || []).map((character: any) => ({
                            label: character.name,
                            value: character.id
                          }))}
                          disabled={attachmentsLoading || rowPending || filteredCharacters.length === 0}
                          onChange={(values) => {
                            void handleListAttachmentChange(
                              record.id,
                              values as Array<number | string>
                            )
                          }}
                        />
                        <div className="text-xs text-text-muted">
                          {attachedIds.length} attached
                        </div>
                        {(attachedDeltaCount > 0 || detachedDeltaCount > 0) && (
                          <div className="flex flex-wrap items-center gap-1 text-[11px]">
                            {attachedDeltaCount > 0 && (
                              <Tag color="blue">+{attachedDeltaCount} new</Tag>
                            )}
                            {detachedDeltaCount > 0 && (
                              <Tag color="orange">-{detachedDeltaCount} removed</Tag>
                            )}
                          </div>
                        )}
                        <Button
                          size="small"
                          type="text"
                          aria-label={`Detach all characters from ${record?.name || "world book"}`}
                          disabled={attachedIds.length === 0 || attachmentsLoading || rowPending}
                          onClick={() => {
                            void handleListAttachmentChange(record.id, [])
                          }}
                        >
                          Detach all
                        </Button>
                      </div>
                    )
                  }
                }
              ] as any}
            />
          </div>
        ) : (
          <div
            className="overflow-x-auto border border-border rounded"
            role="grid"
            aria-label="World book attachment matrix"
            aria-rowcount={filteredBooks.length}
            aria-colcount={filteredCharacters.length + 1}
          >
            <Table
              size="small"
              pagination={false}
              scroll={{ x: "max-content" }}
              rowKey={(r: any) => r.id}
              dataSource={filteredBooks}
              columns={[
                { title: 'World Book', dataIndex: 'name', key: 'name', fixed: 'left', width: 200 },
                ...(filteredCharacters || []).map((c: any, characterColumnIndex: number) => ({
                  title: (
                    <Tooltip title={c.name}>
                      <a
                        href={`/characters?from=world-books&focusCharacterId=${encodeURIComponent(
                          String(c.id)
                        )}`}
                        className="truncate max-w-[140px] inline-block text-primary hover:underline"
                        onClick={(event) => event.stopPropagation()}
                        aria-label={`Open character ${c.name || `Character ${c.id}`}`}
                      >
                        {c.name}
                      </a>
                    </Tooltip>
                  ),
                  key: `char-${c.id}`,
                  width: 120,
                  render: (_: any, record: any, rowIndex: number) => {
                    const checked = isAttached(record.id, c.id)
                    const key = attachmentKeyFor(record.id, c.id)
                    const pending = !!matrixPending[key]
                    const deltaState = matrixSessionDeltas[key] || "none"
                    const pulse = !!matrixSuccessPulse[key]
                    const metadata = getAttachmentMetadata(record.id, c.id)
                    const metadataDraft = matrixMetaDrafts[key] || metadata
                    const isMetaPopoverOpen = matrixMetaPopoverOpenKey === key
                    const normalizedPriority = Number.isFinite(metadata.priority)
                      ? metadata.priority
                      : 0
                    const normalizedDraftPriority = Number.isFinite(metadataDraft.priority)
                      ? metadataDraft.priority
                      : 0
                    return (
                      <div
                        data-testid={`matrix-cell-${record.id}-${c.id}`}
                        data-delta-state={deltaState}
                        className={`inline-flex items-center justify-center gap-1 rounded px-1 py-1 transition-all ${
                          deltaState === "attached"
                            ? "ring-2 ring-blue-400 bg-blue-50"
                            : deltaState === "detached"
                              ? "ring-2 ring-amber-400 bg-amber-50"
                              : ""
                        } ${pulse ? "animate-pulse" : ""}`}
                      >
                        <Checkbox
                          aria-label={`Toggle attachment ${record?.name || "world book"} / ${c?.name || "character"}`}
                          checked={checked}
                          disabled={pending || attachmentsLoading}
                          onChange={(e) => handleMatrixToggle(record.id, c.id, e.target.checked)}
                          data-matrix-checkbox="true"
                          data-matrix-row-index={rowIndex}
                          data-matrix-col-index={characterColumnIndex}
                          onKeyDown={(event) =>
                            handleMatrixCellKeyDown(event, rowIndex, characterColumnIndex)
                          }
                        />
                        {checked && (
                          <>
                            <span
                              className={`text-[10px] ${
                                metadata.enabled ? "text-text-muted" : "text-warning"
                              }`}
                            >
                              P{normalizedPriority}
                            </span>
                            <Popover
                              trigger="click"
                              placement="bottomRight"
                              open={isMetaPopoverOpen}
                              onOpenChange={(nextOpen) => {
                                if (nextOpen) {
                                  openMatrixMetadataEditor(record.id, c.id)
                                } else if (isMetaPopoverOpen) {
                                  setMatrixMetaPopoverOpenKey(null)
                                }
                              }}
                              content={(
                                <div className="w-56 space-y-2">
                                  <div className="text-xs font-medium">Attachment settings</div>
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="text-xs">Enabled</span>
                                    <Switch
                                      size="small"
                                      aria-label={`Attachment enabled ${record?.name || "world book"} / ${c?.name || "character"}`}
                                      checked={metadataDraft.enabled}
                                      disabled={pending}
                                      onChange={(nextEnabled) =>
                                        updateMatrixMetadataDraft(record.id, c.id, {
                                          enabled: nextEnabled
                                        })
                                      }
                                      {...ACCESSIBLE_SWITCH_TEXT_PROPS}
                                    />
                                  </div>
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="text-xs">Priority</span>
                                    <InputNumber
                                      size="small"
                                      aria-label={`Attachment priority ${record?.name || "world book"} / ${c?.name || "character"}`}
                                      value={normalizedDraftPriority}
                                      disabled={pending}
                                      onChange={(value) => {
                                        const nextPriority = Number(value)
                                        updateMatrixMetadataDraft(record.id, c.id, {
                                          priority: Number.isFinite(nextPriority)
                                            ? nextPriority
                                            : 0
                                        })
                                      }}
                                    />
                                  </div>
                                  <div className="flex justify-end gap-2">
                                    <Button
                                      size="small"
                                      onClick={() => setMatrixMetaPopoverOpenKey(null)}
                                      disabled={pending}
                                    >
                                      Cancel
                                    </Button>
                                    <Button
                                      size="small"
                                      type="primary"
                                      loading={pending}
                                      onClick={() => {
                                        void saveMatrixMetadata(record.id, c.id)
                                      }}
                                    >
                                      Save
                                    </Button>
                                  </div>
                                </div>
                              )}
                            >
                              <Button
                                size="small"
                                type="text"
                                icon={<List className="h-3 w-3" />}
                                aria-label={`Edit attachment settings ${record?.name || "world book"} / ${c?.name || "character"}`}
                                disabled={pending}
                              />
                            </Popover>
                          </>
                        )}
                      </div>
                    )
                  }
                }))
              ] as any}
            />
          </div>
        )}
      </Modal>

      <Modal
        title={
          quickAttachWorldBookName
            ? `Quick attach: ${quickAttachWorldBookName}`
            : "Quick attach characters"
        }
        open={!!openAttach}
        onCancel={() => setOpenAttach(null)}
        footer={null}
        styles={{ body: MODAL_BODY_SCROLL_STYLE }}
      >
        <div className="space-y-4">
          <div className="rounded border border-border bg-background-subtle px-3 py-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="text-sm font-medium">Need bulk controls?</div>
                <div className="text-xs text-text-muted">
                  Open the full matrix to manage many world books and characters at once.
                </div>
              </div>
              <Button
                size="small"
                aria-label="Open full attachment matrix"
                onClick={openFullMatrixFromQuickAttach}
              >
                Open full matrix
              </Button>
            </div>
          </div>
          <div>
            <h4 className="text-sm font-medium mb-2">Currently attached</h4>
            {openAttach && getAttachedCharacters(openAttach).length > 0 ? (
              <div className="space-y-2">
                {getAttachedCharacters(openAttach).map((c: any) => (
                  <div key={c.id} className="flex items-center justify-between gap-2">
                    <a
                      href={`/characters?from=world-books&focusCharacterId=${encodeURIComponent(
                        String(c.id)
                      )}&focusWorldBookId=${encodeURIComponent(String(openAttach))}`}
                      className="text-sm text-primary hover:underline"
                      aria-label={`Open character ${c.name || `Character ${c.id}`}`}
                    >
                      {c.name || `Character ${c.id}`}
                    </a>
                    <Button
                      size="small"
                      danger
                      loading={detachingFor?.characterId === c.id && detachingFor?.worldBookId === openAttach}
                      onClick={async () => {
                        setDetachingFor({ characterId: c.id, worldBookId: openAttach })
                        try {
                          await detachWB({ characterId: c.id, worldBookId: openAttach })
                          notification.success({ message: 'Detached' })
                        } finally {
                          setDetachingFor(null)
                        }
                      }}
                    >
                      Detach
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <Empty description="No characters attached" />
            )}
          </div>
          <Divider className="my-2" />
          <Form
            layout="vertical"
            form={attachForm}
            onFinish={async (v) => {
              if (openAttach && v.character_id) {
                await attachWB({ characterId: v.character_id, worldBookId: openAttach })
                notification.success({ message: 'Attached' })
                attachForm.resetFields()
              }
            }}
          >
            <Form.Item name="character_id" label="Attach character" rules={[{ required: true }]}>
              <Select
                showSearch
                optionFilterProp="label"
                options={(characters || []).map((c: any) => ({
                  label: c.name,
                  value: c.id,
                  disabled: openAttach ? getAttachedCharacters(openAttach).some((a: any) => a.id === c.id) : false
                }))}
              />
            </Form.Item>
            <Button type="primary" htmlType="submit" className="w-full" loading={attaching}>
              Attach character
            </Button>
          </Form>
        </div>
      </Modal>
    </div>
  )
}

const WorldBookEntryPreview: React.FC<{ worldBookId: number; entryCount: number }> = ({
  worldBookId,
  entryCount
}) => {
  const { data, status } = useQuery({
    queryKey: ["tldw:worldBookPreviewEntries", worldBookId],
    queryFn: async () => {
      await tldwClient.initialize()
      const response = await tldwClient.listWorldBookEntries(worldBookId, false)
      const entries = Array.isArray(response?.entries) ? response.entries : []
      return entries.slice(0, 5)
    }
  })

  if (status === "pending") {
    return <Skeleton active paragraph={{ rows: 2 }} title={false} />
  }

  const previewEntries = Array.isArray(data) ? data : []
  if (previewEntries.length === 0) {
    return <span className="text-sm text-text-muted">No entries available for preview.</span>
  }

  return (
    <div className="space-y-2">
      {previewEntries.map((entry: any) => (
        <div key={entry.entry_id || `${worldBookId}-${String(entry.content || "").slice(0, 10)}`} className="rounded border border-border px-3 py-2">
          <div className="flex flex-wrap gap-1 mb-1">
            {(entry.keywords || []).map((keyword: string) => (
              <Tag key={`${entry.entry_id}-${keyword}`}>{keyword}</Tag>
            ))}
          </div>
          <p className="text-sm line-clamp-2">{entry.content || ""}</p>
        </div>
      ))}
      {entryCount > previewEntries.length && (
        <p className="text-xs text-text-muted">
          Showing {previewEntries.length} of {entryCount} entries.
        </p>
      )}
    </div>
  )
}
