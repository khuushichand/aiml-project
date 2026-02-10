import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button, Collapse, Divider, Form, Input, Modal, Skeleton, Switch, Table, Tooltip, Tag, InputNumber, Select, Descriptions, Popover } from "antd"
import { useTranslation } from "react-i18next"
import React from "react"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { Pen, Trash2, Book, Play, ChevronDown, ChevronUp, AlertCircle, CheckCircle2, AlertTriangle, Loader2 } from "lucide-react"
import { useConfirmDanger } from "@/components/Common/confirm-danger"
import { useServerOnline } from "@/hooks/useServerOnline"
import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import { useAntdNotification } from "@/hooks/useAntdNotification"
import { LabelWithHelp } from "@/components/Common/LabelWithHelp"

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
  const [activateOnImport, setActivateOnImport] = React.useState(false)
  const [statsFor, setStatsFor] = React.useState<any | null>(null)
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

  const { data, status } = useQuery({
    queryKey: ['tldw:listDictionaries'],
    queryFn: async () => {
      await tldwClient.initialize()
      const res = await tldwClient.listDictionaries(false)
      return res?.dictionaries || []
    },
    enabled: isOnline
  })

  const { mutate: createDict, isPending: creating } = useMutation({
    mutationFn: (v: any) => tldwClient.createDictionary(v),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tldw:listDictionaries'] }); setOpen(false); createForm.resetFields() },
    onError: (e: any) => notification.error({ message: 'Error', description: e?.message || 'Failed to create dictionary' })
  })
  const { mutate: updateDict, isPending: updating } = useMutation({
    mutationFn: (v: any) => editId != null ? tldwClient.updateDictionary(editId, v) : Promise.resolve(null),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tldw:listDictionaries'] }); setOpenEdit(false); editForm.resetFields(); setEditId(null) },
    onError: (e: any) => notification.error({ message: 'Error', description: e?.message || 'Failed to update dictionary' })
  })
  const { mutate: deleteDict } = useMutation({
    mutationFn: (id: number) => tldwClient.deleteDictionary(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tldw:listDictionaries'] })
  })
  const { mutate: importDict, isPending: importing } = useMutation({
    mutationFn: ({ data, activate }: any) => tldwClient.importDictionaryJSON(data, activate),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tldw:listDictionaries'] }); setOpenImport(false) },
    onError: (e: any) => notification.error({ message: 'Import failed', description: e?.message })
  })

  const dictionariesUnsupported =
    !capsLoading && capabilities && !capabilities.hasChatDictionaries

  const columns = [
    { title: '', key: 'icon', width: 48, render: () => <Book className="w-5 h-5 text-text-muted" aria-hidden="true" /> },
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'Description', dataIndex: 'description', key: 'description', render: (v: string) => <span className="line-clamp-1">{v}</span> },
    { title: 'Active', dataIndex: 'is_active', key: 'is_active', render: (v: boolean) => v ? <Tag color="green">Active</Tag> : <Tag>Inactive</Tag> },
    { title: 'Entries', dataIndex: 'entry_count', key: 'entry_count' },
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
        <Tooltip title="Delete dictionary">
          <button
            className="min-w-[44px] min-h-[44px] flex items-center justify-center text-danger hover:bg-danger/10 rounded-md transition-colors"
            onClick={async () => {
              const ok = await confirmDanger({
                title: t('common:confirmTitle', { defaultValue: 'Please confirm' }),
                content: 'Delete dictionary?',
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
      <div className="flex justify-end gap-2">
        <Button onClick={() => setOpenImport(true)}>Import</Button>
        <Button type="primary" onClick={() => setOpen(true)}>New Dictionary</Button>
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
        <Table rowKey={(r: any) => r.id} dataSource={data} columns={columns as any} />
      )}

      <Modal title="Create Dictionary" open={open} onCancel={() => setOpen(false)} footer={null}>
        <Form layout="vertical" form={createForm} onFinish={(v) => createDict(v)}>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="description" label="Description"><Input /></Form.Item>
          <Button type="primary" htmlType="submit" loading={creating} className="w-full">Create</Button>
        </Form>
      </Modal>

      <Modal title="Edit Dictionary" open={openEdit} onCancel={() => setOpenEdit(false)} footer={null}>
        <Form layout="vertical" form={editForm} onFinish={(v) => updateDict(v)}>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="description" label="Description"><Input /></Form.Item>
          <Form.Item name="is_active" label="Active" valuePropName="checked"><Switch /></Form.Item>
          <Button type="primary" htmlType="submit" loading={updating} className="w-full">Save</Button>
        </Form>
      </Modal>

      <Modal title="Manage Entries" open={!!openEntries} onCancel={() => setOpenEntries(null)} footer={null}>
        {openEntries && <DictionaryEntryManager dictionaryId={openEntries} form={entryForm} />}
      </Modal>
      <Modal title="Import Dictionary (JSON)" open={openImport} onCancel={() => setOpenImport(false)} footer={null}>
        <div className="space-y-3">
          <input type="file" accept="application/json" onChange={async (e) => {
            const file = e.target.files?.[0]
            if (!file) return
            try {
              const text = await file.text()
              const parsed = JSON.parse(text)
              await importDict({ data: parsed, activate: activateOnImport })
            } catch (err: any) {
              notification.error({ message: 'Import failed', description: err?.message })
            } finally {
              (e.target as any).value = ''
            }
          }} />
          <label className="inline-flex items-center gap-2 text-sm"><input type="checkbox" checked={activateOnImport} onChange={(ev) => setActivateOnImport(ev.target.checked)} /> Activate after import</label>
        </div>
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

const DictionaryEntryManager: React.FC<{ dictionaryId: number; form: any }> = ({
  dictionaryId,
  form
}) => {
  const { t } = useTranslation(["common", "option"])
  const qc = useQueryClient()
  const confirmDanger = useConfirmDanger()
  const notification = useAntdNotification()
  const [validationStrict, setValidationStrict] = React.useState(false)
  const [validationReport, setValidationReport] = React.useState<any | null>(null)
  const [validationError, setValidationError] = React.useState<string | null>(null)
  const [previewText, setPreviewText] = React.useState("")
  const [previewTokenBudget, setPreviewTokenBudget] = React.useState<number | null>(1000)
  const [previewMaxIterations, setPreviewMaxIterations] = React.useState<number | null>(5)
  const [previewResult, setPreviewResult] = React.useState<any | null>(null)
  const [previewError, setPreviewError] = React.useState<string | null>(null)

  // Simple/Advanced mode toggle
  const [advancedMode, setAdvancedMode] = React.useState(false)

  // Inline regex validation state
  const [regexError, setRegexError] = React.useState<string | null>(null)

  // Entry editing state
  const [editingEntry, setEditingEntry] = React.useState<any | null>(null)
  const [editEntryForm] = Form.useForm()

  // Inline test popover state
  const [testingEntryId, setTestingEntryId] = React.useState<number | null>(null)
  const [inlineTestInput, setInlineTestInput] = React.useState("")
  const [inlineTestResult, setInlineTestResult] = React.useState<string | null>(null)

  const { data: dictionaryMeta } = useQuery({
    queryKey: ["tldw:getDictionary", dictionaryId],
    queryFn: async () => {
      await tldwClient.initialize()
      return await tldwClient.getDictionary(dictionaryId)
    }
  })

  const { data: entriesData, status: entriesStatus } = useQuery({
    queryKey: ["tldw:listDictionaryEntries", dictionaryId],
    queryFn: async () => {
      await tldwClient.initialize()
      const res = await tldwClient.listDictionaryEntries(dictionaryId)
      return res?.entries || []
    }
  })

  const entries = Array.isArray(entriesData) ? entriesData : []

  const { mutate: addEntry, isPending: adding } = useMutation({
    mutationFn: (v: any) => tldwClient.addDictionaryEntry(dictionaryId, v),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tldw:listDictionaryEntries", dictionaryId] })
      form.resetFields()
    }
  })
  const { mutate: deleteEntry } = useMutation({
    mutationFn: (id: number) => tldwClient.deleteDictionaryEntry(id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["tldw:listDictionaryEntries", dictionaryId] })
  })

  const { mutate: updateEntry, isPending: updatingEntry } = useMutation({
    mutationFn: ({ entryId, data }: { entryId: number; data: any }) =>
      tldwClient.updateDictionaryEntry(entryId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tldw:listDictionaryEntries", dictionaryId] })
      setEditingEntry(null)
      editEntryForm.resetFields()
      notification.success({ message: "Entry updated" })
    },
    onError: (e: any) => {
      notification.error({ message: "Update failed", description: e?.message })
    }
  })

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

  return (
    <div className="space-y-4">
      <Collapse
        ghost
        className="rounded-lg border border-border bg-surface2/40"
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
                <div className="flex flex-wrap items-center gap-2">
                  <Switch
                    checked={validationStrict}
                    onChange={setValidationStrict}
                  />
                  <span className="text-sm text-text">
                    {t(
                      "option:dictionariesTools.strictLabel",
                      "Strict validation"
                    )}
                  </span>
                  <Button
                    size="small"
                    onClick={() => runValidation()}
                    loading={validating}
                    disabled={entries.length === 0}>
                    {t(
                      "option:dictionariesTools.validateButton",
                      "Run validation"
                    )}
                  </Button>
                </div>
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
                              <span className="font-medium text-text">
                                {err?.code || "error"}:
                              </span>{" "}
                              {err?.message || String(err)}
                              {err?.field ? ` (${err.field})` : ""}
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
                              <span className="font-medium text-text">
                                {warn?.code || "warning"}:
                              </span>{" "}
                              {warn?.message || String(warn)}
                              {warn?.field ? ` (${warn.field})` : ""}
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
                          "option:dictionariesTools.processedTextLabel",
                          "Processed text"
                        )}
                      </div>
                      <Input.TextArea
                        rows={4}
                        value={previewResult.processed_text || ""}
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

      {entriesStatus === "pending" && <Skeleton active paragraph={{ rows: 4 }} />}
      {entriesStatus === "success" && (
        <Table
          size="small"
          rowKey={(r: any) => r.id}
          dataSource={entries}
          columns={[
            {
              title: "Pattern",
              dataIndex: "pattern",
              key: "pattern",
              render: (v: string, r: any) => (
                <span className="font-mono text-xs">
                  {v}
                  {r.type === "regex" && (
                    <Tag color="blue" className="ml-1 text-[10px]">regex</Tag>
                  )}
                </span>
              )
            },
            {
              title: "Replacement",
              dataIndex: "replacement",
              key: "replacement",
              render: (v: string) => <span className="text-xs">{v}</span>
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
                        editEntryForm.setFieldsValue(r)
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
                        if (ok) deleteEntry(r.id)
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
          onFinish={(v) => {
            if (editingEntry?.id) {
              updateEntry({ entryId: editingEntry.id, data: v })
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
          <Form.Item name="probability" label="Probability" initialValue={1}>
            <InputNumber min={0} max={1} step={0.01} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="group" label="Group">
            <Input />
          </Form.Item>
          <Form.Item name="max_replacements" label="Max Replacements">
            <InputNumber min={0} style={{ width: "100%" }} />
          </Form.Item>
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
          onFinish={(v) => {
            // Validate regex before submitting
            const entryType = form.getFieldValue("type") || "literal"
            if (entryType === "regex") {
              const pattern = form.getFieldValue("pattern")
              const error = validateRegexPattern(pattern)
              if (error) {
                setRegexError(error)
                return
              }
            }
            addEntry(v)
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
              validateStatus={regexError ? "error" : undefined}
              help={regexError}
            >
              <Input
                placeholder={t("option:dictionaries.patternPlaceholder", "e.g., KCl or /hel+o/i")}
                className="font-mono"
                onChange={(e) => {
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
              }}
            />
          </Form.Item>

          {/* Show validation warning for regex */}
          {regexError && (
            <div className="flex items-start gap-2 p-2 mb-3 rounded bg-danger/10 text-danger text-xs">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <div className="font-medium">Invalid regex pattern</div>
                <div className="text-danger/80">{regexError}</div>
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
              >
                <InputNumber min={0} max={1} step={0.01} style={{ width: "100%" }} />
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
                <Input placeholder={t("option:dictionaries.groupPlaceholder", "e.g., medications")} />
              </Form.Item>
              <Form.Item
                name="max_replacements"
                label={
                  <LabelWithHelp
                    label={t("option:dictionaries.maxReplacementsLabel", "Max replacements")}
                    help={t(
                      "option:dictionaries.maxReplacementsHelp",
                      "Limit how many times this pattern is replaced per message. Leave empty for unlimited."
                    )}
                  />
                }
              >
                <InputNumber min={0} style={{ width: "100%" }} placeholder="Unlimited" />
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
            disabled={!!regexError}
            className="w-full mt-3"
          >
            {t("option:dictionaries.addEntryButton", "Add Entry")}
          </Button>
        </Form>
      </div>
    </div>
  )
}
