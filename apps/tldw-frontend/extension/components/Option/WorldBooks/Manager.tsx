import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Skeleton,
  Switch,
  Table,
  Tooltip,
  Tag,
  Select,
  Descriptions
} from "antd"
import type { ColumnsType } from "antd/es/table"
import type { FormInstance } from "antd/es/form"
import React from "react"
import { useConfirmDanger } from "@/components/Common/confirm-danger"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { Pen, Trash2, BookOpen } from "lucide-react"
import { useServerOnline } from "@/hooks/useServerOnline"
import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import { useTranslation } from "react-i18next"
import { useAntdNotification } from "@/hooks/useAntdNotification"

type WorldBook = {
  id: number
  name?: string
  description?: string | null
  enabled?: boolean
  entry_count?: number
  scan_depth?: number
  token_budget?: number
  recursive_scanning?: boolean
}

type WorldBookStats = {
  world_book_id?: number
  name?: string
  total_entries?: number
  enabled_entries?: number
  disabled_entries?: number
  total_keywords?: number
  regex_entries?: number
  case_sensitive_entries?: number
  average_priority?: number
  total_content_length?: number
  estimated_tokens?: number
}

type WorldBookEntry = {
  entry_id: number
  keywords?: string[]
  content?: string
  enabled?: boolean
}

type Character = {
  id: number
  name?: string
}

type AttachFormValues = {
  character_id?: number
}

const getErrorMessage = (err: unknown): string | undefined => {
  if (!err || typeof err !== "object") return undefined
  const record = err as Record<string, unknown>
  return typeof record.message === "string" ? record.message : undefined
}

