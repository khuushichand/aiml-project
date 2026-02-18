import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { AutoComplete, Button, Collapse, Divider, Drawer, Form, Input, Modal, Skeleton, Switch, Table, Tooltip, Tag, InputNumber, Select, Descriptions, Popover, Slider } from "antd"
import { useTranslation } from "react-i18next"
import React from "react"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { Pen, Trash2, Book, Play, ChevronDown, ChevronUp, AlertCircle, CheckCircle2, AlertTriangle, Loader2, Copy, Plus, Check, X } from "lucide-react"
import { useConfirmDanger } from "@/components/Common/confirm-danger"
import { useServerOnline } from "@/hooks/useServerOnline"
import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import { useAntdNotification } from "@/hooks/useAntdNotification"
import { useUndoNotification } from "@/hooks/useUndoNotification"
import { LabelWithHelp } from "@/components/Common/LabelWithHelp"
import {
  buildDictionaryDeactivationWarning,
  buildDictionaryDeletionConfirmationCopy,
  buildDuplicateDictionaryName,
  compareDictionaryActive,
  compareDictionaryEntryCount,
  compareDictionaryName,
  filterDictionariesBySearch,
  isDictionaryVersionConflictError,
  formatDictionaryUsageLabel,
  formatRelativeTimestamp
} from "./listUtils"
import {
  buildImportConflictRenameSuggestion,
  buildDictionaryImportErrorDescription,
  isDictionaryImportConflictError,
  validateDictionaryImportData
} from "./importValidationUtils"
import {
  buildDictionaryEntryGroupOptions,
  DICTIONARY_ENTRY_COLUMN_RESPONSIVE,
  filterDictionaryEntriesBySearchAndGroup,
} from "./entryListUtils"

