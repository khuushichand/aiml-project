import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button, Form, Input, InputNumber, Modal, Skeleton, Switch, Table, Tooltip, Tag, Select, Descriptions, Empty, Popover, Divider, Drawer, Checkbox, Grid } from "antd"
import React from "react"
import { useConfirmDanger } from "@/components/Common/confirm-danger"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { Pen, Trash2, BookOpen, HelpCircle } from "lucide-react"
import { useServerOnline } from "@/hooks/useServerOnline"
import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import { useTranslation } from "react-i18next"
import { useAntdNotification } from "@/hooks/useAntdNotification"
import { useUndoNotification } from "@/hooks/useUndoNotification"
import { parseBulkEntries } from "./entryParsers"

// Helper component for form field labels with tooltips
const LabelWithHelp: React.FC<{ label: string; help: string }> = ({ label, help }) => (
  <span className="inline-flex items-center gap-1">
    {label}
    <Tooltip title={help}>
      <HelpCircle className="w-3.5 h-3.5 text-text-muted cursor-help" />
    </Tooltip>
  </span>
)

// Keyword preview component for real-time feedback
const KeywordPreview: React.FC<{ value?: string }> = ({ value }) => {
  if (!value) return null
  const keywords = value.split(',').map(k => k.trim()).filter(Boolean)
  if (keywords.length === 0) return null
  return (
    <div className="mt-1 flex flex-wrap gap-1">
      {keywords.map((k, i) => <Tag key={i}>{k}</Tag>)}
    </div>
  )
}

const normalizeKeywords = (value: any): string[] => {
  if (Array.isArray(value)) return value.map((v) => String(v).trim()).filter(Boolean)
  if (typeof value === 'string') {
    return value.split(',').map((k) => k.trim()).filter(Boolean)
  }
  return []
}

const buildMatchPreview = (keywordsValue: any, opts: { caseSensitive?: boolean; regexMatch?: boolean; wholeWord?: boolean }) => {
  const keyword = normalizeKeywords(keywordsValue)[0]
  if (!keyword) return "Add a keyword to see a preview."
  if (opts.regexMatch) {
    return `Regex enabled. Example pattern: /${keyword}/`
  }
  const lower = keyword.toLowerCase()
  const upper = keyword.toUpperCase()
  const caseExample = opts.caseSensitive ? `'${keyword}' only` : `'${lower}', '${upper}'`
  const wordExample = opts.wholeWord ? "whole-word matches" : "partial matches"
  return `Preview: ${caseExample}; ${wordExample}.`
}