export const WorldBooksManager: React.FC = () => {
  const isOnline = useServerOnline()
  const { t } = useTranslation(["option"])
  const qc = useQueryClient()
  const notification = useAntdNotification()
  const [open, setOpen] = React.useState(false)
  const [openEdit, setOpenEdit] = React.useState(false)
  const [openEntries, setOpenEntries] = React.useState<null | number>(null)
  const [openAttach, setOpenAttach] = React.useState<null | number>(null)
  const [editId, setEditId] = React.useState<number | null>(null)
  const [openImport, setOpenImport] = React.useState(false)
  const [mergeOnConflict, setMergeOnConflict] = React.useState(false)
  const [statsFor, setStatsFor] = React.useState<WorldBookStats | null>(null)
  const [createForm] = Form.useForm<Record<string, unknown>>()
  const [editForm] = Form.useForm<Record<string, unknown>>()
  const [entryForm] = Form.useForm<Record<string, unknown>>()
  const [attachForm] = Form.useForm<AttachFormValues>()
  const confirmDanger = useConfirmDanger()

  const { data, status } = useQuery<WorldBook[]>({
    queryKey: ['tldw:listWorldBooks'],
    queryFn: async () => {
      await tldwClient.initialize()
      const res = await tldwClient.listWorldBooks(false)
      return Array.isArray(res?.world_books) ? (res.world_books as WorldBook[]) : []
    },
    enabled: isOnline
  })

  const { data: characters } = useQuery<Character[]>({
    queryKey: ['tldw:listCharactersForWB'],
    queryFn: async () => {
      await tldwClient.initialize()
      const res = await tldwClient.listCharacters()
      return Array.isArray(res) ? (res as Character[]) : []
    }
  })

  const { mutate: createWB, isPending: creating } = useMutation({
    mutationFn: (values: Record<string, unknown>) =>
      tldwClient.createWorldBook(values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tldw:listWorldBooks'] })
      setOpen(false)
      createForm.resetFields()
    },
    onError: (e: unknown) =>
      notification.error({
        message: 'Error',
        description: getErrorMessage(e) || 'Failed to create world book'
      })
  })
  const { mutate: updateWB, isPending: updating } = useMutation({
    mutationFn: (values: Record<string, unknown>) =>
      editId != null
        ? tldwClient.updateWorldBook(editId, values)
        : Promise.resolve(null),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tldw:listWorldBooks'] })
      setOpenEdit(false)
      editForm.resetFields()
      setEditId(null)
    },
    onError: (e: unknown) =>
      notification.error({
        message: 'Error',
        description: getErrorMessage(e) || 'Failed to update world book'
      })
  })
  const { mutate: deleteWB, isPending: deleting } = useMutation({
    mutationFn: (id: number) => tldwClient.deleteWorldBook(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tldw:listWorldBooks'] })
    },
    onError: (e: unknown) =>
      notification.error({
        message: 'Error',
        description: getErrorMessage(e) || 'Failed to delete world book'
      })
  })
  const { mutate: doImport } = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      tldwClient.importWorldBook(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tldw:listWorldBooks'] })
      setOpenImport(false)
    },
    onError: (e: unknown) =>
      notification.error({
        message: 'Error',
        description: getErrorMessage(e) || 'Failed to import world book'
      })
  })

  const columns: ColumnsType<WorldBook> = [
    { title: '', key: 'icon', width: 40, render: () => <BookOpen className="w-4 h-4" /> },
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'Description', dataIndex: 'description', key: 'description', render: (v: string) => <span className="line-clamp-1">{v}</span> },
    { title: 'Enabled', dataIndex: 'enabled', key: 'enabled', render: (v: boolean) => v ? <Tag color="green">Enabled</Tag> : <Tag>Disabled</Tag> },
    { title: 'Entries', dataIndex: 'entry_count', key: 'entry_count' },
    { title: 'Actions', key: 'actions', render: (_: unknown, record) => (
      <div className="flex gap-3">
        <Tooltip title="Edit">
          <button className="text-text-muted" onClick={() => { setEditId(record.id); editForm.setFieldsValue(record); setOpenEdit(true) }}>
            <Pen className="w-4 h-4" />
          </button>
        </Tooltip>
        <Tooltip title="Manage Entries">
          <button className="text-text-muted" onClick={() => setOpenEntries(record.id)}>
            Entries
          </button>
        </Tooltip>
        <Tooltip title="Attach to Character">
          <button className="text-text-muted" onClick={() => setOpenAttach(record.id)}>
            Attach
          </button>
        </Tooltip>
        <Tooltip title="Export JSON">
          <button className="text-text-muted" onClick={async () => {
            try {
              const exp = await tldwClient.exportWorldBook(record.id)
              const blob = new Blob([JSON.stringify(exp, null, 2)], { type: 'application/json' })
              const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = `${record.name || 'world-book'}.json`
            a.click()
            URL.revokeObjectURL(url)
          } catch (e: unknown) {
            notification.error({ message: 'Export failed', description: getErrorMessage(e) })
          }
        }}>Export</button>
        </Tooltip>
        <Tooltip title="Statistics">
          <button className="text-text-muted" onClick={async () => {
            try {
              const s = await tldwClient.worldBookStatistics(record.id)
              setStatsFor((s as WorldBookStats) ?? null)
            } catch (e: unknown) {
              notification.error({ message: 'Stats failed', description: getErrorMessage(e) })
            }
          }}>Stats</button>
        </Tooltip>
        <Tooltip title="Delete">
          <button className="text-danger" disabled={deleting} onClick={async () => { const ok = await confirmDanger({ title: 'Please confirm', content: 'Delete this world book?', okText: 'Delete', cancelText: 'Cancel' }); if (ok) deleteWB(record.id) }}>
            <Trash2 className="w-4 h-4" />
          </button>
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
        <Button onClick={() => setOpenImport(true)}>Import</Button>
        <Button type="primary" onClick={() => setOpen(true)}>New World Book</Button>
      </div>
      {status === 'pending' && <Skeleton active paragraph={{ rows: 6 }} />}
      {status === 'success' && (
        <Table<WorldBook>
          rowKey={(record) => record.id}
          dataSource={data ?? []}
          columns={columns}
        />
      )}

      <Modal title="Create World Book" open={open} onCancel={() => setOpen(false)} footer={null}>
        <Form layout="vertical" form={createForm} onFinish={(v) => createWB(v)}>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="description" label="Description"><Input /></Form.Item>
          <Form.Item name="scan_depth" label="Scan Depth"><InputNumber style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="token_budget" label="Token Budget"><InputNumber style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="recursive_scanning" label="Recursive Scanning" valuePropName="checked"><Switch /></Form.Item>
          <Form.Item name="enabled" label="Enabled" valuePropName="checked"><Switch defaultChecked /></Form.Item>
          <Button type="primary" htmlType="submit" loading={creating} className="w-full">Create</Button>
        </Form>
      </Modal>

      <Modal title="Import World Book (JSON)" open={openImport} onCancel={() => setOpenImport(false)} footer={null}>
        <div className="space-y-3">
          <input type="file" accept="application/json" onChange={async (e) => {
            const file = e.target.files?.[0]
            if (!file) return
            try {
              const text = await file.text()
              const parsed = JSON.parse(text)
              const payload = parsed.world_book && parsed.entries ? parsed : { world_book: parsed.world_book || parsed, entries: parsed.entries || [] }
              await doImport({ ...payload, merge_on_conflict: mergeOnConflict })
            } catch (err: unknown) {
              notification.error({ message: 'Import failed', description: getErrorMessage(err) })
            } finally {
              const input = e.target as HTMLInputElement
              input.value = ''
            }
          }} />
          <label className="inline-flex items-center gap-2 text-sm"><input type="checkbox" checked={mergeOnConflict} onChange={(ev) => setMergeOnConflict(ev.target.checked)} /> Merge on conflict</label>
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

      <Modal title="Edit World Book" open={openEdit} onCancel={() => setOpenEdit(false)} footer={null}>
        <Form layout="vertical" form={editForm} onFinish={(v) => updateWB(v)}>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="description" label="Description"><Input /></Form.Item>
          <Form.Item name="scan_depth" label="Scan Depth"><InputNumber style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="token_budget" label="Token Budget"><InputNumber style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="recursive_scanning" label="Recursive Scanning" valuePropName="checked"><Switch /></Form.Item>
          <Form.Item name="enabled" label="Enabled" valuePropName="checked"><Switch /></Form.Item>
          <Button type="primary" htmlType="submit" loading={updating} className="w-full">Save</Button>
        </Form>
      </Modal>

      <Modal title="Manage Entries" open={!!openEntries} onCancel={() => setOpenEntries(null)} footer={null}>
        <EntryManager worldBookId={openEntries!} form={entryForm} />
      </Modal>

      <Modal title="Attach to Character" open={!!openAttach} onCancel={() => setOpenAttach(null)} footer={null}>
        <Form
          layout="vertical"
          form={attachForm}
          onFinish={async (v: AttachFormValues) => {
            if (openAttach && v.character_id != null) {
              await tldwClient.attachWorldBookToCharacter(v.character_id, openAttach)
              notification.success({ message: 'Attached' })
              setOpenAttach(null)
            }
          }}
        >
          <Form.Item name="character_id" label="Character" rules={[{ required: true }]}>
            <Select
              showSearch
              options={(characters ?? []).map((c) => ({ label: c.name, value: c.id }))}
            />
          </Form.Item>
          <Button type="primary" htmlType="submit" className="w-full">Attach</Button>
        </Form>
      </Modal>
    </div>
  )
}