export const DictionariesManager: React.FC = () => {
  const { t } = useTranslation(["common", "option"])
  const isOnline = useServerOnline()
  const qc = useQueryClient()
  const notification = useAntdNotification()
  const [open, setOpen] = React.useState(false)
  const [openEdit, setOpenEdit] = React.useState(false)
  const [openEntries, setOpenEntries] = React.useState<null | number>(null)
  const [editId, setEditId] = React.useState<number | null>(null)
  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()
  const [entryForm] = Form.useForm()
  const [openImport, setOpenImport] = React.useState(false)
  const [importFormat, setImportFormat] = React.useState<DictionaryImportFormat>("json")
  const [importMode, setImportMode] = React.useState<DictionaryImportMode>("file")
  const [importSourceContent, setImportSourceContent] = React.useState("")
  const [importMarkdownName, setImportMarkdownName] = React.useState("")
  const [importPreview, setImportPreview] = React.useState<DictionaryImportPreview | null>(null)
  const [importConflictResolution, setImportConflictResolution] = React.useState<{
    preview: DictionaryImportPreview
    suggestedName: string
  } | null>(null)
  const [activateOnImport, setActivateOnImport] = React.useState(false)
  const [importValidationErrors, setImportValidationErrors] = React.useState<string[]>([])
  const [importFileName, setImportFileName] = React.useState<string | null>(null)
  const [statsFor, setStatsFor] = React.useState<any | null>(null)
  const [dictionarySearch, setDictionarySearch] = React.useState("")
  const [activeUpdateMap, setActiveUpdateMap] = React.useState<Record<number, boolean>>({})
  const { capabilities, loading: capsLoading } = useServerCapabilities()
  const confirmDanger = useConfirmDanger()

  // Track validation status per dictionary: { [id]: { status: 'valid' | 'warning' | 'error' | 'loading', message?: string } }
  const [validationStatus, setValidationStatus] = React.useState<Record<number, { status: 'valid' | 'warning' | 'error' | 'loading' | 'unknown'; message?: string }>>({})

  // Validate dictionary on demand
  const validateDictionary = React.useCallback(async (dictId: number) => {
    setValidationStatus(prev => ({ ...prev, [dictId]: { status: 'loading' } }))
    try {
      await tldwClient.initialize()
      const dict = await tldwClient.getDictionary(dictId)
      const entries = await tldwClient.listDictionaryEntries(dictId)
      const entryList = entries?.entries || []

      const payload = {
        data: {
          name: dict?.name || undefined,
          description: dict?.description || undefined,
          entries: entryList.map((entry: any) => ({
            pattern: entry.pattern,
            replacement: entry.replacement,
            type: entry.type,
            probability: entry.probability,
            enabled: entry.enabled,
            case_sensitive: entry.case_sensitive,
            group: entry.group,
            timed_effects: entry.timed_effects,
            max_replacements: entry.max_replacements
          }))
        },
        schema_version: 1,
        strict: false
      }
      const result = await tldwClient.validateDictionary(payload)

      const errors = Array.isArray(result?.errors) ? result.errors : []
      const warnings = Array.isArray(result?.warnings) ? result.warnings : []

      if (errors.length > 0) {
        setValidationStatus(prev => ({ ...prev, [dictId]: { status: 'error', message: `${errors.length} error(s)` } }))
      } else if (warnings.length > 0) {
        setValidationStatus(prev => ({ ...prev, [dictId]: { status: 'warning', message: `${warnings.length} warning(s)` } }))
      } else {
        setValidationStatus(prev => ({ ...prev, [dictId]: { status: 'valid', message: 'Valid' } }))
      }
    } catch (e: any) {
      setValidationStatus(prev => ({ ...prev, [dictId]: { status: 'error', message: e?.message || 'Validation failed' } }))
    }
  }, [])

  const { data, status, error, refetch } = useQuery({
    queryKey: ['tldw:listDictionaries'],
    queryFn: async () => {
      await tldwClient.initialize()
      const res = await tldwClient.listDictionaries(true, true)
      return res?.dictionaries || []
    },
    enabled: isOnline
  })

  const { mutate: createDict, isPending: creating } = useMutation({
    mutationFn: (v: any) => tldwClient.createDictionary(v),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tldw:listDictionaries'] }); setOpen(false); createForm.resetFields() },
    onError: (e: any) => notification.error({ message: 'Error', description: e?.message || 'Failed to create dictionary' })
  })
  const { mutateAsync: updateDict, isPending: updating } = useMutation({
    mutationFn: (v: any) => editId != null ? tldwClient.updateDictionary(editId, v) : Promise.resolve(null),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tldw:listDictionaries'] }); setOpenEdit(false); editForm.resetFields(); setEditId(null) },
  })
  const { mutate: deleteDict } = useMutation({
    mutationFn: (id: number) => tldwClient.deleteDictionary(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tldw:listDictionaries'] })
  })
  const { mutateAsync: importDict, isPending: importing } = useMutation({
    mutationFn: async (payload: {
      format: DictionaryImportFormat
      activate: boolean
      data?: any
      name?: string
      content?: string
    }) => {
      if (payload.format === "json") {
        return await tldwClient.importDictionaryJSON(payload.data, payload.activate)
      }
      return await tldwClient.importDictionaryMarkdown(
        payload.name || "Imported Dictionary",
        payload.content || "",
        payload.activate
      )
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tldw:listDictionaries'] })
      setOpenImport(false)
      setImportValidationErrors([])
      setImportFileName(null)
      setImportSourceContent("")
      setImportPreview(null)
      setImportMarkdownName("")
      setImportFormat("json")
      setImportMode("file")
      setImportConflictResolution(null)
    },
    onError: (e: any) => {
      if (isDictionaryImportConflictError(e)) return
      notification.error({
        message: "Import failed",
        description: buildDictionaryImportErrorDescription(e)
      })
    }
  })

  const { mutateAsync: updateDictionaryActive } = useMutation({
    mutationFn: async ({
      dictionaryId,
      isActive,
      version
    }: {
      dictionaryId: number
      isActive: boolean
      version?: number
    }) => {
      setActiveUpdateMap((prev) => ({ ...prev, [dictionaryId]: true }))
      return await tldwClient.updateDictionary(dictionaryId, {
        is_active: isActive,
        ...(typeof version === "number" ? { version } : {})
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tldw:listDictionaries'] })
    },
    onSettled: (_result, _error, variables) => {
      setActiveUpdateMap((prev) => {
        const next = { ...prev }
        delete next[variables.dictionaryId]
        return next
      })
    }
  })

  const duplicateDictionary = React.useCallback(
    async (dictionary: any) => {
      try {
        const exported = await tldwClient.exportDictionaryJSON(dictionary.id)
        const existingNames = Array.isArray(data) ? data.map((d: any) => d?.name) : []
        const duplicateName = buildDuplicateDictionaryName(
          exported?.name || dictionary?.name || "Dictionary",
          existingNames
        )
        const duplicatePayload = {
          ...exported,
          name: duplicateName,
          description: exported?.description ?? dictionary?.description
        }
        await tldwClient.importDictionaryJSON(duplicatePayload, Boolean(dictionary?.is_active))
        notification.success({ message: "Dictionary duplicated", description: `"${duplicateName}" created.` })
        qc.invalidateQueries({ queryKey: ['tldw:listDictionaries'] })
      } catch (e: any) {
        notification.error({ message: "Duplicate failed", description: e?.message || "Unable to duplicate dictionary" })
      }
    },
    [data, notification, qc]
  )

  const filteredDictionaries = React.useMemo(
    () => filterDictionariesBySearch(Array.isArray(data) ? data : [], dictionarySearch),
    [data, dictionarySearch]
  )
  const activeEntriesDictionary = React.useMemo(() => {
    if (openEntries == null) return null
    return (
      (Array.isArray(data) ? data : []).find(
        (dictionary: any) => Number(dictionary?.id) === Number(openEntries)
      ) || null
    )
  }, [data, openEntries])
  const useMobileEntriesDrawer =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(max-width: 767px)").matches

  const dictionariesById = React.useMemo(() => {
    const map = new Map<number, any>()
    for (const item of Array.isArray(data) ? data : []) {
      const id = Number(item?.id)
      if (!Number.isNaN(id) && id > 0) {
        map.set(id, item)
      }
    }
    return map
  }, [data])

  const confirmDeactivationIfNeeded = React.useCallback(
    async (dictionary: any, nextIsActive: boolean) => {
      if (nextIsActive) return true
      const warning = buildDictionaryDeactivationWarning(
        dictionary,
        t('common:cancel', { defaultValue: 'Cancel' })
      )
      if (!warning) return true
      return await confirmDanger(warning)
    },
    [confirmDanger, t]
  )

  const handleEditSubmit = React.useCallback(async (values: any) => {
    if (editId == null) {
      try {
        await updateDict(values)
      } catch (e: any) {
        notification.error({
          message: "Error",
          description: e?.message || "Failed to update dictionary"
        })
      }
      return
    }
    const dictionary = dictionariesById.get(editId)
    const nextIsActive = typeof values?.is_active === "boolean"
      ? values.is_active
      : Boolean(dictionary?.is_active)
    const confirmed = await confirmDeactivationIfNeeded(dictionary, nextIsActive)
    if (!confirmed) return

    const version = Number(dictionary?.version)
    const payload = {
      ...values,
      ...(Number.isFinite(version) && version > 0 ? { version } : {})
    }

    try {
      await updateDict(payload)
    } catch (e: any) {
      if (!isDictionaryVersionConflictError(e)) {
        notification.error({
          message: "Error",
          description: e?.message || "Failed to update dictionary"
        })
        return
      }

      const shouldReload = await confirmDanger({
        title: "Dictionary changed in another session",
        content:
          "This dictionary was updated elsewhere. Reload the latest version while keeping your current edits?",
        okText: "Reload latest",
        cancelText: t("common:cancel", { defaultValue: "Cancel" })
      })
      if (!shouldReload) return

      try {
        const latest = await tldwClient.getDictionary(editId)
        editForm.setFieldsValue({
          ...latest,
          ...values,
          version: latest?.version
        })
        notification.info({
          message: "Latest version loaded",
          description: "Your edits were preserved. Save again to retry."
        })
        qc.invalidateQueries({ queryKey: ["tldw:listDictionaries"] })
      } catch (reloadError: any) {
        notification.error({
          message: "Reload failed",
          description:
            reloadError?.message ||
            "Could not load the latest dictionary version. Please retry."
        })
      }
    }
  }, [confirmDanger, confirmDeactivationIfNeeded, dictionariesById, editForm, editId, notification, qc, t, updateDict])

  const handleCloseImportModal = React.useCallback(() => {
    setOpenImport(false)
    setImportValidationErrors([])
    setImportFileName(null)
    setImportSourceContent("")
    setImportPreview(null)
    setImportMarkdownName("")
    setImportFormat("json")
    setImportMode("file")
    setImportConflictResolution(null)
  }, [])

  const handleImportFileSelection = React.useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0]
      if (!file) return
      setImportValidationErrors([])
      setImportPreview(null)
      setImportFileName(file.name)

      const loweredName = file.name.toLowerCase()
      if (loweredName.endsWith(".md") || loweredName.endsWith(".markdown")) {
        setImportFormat("markdown")
      } else if (loweredName.endsWith(".json")) {
        setImportFormat("json")
      }

      try {
        const text = await file.text()
        setImportSourceContent(text)
        if (!importMarkdownName.trim()) {
          setImportMarkdownName(extractFileStem(file.name))
        }
      } catch (error: any) {
        setImportValidationErrors([
          error?.message || "Unable to read selected file."
        ])
        setImportSourceContent("")
      } finally {
        event.target.value = ""
      }
    },
    [importMarkdownName]
  )

  const buildImportPreview = React.useCallback(() => {
    setImportValidationErrors([])
    setImportPreview(null)
    setImportConflictResolution(null)
    const trimmedSource = importSourceContent.trim()
    if (!trimmedSource) {
      setImportValidationErrors([
        importMode === "file"
          ? "Select a file before generating an import preview."
          : "Paste dictionary content before generating an import preview."
      ])
      return
    }

    if (importFormat === "json") {
      try {
        const parsed = JSON.parse(trimmedSource)
        const validation = validateDictionaryImportData(parsed)
        if (!validation.valid) {
          setImportValidationErrors(validation.errors)
          return
        }
        setImportPreview({
          format: "json",
          payload: {
            kind: "json",
            data: validation.normalizedData
          },
          summary: buildImportPreviewSummaryFromJSON(validation.normalizedData)
        })
      } catch (error: any) {
        const parseMessage =
          error instanceof Error && error.message
            ? error.message
            : "Unable to parse JSON"
        setImportValidationErrors([
          `Invalid JSON syntax: ${parseMessage}`,
          "Expected top-level fields: `name` and `entries`."
        ])
      }
      return
    }

    const summary = buildImportPreviewSummaryFromMarkdown(
      trimmedSource,
      importMarkdownName
    )
    setImportPreview({
      format: "markdown",
      payload: {
        kind: "markdown",
        name: summary.name,
        content: trimmedSource
      },
      summary
    })
  }, [importFormat, importMarkdownName, importMode, importSourceContent])

  const runImportWithPreview = React.useCallback(
    async (preview: DictionaryImportPreview) => {
      if (preview.payload.kind === "json") {
        return await importDict({
          format: "json",
          data: preview.payload.data,
          activate: activateOnImport
        })
      }
      return await importDict({
        format: "markdown",
        name: preview.payload.name,
        content: preview.payload.content,
        activate: activateOnImport
      })
    },
    [activateOnImport, importDict]
  )

  const handleConfirmImport = React.useCallback(async () => {
    if (!importPreview) return
    try {
      await runImportWithPreview(importPreview)
    } catch (error: any) {
      if (!isDictionaryImportConflictError(error)) {
        return
      }
      const existingNames = (Array.isArray(data) ? data : []).map(
        (dictionary: any) => dictionary?.name
      )
      const suggestedName = buildImportConflictRenameSuggestion(
        importPreview.summary.name,
        existingNames
      )
      setImportConflictResolution({
        preview: importPreview,
        suggestedName
      })
    }
  }, [data, importPreview, runImportWithPreview])

  const resolveImportConflictRename = React.useCallback(async () => {
    if (!importConflictResolution) return
    const renamedPreview: DictionaryImportPreview = {
      ...importConflictResolution.preview,
      summary: {
        ...importConflictResolution.preview.summary,
        name: importConflictResolution.suggestedName
      },
      payload:
        importConflictResolution.preview.payload.kind === "json"
          ? {
              kind: "json",
              data: {
                ...importConflictResolution.preview.payload.data,
                name: importConflictResolution.suggestedName
              }
            }
          : {
              kind: "markdown",
              name: importConflictResolution.suggestedName,
              content: importConflictResolution.preview.payload.content
            }
    }

    try {
      await runImportWithPreview(renamedPreview)
    } catch {
      // handled by mutation onError
      return
    }
    setImportConflictResolution(null)
  }, [importConflictResolution, runImportWithPreview])

  const resolveImportConflictReplace = React.useCallback(async () => {
    if (!importConflictResolution) return
    const targetName = importConflictResolution.preview.summary.name
    const targetDictionary = (Array.isArray(data) ? data : []).find(
      (dictionary: any) =>
        String(dictionary?.name || "").trim().toLowerCase() ===
        targetName.trim().toLowerCase()
    )

    if (!targetDictionary?.id) {
      notification.error({
        message: "Replace unavailable",
        description: "Could not find the conflicting dictionary to replace."
      })
      return
    }

    const confirmed = await confirmDanger({
      title: "Replace existing dictionary?",
      content: `Delete "${targetName}" and import the new version?`,
      okText: "Replace existing",
      cancelText: t("common:cancel", { defaultValue: "Cancel" })
    })
    if (!confirmed) return

    try {
      await tldwClient.deleteDictionary(Number(targetDictionary.id))
      await runImportWithPreview(importConflictResolution.preview)
      setImportConflictResolution(null)
      qc.invalidateQueries({ queryKey: ["tldw:listDictionaries"] })
    } catch (error: any) {
      notification.error({
        message: "Replace failed",
        description:
          error?.message || "Unable to replace existing dictionary."
      })
    }
  }, [confirmDanger, data, importConflictResolution, notification, qc, runImportWithPreview, t])

  const dictionariesUnsupported =
    !capsLoading && capabilities && !capabilities.hasChatDictionaries

  const columns = [
    {
      title: '',
      key: 'icon',
      width: 48,
      render: () => <Book className="w-5 h-5 text-text-muted" aria-hidden="true" />
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      sorter: (a: any, b: any) => compareDictionaryName(a, b)
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      render: (v: string) => <span className="line-clamp-1">{v}</span>
    },
    {
      title: 'Active',
      dataIndex: 'is_active',
      key: 'is_active',
      sorter: (a: any, b: any) => compareDictionaryActive(a, b),
      filters: [
        { text: 'Active', value: true },
        { text: 'Inactive', value: false }
      ],
      onFilter: (value: any, record: any) => {
        const activeFilter = value === true || value === 'true'
        return Boolean(record.is_active) === activeFilter
      },
      render: (v: boolean, record: any) => (
        <Switch
          checked={Boolean(v)}
          loading={Boolean(activeUpdateMap[record.id])}
          onChange={async (checked) => {
            const confirmed = await confirmDeactivationIfNeeded(record, checked)
            if (!confirmed) return

            const dictionaryId = Number(record.id)
            const version = Number(record?.version)
            try {
              await updateDictionaryActive({
                dictionaryId,
                isActive: checked,
                version: Number.isFinite(version) && version > 0 ? version : undefined
              })
            } catch (e: any) {
              if (isDictionaryVersionConflictError(e)) {
                const shouldReload = await confirmDanger({
                  title: "Dictionary changed in another session",
                  content:
                    "This dictionary was updated elsewhere. Reload the latest dictionary list and try again.",
                  okText: "Reload",
                  cancelText: t("common:cancel", { defaultValue: "Cancel" })
                })
                if (shouldReload) {
                  qc.invalidateQueries({ queryKey: ["tldw:listDictionaries"] })
                }
                return
              }
              notification.error({
                message: "Update failed",
                description:
                  e?.message || "Failed to update dictionary status. Please retry."
              })
            }
          }}
          aria-label={`Set dictionary ${record.name} ${v ? "inactive" : "active"}`}
        />
      )
    },
    {
      title: 'Entries',
      dataIndex: 'entry_count',
      key: 'entry_count',
      sorter: (a: any, b: any) => compareDictionaryEntryCount(a, b),
      render: (_value: number, record: any) => {
        const entryCount = Number(record?.entry_count || 0)
        const regexCount = Number(record?.regex_entry_count ?? record?.regex_entries ?? 0)
        if (regexCount > 0) {
          return `${entryCount} entries (${regexCount} regex)`
        }
        return `${entryCount} entries`
      }
    },
    {
      title: 'Used by',
      dataIndex: 'used_by_chat_count',
      key: 'used_by_chat_count',
      sorter: (a: any, b: any) => Number(a?.used_by_chat_count || 0) - Number(b?.used_by_chat_count || 0),
      render: (_value: number, record: any) => {
        const totalChats = Number(record?.used_by_chat_count || 0)
        const chatRefs = Array.isArray(record?.used_by_chat_refs) ? record.used_by_chat_refs : []

        if (totalChats <= 0) {
          return <span className="text-xs text-text-muted">—</span>
        }

        const label = formatDictionaryUsageLabel(record)
        if (chatRefs.length === 0) {
          return <span className="text-xs">{label}</span>
        }

        return (
          <Tooltip
            title={
              <div className="space-y-1">
                {chatRefs.map((chat: any) => {
                  const chatId = String(chat?.chat_id || '')
                  const shortId = chatId.length > 8 ? chatId.slice(0, 8) : chatId
                  const title = String(chat?.title || '').trim() || `Chat ${shortId}`
                  const state = String(chat?.state || 'in-progress')
                  return (
                    <div key={chatId || `${title}-${state}`} className="text-xs">
                      {title} <span className="text-text-muted">({state})</span>
                    </div>
                  )
                })}
              </div>
            }
          >
            <span className="text-xs underline decoration-dotted cursor-help">{label}</span>
          </Tooltip>
        )
      }
    },
    {
      title: 'Updated',
      dataIndex: 'updated_at',
      key: 'updated_at',
      sorter: (a: any, b: any) => {
        const valueA = new Date(a?.updated_at || 0).getTime()
        const valueB = new Date(b?.updated_at || 0).getTime()
        return valueA - valueB
      },
      render: (value: string | null | undefined) => {
        const relative = formatRelativeTimestamp(value)
        const absolute = value ? new Date(value).toLocaleString() : 'No updates yet'
        return (
          <Tooltip title={absolute}>
            <span className="text-xs text-text-muted">{relative}</span>
          </Tooltip>
        )
      }
    },
    {
      title: 'Status',
      key: 'validation_status',
      width: 100,
      render: (_: any, record: any) => {
        const status = validationStatus[record.id]
        if (!status) {
          return (
            <Tooltip title="Click to validate">
              <button
                className="min-w-[36px] min-h-[36px] flex items-center justify-center text-text-muted hover:text-text hover:bg-surface2 rounded-md transition-colors"
                onClick={() => validateDictionary(record.id)}
                aria-label={`Validate dictionary ${record.name}`}
              >
                <CheckCircle2 className="w-4 h-4 opacity-30" />
              </button>
            </Tooltip>
          )
        }
        if (status.status === 'loading') {
          return (
            <Tooltip title="Validating...">
              <Loader2 className="w-4 h-4 animate-spin text-text-muted" />
            </Tooltip>
          )
        }
        if (status.status === 'valid') {
          return (
            <Tooltip title={status.message || 'Valid'}>
              <button
                className="min-w-[36px] min-h-[36px] flex items-center justify-center text-success hover:bg-success/10 rounded-md transition-colors"
                onClick={() => validateDictionary(record.id)}
                aria-label={`Dictionary ${record.name} is valid. Click to re-validate.`}
              >
                <CheckCircle2 className="w-4 h-4" />
              </button>
            </Tooltip>
          )
        }
        if (status.status === 'warning') {
          return (
            <Tooltip title={status.message || 'Has warnings'}>
              <button
                className="min-w-[36px] min-h-[36px] flex items-center justify-center text-warn hover:bg-warn/10 rounded-md transition-colors"
                onClick={() => validateDictionary(record.id)}
                aria-label={`Dictionary ${record.name} has warnings. Click to re-validate.`}
              >
                <AlertTriangle className="w-4 h-4" />
              </button>
            </Tooltip>
          )
        }
        // error
        return (
          <Tooltip title={status.message || 'Has errors'}>
            <button
              className="min-w-[36px] min-h-[36px] flex items-center justify-center text-danger hover:bg-danger/10 rounded-md transition-colors"
              onClick={() => validateDictionary(record.id)}
              aria-label={`Dictionary ${record.name} has errors. Click to re-validate.`}
            >
              <AlertCircle className="w-4 h-4" />
            </button>
          </Tooltip>
        )
      }
    },
    { title: 'Actions', key: 'actions', render: (_: any, record: any) => (
      <div className="flex gap-1 flex-wrap items-center">
        <Tooltip title="Edit dictionary">
          <button
            className="min-w-[44px] min-h-[44px] flex items-center justify-center text-text-muted hover:text-text hover:bg-surface2 rounded-md transition-colors"
            onClick={() => { setEditId(record.id); editForm.setFieldsValue(record); setOpenEdit(true) }}
            aria-label={`Edit dictionary ${record.name}`}
          >
            <Pen className="w-5 h-5" />
          </button>
        </Tooltip>
        <Tooltip title="Manage entries">
          <button
            className="min-w-[44px] min-h-[44px] px-2 flex items-center justify-center text-text-muted hover:text-text hover:bg-surface2 rounded-md transition-colors text-sm"
            onClick={() => setOpenEntries(record.id)}
            aria-label={`Manage entries for ${record.name}`}
          >
            Entries
          </button>
        </Tooltip>
        <Tooltip title="Export as JSON">
          <button
            className="min-w-[44px] min-h-[44px] px-2 flex items-center justify-center text-text-muted hover:text-text hover:bg-surface2 rounded-md transition-colors text-sm"
            onClick={async () => {
              try {
                const exp = await tldwClient.exportDictionaryJSON(record.id)
                const blob = new Blob([JSON.stringify(exp, null, 2)], { type: 'application/json' })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `${record.name || 'dictionary'}.json`
                a.click()
                URL.revokeObjectURL(url)
              } catch (e: any) {
                notification.error({ message: 'Export failed', description: e?.message })
              }
            }}
            aria-label={`Export ${record.name} as JSON`}
          >
            JSON
          </button>
        </Tooltip>
        <Tooltip title="Export as Markdown">
          <button
            className="min-w-[44px] min-h-[44px] px-2 flex items-center justify-center text-text-muted hover:text-text hover:bg-surface2 rounded-md transition-colors text-sm"
            onClick={async () => {
              try {
                const fullExport = await tldwClient.exportDictionaryJSON(record.id)
                const exportedEntries = Array.isArray(fullExport?.entries) ? fullExport.entries : []
                if (hasAdvancedDictionaryEntryFields(exportedEntries)) {
                  const proceed = await confirmDanger({
                    title: "Markdown export may lose advanced settings",
                    content:
                      "This dictionary includes advanced entry settings (for example probability, timed effects, or replacement limits). Export JSON for full fidelity.",
                    okText: "Export Markdown anyway",
                    cancelText: t("common:cancel", { defaultValue: "Cancel" })
                  })
                  if (!proceed) return
                }

                const exp = await tldwClient.exportDictionaryMarkdown(record.id)
                const blob = new Blob([exp?.content || '' ], { type: 'text/markdown' })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `${record.name || 'dictionary'}.md`
                a.click()
                URL.revokeObjectURL(url)
              } catch (e: any) {
                notification.error({ message: 'Export failed', description: e?.message })
              }
            }}
            aria-label={`Export ${record.name} as Markdown`}
          >
            MD
          </button>
        </Tooltip>
        <Tooltip title="View statistics">
          <button
            className="min-w-[44px] min-h-[44px] px-2 flex items-center justify-center text-text-muted hover:text-text hover:bg-surface2 rounded-md transition-colors text-sm"
            onClick={async () => {
              try {
                const s = await tldwClient.dictionaryStatistics(record.id)
                setStatsFor(s)
              } catch (e: any) {
                notification.error({ message: 'Stats failed', description: e?.message })
              }
            }}
            aria-label={`View statistics for ${record.name}`}
          >
            Stats
          </button>
        </Tooltip>
        <Tooltip title="Duplicate dictionary">
          <button
            className="min-w-[44px] min-h-[44px] flex items-center justify-center text-text-muted hover:text-text hover:bg-surface2 rounded-md transition-colors"
            onClick={() => duplicateDictionary(record)}
            aria-label={`Duplicate dictionary ${record.name}`}
          >
            <Copy className="w-5 h-5" />
          </button>
        </Tooltip>
        <Tooltip title="Delete dictionary">
          <button
            className="min-w-[44px] min-h-[44px] flex items-center justify-center text-danger hover:bg-danger/10 rounded-md transition-colors"
            onClick={async () => {
              const confirmationCopy = buildDictionaryDeletionConfirmationCopy(record)
              const ok = await confirmDanger({
                title: t('common:confirmTitle', { defaultValue: 'Please confirm' }),
                content: confirmationCopy,
                okText: t('common:delete', { defaultValue: 'Delete' }),
                cancelText: t('common:cancel', { defaultValue: 'Cancel' })
              })
              if (ok) deleteDict(record.id)
            }}
            aria-label={`Delete dictionary ${record.name}`}
          >
            <Trash2 className="w-5 h-5" />
          </button>
        </Tooltip>
      </div>
    )}
  ]

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <Input
          value={dictionarySearch}
          onChange={(e) => setDictionarySearch(e.target.value)}
          allowClear
          className="sm:max-w-md"
          placeholder="Search dictionaries by name or description"
          aria-label="Search dictionaries"
        />
        <div className="flex justify-end gap-2">
          <Button onClick={() => setOpenImport(true)}>Import</Button>
          <Button type="primary" icon={<Plus className="w-4 h-4" />} onClick={() => setOpen(true)}>
            New Dictionary
          </Button>
        </div>
      </div>
      {status === 'pending' && <Skeleton active paragraph={{ rows: 6 }} />}
      {status === 'success' && dictionariesUnsupported && (
        <FeatureEmptyState
          title={t("option:dictionaries.offlineTitle", {
            defaultValue: "Chat dictionaries API not available on this server"
          })}
          description={t("option:dictionaries.offlineDescription", {
            defaultValue:
              "This tldw server does not advertise the /api/v1/chat/dictionaries endpoints. Upgrade your server to a version that includes chat dictionaries to use this workspace."
          })}
          primaryActionLabel={t("settings:healthSummary.diagnostics", {
            defaultValue: "Health & diagnostics"
          })}
          onPrimaryAction={() => {
            try {
              window.location.hash = "#/settings/health"
            } catch {}
          }}
        />
      )}
      {status === 'success' && !dictionariesUnsupported && (
        Array.isArray(data) && data.length === 0 ? (
          <FeatureEmptyState
            title="No dictionaries yet"
            description="Create your first dictionary to transform text consistently across chats."
            examples={[
              "Medical abbreviations (e.g., BP -> blood pressure)",
              "Custom terminology (e.g., internal product names)",
              "Roleplay language style mappings",
            ]}
            primaryActionLabel="Create your first dictionary"
            onPrimaryAction={() => setOpen(true)}
            secondaryActionLabel="Import dictionary"
            onSecondaryAction={() => setOpenImport(true)}
          />
        ) : (
        <Table
          rowKey={(r: any) => r.id}
          dataSource={filteredDictionaries}
          columns={columns as any}
          pagination={{
            pageSize: 20,
            showSizeChanger: true,
            pageSizeOptions: [10, 20, 50, 100],
            showTotal: (total, range) => `${range[0]}-${range[1]} of ${total}`
          }}
        />
        )
      )}
      {status === 'error' && !dictionariesUnsupported && (
        <FeatureEmptyState
          title="Unable to load dictionaries"
          description={
            error instanceof Error
              ? `Could not load dictionaries: ${error.message}`
              : "Could not load dictionaries right now. Check your server connection and try again."
          }
          primaryActionLabel="Retry"
          onPrimaryAction={() => void refetch()}
          secondaryActionLabel="Import dictionary"
          onSecondaryAction={() => setOpenImport(true)}
        />
      )}

      <Modal title="Create Dictionary" open={open} onCancel={() => setOpen(false)} footer={null}>
        <Form layout="vertical" form={createForm} onFinish={(v) => createDict(v)}>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="description" label="Description"><Input /></Form.Item>
          <Button type="primary" htmlType="submit" loading={creating} className="w-full">Create</Button>
        </Form>
      </Modal>

      <Modal title="Edit Dictionary" open={openEdit} onCancel={() => setOpenEdit(false)} footer={null}>
        <Form layout="vertical" form={editForm} onFinish={handleEditSubmit}>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="description" label="Description"><Input /></Form.Item>
          <Form.Item name="is_active" label="Active" valuePropName="checked"><Switch /></Form.Item>
          <Button type="primary" htmlType="submit" loading={updating} className="w-full">Save</Button>
        </Form>
      </Modal>

      <Drawer
        title={
          activeEntriesDictionary?.name
            ? `Manage Entries: ${activeEntriesDictionary.name}`
            : "Manage Entries"
        }
        open={!!openEntries}
        onClose={() => setOpenEntries(null)}
        placement="right"
        destroyOnClose
        size={useMobileEntriesDrawer ? "100vw" : 1040}
      >
        {openEntries && <DictionaryEntryManager dictionaryId={openEntries} form={entryForm} />}
      </Drawer>
      <Modal title="Import Dictionary" open={openImport} onCancel={handleCloseImportModal} footer={null}>
        <div className="space-y-3">
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="space-y-1">
              <div className="text-xs font-medium text-text">Format</div>
              <Select
                value={importFormat}
                onChange={(value) => {
                  setImportFormat(value as DictionaryImportFormat)
                  setImportPreview(null)
                  setImportValidationErrors([])
                }}
                options={[
                  { label: "JSON (full fidelity)", value: "json" },
                  { label: "Markdown", value: "markdown" }
                ]}
              />
            </div>
            <div className="space-y-1">
              <div className="text-xs font-medium text-text">Source</div>
              <Select
                value={importMode}
                onChange={(value) => {
                  setImportMode(value as DictionaryImportMode)
                  setImportPreview(null)
                  setImportValidationErrors([])
                }}
                options={[
                  { label: "File upload", value: "file" },
                  { label: "Paste content", value: "paste" }
                ]}
              />
            </div>
          </div>

          {importMode === "file" ? (
            <div className="space-y-2">
              <input
                type="file"
                accept={
                  importFormat === "markdown"
                    ? ".md,.markdown,text/markdown,text/plain"
                    : "application/json,.json"
                }
                onChange={handleImportFileSelection}
              />
              {importFileName && (
                <p className="text-xs text-text-muted">Selected: {importFileName}</p>
              )}
            </div>
          ) : (
            <Input.TextArea
              rows={6}
              value={importSourceContent}
              onChange={(event) => {
                setImportSourceContent(event.target.value)
                setImportPreview(null)
                setImportValidationErrors([])
              }}
              placeholder={
                importFormat === "markdown"
                  ? "Paste markdown dictionary content..."
                  : "Paste JSON dictionary content..."
              }
            />
          )}

          {importFormat === "markdown" && (
            <div className="space-y-1">
              <div className="text-xs font-medium text-text">Dictionary name</div>
              <Input
                value={importMarkdownName}
                onChange={(event) => setImportMarkdownName(event.target.value)}
                placeholder="Optional (defaults to markdown heading or file name)"
              />
            </div>
          )}

          <label className="inline-flex items-center gap-2 text-sm"><input type="checkbox" checked={activateOnImport} onChange={(ev) => setActivateOnImport(ev.target.checked)} /> Activate after import</label>
          <Button onClick={buildImportPreview} disabled={!importSourceContent.trim()}>
            Preview import
          </Button>
          {importValidationErrors.length > 0 && (
            <div className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2">
              <p className="text-sm font-medium text-danger">
                Unable to import this file. Fix the following and retry:
              </p>
              <ul className="mt-1 list-disc pl-4 text-xs text-danger/90 space-y-1">
                {importValidationErrors.map((issue, index) => (
                  <li key={`${issue}-${index}`}>{issue}</li>
                ))}
              </ul>
            </div>
          )}
          {importPreview && (
            <div className="space-y-2 rounded-md border border-border bg-surface2/40 px-3 py-2">
              <div className="text-sm font-medium text-text">Import preview</div>
              <Descriptions size="small" bordered column={1}>
                <Descriptions.Item label="Format">
                  {importPreview.format === "json" ? "JSON" : "Markdown"}
                </Descriptions.Item>
                <Descriptions.Item label="Dictionary name">
                  {importPreview.summary.name}
                </Descriptions.Item>
                <Descriptions.Item label="Entries">
                  {importPreview.summary.entryCount}
                </Descriptions.Item>
                <Descriptions.Item label="Groups">
                  {importPreview.summary.groups.length > 0
                    ? importPreview.summary.groups.join(", ")
                    : "—"}
                </Descriptions.Item>
                <Descriptions.Item label="Advanced fields">
                  {importPreview.summary.hasAdvancedFields ? "Detected" : "Not detected"}
                </Descriptions.Item>
              </Descriptions>
              <Button type="primary" onClick={() => void handleConfirmImport()} loading={importing}>
                Confirm import
              </Button>
            </div>
          )}
          {importing && (
            <p className="text-xs text-text-muted">Importing dictionary...</p>
          )}
        </div>
      </Modal>
      <Modal
        title="Dictionary name conflict"
        open={!!importConflictResolution}
        onCancel={() => setImportConflictResolution(null)}
        footer={null}
      >
        {importConflictResolution && (
          <div className="space-y-3">
            <p className="text-sm text-text">
              A dictionary named{" "}
              <span className="font-medium">
                {importConflictResolution.preview.summary.name}
              </span>{" "}
              already exists.
            </p>
            <div className="space-y-2">
              <Button
                type="primary"
                onClick={() => void resolveImportConflictRename()}
                loading={importing}
                block
              >
                Rename to "{importConflictResolution.suggestedName}"
              </Button>
              <Button
                danger
                onClick={() => void resolveImportConflictReplace()}
                loading={importing}
                block
              >
                Replace existing
              </Button>
              <Button onClick={() => setImportConflictResolution(null)} block>
                Cancel
              </Button>
            </div>
          </div>
        )}
      </Modal>
      <Modal title="Dictionary Statistics" open={!!statsFor} onCancel={() => setStatsFor(null)} footer={null}>
        {statsFor && (
          <Descriptions size="small" bordered column={1}>
            <Descriptions.Item label="ID">{statsFor.dictionary_id}</Descriptions.Item>
            <Descriptions.Item label="Name">{statsFor.name}</Descriptions.Item>
            <Descriptions.Item label="Total Entries">{statsFor.total_entries}</Descriptions.Item>
            <Descriptions.Item label="Regex Entries">{statsFor.regex_entries}</Descriptions.Item>
            <Descriptions.Item label="Literal Entries">{statsFor.literal_entries}</Descriptions.Item>
            <Descriptions.Item label="Groups">{(statsFor.groups||[]).join(', ')}</Descriptions.Item>
            <Descriptions.Item label="Average Probability">{statsFor.average_probability}</Descriptions.Item>
            <Descriptions.Item label="Total Usage Count">{statsFor.total_usage_count}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  )
}

/** Validates regex pattern and returns error message or null if valid */
function validateRegexPattern(pattern: string): string | null {
  if (!pattern) return null
  try {
    // Check if it looks like a regex pattern (starts and ends with /)
    const regexMatch = pattern.match(/^\/(.*)\/([gimsuvy]*)$/)
    if (regexMatch) {
      new RegExp(regexMatch[1], regexMatch[2])
    } else {
      // Try as plain regex
      new RegExp(pattern)
    }
    return null
  } catch (e: any) {
    return e.message || "Invalid regex pattern"
  }
}

type InlineEditableEntryField = "pattern" | "replacement"

function toSafeNonNegativeInteger(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    return 0
  }
  return Math.floor(value)
}