export const WorldBooksManager: React.FC = () => {
  const isOnline = useServerOnline()
  const { t } = useTranslation(["option"])
  const screens = Grid.useBreakpoint()
  const qc = useQueryClient()
  const notification = useAntdNotification()
  const { showUndoNotification } = useUndoNotification()
  const [open, setOpen] = React.useState(false)
  const [openEdit, setOpenEdit] = React.useState(false)
  const [openEntries, setOpenEntries] = React.useState<null | { id: number; name: string; entryCount?: number }>(null)
  const [openAttach, setOpenAttach] = React.useState<null | number>(null)
  const [editId, setEditId] = React.useState<number | null>(null)
  const [openImport, setOpenImport] = React.useState(false)
  const [openMatrix, setOpenMatrix] = React.useState(false)
  const [mergeOnConflict, setMergeOnConflict] = React.useState(false)
  const [importPreview, setImportPreview] = React.useState<{ name?: string; entryCount: number; conflict?: boolean } | null>(null)
  const [importPayload, setImportPayload] = React.useState<any | null>(null)
  const [importError, setImportError] = React.useState<string | null>(null)
  const [importFileName, setImportFileName] = React.useState<string | null>(null)
  const [statsFor, setStatsFor] = React.useState<any | null>(null)
  const [exportingId, setExportingId] = React.useState<number | null>(null)
  const [statsLoadingId, setStatsLoadingId] = React.useState<number | null>(null)
  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()
  const [entryForm] = Form.useForm()
  const [attachForm] = Form.useForm()
  const confirmDanger = useConfirmDanger()
  const deleteTimersRef = React.useRef<Record<number, any>>({})
  const [pendingDeleteIds, setPendingDeleteIds] = React.useState<number[]>([])
  const [matrixPending, setMatrixPending] = React.useState<Record<string, boolean>>({})
  const [matrixBookFilter, setMatrixBookFilter] = React.useState('')
  const [matrixCharacterFilter, setMatrixCharacterFilter] = React.useState('')

  const { data, status } = useQuery({
    queryKey: ['tldw:listWorldBooks'],
    queryFn: async () => {
      await tldwClient.initialize()
      const res = await tldwClient.listWorldBooks(false)
      return res?.world_books || []
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
      const results = await Promise.all(
        (characters || []).map(async (c: any) => {
          try {
            const books = await tldwClient.listCharacterWorldBooks(c.id)
            return { character: c, books: books || [] }
          } catch {
            return { character: c, books: [] }
          }
        })
      )
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
    enabled: isOnline && !!characters && characters.length > 0
  })

  const getAttachedCharacters = React.useCallback(
    (worldBookId: number) => (attachmentsByBook && (attachmentsByBook as any)[worldBookId]) || [],
    [attachmentsByBook]
  )

  const { mutate: createWB, isPending: creating } = useMutation({
    mutationFn: (values: any) => tldwClient.createWorldBook(values),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tldw:listWorldBooks'] }); setOpen(false); createForm.resetFields() },
    onError: (e: any) => notification.error({ message: 'Error', description: e?.message || 'Failed to create world book' })
  })
  const { mutate: updateWB, isPending: updating } = useMutation({
    mutationFn: (values: any) => editId != null ? tldwClient.updateWorldBook(editId, values) : Promise.resolve(null),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tldw:listWorldBooks'] }); setOpenEdit(false); editForm.resetFields(); setEditId(null) },
    onError: (e: any) => notification.error({ message: 'Error', description: e?.message || 'Failed to update world book' })
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
      setOpenImport(false)
      setImportPreview(null)
      setImportPayload(null)
      setImportError(null)
      setImportFileName(null)
    },
    onError: (e: any) => notification.error({ message: 'Error', description: e?.message || 'Failed to import world book' })
  })

  const { mutateAsync: attachWB, isPending: attaching } = useMutation({
    mutationFn: ({ characterId, worldBookId }: { characterId: number; worldBookId: number }) =>
      tldwClient.attachWorldBookToCharacter(characterId, worldBookId),
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
    if (attachmentsLoading) return <span className="text-text-muted">Loading…</span>
    const attached = getAttachedCharacters(record.id)
    if (!attached || attached.length === 0) return <span className="text-text-muted">—</span>
    const visible = attached.slice(0, 2)
    const overflow = attached.length - visible.length
    return (
      <Popover
        trigger="click"
        title="Attached Characters"
        content={
          <div className="space-y-2">
            {attached.map((c: any) => (
              <div key={c.id} className="flex items-center justify-between gap-2">
                <span className="text-sm">{c.name || `Character ${c.id}`}</span>
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
        <div className="flex flex-wrap gap-1 cursor-pointer">
          {visible.map((c: any) => <Tag key={c.id}>{c.name || `Character ${c.id}`}</Tag>)}
          {overflow > 0 && <Tag>+{overflow}</Tag>}
        </div>
      </Popover>
    )
  }

  const isAttached = React.useCallback((worldBookId: number, characterId: number) => {
    const attached = getAttachedCharacters(worldBookId)
    return attached.some((c: any) => c.id === characterId)
  }, [getAttachedCharacters])

  const handleMatrixToggle = async (worldBookId: number, characterId: number, next: boolean) => {
    const key = `${worldBookId}:${characterId}`
    if (matrixPending[key]) return
    setMatrixPending((prev) => ({ ...prev, [key]: true }))
    try {
      if (next) {
        await attachWB({ characterId, worldBookId })
      } else {
        await detachWB({ characterId, worldBookId })
      }
    } finally {
      setMatrixPending((prev) => {
        const copy = { ...prev }
        delete copy[key]
        return copy
      })
    }
  }

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
    setOpenEntries(null)
    entryForm.resetFields()
  }

  React.useEffect(() => {
    return () => {
      Object.values(deleteTimersRef.current).forEach((t) => clearTimeout(t))
      deleteTimersRef.current = {}
    }
  }, [])

  const columns = [
    { title: '', key: 'icon', width: 40, render: () => <BookOpen className="w-4 h-4" /> },
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'Description', dataIndex: 'description', key: 'description', render: (v: string) => <span className="line-clamp-1">{v}</span> },
    { title: 'Attached To', key: 'attached_to', render: (_: any, record: any) => renderAttachedCell(record) },
    { title: 'Enabled', dataIndex: 'enabled', key: 'enabled', render: (v: boolean) => v ? <Tag color="green">Enabled</Tag> : <Tag>Disabled</Tag> },
    { title: 'Entries', dataIndex: 'entry_count', key: 'entry_count' },
    { title: 'Actions', key: 'actions', render: (_: any, record: any) => (
      <div className="flex gap-2">
        <Tooltip title="Edit">
          <Button
            type="text"
            size="small"
            aria-label="Edit world book"
            icon={<Pen className="w-4 h-4" />}
            onClick={() => { setEditId(record.id); editForm.setFieldsValue(record); setOpenEdit(true) }}
          />
        </Tooltip>
        <Tooltip title="Manage Entries">
          <Button type="text" size="small" onClick={() => setOpenEntries({ id: record.id, name: record.name, entryCount: record.entry_count })}>
            Entries
          </Button>
        </Tooltip>
        <Tooltip title="Manage Character Links">
          <Button type="text" size="small" onClick={() => setOpenAttach(record.id)}>
            Link
          </Button>
        </Tooltip>
        <Tooltip title="Export JSON">
          <Button
            type="text"
            size="small"
            loading={exportingId === record.id}
            onClick={async () => {
              setExportingId(record.id)
              try {
                const exp = await tldwClient.exportWorldBook(record.id)
                const blob = new Blob([JSON.stringify(exp, null, 2)], { type: 'application/json' })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `${record.name || 'world-book'}.json`
                a.click()
                URL.revokeObjectURL(url)
              } catch (e: any) {
                notification.error({ message: 'Export failed', description: e?.message })
              } finally {
                setExportingId(null)
              }
            }}
          >
            Export
          </Button>
        </Tooltip>
        <Tooltip title="Statistics">
          <Button
            type="text"
            size="small"
            loading={statsLoadingId === record.id}
            onClick={async () => {
              setStatsLoadingId(record.id)
              try {
                const s = await tldwClient.worldBookStatistics(record.id)
                setStatsFor(s)
              } catch (e: any) {
                notification.error({ message: 'Stats failed', description: e?.message })
              } finally {
                setStatsLoadingId(null)
              }
            }}
          >
            Stats
          </Button>
        </Tooltip>
        <Tooltip title="Delete">
          <Button
            type="text"
            size="small"
            danger
            aria-label="Delete world book"
            icon={<Trash2 className="w-4 h-4" />}
            disabled={deleting || pendingDeleteIds.includes(record.id)}
            onClick={async () => {
              const entryCount = record.entry_count || 0
              const attached = attachmentsLoading ? null : getAttachedCharacters(record.id)
              const attachedNames = attached ? attached.map((c: any) => c.name || `Character ${c.id}`) : []
              const attachedSummary = attachmentsLoading
                ? 'Attachment info loading'
                : attachedNames.length === 0
                  ? 'No character attachments'
                  : `${attachedNames.length} attached (${attachedNames.slice(0, 3).join(', ')}${attachedNames.length > 3 ? ` +${attachedNames.length - 3} more` : ''})`
              const ok = await confirmDanger({
                title: `Delete "${record.name}"?`,
                content: (
                  <div className="space-y-2">
                    <p>This will permanently remove:</p>
                    <ul className="list-disc list-inside text-sm">
                      <li>{entryCount} {entryCount === 1 ? 'entry' : 'entries'}</li>
                      <li>{attachedSummary}</li>
                    </ul>
                    <p className="text-danger text-sm mt-2">Deletion will run after 10 seconds unless you undo.</p>
                  </div>
                ),
                okText: "Delete",
                cancelText: "Cancel",
                autoFocusButton: "ok"
              })
              if (ok) {
                if (deleteTimersRef.current[record.id]) return
                setPendingDeleteIds((prev) => [...prev, record.id])
                deleteTimersRef.current[record.id] = setTimeout(() => {
                  deleteWB(record.id)
                  setPendingDeleteIds((prev) => prev.filter((id) => id !== record.id))
                  delete deleteTimersRef.current[record.id]
                }, 10000)

                showUndoNotification({
                  title: "World book deletion scheduled",
                  description: `“${record.name}” will be deleted in 10 seconds.`,
                  duration: 10,
                  onUndo: () => {
                    if (deleteTimersRef.current[record.id]) {
                      clearTimeout(deleteTimersRef.current[record.id])
                      delete deleteTimersRef.current[record.id]
                    }
                    setPendingDeleteIds((prev) => prev.filter((id) => id !== record.id))
                  }
                })
              }
            }}
          />
        </Tooltip>
      </div>
    )}
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
    <div className="space-y-4">
      <div className="flex justify-end gap-2">
        <Button onClick={() => setOpenMatrix(true)}>Relationship Matrix</Button>
        <Button onClick={() => setOpenImport(true)}>Import</Button>
        <Button type="primary" onClick={() => setOpen(true)}>New World Book</Button>
      </div>
      {status === 'pending' && <Skeleton active paragraph={{ rows: 6 }} />}
      {status === 'success' && <Table rowKey={(r: any) => r.id} dataSource={data} columns={columns as any} />}

      <Modal title="Create World Book" open={open} onCancel={handleCloseCreate} footer={null}>
        <Form layout="vertical" form={createForm} onFinish={(v) => createWB(v)}>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="description" label="Description"><Input /></Form.Item>
          <Form.Item name="enabled" label="Enabled" valuePropName="checked"><Switch defaultChecked /></Form.Item>
          <details className="mb-4">
            <summary className="cursor-pointer text-sm text-text-muted hover:text-text">Advanced Settings</summary>
            <div className="mt-3 pl-2 border-l-2 border-border space-y-0">
              <Form.Item
                name="scan_depth"
                label={<LabelWithHelp label="Scan Depth" help="How many recent messages to search for keywords (1-20). Higher values find more matches but use more processing." />}
              >
                <InputNumber style={{ width: '100%' }} min={1} max={20} placeholder="Default: 5" />
              </Form.Item>
              <Form.Item
                name="token_budget"
                label={<LabelWithHelp label="Token Budget" help="Maximum characters of world info to inject into context (~4 characters = 1 token). This is the most impactful setting for context usage." />}
              >
                <InputNumber style={{ width: '100%' }} min={0} placeholder="Default: 2048" />
              </Form.Item>
              <Form.Item
                name="recursive_scanning"
                label={<LabelWithHelp label="Recursive Scanning" help="Also search matched content for additional keyword matches. Useful for interconnected lore but may increase context usage." />}
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
            </div>
          </details>
          <Button type="primary" htmlType="submit" loading={creating} className="w-full">Create</Button>
        </Form>
      </Modal>

      <Modal
        title="Import World Book (JSON)"
        open={openImport}
        onCancel={() => {
          setOpenImport(false)
          setImportPreview(null)
          setImportPayload(null)
          setImportError(null)
          setImportFileName(null)
        }}
        footer={null}
      >
        <div className="space-y-3">
          <input type="file" accept="application/json" onChange={async (e) => {
            const file = e.target.files?.[0]
            if (!file) return
            try {
              const text = await file.text()
              const parsed = JSON.parse(text)
              const payload = parsed.world_book && parsed.entries ? parsed : { world_book: parsed.world_book || parsed, entries: parsed.entries || [] }
              const name = payload?.world_book?.name
              const entryCount = Array.isArray(payload?.entries) ? payload.entries.length : 0
              const conflict = !!(data || []).find((wb: any) => wb.name === name)
              setImportPayload(payload)
              setImportPreview({ name, entryCount, conflict })
              setImportFileName(file.name)
              if (!payload?.world_book || !name) {
                setImportError('Invalid file: missing world_book.name')
              } else {
                setImportError(null)
              }
            } catch (err: any) {
              setImportError(err?.message || 'Invalid JSON')
              setImportPreview(null)
              setImportPayload(null)
            } finally {
              (e.target as any).value = ''
            }
          }} />
          <label className="inline-flex items-center gap-2 text-sm"><input type="checkbox" checked={mergeOnConflict} onChange={(ev) => setMergeOnConflict(ev.target.checked)} /> Merge on conflict</label>
          {importFileName && <p className="text-xs text-text-muted">Selected: {importFileName}</p>}
          {importError && <p className="text-sm text-danger">{importError}</p>}
          {importPreview && !importError && (
            <div className="p-3 rounded bg-surface-secondary text-sm space-y-1">
              <p><strong>Will import:</strong> {importPreview.name}</p>
              <p><strong>Entries:</strong> {importPreview.entryCount}</p>
              {importPreview.conflict && <p className="text-warning">Name conflict detected. Enable “Merge on conflict” to update existing.</p>}
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

      <Modal title="World Book Statistics" open={!!statsFor} onCancel={() => setStatsFor(null)} footer={null}>
        {statsFor && (
          <Descriptions size="small" bordered column={1}>
            <Descriptions.Item label="ID">{statsFor.world_book_id}</Descriptions.Item>
            <Descriptions.Item label="Name">{statsFor.name}</Descriptions.Item>
            <Descriptions.Item label="Total Entries">{statsFor.total_entries}</Descriptions.Item>
            <Descriptions.Item label="Enabled Entries">{statsFor.enabled_entries}</Descriptions.Item>
            <Descriptions.Item label="Disabled Entries">{statsFor.disabled_entries}</Descriptions.Item>
            <Descriptions.Item label="Total Keywords">{statsFor.total_keywords}</Descriptions.Item>
            <Descriptions.Item label="Regex Entries">{statsFor.regex_entries}</Descriptions.Item>
            <Descriptions.Item label="Case Sensitive Entries">{statsFor.case_sensitive_entries}</Descriptions.Item>
            <Descriptions.Item label="Average Priority">{statsFor.average_priority}</Descriptions.Item>
            <Descriptions.Item label="Total Content Length">{statsFor.total_content_length}</Descriptions.Item>
            <Descriptions.Item label="Estimated Tokens">{statsFor.estimated_tokens}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>

      <Modal title="Edit World Book" open={openEdit} onCancel={handleCloseEdit} footer={null}>
        <Form layout="vertical" form={editForm} onFinish={(v) => updateWB(v)}>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="description" label="Description"><Input /></Form.Item>
          <Form.Item name="enabled" label="Enabled" valuePropName="checked"><Switch /></Form.Item>
          <details className="mb-4">
            <summary className="cursor-pointer text-sm text-text-muted hover:text-text">Advanced Settings</summary>
            <div className="mt-3 pl-2 border-l-2 border-border space-y-0">
              <Form.Item
                name="scan_depth"
                label={<LabelWithHelp label="Scan Depth" help="How many recent messages to search for keywords (1-20). Higher values find more matches but use more processing." />}
              >
                <InputNumber style={{ width: '100%' }} min={1} max={20} placeholder="Default: 5" />
              </Form.Item>
              <Form.Item
                name="token_budget"
                label={<LabelWithHelp label="Token Budget" help="Maximum characters of world info to inject into context (~4 characters = 1 token). This is the most impactful setting for context usage." />}
              >
                <InputNumber style={{ width: '100%' }} min={0} placeholder="Default: 2048" />
              </Form.Item>
              <Form.Item
                name="recursive_scanning"
                label={<LabelWithHelp label="Recursive Scanning" help="Also search matched content for additional keyword matches. Useful for interconnected lore but may increase context usage." />}
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
            </div>
          </details>
          <Button type="primary" htmlType="submit" loading={updating} className="w-full">Save</Button>
        </Form>
      </Modal>

      <Drawer
        title={(
          <div className="space-y-1">
            <div className="text-xs text-text-muted">World Books &gt; {openEntries?.name || ''} &gt; Entries</div>
            <div className="font-semibold">Entries: {openEntries?.name || ''}</div>
          </div>
        )}
        placement="right"
        width={screens.md ? "60vw" : "100%"}
        open={!!openEntries}
        onClose={handleCloseEntries}
        destroyOnHidden
      >
        {openEntries && (
          <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
            <Tag color="blue">Editing: {openEntries.name}</Tag>
            <Tag>Entries: {openEntries.entryCount ?? '—'}</Tag>
            <Tag>Attached: {getAttachedCharacters(openEntries.id).length}</Tag>
          </div>
        )}
        <EntryManager worldBookId={openEntries?.id!} form={entryForm} />
      </Drawer>

      <Modal
        title="World Book ↔ Character Matrix"
        open={openMatrix}
        onCancel={() => setOpenMatrix(false)}
        footer={null}
        width="90vw"
      >
        <div className="text-sm text-text-muted mb-3">
          Toggle checkboxes to attach or detach world books from characters.
        </div>
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
        <div className="overflow-x-auto border border-border rounded">
          <Table
            size="small"
            pagination={false}
            scroll={{ x: "max-content" }}
            rowKey={(r: any) => r.id}
            dataSource={filteredBooks}
            columns={[
              { title: 'World Book', dataIndex: 'name', key: 'name', fixed: 'left', width: 200 },
              ...(filteredCharacters || []).map((c: any) => ({
                title: (
                  <Tooltip title={c.name}>
                    <span className="truncate max-w-[140px] inline-block">{c.name}</span>
                  </Tooltip>
                ),
                key: `char-${c.id}`,
                width: 120,
                render: (_: any, record: any) => {
                  const checked = isAttached(record.id, c.id)
                  const pending = !!matrixPending[`${record.id}:${c.id}`]
                  return (
                    <Checkbox
                      checked={checked}
                      disabled={pending || attachmentsLoading}
                      onChange={(e) => handleMatrixToggle(record.id, c.id, e.target.checked)}
                    />
                  )
                }
              }))
            ] as any}
          />
        </div>
      </Modal>

      <Modal title="Manage Character Attachments" open={!!openAttach} onCancel={() => setOpenAttach(null)} footer={null}>
        <div className="space-y-4">
          <div>
            <h4 className="text-sm font-medium mb-2">Attached Characters</h4>
            {openAttach && getAttachedCharacters(openAttach).length > 0 ? (
              <div className="space-y-2">
                {getAttachedCharacters(openAttach).map((c: any) => (
                  <div key={c.id} className="flex items-center justify-between gap-2">
                    <span className="text-sm">{c.name || `Character ${c.id}`}</span>
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
            <Form.Item name="character_id" label="Add Character" rules={[{ required: true }]}>
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
            <Button type="primary" htmlType="submit" className="w-full" loading={attaching}>Attach</Button>
          </Form>
        </div>
      </Modal>
    </div>
  )
}

const EntryManager: React.FC<{ worldBookId: number; form: any }> = ({ worldBookId, form }) => {
  const qc = useQueryClient()
  const notification = useAntdNotification()
  const confirmDanger = useConfirmDanger()
  const [editingEntry, setEditingEntry] = React.useState<any | null>(null)
  const [editForm] = Form.useForm()
  const [keywordValue, setKeywordValue] = React.useState('')
  const [bulkMode, setBulkMode] = React.useState(false)
  const [bulkText, setBulkText] = React.useState('')
  const [bulkAdding, setBulkAdding] = React.useState(false)
  const [selectedRowKeys, setSelectedRowKeys] = React.useState<React.Key[]>([])
  const addRegexMatch = Form.useWatch('regex_match', form)
  const addCaseSensitive = Form.useWatch('case_sensitive', form)
  const addWholeWord = Form.useWatch('whole_word_match', form)
  const addKeywordsWatch = Form.useWatch('keywords', form)
  const editRegexMatch = Form.useWatch('regex_match', editForm)
  const editCaseSensitive = Form.useWatch('case_sensitive', editForm)
  const editWholeWord = Form.useWatch('whole_word_match', editForm)
  const editKeywordsWatch = Form.useWatch('keywords', editForm)

  const { data, status } = useQuery({
    queryKey: ['tldw:listWorldBookEntries', worldBookId],
    queryFn: async () => {
      await tldwClient.initialize()
      const res = await tldwClient.listWorldBookEntries(worldBookId, false)
      return res?.entries || []
    }
  })
  const { mutate: addEntry, isPending: adding } = useMutation({
    mutationFn: (v: any) => tldwClient.addWorldBookEntry(worldBookId, { ...v, keywords: normalizeKeywords(v.keywords) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tldw:listWorldBookEntries', worldBookId] }); form.resetFields(); setKeywordValue('') },
    onError: (e: any) => notification.error({ message: 'Error', description: e?.message || 'Failed to add entry' })
  })
  const { mutate: updateEntry, isPending: updating } = useMutation({
    mutationFn: (v: any) => editingEntry ? tldwClient.updateWorldBookEntry(editingEntry.entry_id, { ...v, keywords: normalizeKeywords(v.keywords) }) : Promise.resolve(null),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tldw:listWorldBookEntries', worldBookId] }); setEditingEntry(null); editForm.resetFields() },
    onError: (e: any) => notification.error({ message: 'Error', description: e?.message || 'Failed to update entry' })
  })
  const { mutate: deleteEntry } = useMutation({
    mutationFn: (id: number) => tldwClient.deleteWorldBookEntry(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tldw:listWorldBookEntries', worldBookId] })
  })
  const { mutateAsync: bulkOperate, isPending: bulkPending } = useMutation({
    mutationFn: (payload: { entry_ids: number[]; operation: string; priority?: number }) =>
      tldwClient.bulkWorldBookEntries(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tldw:listWorldBookEntries', worldBookId] })
      setSelectedRowKeys([])
    },
    onError: (e: any) => notification.error({ message: 'Error', description: e?.message || 'Bulk operation failed' })
  })

  const openEditModal = (entry: any) => {
    setEditingEntry(entry)
    editForm.setFieldsValue({
      keywords: (entry.keywords || []).join(', '),
      content: entry.content,
      priority: entry.priority,
      enabled: entry.enabled,
      case_sensitive: entry.case_sensitive,
      regex_match: entry.regex_match,
      whole_word_match: entry.whole_word_match
    })
  }

  const keywordIndex = React.useMemo(() => {
    const map = new Map<string, { count: number; contentVariants: Set<string> }>()
    ;(data || []).forEach((entry: any) => {
      ;(entry.keywords || []).forEach((kw: string) => {
        const key = String(kw).trim()
        if (!key) return
        const current = map.get(key) || { count: 0, contentVariants: new Set<string>() }
        current.count += 1
        current.contentVariants.add(entry.content || '')
        map.set(key, current)
      })
    })
    return Array.from(map.entries())
      .map(([keyword, info]) => ({
        keyword,
        count: info.count,
        conflict: info.contentVariants.size > 1,
        variantCount: info.contentVariants.size
      }))
      .sort((a, b) => b.count - a.count)
  }, [data])

  const bulkParse = React.useMemo(() => parseBulkEntries(bulkText), [bulkText])

  const handleBulkAction = async (operation: "enable" | "disable" | "delete") => {
    if (selectedRowKeys.length === 0) return
    if (operation === "delete") {
      const ok = await confirmDanger({
        title: "Delete selected entries?",
        content: `This will permanently remove ${selectedRowKeys.length} entries.`,
        okText: "Delete",
        cancelText: "Cancel"
      })
      if (!ok) return
    }
    await bulkOperate({ entry_ids: selectedRowKeys as number[], operation })
    notification.success({ message: "Bulk action complete" })
  }

  return (
    <div className="space-y-3">
      {status === 'pending' && <Skeleton active paragraph={{ rows: 4 }} />}
      {status === 'success' && data.length === 0 && (
        <Empty
          description={
            <div className="text-center space-y-2">
              <p className="text-text-muted">No entries yet</p>
              <p className="text-sm text-text-muted">
                Entries define keyword→content mappings. When a keyword appears
                in chat, the content is injected into the AI's context.
              </p>
              <div className="text-left bg-surface-secondary p-3 rounded text-sm mt-3">
                <p className="font-medium mb-1">Example:</p>
                <p><strong>Keywords:</strong> Hermione, Granger</p>
                <p><strong>Content:</strong> Hermione Granger is a brilliant witch and one of Harry's closest friends. She values knowledge and justice.</p>
              </div>
            </div>
          }
        />
      )}
      {status === 'success' && data.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-text-muted">{selectedRowKeys.length} selected</span>
            <div className="flex gap-2">
              <Button size="small" disabled={selectedRowKeys.length === 0} loading={bulkPending} onClick={() => handleBulkAction("enable")}>
                Enable
              </Button>
              <Button size="small" disabled={selectedRowKeys.length === 0} loading={bulkPending} onClick={() => handleBulkAction("disable")}>
                Disable
              </Button>
              <Button size="small" danger disabled={selectedRowKeys.length === 0} loading={bulkPending} onClick={() => handleBulkAction("delete")}>
                Delete
              </Button>
            </div>
          </div>
          <Table
            size="small"
            rowKey={(r: any) => r.entry_id}
            rowSelection={{
              selectedRowKeys,
              onChange: (keys) => setSelectedRowKeys(keys)
            }}
            dataSource={data}
            columns={[
              { title: 'Keywords', dataIndex: 'keywords', key: 'keywords', width: 200, render: (arr: string[]) => <div className="flex flex-wrap gap-1">{(arr||[]).map((k) => <Tag key={k}>{k}</Tag>)}</div> },
              { title: 'Content', dataIndex: 'content', key: 'content', render: (v: string) => <span className="line-clamp-2">{v}</span> },
              { title: 'Priority', dataIndex: 'priority', key: 'priority', width: 70 },
              { title: 'Enabled', dataIndex: 'enabled', key: 'enabled', width: 70, render: (v: boolean) => v ? <Tag color="green">Yes</Tag> : <Tag>No</Tag> },
              { title: 'Actions', key: 'actions', width: 80, render: (_: any, r: any) => (
                <div className="flex gap-2">
                  <Tooltip title="Edit">
                    <Button
                      type="text"
                      size="small"
                      aria-label="Edit entry"
                      icon={<Pen className="w-4 h-4" />}
                      onClick={() => openEditModal(r)}
                    />
                  </Tooltip>
                  <Tooltip title="Delete">
                    <Button
                      type="text"
                      size="small"
                      danger
                      aria-label="Delete entry"
                      icon={<Trash2 className="w-4 h-4" />}
                      onClick={async () => {
                        const ok = await confirmDanger({
                          title: 'Delete entry?',
                          content: `This will remove the entry with keywords: ${(r.keywords || []).join(', ') || '(none)'}`,
                          okText: 'Delete',
                          cancelText: 'Cancel'
                        })
                        if (ok) deleteEntry(r.entry_id)
                      }}
                    />
                  </Tooltip>
                </div>
              ) }
            ] as any}
          />
          <details className="mt-2">
            <summary className="cursor-pointer text-sm text-text-muted hover:text-text">Keyword Index</summary>
            <div className="mt-2 flex flex-wrap gap-1">
              {keywordIndex.length === 0 && <span className="text-sm text-text-muted">No keywords yet</span>}
              {keywordIndex.map((k) => (
                <Tooltip key={k.keyword} title={k.conflict ? `Conflict: ${k.variantCount} content variations` : `${k.count} entries`}>
                  <Tag color={k.conflict ? "red" : undefined}>{k.keyword} ({k.count})</Tag>
                </Tooltip>
              ))}
            </div>
          </details>
        </div>
      )}

      {/* Edit Entry Modal */}
      <Modal
        title="Edit Entry"
        open={!!editingEntry}
        onCancel={async () => {
          if (editForm.isFieldsTouched()) {
            const ok = await confirmDanger({
              title: "Discard changes?",
              content: "You have unsaved changes. Are you sure you want to close?",
              okText: "Discard",
              cancelText: "Keep editing"
            })
            if (!ok) return
          }
          setEditingEntry(null)
          editForm.resetFields()
        }}
        footer={null}
      >
        <Form layout="vertical" form={editForm} onFinish={(v) => updateEntry(v)}>
          <Form.Item name="keywords" label="Keywords (comma separated)">
            <Input placeholder="e.g. Hermione, Hogwarts" />
          </Form.Item>
          <Form.Item name="content" label="Content" rules={[{ required: true }]}>
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
          </Form.Item>
          <Form.Item
            name="priority"
            label={<LabelWithHelp label="Priority" help="Higher values = more important (0-100). Higher priority entries are selected first when token budget is limited." />}
          >
            <InputNumber style={{ width: '100%' }} min={0} max={100} />
          </Form.Item>
          <Form.Item name="enabled" label="Enabled" valuePropName="checked"><Switch /></Form.Item>
          <details className="mb-4">
            <summary className="cursor-pointer text-sm text-text-muted hover:text-text">Matching Options</summary>
            <p className="text-xs text-text-muted mt-1 mb-2">These options control how keywords are matched in chat messages.</p>
            <div className="mt-2 pl-2 border-l-2 border-border space-y-0">
              <Form.Item name="case_sensitive" label="Case Sensitive" valuePropName="checked"><Switch /></Form.Item>
              <Form.Item name="regex_match" label="Regex Match" valuePropName="checked">
                <Switch onChange={(checked) => { if (checked) editForm.setFieldsValue({ whole_word_match: false }) }} />
              </Form.Item>
              {!editRegexMatch && (
                <Form.Item name="whole_word_match" label="Whole Word Match" valuePropName="checked"><Switch /></Form.Item>
              )}
            </div>
            <p className="text-xs text-text-muted mt-2">
              {buildMatchPreview(editKeywordsWatch, {
                caseSensitive: editCaseSensitive,
                regexMatch: editRegexMatch,
                wholeWord: editWholeWord
              })}
            </p>
          </details>
          <Button type="primary" htmlType="submit" loading={updating} className="w-full">Save Changes</Button>
        </Form>
      </Modal>

      {/* Add Entry Form */}
      <div className="border-t border-border pt-4 mt-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-medium">Add New Entry</h4>
          <div className="flex items-center gap-2">
            <Switch checked={bulkMode} onChange={setBulkMode} />
            <span className="text-xs text-text-muted">Bulk add mode</span>
          </div>
        </div>
        {!bulkMode && (
          <Form layout="vertical" form={form} onFinish={(v) => addEntry(v)}>
            <Form.Item name="keywords" label="Keywords (comma separated)">
              <Input
                placeholder="e.g. Hermione, Hogwarts"
                onChange={(e) => setKeywordValue(e.target.value)}
              />
            </Form.Item>
            <KeywordPreview value={keywordValue} />
            <Form.Item name="content" label="Content" rules={[{ required: true }]}>
              <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
            </Form.Item>
            <Form.Item
              name="priority"
              label={<LabelWithHelp label="Priority" help="Higher values = more important (0-100). Higher priority entries are selected first when token budget is limited." />}
            >
              <InputNumber style={{ width: '100%' }} min={0} max={100} placeholder="Default: 50" />
            </Form.Item>
            <Form.Item name="enabled" label="Enabled" valuePropName="checked"><Switch defaultChecked /></Form.Item>
          <details className="mb-4">
            <summary className="cursor-pointer text-sm text-text-muted hover:text-text">Matching Options</summary>
            <p className="text-xs text-text-muted mt-1 mb-2">These options control how keywords are matched in chat messages.</p>
            <div className="mt-2 pl-2 border-l-2 border-border space-y-0">
              <Form.Item name="case_sensitive" label="Case Sensitive" valuePropName="checked"><Switch /></Form.Item>
              <Form.Item name="regex_match" label="Regex Match" valuePropName="checked">
                <Switch onChange={(checked) => { if (checked) form.setFieldsValue({ whole_word_match: false }) }} />
              </Form.Item>
              {!addRegexMatch && (
                <Form.Item name="whole_word_match" label="Whole Word Match" valuePropName="checked"><Switch /></Form.Item>
              )}
            </div>
            <p className="text-xs text-text-muted mt-2">
              {buildMatchPreview(addKeywordsWatch, {
                caseSensitive: addCaseSensitive,
                regexMatch: addRegexMatch,
                wholeWord: addWholeWord
              })}
            </p>
          </details>
          <Button type="primary" htmlType="submit" loading={adding} className="w-full">Add Entry</Button>
        </Form>
      )}
        {bulkMode && (
          <div className="space-y-2">
            <Input.TextArea
              value={bulkText}
              onChange={(e) => setBulkText(e.target.value)}
              autoSize={{ minRows: 4, maxRows: 10 }}
              placeholder="One per line: keyword1, keyword2 -> content"
            />
            {bulkParse.errors.length > 0 && (
              <div className="text-sm text-danger space-y-1">
                {bulkParse.errors.map((err, i) => <p key={i}>{err}</p>)}
              </div>
            )}
            <div className="text-xs text-text-muted">Parsed entries: {bulkParse.entries.length}</div>
            <Button
              type="primary"
              className="w-full"
              loading={bulkAdding}
              disabled={bulkParse.entries.length === 0 || bulkParse.errors.length > 0}
              onClick={async () => {
                setBulkAdding(true)
                try {
                  for (const entry of bulkParse.entries) {
                    await tldwClient.addWorldBookEntry(worldBookId, entry)
                  }
                  notification.success({ message: `Added ${bulkParse.entries.length} entries` })
                  qc.invalidateQueries({ queryKey: ['tldw:listWorldBookEntries', worldBookId] })
                  setBulkText('')
                } catch (err: any) {
                  notification.error({ message: 'Bulk add failed', description: err?.message })
                } finally {
                  setBulkAdding(false)
                }
              }}
            >
              Add Entries
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