const EntryManager: React.FC<{
  worldBookId: number
  form: FormInstance<Record<string, unknown>>
}> = ({ worldBookId, form }) => {
  const qc = useQueryClient()
  const notification = useAntdNotification()
  const confirmDanger = useConfirmDanger()
  const { data, status } = useQuery<WorldBookEntry[]>({
    queryKey: ['tldw:listWorldBookEntries', worldBookId],
    queryFn: async () => {
      await tldwClient.initialize()
      const res = await tldwClient.listWorldBookEntries(worldBookId, false)
      return Array.isArray(res?.entries) ? (res.entries as WorldBookEntry[]) : []
    }
  })
  const { mutate: addEntry, isPending: adding } = useMutation({
    mutationFn: (v: Record<string, unknown>) =>
      tldwClient.addWorldBookEntry(worldBookId, v),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tldw:listWorldBookEntries', worldBookId] }); form.resetFields() },
    onError: (e: unknown) =>
      notification.error({
        message: 'Error',
        description: getErrorMessage(e) || 'Failed to add entry'
      })
  })
  const { mutate: deleteEntry } = useMutation({
    mutationFn: (id: number) => tldwClient.deleteWorldBookEntry(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tldw:listWorldBookEntries', worldBookId] })
  })
  const entryColumns: ColumnsType<WorldBookEntry> = [
    {
      title: 'Keywords',
      dataIndex: 'keywords',
      key: 'keywords',
      render: (arr: string[] | undefined) => (
        <div className="flex flex-wrap gap-1">
          {(arr || []).map((k) => (
            <Tag key={k}>{k}</Tag>
          ))}
        </div>
      )
    },
    {
      title: 'Content',
      dataIndex: 'content',
      key: 'content',
      render: (v: string | undefined) => <span className="line-clamp-2">{v}</span>
    },
    {
      title: 'Enabled',
      dataIndex: 'enabled',
      key: 'enabled',
      render: (v: boolean | undefined) => (v ? 'Yes' : 'No')
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, r) => (
        <div className="flex gap-2">
          <Tooltip title="Delete">
            <button
              className="text-danger"
              onClick={async () => {
                const ok = await confirmDanger({
                  title: 'Please confirm',
                  content: 'Delete entry?',
                  okText: 'Delete',
                  cancelText: 'Cancel'
                })
                if (ok) deleteEntry(r.entry_id)
              }}
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </Tooltip>
        </div>
      )
    }
  ]
  return (
    <div className="space-y-3">
      {status === 'pending' && <Skeleton active paragraph={{ rows: 4 }} />}
      {status === 'success' && (
        <Table
          size="small"
          rowKey={(record) => record.entry_id}
          dataSource={data ?? []}
          columns={entryColumns}
        />
      )}
      <Form layout="vertical" form={form} onFinish={(v) => addEntry(v)}>
        <Form.Item name="keywords" label="Keywords (comma separated)"><Input placeholder="e.g. Hermione, Hogwarts" /></Form.Item>
        <Form.Item name="content" label="Content" rules={[{ required: true }]}><Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} /></Form.Item>
        <Form.Item name="priority" label="Priority"><InputNumber style={{ width: '100%' }} /></Form.Item>
        <Form.Item name="enabled" label="Enabled" valuePropName="checked"><Switch defaultChecked /></Form.Item>
        <Form.Item name="case_sensitive" label="Case Sensitive" valuePropName="checked"><Switch /></Form.Item>
        <Form.Item name="regex_match" label="Regex Match" valuePropName="checked"><Switch /></Form.Item>
        <Form.Item name="whole_word_match" label="Whole Word Match" valuePropName="checked"><Switch /></Form.Item>
        <Button type="primary" htmlType="submit" loading={adding} className="w-full">Add Entry</Button>
      </Form>
    </div>
  )
}