function buildTimedEffectsPayload(
  source: unknown,
  options: { forceObject?: boolean } = {}
): { sticky: number; cooldown: number; delay: number } | undefined {
  const forceObject = options.forceObject === true
  const raw =
    source && typeof source === "object"
      ? (source as Record<string, unknown>)
      : null

  if (!raw && !forceObject) {
    return undefined
  }

  const sticky = toSafeNonNegativeInteger(raw?.sticky)
  const cooldown = toSafeNonNegativeInteger(raw?.cooldown)
  const delay = toSafeNonNegativeInteger(raw?.delay)

  if (!forceObject) {
    const hasInput = Boolean(raw) && ["sticky", "cooldown", "delay"].some((key) => {
      const value = raw?.[key]
      return value !== null && value !== undefined && value !== ""
    })
    if (!hasInput) {
      return undefined
    }
  }

  return {
    sticky,
    cooldown,
    delay
  }
}

function normalizeProbabilityValue(value: unknown, fallback = 1): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return fallback
  }
  return Math.min(1, Math.max(0, value))
}

function formatProbabilityFrequencyHint(value: unknown): string {
  const normalizedValue = normalizeProbabilityValue(value, 1)
  const percent = Math.round(normalizedValue * 100)
  const outOfTen = Math.round(normalizedValue * 10)
  return `Fires ~${outOfTen} out of 10 messages (${percent}%).`
}

type TextDiffSegment = {
  type: "unchanged" | "removed" | "added"
  text: string
}

function tokenizeDiffText(source: string): string[] {
  return source.split(/(\s+)/).filter((token) => token.length > 0)
}

function appendDiffSegment(
  segments: TextDiffSegment[],
  type: TextDiffSegment["type"],
  text: string
) {
  if (!text) return
  const previous = segments[segments.length - 1]
  if (previous && previous.type === type) {
    previous.text += text
    return
  }
  segments.push({ type, text })
}

function buildTextDiffSegments(
  originalText: string,
  processedText: string
): TextDiffSegment[] {
  const originalTokens = tokenizeDiffText(originalText)
  const processedTokens = tokenizeDiffText(processedText)
  const originalLength = originalTokens.length
  const processedLength = processedTokens.length

  if (originalLength === 0 && processedLength === 0) {
    return []
  }

  const lcs: number[][] = Array.from({ length: originalLength + 1 }, () =>
    Array(processedLength + 1).fill(0)
  )

  for (let originalIndex = originalLength - 1; originalIndex >= 0; originalIndex -= 1) {
    for (let processedIndex = processedLength - 1; processedIndex >= 0; processedIndex -= 1) {
      if (originalTokens[originalIndex] === processedTokens[processedIndex]) {
        lcs[originalIndex][processedIndex] = lcs[originalIndex + 1][processedIndex + 1] + 1
      } else {
        lcs[originalIndex][processedIndex] = Math.max(
          lcs[originalIndex + 1][processedIndex],
          lcs[originalIndex][processedIndex + 1]
        )
      }
    }
  }

  const segments: TextDiffSegment[] = []
  let originalIndex = 0
  let processedIndex = 0

  while (originalIndex < originalLength && processedIndex < processedLength) {
    if (originalTokens[originalIndex] === processedTokens[processedIndex]) {
      appendDiffSegment(segments, "unchanged", originalTokens[originalIndex])
      originalIndex += 1
      processedIndex += 1
      continue
    }

    if (lcs[originalIndex + 1][processedIndex] >= lcs[originalIndex][processedIndex + 1]) {
      appendDiffSegment(segments, "removed", originalTokens[originalIndex])
      originalIndex += 1
      continue
    }

    appendDiffSegment(segments, "added", processedTokens[processedIndex])
    processedIndex += 1
  }

  while (originalIndex < originalLength) {
    appendDiffSegment(segments, "removed", originalTokens[originalIndex])
    originalIndex += 1
  }
  while (processedIndex < processedLength) {
    appendDiffSegment(segments, "added", processedTokens[processedIndex])
    processedIndex += 1
  }

  return segments
}

type DictionaryImportFormat = "json" | "markdown"
type DictionaryImportMode = "file" | "paste"

type DictionaryImportPreview = {
  format: DictionaryImportFormat
  payload:
    | { kind: "json"; data: any }
    | { kind: "markdown"; name: string; content: string }
  summary: {
    name: string
    entryCount: number
    groups: string[]
    hasAdvancedFields: boolean
  }
}

function extractFileStem(fileName: string): string {
  const trimmed = fileName.trim()
  if (!trimmed) return "Imported Dictionary"
  const dotIndex = trimmed.lastIndexOf(".")
  if (dotIndex <= 0) return trimmed
  return trimmed.slice(0, dotIndex)
}

function buildImportPreviewSummaryFromJSON(data: any) {
  const normalizedName = String(data?.name || "Imported Dictionary").trim() || "Imported Dictionary"
  const entries = Array.isArray(data?.entries) ? data.entries : []
  const groups = Array.from(
    new Set(
      entries
        .map((entry: any) => (typeof entry?.group === "string" ? entry.group.trim() : ""))
        .filter((group: string) => group.length > 0)
    )
  )
  const hasAdvancedFields = hasAdvancedDictionaryEntryFields(entries)

  return {
    name: normalizedName,
    entryCount: entries.length,
    groups,
    hasAdvancedFields
  }
}

function hasAdvancedDictionaryEntryFields(entries: any[]): boolean {
  return entries.some((entry: any) => {
    const probability = typeof entry?.probability === "number" ? entry.probability : 1
    const caseSensitive = typeof entry?.case_sensitive === "boolean" ? entry.case_sensitive : undefined
    const maxReplacements =
      Number.isInteger(entry?.max_replacements) && entry.max_replacements > 0
    const timedEffects =
      entry?.timed_effects &&
      typeof entry.timed_effects === "object" &&
      ["sticky", "cooldown", "delay"].some((key) => {
        const value = Number((entry.timed_effects as any)?.[key])
        return Number.isFinite(value) && value > 0
      })
    return probability !== 1 || maxReplacements || timedEffects || caseSensitive === false
  })
}

function buildImportPreviewSummaryFromMarkdown(content: string, fallbackName?: string) {
  const headingMatch = content.match(/^#\s+(.+)$/m)
  const detectedName = headingMatch?.[1]?.trim()
  const fallback = fallbackName?.trim()
  const name = detectedName || fallback || "Imported Dictionary"
  const entryMatches = content.match(/^##\s*Entry:/gm)
  const legacyEntryMatches = content
    .split("\n")
    .filter((line) => {
      const trimmed = line.trim()
      if (!trimmed || trimmed.startsWith("#")) return false
      return trimmed.includes(":")
    })
  const groups = Array.from(
    new Set(
      Array.from(content.matchAll(/^##\s+(?!Entry:)(.+)$/gm))
        .map((match) => match[1]?.trim())
        .filter((group): group is string => Boolean(group))
    )
  )
  const hasAdvancedFields =
    /-\s+\*\*(Probability|Type|Enabled)\*\*:/.test(content) ||
    /\/.+\/[gimsuvy]*/.test(content)

  return {
    name,
    entryCount: entryMatches ? entryMatches.length : legacyEntryMatches.length,
    groups,
    hasAdvancedFields
  }
}

function extractRegexSafetyMessage(validationReport: any): string | null {
  const errors = Array.isArray(validationReport?.errors)
    ? validationReport.errors
    : []

  if (errors.length === 0) {
    return null
  }

  const regexIssue = errors.find((issue: any) => {
    const code = String(issue?.code || "").toLowerCase()
    const field = String(issue?.field || "").toLowerCase()
    const message = String(issue?.message || "").toLowerCase()
    return (
      code.startsWith("regex_") ||
      field.endsWith(".pattern") ||
      message.includes("regex")
    )
  })

  if (regexIssue?.message) {
    return String(regexIssue.message)
  }

  const firstError = errors[0]
  if (firstError?.message) {
    return String(firstError.message)
  }

  return "Regex pattern failed server validation."
}

function buildRestorableDictionaryEntryPayload(entry: any): Record<string, any> {
  const payload: Record<string, any> = {
    pattern: typeof entry?.pattern === "string" ? entry.pattern : "",
    replacement: typeof entry?.replacement === "string" ? entry.replacement : "",
    type: entry?.type === "regex" ? "regex" : "literal",
    enabled: typeof entry?.enabled === "boolean" ? entry.enabled : true,
    case_sensitive:
      typeof entry?.case_sensitive === "boolean" ? entry.case_sensitive : true,
    probability:
      typeof entry?.probability === "number" && Number.isFinite(entry.probability)
        ? Math.min(1, Math.max(0, entry.probability))
        : 1,
    max_replacements:
      Number.isInteger(entry?.max_replacements) && entry.max_replacements >= 0
        ? entry.max_replacements
        : 0
  }
  if (typeof entry?.group === "string" && entry.group.trim()) {
    payload.group = entry.group
  }
  if (entry?.timed_effects && typeof entry.timed_effects === "object") {
    payload.timed_effects = entry.timed_effects
  }
  return payload
}

const DictionaryEntryManager: React.FC<{ dictionaryId: number; form: any }> = ({
  dictionaryId,
  form
}) => {
  const { t } = useTranslation(["common", "option"])
  const qc = useQueryClient()
  const confirmDanger = useConfirmDanger()
  const notification = useAntdNotification()
  const { showUndoNotification } = useUndoNotification()
  const [validationStrict, setValidationStrict] = React.useState(false)
  const [validationReport, setValidationReport] = React.useState<any | null>(null)
  const [validationError, setValidationError] = React.useState<string | null>(null)
  const [previewText, setPreviewText] = React.useState("")
  const [previewTokenBudget, setPreviewTokenBudget] = React.useState<number | null>(1000)
  const [previewMaxIterations, setPreviewMaxIterations] = React.useState<number | null>(5)
  const [previewResult, setPreviewResult] = React.useState<any | null>(null)
  const [previewError, setPreviewError] = React.useState<string | null>(null)
  const [savedPreviewCases, setSavedPreviewCases] = React.useState<
    Array<{ id: string; name: string; text: string }>
  >([])
  const [previewCaseName, setPreviewCaseName] = React.useState("")
  const [previewCaseError, setPreviewCaseError] = React.useState<string | null>(null)
  const [toolsPanelKeys, setToolsPanelKeys] = React.useState<string[]>([])
  const [highlightedValidationEntryId, setHighlightedValidationEntryId] = React.useState<number | null>(null)
  const [entrySearch, setEntrySearch] = React.useState("")
  const [entryGroupFilter, setEntryGroupFilter] = React.useState<string | undefined>(undefined)

  // Simple/Advanced mode toggle
  const [advancedMode, setAdvancedMode] = React.useState(false)

  // Inline regex validation state
  const [regexError, setRegexError] = React.useState<string | null>(null)
  const [regexServerError, setRegexServerError] = React.useState<string | null>(null)
  const [inlineEdit, setInlineEdit] = React.useState<{
    entryId: number
    field: InlineEditableEntryField
    value: string
    initialValue: string
  } | null>(null)
  const [inlineEditError, setInlineEditError] = React.useState<string | null>(null)
  const [inlineEditSaving, setInlineEditSaving] = React.useState(false)

  // Entry editing state
  const [editingEntry, setEditingEntry] = React.useState<any | null>(null)
  const [editEntryForm] = Form.useForm()

  // Inline test popover state
  const [testingEntryId, setTestingEntryId] = React.useState<number | null>(null)
  const [inlineTestInput, setInlineTestInput] = React.useState("")
  const [inlineTestResult, setInlineTestResult] = React.useState<string | null>(null)
  const [selectedEntryRowKeys, setSelectedEntryRowKeys] = React.useState<
    React.Key[]
  >([])
  const [bulkGroupName, setBulkGroupName] = React.useState("")
  const [bulkEntryAction, setBulkEntryAction] = React.useState<
    null | "activate" | "deactivate" | "delete" | "group"
  >(null)
  const [reorderBusyEntryId, setReorderBusyEntryId] = React.useState<number | null>(
    null
  )
  const validationRowHighlightTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(
    null
  )
  const previewDraftStorageKey = React.useMemo(
    () => `tldw:dictionaries:preview-draft:${dictionaryId}`,
    [dictionaryId]
  )
  const previewCasesStorageKey = React.useMemo(
    () => `tldw:dictionaries:preview-cases:${dictionaryId}`,
    [dictionaryId]
  )

  React.useEffect(() => {
    return () => {
      if (validationRowHighlightTimerRef.current) {
        clearTimeout(validationRowHighlightTimerRef.current)
      }
    }
  }, [])

  React.useEffect(() => {
    if (typeof window === "undefined") return
    try {
      const savedDraft = window.localStorage.getItem(previewDraftStorageKey)
      setPreviewText(savedDraft ?? "")
    } catch {
      setPreviewText("")
    }

    try {
      const rawSavedCases = window.localStorage.getItem(previewCasesStorageKey)
      if (!rawSavedCases) {
        setSavedPreviewCases([])
        return
      }
      const parsed = JSON.parse(rawSavedCases)
      if (!Array.isArray(parsed)) {
        setSavedPreviewCases([])
        return
      }
      const normalized = parsed
        .filter((item) => item && typeof item === "object")
        .map((item) => ({
          id: String((item as any).id || ""),
          name: String((item as any).name || "").trim(),
          text: String((item as any).text || "")
        }))
        .filter((item) => item.id && item.name)
      setSavedPreviewCases(normalized)
    } catch {
      setSavedPreviewCases([])
    }
  }, [previewCasesStorageKey, previewDraftStorageKey])

  React.useEffect(() => {
    if (typeof window === "undefined") return
    try {
      window.localStorage.setItem(previewDraftStorageKey, previewText)
    } catch {
      // no-op (private mode or disabled storage)
    }
  }, [previewDraftStorageKey, previewText])

  React.useEffect(() => {
    if (typeof window === "undefined") return
    try {
      window.localStorage.setItem(
        previewCasesStorageKey,
        JSON.stringify(savedPreviewCases)
      )
    } catch {
      // no-op (private mode or disabled storage)
    }
  }, [previewCasesStorageKey, savedPreviewCases])

  const normalizedEntryGroupFilter = React.useMemo(() => {
    if (typeof entryGroupFilter !== "string") return undefined
    const trimmed = entryGroupFilter.trim()
    return trimmed.length > 0 ? trimmed : undefined
  }, [entryGroupFilter])

  const entriesQueryKey = React.useMemo(
    () =>
      [
        "tldw:listDictionaryEntries",
        dictionaryId,
        normalizedEntryGroupFilter ?? "__all__",
      ] as const,
    [dictionaryId, normalizedEntryGroupFilter]
  )
  const allEntriesQueryKey = React.useMemo(
    () => ["tldw:listDictionaryEntriesAll", dictionaryId] as const,
    [dictionaryId]
  )

  const { data: dictionaryMeta } = useQuery({
    queryKey: ["tldw:getDictionary", dictionaryId],
    queryFn: async () => {
      await tldwClient.initialize()
      return await tldwClient.getDictionary(dictionaryId)
    }
  })

  const {
    data: entriesData,
    status: entriesStatus,
    error: entriesError,
    refetch: refetchEntries
  } = useQuery({
    queryKey: entriesQueryKey,
    queryFn: async () => {
      await tldwClient.initialize()
      const res = await tldwClient.listDictionaryEntries(
        dictionaryId,
        normalizedEntryGroupFilter
      )
      return res?.entries || []
    }
  })

  const { data: allEntriesData } = useQuery({
    queryKey: allEntriesQueryKey,
    queryFn: async () => {
      await tldwClient.initialize()
      const res = await tldwClient.listDictionaryEntries(dictionaryId)
      return res?.entries || []
    }
  })

  const entries = Array.isArray(entriesData) ? entriesData : []
  const allEntries = Array.isArray(allEntriesData) ? allEntriesData : entries

  const entryGroupOptions = React.useMemo(
    () => buildDictionaryEntryGroupOptions(allEntries),
    [allEntries]
  )
  const filteredEntries = React.useMemo(
    () =>
      filterDictionaryEntriesBySearchAndGroup(
        entries,
        entrySearch,
        normalizedEntryGroupFilter
      ),
    [entries, entrySearch, normalizedEntryGroupFilter]
  )
  const hasAnyEntries = allEntries.length > 0
  const allEntriesById = React.useMemo(() => {
    const map = new Map<number, any>()
    for (const entry of allEntries) {
      const entryId = Number(entry?.id)
      if (Number.isFinite(entryId) && entryId > 0) {
        map.set(entryId, entry)
      }
    }
    return map
  }, [allEntries])
  const filteredEntryIds = React.useMemo(
    () =>
      filteredEntries
        .map((entry: any) => Number(entry?.id))
        .filter((entryId: number) => Number.isFinite(entryId) && entryId > 0),
    [filteredEntries]
  )
  const selectedEntryIds = React.useMemo(
    () =>
      selectedEntryRowKeys
        .map((entryId) => Number(entryId))
        .filter((entryId) => Number.isFinite(entryId) && entryId > 0),
    [selectedEntryRowKeys]
  )
  const orderedEntryIds = React.useMemo(
    () =>
      allEntries
        .map((entry: any) => Number(entry?.id))
        .filter((entryId: number) => Number.isFinite(entryId) && entryId > 0),
    [allEntries]
  )
  const entryPriorityById = React.useMemo(() => {
    const map = new Map<number, number>()
    orderedEntryIds.forEach((entryId, index) => {
      map.set(entryId, index + 1)
    })
    return map
  }, [orderedEntryIds])
  const canReorderEntries =
    orderedEntryIds.length > 1 &&
    entrySearch.trim().length === 0 &&
    !normalizedEntryGroupFilter &&
    filteredEntries.length === allEntries.length
  const canEscalateSelectAllFilteredEntries =
    selectedEntryIds.length > 0 &&
    selectedEntryIds.length < filteredEntryIds.length

  const validateRegexWithServer = React.useCallback(
    async (entryDraft: any): Promise<string | null> => {
      const type = entryDraft?.type === "regex" ? "regex" : "literal"
      if (type !== "regex") return null

      const pattern =
        typeof entryDraft?.pattern === "string" ? entryDraft.pattern : ""
      const replacement =
        typeof entryDraft?.replacement === "string" ? entryDraft.replacement : ""

      if (!pattern.trim()) {
        return "Pattern is required."
      }

      const clientRegexError = validateRegexPattern(pattern)
      if (clientRegexError) {
        return clientRegexError
      }

      const timedEffectsPayload = buildTimedEffectsPayload(entryDraft?.timed_effects)
      const validationEntry: Record<string, any> = {
        pattern,
        replacement,
        type: "regex",
        probability:
          typeof entryDraft?.probability === "number" &&
          Number.isFinite(entryDraft.probability)
            ? Math.min(1, Math.max(0, entryDraft.probability))
            : 1,
        enabled:
          typeof entryDraft?.enabled === "boolean" ? entryDraft.enabled : true,
        case_sensitive:
          typeof entryDraft?.case_sensitive === "boolean"
            ? entryDraft.case_sensitive
            : true,
        max_replacements:
          Number.isInteger(entryDraft?.max_replacements) &&
          entryDraft.max_replacements >= 0
            ? entryDraft.max_replacements
            : 0
      }
      if (typeof entryDraft?.group === "string" && entryDraft.group.trim()) {
        validationEntry.group = entryDraft.group.trim()
      }
      if (timedEffectsPayload) {
        validationEntry.timed_effects = timedEffectsPayload
      }

      try {
        await tldwClient.initialize()
        const validationResult = await tldwClient.validateDictionary({
          data: {
            name: dictionaryMeta?.name || "Entry validation",
            entries: [validationEntry]
          },
          schema_version: 1,
          strict: true
        })
        return extractRegexSafetyMessage(validationResult)
      } catch (e: any) {
        return (
          e?.message ||
          "Unable to validate regex pattern safety with server."
        )
      }
    },
    [dictionaryMeta?.name]
  )

  const { mutate: addEntry, isPending: adding } = useMutation({
    mutationFn: (v: any) => tldwClient.addDictionaryEntry(dictionaryId, v),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tldw:listDictionaryEntries", dictionaryId] })
      qc.invalidateQueries({ queryKey: allEntriesQueryKey })
      form.resetFields()
      setRegexError(null)
      setRegexServerError(null)
    },
    onError: (e: any) => {
      const message = e?.message || "Failed to add entry."
      setRegexServerError(message)
      notification.error({ message: "Add entry failed", description: message })
    }
  })
  const { mutateAsync: deleteEntry } = useMutation({
    mutationFn: (id: number) => tldwClient.deleteDictionaryEntry(id)
  })

  const { mutateAsync: updateEntry, isPending: updatingEntry } = useMutation({
    mutationFn: ({ entryId, data }: { entryId: number; data: any }) =>
      tldwClient.updateDictionaryEntry(entryId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tldw:listDictionaryEntries", dictionaryId] })
      qc.invalidateQueries({ queryKey: allEntriesQueryKey })
      setEditingEntry(null)
      editEntryForm.resetFields()
      notification.success({ message: "Entry updated" })
    },
    onError: (e: any) => {
      notification.error({ message: "Update failed", description: e?.message })
    }
  })

  const startInlineEdit = React.useCallback(
    (entry: any, field: InlineEditableEntryField) => {
      if (inlineEditSaving) return
      const entryId = Number(entry?.id)
      if (!Number.isFinite(entryId) || entryId <= 0) return
      const rawValue = entry?.[field]
      const currentValue = typeof rawValue === "string" ? rawValue : ""
      setInlineEdit({
        entryId,
        field,
        value: currentValue,
        initialValue: currentValue
      })
      setInlineEditError(null)
    },
    [inlineEditSaving]
  )

  const cancelInlineEdit = React.useCallback(() => {
    if (inlineEditSaving) return
    setInlineEdit(null)
    setInlineEditError(null)
  }, [inlineEditSaving])

  const saveInlineEdit = React.useCallback(async () => {
    if (!inlineEdit || inlineEditSaving) return

    const nextValue = inlineEdit.value
    const trimmedValue = nextValue.trim()
    const fieldLabel =
      inlineEdit.field === "pattern" ? "Pattern" : "Replacement"

    if (!trimmedValue) {
      setInlineEditError(`${fieldLabel} is required.`)
      return
    }

    if (nextValue === inlineEdit.initialValue) {
      setInlineEdit(null)
      setInlineEditError(null)
      return
    }

    const currentEntry = allEntriesById.get(inlineEdit.entryId)
    if (!currentEntry) {
      setInlineEditError("Entry no longer exists. Refresh and retry.")
      return
    }

    if (inlineEdit.field === "pattern" && currentEntry?.type === "regex") {
      const clientRegexError = validateRegexPattern(nextValue)
      if (clientRegexError) {
        setInlineEditError(clientRegexError)
        return
      }
      const serverRegexError = await validateRegexWithServer({
        ...currentEntry,
        pattern: nextValue
      })
      if (serverRegexError) {
        setInlineEditError(serverRegexError)
        return
      }
    }

    setInlineEditSaving(true)
    try {
      await tldwClient.updateDictionaryEntry(inlineEdit.entryId, {
        [inlineEdit.field]: nextValue
      })
      await qc.invalidateQueries({
        queryKey: ["tldw:listDictionaryEntries", dictionaryId]
      })
      await qc.invalidateQueries({ queryKey: allEntriesQueryKey })
      setInlineEdit(null)
      setInlineEditError(null)
      notification.success({ message: `${fieldLabel} updated` })
    } catch (e: any) {
      setInlineEditError(e?.message || "Unable to save inline edit.")
    } finally {
      setInlineEditSaving(false)
    }
  }, [
    allEntriesById,
    allEntriesQueryKey,
    dictionaryId,
    inlineEdit,
    inlineEditSaving,
    notification,
    qc,
    validateRegexWithServer
  ])

  React.useEffect(() => {
    setSelectedEntryRowKeys((current) => {
      const filtered = current.filter((entryId) =>
        allEntriesById.has(Number(entryId))
      )
      if (
        filtered.length === current.length &&
        filtered.every((entryId, index) => entryId === current[index])
      ) {
        return current
      }
      return filtered
    })
  }, [allEntriesById])

  React.useEffect(() => {
    setSelectedEntryRowKeys([])
    setBulkGroupName("")
    setReorderBusyEntryId(null)
  }, [dictionaryId])

  const handleSelectAllFilteredEntries = React.useCallback(() => {
    setSelectedEntryRowKeys(filteredEntryIds)
  }, [filteredEntryIds])

  const handleBulkEntryAction = React.useCallback(
    async (operation: "activate" | "deactivate" | "delete" | "group") => {
      if (selectedEntryIds.length === 0) return

      const trimmedGroupName = bulkGroupName.trim()
      if (operation === "group" && !trimmedGroupName) {
        notification.warning({
          message: "Group name required",
          description: "Provide a group name before running bulk set group."
        })
        return
      }

      if (operation === "delete") {
        const ok = await confirmDanger({
          title: t("common:confirmTitle", { defaultValue: "Please confirm" }),
          content: `Delete ${selectedEntryIds.length} selected entries?`,
          okText: t("common:delete", { defaultValue: "Delete" }),
          cancelText: t("common:cancel", { defaultValue: "Cancel" })
        })
        if (!ok) return
      }

      setBulkEntryAction(operation)
      try {
        const payload: {
          entry_ids: number[]
          operation: "activate" | "deactivate" | "delete" | "group"
          group_name?: string
        } = {
          entry_ids: selectedEntryIds,
          operation
        }
        if (operation === "group") {
          payload.group_name = trimmedGroupName
        }

        const result = await tldwClient.bulkDictionaryEntries(payload)
        const failedIds = Array.isArray(result?.failed_ids)
          ? result.failed_ids
              .map((entryId: unknown) => Number(entryId))
              .filter((entryId: number) => Number.isFinite(entryId) && entryId > 0)
          : []
        const affectedCount =
          typeof result?.affected_count === "number"
            ? result.affected_count
            : selectedEntryIds.length - failedIds.length

        if (failedIds.length > 0) {
          notification.warning({
            message: "Bulk action completed with errors",
            description:
              result?.message ||
              `${affectedCount} entries updated, ${failedIds.length} failed.`
          })
          setSelectedEntryRowKeys(failedIds)
        } else {
          notification.success({
            message: "Bulk action complete",
            description:
              result?.message || `${affectedCount} entries updated successfully.`
          })
          setSelectedEntryRowKeys([])
          if (operation === "group") {
            setBulkGroupName("")
          }
        }

        await qc.invalidateQueries({
          queryKey: ["tldw:listDictionaryEntries", dictionaryId]
        })
        await qc.invalidateQueries({ queryKey: allEntriesQueryKey })
      } catch (e: any) {
        notification.error({
          message: "Bulk action failed",
          description: e?.message || "Unable to complete bulk action."
        })
      } finally {
        setBulkEntryAction(null)
      }
    },
    [
      allEntriesQueryKey,
      bulkGroupName,
      confirmDanger,
      dictionaryId,
      notification,
      qc,
      selectedEntryIds,
      t
    ]
  )

  const persistEntryOrder = React.useCallback(
    async (nextOrderedEntryIds: number[], changedEntryId?: number) => {
      if (nextOrderedEntryIds.length <= 1) return
      if (nextOrderedEntryIds.length !== orderedEntryIds.length) {
        notification.error({
          message: "Reorder failed",
          description: "Current filter hides entries. Clear filters and retry."
        })
        return
      }
      const isSameOrder =
        nextOrderedEntryIds.length === orderedEntryIds.length &&
        nextOrderedEntryIds.every(
          (entryId, index) => entryId === orderedEntryIds[index]
        )
      if (isSameOrder) return

      setReorderBusyEntryId(changedEntryId ?? -1)
      try {
        await tldwClient.reorderDictionaryEntries(dictionaryId, {
          entry_ids: nextOrderedEntryIds
        })
        await qc.invalidateQueries({
          queryKey: ["tldw:listDictionaryEntries", dictionaryId]
        })
        await qc.invalidateQueries({ queryKey: allEntriesQueryKey })
      } catch (e: any) {
        notification.error({
          message: "Reorder failed",
          description:
            e?.message || "Unable to persist entry priority. Please retry."
        })
      } finally {
        setReorderBusyEntryId(null)
      }
    },
    [allEntriesQueryKey, dictionaryId, notification, orderedEntryIds, qc]
  )

  const handleMoveEntry = React.useCallback(
    async (entryId: number, direction: -1 | 1) => {
      if (!canReorderEntries || reorderBusyEntryId != null) return
      const currentIndex = orderedEntryIds.findIndex((id) => id === entryId)
      if (currentIndex < 0) return
      const nextIndex = currentIndex + direction
      if (nextIndex < 0 || nextIndex >= orderedEntryIds.length) return

      const nextOrder = [...orderedEntryIds]
      ;[nextOrder[currentIndex], nextOrder[nextIndex]] = [
        nextOrder[nextIndex],
        nextOrder[currentIndex]
      ]
      await persistEntryOrder(nextOrder, entryId)
    },
    [canReorderEntries, orderedEntryIds, persistEntryOrder, reorderBusyEntryId]
  )

  const { mutate: runValidation, isPending: validating } = useMutation({
    mutationFn: async () => {
      await tldwClient.initialize()
      const payload = {
        data: {
          name: dictionaryMeta?.name || undefined,
          description: dictionaryMeta?.description || undefined,
          entries: entries.map((entry: any) => ({
            pattern: entry.pattern,
            replacement: entry.replacement,
            type: entry.type,
            probability: entry.probability,
            enabled: entry.enabled,
            case_sensitive: entry.case_sensitive,
            group: entry.group,
            timed_effects: entry.timed_effects,
            max_replacements: entry.max_replacements
          }))
        },
        schema_version: 1,
        strict: validationStrict
      }
      return await tldwClient.validateDictionary(payload)
    },
    onSuccess: (res) => {
      setValidationReport(res)
      setValidationError(null)
    },
    onError: (e: any) => {
      setValidationReport(null)
      setValidationError(
        e?.message ||
          t("option:dictionariesTools.validateError", "Validation failed.")
      )
    }
  })

  const { mutate: runPreview, isPending: previewing } = useMutation({
    mutationFn: async () => {
      await tldwClient.initialize()
      const trimmed = previewText.trim()
      if (!trimmed) {
        throw new Error(
          t(
            "option:dictionariesTools.previewEmpty",
            "Enter sample text to preview."
          )
        )
      }
      const payload: {
        text: string
        token_budget?: number
        dictionary_id?: number | string
        max_iterations?: number
      } = {
        text: trimmed,
        dictionary_id: dictionaryId
      }
      if (typeof previewTokenBudget === "number" && previewTokenBudget > 0) {
        payload.token_budget = previewTokenBudget
      }
      if (
        typeof previewMaxIterations === "number" &&
        previewMaxIterations > 0
      ) {
        payload.max_iterations = previewMaxIterations
      }
      return await tldwClient.processDictionary(payload)
    },
    onSuccess: (res) => {
      setPreviewResult(res)
      setPreviewError(null)
    },
    onError: (e: any) => {
      setPreviewResult(null)
      setPreviewError(
        e?.message ||
          t("option:dictionariesTools.previewError", "Preview failed.")
      )
    }
  })

  const handlePreview = () => {
    if (!previewText.trim()) {
      setPreviewError(
        t(
          "option:dictionariesTools.previewEmpty",
          "Enter sample text to preview."
        )
      )
      return
    }
    runPreview()
  }

  const openToolsPanel = React.useCallback((panelKey: "validate" | "preview") => {
    setToolsPanelKeys((prev) =>
      prev.includes(panelKey) ? prev : [...prev, panelKey]
    )
  }, [])

  const savePreviewCase = React.useCallback(() => {
    const trimmedText = previewText.trim()
    if (!trimmedText) {
      setPreviewCaseError(
        t(
          "option:dictionariesTools.saveCaseEmpty",
          "Enter sample text before saving a test case."
        )
      )
      return
    }

    const trimmedName = previewCaseName.trim()
    const fallbackName = `Case ${savedPreviewCases.length + 1}`
    const nextCase = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      name: trimmedName || fallbackName,
      text: previewText
    }
    setSavedPreviewCases((prev) => [...prev, nextCase])
    setPreviewCaseName("")
    setPreviewCaseError(null)
  }, [previewCaseName, previewText, savedPreviewCases.length, t])

  const loadPreviewCase = React.useCallback(
    (caseId: string) => {
      const selectedCase = savedPreviewCases.find((item) => item.id === caseId)
      if (selectedCase) {
        setPreviewText(selectedCase.text)
      }
      setPreviewCaseError(null)
    },
    [savedPreviewCases]
  )

  const deletePreviewCase = React.useCallback((caseId: string) => {
    setSavedPreviewCases((current) =>
      current.filter((item) => item.id !== caseId)
    )
    setPreviewCaseError(null)
  }, [])

  const jumpToValidationEntry = React.useCallback(
    (field: unknown) => {
      if (typeof field !== "string") return
      const match = field.match(/^entries\[(\d+)\]/)
      if (!match) return
      const fieldIndex = Number(match[1])
      if (!Number.isFinite(fieldIndex) || fieldIndex < 0 || fieldIndex >= entries.length) {
        return
      }

      const entryId = Number(entries[fieldIndex]?.id)
      if (!Number.isFinite(entryId) || entryId <= 0) return

      if (validationRowHighlightTimerRef.current) {
        clearTimeout(validationRowHighlightTimerRef.current)
      }
      setHighlightedValidationEntryId(entryId)
      validationRowHighlightTimerRef.current = setTimeout(() => {
        setHighlightedValidationEntryId(null)
      }, 2200)

      if (typeof document !== "undefined") {
        const rowElement = document.querySelector(`tr[data-row-key="${entryId}"]`)
        if (rowElement instanceof HTMLElement) {
          try {
            rowElement.scrollIntoView({ behavior: "smooth", block: "center" })
          } catch {
            rowElement.scrollIntoView()
          }
        }
      }
    },
    [entries]
  )

  const validationErrors = Array.isArray(validationReport?.errors)
    ? validationReport.errors
    : []
  const validationWarnings = Array.isArray(validationReport?.warnings)
    ? validationReport.warnings
    : []
  const entryStats = validationReport?.entry_stats || null

  const previewEntriesUsed = Array.isArray(previewResult?.entries_used)
    ? previewResult.entries_used
    : []
  const previewOriginalText =
    typeof previewResult?.original_text === "string"
      ? previewResult.original_text
      : previewText
  const previewProcessedText =
    typeof previewResult?.processed_text === "string"
      ? previewResult.processed_text
      : ""
  const previewDiffSegments = React.useMemo(
    () => buildTextDiffSegments(previewOriginalText || "", previewProcessedText || ""),
    [previewOriginalText, previewProcessedText]
  )
  const previewHasDiffChanges = previewDiffSegments.some(
    (segment) => segment.type !== "unchanged"
  )

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-border bg-surface2/40 px-3 py-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-xs text-text-muted">
            {t(
              "option:dictionariesTools.actionsHelp",
              "Run validation or preview without opening accordion sections first."
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-2">
              <Switch
                checked={validationStrict}
                onChange={setValidationStrict}
              />
              <span className="text-xs text-text">
                {t(
                  "option:dictionariesTools.strictLabel",
                  "Strict validation"
                )}
              </span>
            </div>
            <Button
              size="small"
              onClick={() => {
                openToolsPanel("validate")
                runValidation()
              }}
              loading={validating}
              disabled={entries.length === 0}>
              {t(
                "option:dictionariesTools.validateButton",
                "Run validation"
              )}
            </Button>
            <Button
              size="small"
              type="primary"
              onClick={() => {
                openToolsPanel("preview")
                handlePreview()
              }}
              loading={previewing}>
              {t("option:dictionariesTools.previewButton", "Run preview")}
            </Button>
          </div>
        </div>
        {entries.length === 0 && (
          <div className="mt-2 text-xs text-text-muted">
            {t(
              "option:dictionariesTools.validateEmpty",
              "Add at least one entry to validate."
            )}
          </div>
        )}
      </div>
      <Collapse
        ghost
        className="rounded-lg border border-border bg-surface2/40"
        activeKey={toolsPanelKeys}
        onChange={(nextKeys) => {
          if (Array.isArray(nextKeys)) {
            setToolsPanelKeys(nextKeys.map((key) => String(key)))
            return
          }
          if (nextKeys) {
            setToolsPanelKeys([String(nextKeys)])
            return
          }
          setToolsPanelKeys([])
        }}
        items={[
          {
            key: "validate",
            label: t(
              "option:dictionariesTools.validateTitle",
              "Validate dictionary"
            ),
            children: (
              <div className="space-y-3">
                <p className="text-xs text-text-muted">
                  {t(
                    "option:dictionariesTools.validateHelp",
                    "Check schema, regex safety, and template syntax for this dictionary."
                  )}
                </p>
                {entries.length === 0 && (
                  <div className="text-xs text-text-muted">
                    {t(
                      "option:dictionariesTools.validateEmpty",
                      "Add at least one entry to validate."
                    )}
                  </div>
                )}
                {validationError && (
                  <div className="text-xs text-danger">{validationError}</div>
                )}
                {validationReport && (
                  <div className="space-y-3 rounded-md border border-border bg-surface px-3 py-2">
                    <Descriptions size="small" column={1} bordered>
                      <Descriptions.Item
                        label={t(
                          "option:dictionariesTools.validationOk",
                          "Valid"
                        )}>
                        {validationReport.ok ? "Yes" : "No"}
                      </Descriptions.Item>
                      <Descriptions.Item
                        label={t(
                          "option:dictionariesTools.schemaVersion",
                          "Schema version"
                        )}>
                        {validationReport.schema_version ?? "—"}
                      </Descriptions.Item>
                      {entryStats && (
                        <Descriptions.Item
                          label={t(
                            "option:dictionariesTools.entryStats",
                            "Entry stats"
                          )}>
                          {`${entryStats.total ?? 0} total · ${entryStats.literal ?? 0} literal · ${entryStats.regex ?? 0} regex`}
                        </Descriptions.Item>
                      )}
                    </Descriptions>
                    <div>
                      <div className="text-xs font-medium text-text">
                        {t("option:dictionariesTools.errorsLabel", "Errors")}
                      </div>
                      {validationErrors.length > 0 ? (
                        <ul className="list-disc pl-4 text-xs text-text-muted">
                          {validationErrors.map((err: any, idx: number) => (
                            <li key={`err-${idx}`}>
                              <button
                                type="button"
                                className={
                                  typeof err?.field === "string" && /^entries\[\d+\]/.test(err.field)
                                    ? "w-full text-left hover:text-text hover:underline"
                                    : "w-full cursor-default text-left"
                                }
                                onClick={() => jumpToValidationEntry(err?.field)}
                                disabled={
                                  !(
                                    typeof err?.field === "string" &&
                                    /^entries\[\d+\]/.test(err.field)
                                  )
                                }
                              >
                                <span className="font-medium text-text">
                                  {err?.code || "error"}:
                                </span>{" "}
                                {err?.message || String(err)}
                                {err?.field ? ` (${err.field})` : ""}
                              </button>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <div className="text-xs text-text-muted">
                          {t(
                            "option:dictionariesTools.noErrors",
                            "No errors found."
                          )}
                        </div>
                      )}
                    </div>
                    <div>
                      <div className="text-xs font-medium text-text">
                        {t(
                          "option:dictionariesTools.warningsLabel",
                          "Warnings"
                        )}
                      </div>
                      {validationWarnings.length > 0 ? (
                        <ul className="list-disc pl-4 text-xs text-text-muted">
                          {validationWarnings.map((warn: any, idx: number) => (
                            <li key={`warn-${idx}`}>
                              <button
                                type="button"
                                className={
                                  typeof warn?.field === "string" && /^entries\[\d+\]/.test(warn.field)
                                    ? "w-full text-left hover:text-text hover:underline"
                                    : "w-full cursor-default text-left"
                                }
                                onClick={() => jumpToValidationEntry(warn?.field)}
                                disabled={
                                  !(
                                    typeof warn?.field === "string" &&
                                    /^entries\[\d+\]/.test(warn.field)
                                  )
                                }
                              >
                                <span className="font-medium text-text">
                                  {warn?.code || "warning"}:
                                </span>{" "}
                                {warn?.message || String(warn)}
                                {warn?.field ? ` (${warn.field})` : ""}
                              </button>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <div className="text-xs text-text-muted">
                          {t(
                            "option:dictionariesTools.noWarnings",
                            "No warnings found."
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )
          },
          {
            key: "preview",
            label: t(
              "option:dictionariesTools.previewTitle",
              "Preview transforms"
            ),
            children: (
              <div className="space-y-3">
                <p className="text-xs text-text-muted">
                  {t(
                    "option:dictionariesTools.previewHelp",
                    "Test how this dictionary rewrites sample text."
                  )}
                </p>
                <div className="space-y-2">
                  <div className="text-xs font-medium text-text">
                    {t(
                      "option:dictionariesTools.sampleTextLabel",
                      "Sample text"
                    )}
                  </div>
                  <Input.TextArea
                    rows={4}
                    value={previewText}
                    onChange={(e) => setPreviewText(e.target.value)}
                    placeholder={t(
                      "option:dictionariesTools.sampleTextPlaceholder",
                      "Paste text to preview dictionary substitutions."
                    )}
                  />
                </div>
                <div className="space-y-2 rounded-md border border-border bg-surface2/40 px-3 py-2">
                  <div className="text-xs font-medium text-text">
                    {t(
                      "option:dictionariesTools.savedCasesLabel",
                      "Saved test cases"
                    )}
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Input
                      size="small"
                      value={previewCaseName}
                      onChange={(event) => {
                        setPreviewCaseName(event.target.value)
                        setPreviewCaseError(null)
                      }}
                      placeholder={t(
                        "option:dictionariesTools.caseNamePlaceholder",
                        "Case name (optional)"
                      )}
                      aria-label={t(
                        "option:dictionariesTools.caseNameAria",
                        "Test case name"
                      )}
                    />
                    <Button size="small" onClick={savePreviewCase}>
                      {t(
                        "option:dictionariesTools.saveCaseButton",
                        "Save test case"
                      )}
                    </Button>
                  </div>
                  {previewCaseError && (
                    <div className="text-xs text-danger">{previewCaseError}</div>
                  )}
                  {savedPreviewCases.length > 0 ? (
                    <div className="space-y-1">
                      {savedPreviewCases.map((savedCase) => (
                        <div
                          key={savedCase.id}
                          className="flex items-center justify-between gap-2 rounded border border-border bg-surface px-2 py-1"
                        >
                          <div className="truncate text-xs text-text">
                            {savedCase.name}
                          </div>
                          <div className="flex items-center gap-1">
                            <Button
                              size="small"
                              onClick={() => loadPreviewCase(savedCase.id)}
                              aria-label={`Load test case ${savedCase.name}`}
                            >
                              {t(
                                "option:dictionariesTools.loadCaseButton",
                                "Load"
                              )}
                            </Button>
                            <Button
                              size="small"
                              danger
                              onClick={() => deletePreviewCase(savedCase.id)}
                              aria-label={`Delete test case ${savedCase.name}`}
                            >
                              {t(
                                "option:dictionariesTools.deleteCaseButton",
                                "Delete"
                              )}
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-text-muted">
                      {t(
                        "option:dictionariesTools.noSavedCases",
                        "No saved test cases for this dictionary yet."
                      )}
                    </div>
                  )}
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-text">
                      {t(
                        "option:dictionariesTools.tokenBudgetLabel",
                        "Token budget"
                      )}
                    </div>
                    <InputNumber
                      min={0}
                      style={{ width: "100%" }}
                      value={previewTokenBudget ?? undefined}
                      onChange={(value) =>
                        setPreviewTokenBudget(
                          typeof value === "number" ? value : null
                        )
                      }
                    />
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-text">
                      {t(
                        "option:dictionariesTools.maxIterationsLabel",
                        "Max iterations"
                      )}
                    </div>
                    <InputNumber
                      min={1}
                      style={{ width: "100%" }}
                      value={previewMaxIterations ?? undefined}
                      onChange={(value) =>
                        setPreviewMaxIterations(
                          typeof value === "number" ? value : null
                        )
                      }
                    />
                  </div>
                </div>
                <Button
                  size="small"
                  type="primary"
                  onClick={handlePreview}
                  loading={previewing}
                  disabled={!previewText.trim()}>
                  {t("option:dictionariesTools.previewButton", "Run preview")}
                </Button>
                {previewError && (
                  <div className="text-xs text-danger">{previewError}</div>
                )}
                {previewResult && (
                  <div className="space-y-2 rounded-md border border-border bg-surface px-3 py-2">
                    <div className="space-y-1">
                      <div className="text-xs font-medium text-text">
                        {t(
                          "option:dictionariesTools.diffPreviewLabel",
                          "Diff preview"
                        )}
                      </div>
                      {previewHasDiffChanges ? (
                        <div className="grid gap-2 sm:grid-cols-2">
                          <div className="rounded border border-border bg-surface2/50 p-2">
                            <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-text-muted">
                              {t(
                                "option:dictionariesTools.originalDiffLabel",
                                "Original (with removals)"
                              )}
                            </div>
                            <p className="text-xs leading-relaxed whitespace-pre-wrap break-words">
                              {previewDiffSegments
                                .filter((segment) => segment.type !== "added")
                                .map((segment, index) => (
                                  <span
                                    key={`diff-original-${index}`}
                                    className={
                                      segment.type === "removed"
                                        ? "rounded-sm bg-danger/15 px-0.5 text-danger line-through"
                                        : ""
                                    }>
                                    {segment.text}
                                  </span>
                                ))}
                            </p>
                          </div>
                          <div className="rounded border border-border bg-surface2/50 p-2">
                            <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-text-muted">
                              {t(
                                "option:dictionariesTools.processedDiffLabel",
                                "Processed (with additions)"
                              )}
                            </div>
                            <p className="text-xs leading-relaxed whitespace-pre-wrap break-words">
                              {previewDiffSegments
                                .filter((segment) => segment.type !== "removed")
                                .map((segment, index) => (
                                  <span
                                    key={`diff-processed-${index}`}
                                    className={
                                      segment.type === "added"
                                        ? "rounded-sm bg-success/15 px-0.5 text-success"
                                        : ""
                                    }>
                                    {segment.text}
                                  </span>
                                ))}
                            </p>
                          </div>
                        </div>
                      ) : (
                        <div className="text-xs text-text-muted">
                          {t(
                            "option:dictionariesTools.noDiffChanges",
                            "No differences detected between original and processed text."
                          )}
                        </div>
                      )}
                    </div>
                    <div className="space-y-1">
                      <div className="text-xs font-medium text-text">
                        {t(
                          "option:dictionariesTools.processedTextLabel",
                          "Processed text"
                        )}
                      </div>
                      <Input.TextArea
                        rows={4}
                        value={previewProcessedText || ""}
                        readOnly
                      />
                    </div>
                    <Descriptions size="small" column={1} bordered>
                      <Descriptions.Item
                        label={t(
                          "option:dictionariesTools.replacementsLabel",
                          "Replacements"
                        )}>
                        {previewResult.replacements ?? 0}
                      </Descriptions.Item>
                      <Descriptions.Item
                        label={t(
                          "option:dictionariesTools.iterationsLabel",
                          "Iterations"
                        )}>
                        {previewResult.iterations ?? 0}
                      </Descriptions.Item>
                      <Descriptions.Item
                        label={t(
                          "option:dictionariesTools.entriesUsedLabel",
                          "Entries used"
                        )}>
                        {previewEntriesUsed.length > 0
                          ? previewEntriesUsed.join(", ")
                          : "—"}
                      </Descriptions.Item>
                    </Descriptions>
                    {previewResult.token_budget_exceeded && (
                      <Tag color="red">
                        {t(
                          "option:dictionariesTools.tokenBudgetExceeded",
                          "Token budget exceeded"
                        )}
                      </Tag>
                    )}
                  </div>
                )}
              </div>
            )
          }
        ]}
      />

      <Divider className="!my-2" />

      <h3 className="text-sm font-medium text-text mt-4 mb-2">
        {t("option:dictionaries.entriesHeading", "Dictionary Entries")}
      </h3>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <Input
          value={entrySearch}
          onChange={(e) => setEntrySearch(e.target.value)}
          allowClear
          className="sm:max-w-md"
          placeholder="Search entries by pattern, replacement, or group"
          aria-label="Search dictionary entries"
        />
        <Select
          allowClear
          value={entryGroupFilter}
          onChange={(value) =>
            setEntryGroupFilter(
              typeof value === "string" && value.trim() ? value : undefined
            )
          }
          placeholder="All groups"
          options={entryGroupOptions}
          className="sm:w-56"
          aria-label="Filter entries by group"
        />
      </div>
      {entriesStatus === "success" && hasAnyEntries && (
        <div className="space-y-2">
          <p className="text-xs text-text-muted">
            {canReorderEntries
              ? "Entries are processed in priority order (top to bottom). Use the up/down controls to reorder."
              : "Entries are processed in priority order. Clear search/group filters to reorder."}
          </p>
          {selectedEntryIds.length > 0 && (
            <div className="rounded border border-border p-2 space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-semibold">
                  {selectedEntryIds.length} selected
                </span>
                <div className="flex flex-wrap items-center gap-2">
                  {canEscalateSelectAllFilteredEntries && (
                    <Button
                      type="link"
                      size="small"
                      className="px-0"
                      onClick={handleSelectAllFilteredEntries}
                      aria-label={`Select all ${filteredEntryIds.length} entries`}>
                      Select all {filteredEntryIds.length} entries
                    </Button>
                  )}
                  <Button
                    type="link"
                    size="small"
                    className="px-0"
                    onClick={() => setSelectedEntryRowKeys([])}
                    aria-label="Clear selected entries">
                    Clear selection
                  </Button>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  size="small"
                  loading={bulkEntryAction === "activate"}
                  onClick={() => void handleBulkEntryAction("activate")}>
                  Enable
                </Button>
                <Button
                  size="small"
                  loading={bulkEntryAction === "deactivate"}
                  onClick={() => void handleBulkEntryAction("deactivate")}>
                  Disable
                </Button>
                <AutoComplete
                  options={entryGroupOptions}
                  value={bulkGroupName}
                  onChange={(value) => setBulkGroupName(String(value || ""))}
                  placeholder="Group name"
                  className="min-w-[180px]"
                  aria-label="Bulk group name"
                  filterOption={(inputValue, option) =>
                    String(option?.value || "")
                      .toLowerCase()
                      .includes(inputValue.toLowerCase())
                  }
                />
                <Button
                  size="small"
                  loading={bulkEntryAction === "group"}
                  onClick={() => void handleBulkEntryAction("group")}>
                  Set Group
                </Button>
                <Button
                  size="small"
                  danger
                  loading={bulkEntryAction === "delete"}
                  onClick={() => void handleBulkEntryAction("delete")}>
                  Delete
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {entriesStatus === "pending" && <Skeleton active paragraph={{ rows: 4 }} />}
      {entriesStatus === "error" && (
        <FeatureEmptyState
          title="Unable to load entries"
          description={
            entriesError instanceof Error
              ? `Could not load entries: ${entriesError.message}`
              : "Could not load entries right now. Please retry."
          }
          primaryActionLabel="Retry"
          onPrimaryAction={() => void refetchEntries()}
        />
      )}
      {entriesStatus === "success" && (
        !hasAnyEntries ? (
          <FeatureEmptyState
            title="No entries yet"
            description="Add a pattern/replacement pair to start transforming text."
            examples={[
              "Literal: BP -> blood pressure",
              "Regex: /Dr\\./ -> Doctor",
              "Group entries to organize related substitutions",
            ]}
            primaryActionLabel="Add first entry"
            onPrimaryAction={() => form.scrollToField("pattern")}
          />
        ) : (
          <Table
            size="small"
            rowKey={(r: any) => r.id}
            dataSource={filteredEntries}
            rowClassName={(record: any) =>
              Number(record?.id) === highlightedValidationEntryId
                ? "bg-warn/10"
                : ""
            }
            rowSelection={{
              selectedRowKeys: selectedEntryRowKeys,
              onChange: (keys) => setSelectedEntryRowKeys(keys),
              preserveSelectedRowKeys: true
            }}
            locale={{
              emptyText:
                entrySearch.trim() || normalizedEntryGroupFilter
                  ? "No entries match the current filters."
                  : "No entries available."
            }}
            columns={[
              {
                title: "Pattern",
                dataIndex: "pattern",
                key: "pattern",
                render: (v: string, r: any) => {
                  const entryId = Number(r?.id)
                  const isEditing =
                    inlineEdit?.entryId === entryId &&
                    inlineEdit?.field === "pattern"
                  if (isEditing) {
                    return (
                      <div className="space-y-1">
                        <div className="flex items-center gap-1">
                          <Input
                            size="small"
                            autoFocus
                            value={inlineEdit.value}
                            className="font-mono"
                            onChange={(event) => {
                              setInlineEdit((current) =>
                                current
                                  ? { ...current, value: event.target.value }
                                  : current
                              )
                              setInlineEditError(null)
                            }}
                            onKeyDown={(event) => {
                              if (event.key === "Escape") {
                                event.preventDefault()
                                cancelInlineEdit()
                                return
                              }
                              if (event.key === "Enter") {
                                event.preventDefault()
                                void saveInlineEdit()
                              }
                            }}
                            onBlur={() => {
                              void saveInlineEdit()
                            }}
                            disabled={inlineEditSaving}
                            aria-label={`Inline edit pattern for ${r.pattern}`}
                          />
                          <button
                            type="button"
                            className="min-w-[28px] min-h-[28px] flex items-center justify-center rounded border border-border text-success hover:bg-success/10"
                            onMouseDown={(event) => event.preventDefault()}
                            onClick={() => {
                              void saveInlineEdit()
                            }}
                            disabled={inlineEditSaving}
                            aria-label={`Save pattern edit for ${r.pattern}`}
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            className="min-w-[28px] min-h-[28px] flex items-center justify-center rounded border border-border text-text-muted hover:bg-surface2"
                            onMouseDown={(event) => event.preventDefault()}
                            onClick={cancelInlineEdit}
                            disabled={inlineEditSaving}
                            aria-label={`Cancel pattern edit for ${r.pattern}`}
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                        {inlineEditError && (
                          <p className="text-[11px] text-danger">{inlineEditError}</p>
                        )}
                      </div>
                    )
                  }

                  return (
                    <button
                      type="button"
                      className="group inline-flex max-w-full items-center gap-1 rounded px-1 py-0.5 text-left hover:bg-surface2"
                      onClick={() => startInlineEdit(r, "pattern")}
                      disabled={inlineEditSaving}
                      aria-label={`Inline edit pattern ${r.pattern}`}
                    >
                      <span className="font-mono text-xs truncate">{v}</span>
                      {r.type === "regex" && (
                        <Tag color="blue" className="ml-1 text-[10px]">regex</Tag>
                      )}
                    </button>
                  )
                }
              },
              {
                title: "Replacement",
                dataIndex: "replacement",
                key: "replacement",
                render: (v: string, r: any) => {
                  const entryId = Number(r?.id)
                  const isEditing =
                    inlineEdit?.entryId === entryId &&
                    inlineEdit?.field === "replacement"
                  if (isEditing) {
                    return (
                      <div className="space-y-1">
                        <div className="flex items-center gap-1">
                          <Input
                            size="small"
                            autoFocus
                            value={inlineEdit.value}
                            onChange={(event) => {
                              setInlineEdit((current) =>
                                current
                                  ? { ...current, value: event.target.value }
                                  : current
                              )
                              setInlineEditError(null)
                            }}
                            onKeyDown={(event) => {
                              if (event.key === "Escape") {
                                event.preventDefault()
                                cancelInlineEdit()
                                return
                              }
                              if (event.key === "Enter") {
                                event.preventDefault()
                                void saveInlineEdit()
                              }
                            }}
                            onBlur={() => {
                              void saveInlineEdit()
                            }}
                            disabled={inlineEditSaving}
                            aria-label={`Inline edit replacement for ${r.pattern}`}
                          />
                          <button
                            type="button"
                            className="min-w-[28px] min-h-[28px] flex items-center justify-center rounded border border-border text-success hover:bg-success/10"
                            onMouseDown={(event) => event.preventDefault()}
                            onClick={() => {
                              void saveInlineEdit()
                            }}
                            disabled={inlineEditSaving}
                            aria-label={`Save replacement edit for ${r.pattern}`}
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            className="min-w-[28px] min-h-[28px] flex items-center justify-center rounded border border-border text-text-muted hover:bg-surface2"
                            onMouseDown={(event) => event.preventDefault()}
                            onClick={cancelInlineEdit}
                            disabled={inlineEditSaving}
                            aria-label={`Cancel replacement edit for ${r.pattern}`}
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                        {inlineEditError && (
                          <p className="text-[11px] text-danger">{inlineEditError}</p>
                        )}
                      </div>
                    )
                  }

                  return (
                    <button
                      type="button"
                      className="max-w-full rounded px-1 py-0.5 text-left text-xs hover:bg-surface2"
                      onClick={() => startInlineEdit(r, "replacement")}
                      disabled={inlineEditSaving}
                      aria-label={`Inline edit replacement ${r.pattern}`}
                    >
                      <span className="truncate">{v}</span>
                    </button>
                  )
                }
              },
              {
                title: "Type",
                dataIndex: "type",
                key: "type",
                responsive: DICTIONARY_ENTRY_COLUMN_RESPONSIVE.type,
                render: (value: string) => {
                  const normalized = value === "regex" ? "regex" : "literal"
                  return (
                    <Tag color={normalized === "regex" ? "blue" : "default"}>
                      {normalized}
                    </Tag>
                  )
                }
              },
              {
                title: "Probability",
                dataIndex: "probability",
                key: "probability",
                responsive: DICTIONARY_ENTRY_COLUMN_RESPONSIVE.probability,
                render: (value: number | null | undefined) => {
                  const safeValue =
                    typeof value === "number" && Number.isFinite(value) ? value : 1
                  return (
                    <span className="text-xs font-mono">
                      {safeValue.toFixed(2)}
                    </span>
                  )
                }
              },
              {
                title: "Group",
                dataIndex: "group",
                key: "group",
                responsive: DICTIONARY_ENTRY_COLUMN_RESPONSIVE.group,
                render: (value: string | null | undefined) => {
                  const group = typeof value === "string" ? value.trim() : ""
                  if (!group) {
                    return <span className="text-xs text-text-muted">—</span>
                  }
                  return <Tag>{group}</Tag>
                }
              },
              {
                title: "Priority",
                key: "priority",
                width: 128,
                render: (_value: unknown, entry: any) => {
                  const entryId = Number(entry?.id)
                  const priority = entryPriorityById.get(entryId)
                  const isBusy =
                    reorderBusyEntryId != null &&
                    (reorderBusyEntryId === -1 || reorderBusyEntryId === entryId)
                  const canMoveUp =
                    canReorderEntries &&
                    Number.isFinite(entryId) &&
                    !!priority &&
                    priority > 1 &&
                    !isBusy
                  const canMoveDown =
                    canReorderEntries &&
                    Number.isFinite(entryId) &&
                    !!priority &&
                    priority < orderedEntryIds.length &&
                    !isBusy

                  return (
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        className="min-w-[28px] min-h-[28px] flex items-center justify-center rounded border border-border text-text-muted hover:bg-surface2 disabled:opacity-50"
                        aria-label={`Move entry ${entry?.pattern || entryId} up`}
                        onClick={() => {
                          void handleMoveEntry(entryId, -1)
                        }}
                        disabled={!canMoveUp}
                      >
                        <ChevronUp className="w-3.5 h-3.5" />
                      </button>
                      <button
                        type="button"
                        className="min-w-[28px] min-h-[28px] flex items-center justify-center rounded border border-border text-text-muted hover:bg-surface2 disabled:opacity-50"
                        aria-label={`Move entry ${entry?.pattern || entryId} down`}
                        onClick={() => {
                          void handleMoveEntry(entryId, 1)
                        }}
                        disabled={!canMoveDown}
                      >
                        <ChevronDown className="w-3.5 h-3.5" />
                      </button>
                      <span className="min-w-[2ch] text-right text-xs font-mono">
                        {priority ?? "—"}
                      </span>
                    </div>
                  )
                }
              },
              {
                title: "Enabled",
                dataIndex: "enabled",
                key: "enabled",
                width: 80,
                render: (v: boolean) => (
                  v ? (
                    <Tag color="green" icon={<CheckCircle2 className="w-3 h-3 inline mr-1" />}>On</Tag>
                  ) : (
                    <Tag>Off</Tag>
                  )
                )
              },
              {
                title: "Actions",
                key: "actions",
                width: 180,
                render: (_: any, r: any) => (
                  <div className="flex gap-1 items-center">
                    {/* Inline Test Button */}
                    <Popover
                      trigger="click"
                      open={testingEntryId === r.id}
                      onOpenChange={(open) => {
                        if (open) {
                          setTestingEntryId(r.id)
                          setInlineTestInput("")
                          setInlineTestResult(null)
                        } else {
                          setTestingEntryId(null)
                        }
                      }}
                      content={
                        <div className="w-64 space-y-2">
                          <div className="text-xs font-medium">Test this entry</div>
                          <Input
                            size="small"
                            placeholder="Enter test text..."
                            value={inlineTestInput}
                            onChange={(e) => setInlineTestInput(e.target.value)}
                            onPressEnter={() => {
                              if (!inlineTestInput.trim()) return
                              try {
                                let result = inlineTestInput
                                if (r.type === "regex") {
                                  const regexMatch = r.pattern.match(/^\/(.*)\/([gimsuvy]*)$/)
                                  const regex = regexMatch
                                    ? new RegExp(regexMatch[1], regexMatch[2])
                                    : new RegExp(r.pattern, r.case_sensitive ? "" : "i")
                                  result = inlineTestInput.replace(regex, r.replacement)
                                } else {
                                  const flags = r.case_sensitive ? "g" : "gi"
                                  result = inlineTestInput.replace(new RegExp(r.pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), flags), r.replacement)
                                }
                                setInlineTestResult(result)
                              } catch (e: any) {
                                setInlineTestResult(`Error: ${e.message}`)
                              }
                            }}
                          />
                          <Button
                            size="small"
                            type="primary"
                            className="w-full"
                            onClick={() => {
                              if (!inlineTestInput.trim()) return
                              try {
                                let result = inlineTestInput
                                if (r.type === "regex") {
                                  const regexMatch = r.pattern.match(/^\/(.*)\/([gimsuvy]*)$/)
                                  const regex = regexMatch
                                    ? new RegExp(regexMatch[1], regexMatch[2])
                                    : new RegExp(r.pattern, r.case_sensitive ? "" : "i")
                                  result = inlineTestInput.replace(regex, r.replacement)
                                } else {
                                  const flags = r.case_sensitive ? "g" : "gi"
                                  result = inlineTestInput.replace(new RegExp(r.pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), flags), r.replacement)
                                }
                                setInlineTestResult(result)
                              } catch (e: any) {
                                setInlineTestResult(`Error: ${e.message}`)
                              }
                            }}
                          >
                            Test
                          </Button>
                          {inlineTestResult !== null && (
                            <div className="mt-2 p-2 bg-surface2 rounded text-xs">
                              <div className="text-text-muted mb-1">Result:</div>
                              <div className="font-mono break-all">{inlineTestResult}</div>
                            </div>
                          )}
                        </div>
                      }
                    >
                      <Tooltip title="Test entry">
                        <button
                          className="min-w-[36px] min-h-[36px] flex items-center justify-center text-text-muted hover:text-text hover:bg-surface2 rounded-md transition-colors"
                          aria-label={`Test entry ${r.pattern}`}
                        >
                          <Play className="w-4 h-4" />
                        </button>
                      </Tooltip>
                    </Popover>

                    {/* Edit Button */}
                    <Tooltip title="Edit entry">
                      <button
                        className="min-w-[36px] min-h-[36px] flex items-center justify-center text-text-muted hover:text-text hover:bg-surface2 rounded-md transition-colors"
                        onClick={() => {
                          setEditingEntry(r)
                          editEntryForm.setFieldsValue({
                            ...r,
                            timed_effects: buildTimedEffectsPayload(
                              r?.timed_effects,
                              { forceObject: true }
                            )
                          })
                          editEntryForm.setFields([{ name: "pattern", errors: [] }])
                        }}
                        aria-label={`Edit entry ${r.pattern}`}
                      >
                        <Pen className="w-4 h-4" />
                      </button>
                    </Tooltip>

                    {/* Delete Button */}
                    <Tooltip title="Delete entry">
                      <button
                        className="min-w-[36px] min-h-[36px] flex items-center justify-center text-danger hover:bg-danger/10 rounded-md transition-colors"
                        onClick={async () => {
                        const ok = await confirmDanger({
                          title: t("common:confirmTitle", {
                            defaultValue: "Please confirm"
                          }),
                          content: "Delete entry?",
                            okText: t("common:delete", { defaultValue: "Delete" }),
                            cancelText: t("common:cancel", {
                            defaultValue: "Cancel"
                          })
                        })
                        if (!ok) return

                        const entryId = Number(r?.id)
                        if (!Number.isFinite(entryId) || entryId <= 0) {
                          notification.error({
                            message: "Delete failed",
                            description: "Entry ID is invalid. Please refresh and retry."
                          })
                          return
                        }

                        const entrySnapshot = { ...r }
                        const previousEntries = Array.isArray(entries)
                          ? [...entries]
                          : []

                        qc.setQueryData(entriesQueryKey, (current: any) => {
                          const currentEntries = Array.isArray(current)
                            ? current
                            : previousEntries
                          return currentEntries.filter(
                            (entry: any) => Number(entry?.id) !== entryId
                          )
                        })
                        qc.setQueryData(allEntriesQueryKey, (current: any) => {
                          const currentEntries = Array.isArray(current)
                            ? current
                            : allEntries
                          return currentEntries.filter(
                            (entry: any) => Number(entry?.id) !== entryId
                          )
                        })

                        try {
                          await deleteEntry(entryId)
                          const previewPattern = String(entrySnapshot?.pattern || "Entry")
                          showUndoNotification({
                            title: "Entry deleted",
                            description: `"${previewPattern}" was removed. Undo to restore it.`,
                            duration: 10,
                            onUndo: async () => {
                              const payload =
                                buildRestorableDictionaryEntryPayload(entrySnapshot)
                              const restored = await tldwClient.addDictionaryEntry(
                                dictionaryId,
                                payload
                              )
                              qc.setQueryData(entriesQueryKey, (current: any) => {
                                const currentEntries = Array.isArray(current)
                                  ? current
                                  : []
                                return [...currentEntries, restored || { ...entrySnapshot, ...payload }]
                              })
                              qc.setQueryData(allEntriesQueryKey, (current: any) => {
                                const currentEntries = Array.isArray(current)
                                  ? current
                                  : []
                                return [...currentEntries, restored || { ...entrySnapshot, ...payload }]
                              })
                              await qc.invalidateQueries({ queryKey: ["tldw:listDictionaryEntries", dictionaryId] })
                              await qc.invalidateQueries({ queryKey: allEntriesQueryKey })
                            },
                            onDismiss: () => {
                              void qc.invalidateQueries({ queryKey: ["tldw:listDictionaryEntries", dictionaryId] })
                              void qc.invalidateQueries({ queryKey: allEntriesQueryKey })
                            }
                          })
                        } catch (deleteError: any) {
                          qc.setQueryData(entriesQueryKey, previousEntries)
                          qc.setQueryData(allEntriesQueryKey, allEntries)
                          notification.error({
                            message: "Delete failed",
                            description:
                              (deleteError?.message
                                ? `${deleteError.message}.`
                                : "Failed to delete entry.") +
                              " Please retry."
                          })
                        }
                      }}
                      aria-label={`Delete entry ${r.pattern}`}
                    >
                      <Trash2 className="w-4 h-4" />
                      </button>
                    </Tooltip>
                  </div>
                )
              }
            ] as any}
          />
        )
      )}

      {/* Edit Entry Modal */}
      <Modal
        title="Edit Entry"
        open={!!editingEntry}
        onCancel={() => {
          setEditingEntry(null)
          editEntryForm.resetFields()
        }}
        footer={null}
      >
        <Form
          layout="vertical"
          form={editEntryForm}
          onFinish={async (v) => {
            if (!editingEntry?.id) return

            const entryType = v?.type === "regex" ? "regex" : "literal"
            const pattern = typeof v?.pattern === "string" ? v.pattern : ""
            if (entryType === "regex") {
              const regexValidationError = validateRegexPattern(pattern)
              if (regexValidationError) {
                editEntryForm.setFields([
                  { name: "pattern", errors: [regexValidationError] }
                ])
                return
              }

              const serverRegexError = await validateRegexWithServer(v)
              if (serverRegexError) {
                editEntryForm.setFields([
                  { name: "pattern", errors: [serverRegexError] }
                ])
                return
              }
            }

            const payload: Record<string, any> = {
              ...v,
              timed_effects: buildTimedEffectsPayload(v?.timed_effects, {
                forceObject: true
              })
            }

            try {
              await updateEntry({ entryId: editingEntry.id, data: payload })
            } catch (e: any) {
              const message = e?.message || "Update failed"
              if (/regex|pattern|dangerous/i.test(message)) {
                editEntryForm.setFields([{ name: "pattern", errors: [message] }])
              }
            }
          }}
        >
          <Form.Item
            name="pattern"
            label={<LabelWithHelp label="Pattern" help="The text or regex pattern to match. For regex, use /pattern/flags format." />}
            rules={[{ required: true }]}
          >
            <Input placeholder="e.g., KCl or /hel+o/i" className="font-mono" />
          </Form.Item>
          <Form.Item
            name="replacement"
            label={<LabelWithHelp label="Replacement" help="The text to replace matches with." />}
            rules={[{ required: true }]}
          >
            <Input placeholder="e.g., Potassium Chloride" />
          </Form.Item>
          <Form.Item name="type" label="Type" initialValue="literal">
            <Select
              options={[
                { label: "Literal (exact match)", value: "literal" },
                { label: "Regex (pattern match)", value: "regex" }
              ]}
            />
          </Form.Item>
          <Form.Item name="enabled" label="Enabled" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>
          <Form.Item
            name="probability"
            label="Probability"
            initialValue={1}
            rules={[
              {
                type: "number",
                min: 0,
                max: 1,
                message: "Probability must be between 0 and 1."
              }
            ]}
          >
            <InputNumber min={0} max={1} step={0.01} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item noStyle shouldUpdate={(prev, current) => prev.probability !== current.probability}>
            {() => {
              const probabilityValue = Number(
                normalizeProbabilityValue(editEntryForm.getFieldValue("probability"), 1).toFixed(2)
              )
              return (
                <div className="mt-[-8px] mb-3">
                  <Slider
                    min={0}
                    max={1}
                    step={0.01}
                    value={probabilityValue}
                    onChange={(value) => {
                      const nextValue = Array.isArray(value) ? value[0] : value
                      editEntryForm.setFieldValue(
                        "probability",
                        Number(normalizeProbabilityValue(nextValue, 1).toFixed(2))
                      )
                    }}
                    aria-label="Probability slider"
                  />
                  <div className="text-xs text-text-muted">
                    {formatProbabilityFrequencyHint(probabilityValue)}
                  </div>
                </div>
              )
            }}
          </Form.Item>
          <Form.Item name="group" label="Group">
            <AutoComplete
              options={entryGroupOptions}
              placeholder="e.g., medications"
              filterOption={(inputValue, option) =>
                String(option?.value || "")
                  .toLowerCase()
                  .includes(inputValue.toLowerCase())
              }
            />
          </Form.Item>
          <Form.Item
            name="max_replacements"
            label={
              <LabelWithHelp
                label="Max Replacements"
                help="Probability controls whether this entry fires. Max replacements caps how many times it can apply per message."
              />
            }
          >
            <InputNumber min={0} style={{ width: "100%" }} />
          </Form.Item>
          <div className="grid gap-3 sm:grid-cols-3">
            <Form.Item
              name={["timed_effects", "sticky"]}
              label={
                <LabelWithHelp
                  label="Sticky (seconds)"
                  help="Keep this replacement active for additional messages after it fires. Use 0 to disable."
                />
              }
              initialValue={0}
            >
              <InputNumber min={0} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item
              name={["timed_effects", "cooldown"]}
              label={
                <LabelWithHelp
                  label="Cooldown (seconds)"
                  help="Minimum wait time before this entry can fire again. Use 0 to disable."
                />
              }
              initialValue={0}
            >
              <InputNumber min={0} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item
              name={["timed_effects", "delay"]}
              label={
                <LabelWithHelp
                  label="Delay (seconds)"
                  help="Wait time before this entry becomes eligible to run. Use 0 to disable."
                />
              }
              initialValue={0}
            >
              <InputNumber min={0} style={{ width: "100%" }} />
            </Form.Item>
          </div>
          <Form.Item name="case_sensitive" label="Case Sensitive" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={updatingEntry} className="w-full">
            Save Changes
          </Button>
        </Form>
      </Modal>
      {/* Add Entry Form */}
      <div className="border border-border rounded-lg p-4 bg-surface2/30 mt-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-medium text-text">
            {t("option:dictionaries.addEntry", "Add New Entry")}
          </h4>
          <button
            type="button"
            className="flex items-center gap-1 text-xs text-text-muted hover:text-text transition-colors"
            onClick={() => setAdvancedMode(!advancedMode)}
            aria-expanded={advancedMode}
          >
            {advancedMode ? (
              <>
                <ChevronUp className="w-3 h-3" />
                {t("option:dictionaries.simpleMode", "Simple mode")}
              </>
            ) : (
              <>
                <ChevronDown className="w-3 h-3" />
                {t("option:dictionaries.advancedMode", "Advanced options")}
              </>
            )}
          </button>
        </div>

        <Form
          layout="vertical"
          form={form}
          onFinish={async (v) => {
            // Validate regex before submitting
            const entryType = form.getFieldValue("type") || "literal"
            setRegexServerError(null)
            if (entryType === "regex") {
              const pattern = form.getFieldValue("pattern")
              const error = validateRegexPattern(pattern)
              if (error) {
                setRegexError(error)
                return
              }

              const serverRegexError = await validateRegexWithServer({
                ...v,
                type: "regex"
              })
              if (serverRegexError) {
                setRegexServerError(serverRegexError)
                return
              }
            }

            const payload: Record<string, any> = { ...v }
            payload.case_sensitive =
              typeof v?.case_sensitive === "boolean" ? v.case_sensitive : false
            const timedEffectsPayload = buildTimedEffectsPayload(v?.timed_effects)
            if (timedEffectsPayload) {
              payload.timed_effects = timedEffectsPayload
            } else {
              delete payload.timed_effects
            }
            addEntry(payload)
          }}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <Form.Item
              name="pattern"
              label={
                <LabelWithHelp
                  label={t("option:dictionaries.patternLabel", "Find")}
                  help={t(
                    "option:dictionaries.patternHelp",
                    "Text to find. For simple terms like 'KCl', just type it. For patterns, select Regex type and use /pattern/flags format."
                  )}
                  required
                />
              }
              rules={[{ required: true, message: "Pattern is required" }]}
              validateStatus={regexError || regexServerError ? "error" : undefined}
              help={regexError || regexServerError}
            >
              <Input
                placeholder={t("option:dictionaries.patternPlaceholder", "e.g., KCl or /hel+o/i")}
                className="font-mono"
                onChange={(e) => {
                  setRegexServerError(null)
                  // Real-time regex validation
                  const entryType = form.getFieldValue("type") || "literal"
                  if (entryType === "regex") {
                    const error = validateRegexPattern(e.target.value)
                    setRegexError(error)
                  } else {
                    setRegexError(null)
                  }
                }}
                aria-describedby="pattern-help"
              />
            </Form.Item>
            <Form.Item
              name="replacement"
              label={
                <LabelWithHelp
                  label={t("option:dictionaries.replacementLabel", "Replace with")}
                  help={t(
                    "option:dictionaries.replacementHelp",
                    "The text that will replace matches. For regex, you can use $1, $2 for capture groups."
                  )}
                  required
                />
              }
              rules={[{ required: true, message: "Replacement is required" }]}
            >
              <Input
                placeholder={t("option:dictionaries.replacementPlaceholder", "e.g., Potassium Chloride")}
                onChange={() => {
                  setRegexServerError(null)
                }}
                aria-describedby="replacement-help"
              />
            </Form.Item>
          </div>

          <Form.Item
            name="type"
            label={
              <LabelWithHelp
                label={t("option:dictionaries.typeLabel", "Match type")}
                help={t(
                  "option:dictionaries.typeHelp",
                  "Literal matches exact text. Regex allows pattern matching with regular expressions."
                )}
              />
            }
            initialValue="literal"
          >
            <Select
              options={[
                { label: t("option:dictionaries.typeLiteral", "Literal (exact match)"), value: "literal" },
                { label: t("option:dictionaries.typeRegex", "Regex (pattern match)"), value: "regex" }
              ]}
              onChange={(value) => {
                // Re-validate pattern when type changes
                const pattern = form.getFieldValue("pattern")
                if (value === "regex" && pattern) {
                  setRegexError(validateRegexPattern(pattern))
                } else {
                  setRegexError(null)
                }
                setRegexServerError(null)
              }}
            />
          </Form.Item>

          {/* Show validation warning for regex */}
          {(regexError || regexServerError) && (
            <div className="flex items-start gap-2 p-2 mb-3 rounded bg-danger/10 text-danger text-xs">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <div className="font-medium">Regex validation issue</div>
                <div className="text-danger/80">{regexError || regexServerError}</div>
              </div>
            </div>
          )}

          {/* Advanced options - hidden by default */}
          {advancedMode && (
            <div className="grid gap-3 sm:grid-cols-2 mt-3 pt-3 border-t border-border">
              <Form.Item
                name="probability"
                label={
                  <LabelWithHelp
                    label={t("option:dictionaries.probabilityLabel", "Probability")}
                    help={t(
                      "option:dictionaries.probabilityHelp",
                      "Chance of applying this replacement (0-1). Use 1 for always, 0.5 for 50% of the time."
                    )}
                  />
                }
                initialValue={1}
                rules={[
                  {
                    type: "number",
                    min: 0,
                    max: 1,
                    message: "Probability must be between 0 and 1."
                  }
                ]}
              >
                <InputNumber min={0} max={1} step={0.01} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item noStyle shouldUpdate={(prev, current) => prev.probability !== current.probability}>
                {() => {
                  const probabilityValue = Number(
                    normalizeProbabilityValue(form.getFieldValue("probability"), 1).toFixed(2)
                  )
                  return (
                    <div className="-mt-2 mb-3">
                      <Slider
                        min={0}
                        max={1}
                        step={0.01}
                        value={probabilityValue}
                        onChange={(value) => {
                          const nextValue = Array.isArray(value) ? value[0] : value
                          form.setFieldValue(
                            "probability",
                            Number(normalizeProbabilityValue(nextValue, 1).toFixed(2))
                          )
                        }}
                        aria-label="Probability slider"
                      />
                      <div className="text-xs text-text-muted">
                        {formatProbabilityFrequencyHint(probabilityValue)}
                      </div>
                    </div>
                  )
                }}
              </Form.Item>
              <Form.Item
                name="group"
                label={
                  <LabelWithHelp
                    label={t("option:dictionaries.groupLabel", "Group")}
                    help={t(
                      "option:dictionaries.groupHelp",
                      "Optional category for organizing entries (e.g., 'medications', 'abbreviations')."
                    )}
                  />
                }
              >
                <AutoComplete
                  options={entryGroupOptions}
                  placeholder={t("option:dictionaries.groupPlaceholder", "e.g., medications")}
                  filterOption={(inputValue, option) =>
                    String(option?.value || "")
                      .toLowerCase()
                      .includes(inputValue.toLowerCase())
                  }
                />
              </Form.Item>
              <Form.Item
                name="max_replacements"
                label={
                    <LabelWithHelp
                      label={t("option:dictionaries.maxReplacementsLabel", "Max replacements")}
                      help={t(
                        "option:dictionaries.maxReplacementsHelp",
                        "Probability controls whether this entry fires. Max replacements limits how many replacements happen when it does."
                      )}
                    />
                  }
              >
                <InputNumber min={0} style={{ width: "100%" }} placeholder="Unlimited" />
              </Form.Item>
              <Form.Item
                name={["timed_effects", "sticky"]}
                label={
                  <LabelWithHelp
                    label="Sticky (seconds)"
                    help="Keep this replacement active for additional messages after it fires. Use 0 to disable."
                  />
                }
                initialValue={0}
              >
                <InputNumber min={0} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item
                name={["timed_effects", "cooldown"]}
                label={
                  <LabelWithHelp
                    label="Cooldown (seconds)"
                    help="Minimum wait time before this entry can fire again. Use 0 to disable."
                  />
                }
                initialValue={0}
              >
                <InputNumber min={0} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item
                name={["timed_effects", "delay"]}
                label={
                  <LabelWithHelp
                    label="Delay (seconds)"
                    help="Wait time before this entry becomes eligible to run. Use 0 to disable."
                  />
                }
                initialValue={0}
              >
                <InputNumber min={0} style={{ width: "100%" }} />
              </Form.Item>
              <div className="flex gap-4">
                <Form.Item
                  name="enabled"
                  label={t("option:dictionaries.enabledLabel", "Enabled")}
                  valuePropName="checked"
                  initialValue={true}
                >
                  <Switch />
                </Form.Item>
                <Form.Item
                  name="case_sensitive"
                  label={
                    <LabelWithHelp
                      label={t("option:dictionaries.caseSensitiveLabel", "Case sensitive")}
                      help={t(
                        "option:dictionaries.caseSensitiveHelp",
                        "When off (default), 'KCl' matches 'kcl', 'KCL', etc. Recommended off for medical terms."
                      )}
                    />
                  }
                  valuePropName="checked"
                  initialValue={false}
                >
                  <Switch />
                </Form.Item>
              </div>
            </div>
          )}

          <Button
            type="primary"
            htmlType="submit"
            loading={adding}
            disabled={!!regexError || !!regexServerError}
            className="w-full mt-3"
          >
            {t("option:dictionaries.addEntryButton", "Add Entry")}
          </Button>
        </Form>
      </div>
    </div>
  )
}
