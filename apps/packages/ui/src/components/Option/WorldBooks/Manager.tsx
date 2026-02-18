import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button, Form, Input, InputNumber, Modal, Skeleton, Switch, Table, Tooltip, Tag, Select, Descriptions, Empty, Popover, Divider, Drawer, Checkbox, Grid, Progress, Upload } from "antd"
import React from "react"
import { useConfirmDanger } from "@/components/Common/confirm-danger"
import {
  tldwClient,
  type WorldBookProcessDiagnostic,
  type WorldBookProcessResponse
} from "@/services/tldw/TldwApiClient"
import { Pen, Trash2, BookOpen, HelpCircle, Link2, Download, BarChart3, Copy, List, Upload as UploadIcon } from "lucide-react"
import { useServerOnline } from "@/hooks/useServerOnline"
import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import { useTranslation } from "react-i18next"
import { useAntdNotification } from "@/hooks/useAntdNotification"
import { useUndoNotification } from "@/hooks/useUndoNotification"
import { parseBulkEntries, SUPPORTED_BULK_SEPARATORS } from "./entryParsers"
import {
  buildDuplicateWorldBookName,
  WORLD_BOOK_FORM_DEFAULTS,
  WORLD_BOOK_STARTER_TEMPLATES,
  buildWorldBookFormPayload,
  buildWorldBookMutationErrorMessage,
  getWorldBookStarterTemplate,
  hasDuplicateWorldBookName,
  normalizeWorldBookName,
  toWorldBookFormValues
} from "./worldBookFormUtils"
import {
  formatWorldBookLastModified,
  UNKNOWN_LAST_MODIFIED_LABEL
} from "./worldBookListUtils"
import {
  formatEntryContentStats,
  getPriorityBand,
  getPriorityTagColor,
  normalizeKeywordList,
  validateRegexKeywords
} from "./worldBookEntryUtils"
import {
  DEFAULT_BULK_ADD_CONCURRENCY,
  type BulkAddFailure,
  type BulkAddProgress,
  runBulkAddEntries
} from "./worldBookBulkUtils"
import {
  buildBulkSetPriorityPayload,
  clampBulkPriority,
  normalizeBulkEntryIds
} from "./worldBookBulkActionUtils"
import {
  convertWorldBookImport,
  getWorldBookImportFormatLabel,
  getWorldBookImportJsonErrorMessage,
  validateWorldBookImportConversion,
  WORLD_BOOK_IMPORT_MERGE_HELP_TEXT,
  type WorldBookImportFormat
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

// Helper component for form field labels with tooltips
const LabelWithHelp: React.FC<{ label: string; help: string }> = ({ label, help }) => (
  <span className="inline-flex items-center gap-1">
    {label}
    <Tooltip title={help}>
      <HelpCircle className="w-4 h-4 text-text-muted cursor-help" />
    </Tooltip>
  </span>
)

// Keyword preview component for real-time feedback
const KeywordPreview: React.FC<{ value?: unknown }> = ({ value }) => {
  const keywords = normalizeKeywordList(value)
  if (keywords.length === 0) return null
  return (
    <div className="mt-1 flex flex-wrap gap-1">
      {keywords.map((k, i) => <Tag key={i}>{k}</Tag>)}
    </div>
  )
}

const normalizeKeywords = (value: any): string[] => {
  return normalizeKeywordList(value)
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

const BULK_ENTRY_FORMAT_EXAMPLES = [
  { separator: "=>", example: "keyword1, keyword2 => content" },
  { separator: "->", example: "keyword1, keyword2 -> content" },
  { separator: "|", example: "keyword1, keyword2 | content" },
  { separator: "\t", example: "keyword1, keyword2<TAB>content" }
] as const

const IMPORT_PREVIEW_ENTRY_LIMIT = 5
const IMPORT_PREVIEW_CONTENT_LIMIT = 140

const truncateImportPreviewContent = (content: unknown): string => {
  const text = String(content || "")
  if (text.length <= IMPORT_PREVIEW_CONTENT_LIMIT) return text
  return `${text.slice(0, IMPORT_PREVIEW_CONTENT_LIMIT - 3)}...`
}

const ATTACHMENT_MATRIX_CHARACTER_THRESHOLD = 10
const ATTACHMENT_LIST_PAGE_SIZE = 8
const ATTACHMENT_FEEDBACK_DURATION_MS = 2400
const ATTACHMENT_PULSE_DURATION_MS = 1200
const LOREBOOK_DEBUG_ENTRYPOINT_HREF = "/playground?from=world-books&focus=lorebook-debug"
const LOREBOOK_METRIC_LABELS = {
  entriesMatched: "Entries matched",
  booksUsed: "Books used",
  tokensUsed: "Tokens used",
  tokenBudget: "Token budget"
} as const

type WorldBookFormMode = "create" | "edit"
type EntryFilterPreset = {
  enabledFilter: "all" | "enabled" | "disabled"
  matchFilter: "all" | "regex" | "plain"
  searchText: string
}

const DEFAULT_ENTRY_FILTER_PRESET: EntryFilterPreset = {
  enabledFilter: "all",
  matchFilter: "all",
  searchText: ""
}

type WorldBookFormProps = {
  mode: WorldBookFormMode
  form: any
  worldBooks: Array<{ id?: number; name?: string }>
  submitting: boolean
  currentWorldBookId?: number | null
  onSubmit: (values: Record<string, any>) => void
}

export const WorldBookForm: React.FC<WorldBookFormProps> = ({
  mode,
  form,
  worldBooks,
  submitting,
  currentWorldBookId,
  onSubmit
}) => {
  const submitLabel = mode === "create" ? "Create" : "Save"
  const handleTemplateChange = React.useCallback(
    (templateKey?: string) => {
      if (!templateKey) return
      const template = getWorldBookStarterTemplate(templateKey)
      if (!template) return

      const currentValues = form.getFieldsValue()
      const templateDefaults = { ...WORLD_BOOK_FORM_DEFAULTS, ...(template.defaults || {}) }
      const nextValues: Record<string, any> = {
        template_key: template.key,
        scan_depth: templateDefaults.scan_depth,
        token_budget: templateDefaults.token_budget,
        recursive_scanning: templateDefaults.recursive_scanning,
        enabled: templateDefaults.enabled
      }

      if (!normalizeWorldBookName(currentValues?.name)) {
        nextValues.name = template.suggestedName
      }
      if (!normalizeWorldBookName(currentValues?.description)) {
        nextValues.description = template.description
      }
      form.setFieldsValue(nextValues)
    },
    [form]
  )

  return (
    <Form
      layout="vertical"
      form={form}
      initialValues={WORLD_BOOK_FORM_DEFAULTS}
      onFinish={(values) => onSubmit(buildWorldBookFormPayload(values, mode))}
    >
      {mode === "create" && (
        <Form.Item name="template_key" label="Starter Template (optional)">
          <Select
            allowClear
            placeholder="Choose a starter template"
            options={WORLD_BOOK_STARTER_TEMPLATES.map((template) => ({
              label: template.label,
              value: template.key
            }))}
            onChange={(value) => handleTemplateChange(value)}
          />
        </Form.Item>
      )}
      <Form.Item
        name="name"
        label="Name"
        rules={[
          { required: true, whitespace: true, message: "Name is required" },
          {
            validator: (_: any, value: string) => {
              const candidate = normalizeWorldBookName(value)
              if (!candidate) return Promise.resolve()
              if (hasDuplicateWorldBookName(candidate, worldBooks, { excludeId: currentWorldBookId })) {
                return Promise.reject(new Error(`A world book named "${candidate}" already exists.`))
              }
              return Promise.resolve()
            }
          }
        ]}
      >
        <Input />
      </Form.Item>
      <Form.Item name="description" label="Description (optional)">
        <Input />
      </Form.Item>
      <Form.Item name="enabled" label="Enabled" valuePropName="checked">
        <Switch />
      </Form.Item>
      <details className="mb-4">
        <summary className="cursor-pointer text-sm text-text-muted hover:text-text">Advanced Settings</summary>
        <div className="mt-3 pl-2 border-l-2 border-border space-y-0">
          <Form.Item
            name="scan_depth"
            label={<LabelWithHelp label="Scan Depth" help="How many recent messages to search for keywords (1-20). Higher values find more matches but use more processing." />}
          >
            <InputNumber style={{ width: "100%" }} min={1} max={20} />
          </Form.Item>
          <Form.Item
            name="token_budget"
            label={<LabelWithHelp label="Token Budget" help="Maximum characters of world info to inject into context (~4 characters = 1 token). This is the most impactful setting for context usage." />}
          >
            <InputNumber style={{ width: "100%" }} min={50} max={5000} />
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
      <Button type="primary" htmlType="submit" loading={submitting} className="w-full">
        {submitLabel}
      </Button>
    </Form>
  )
}

type WorldBookTestMatchingModalProps = {
  open: boolean
  onClose: () => void
  worldBooks: Array<Record<string, any>>
  initialWorldBookId?: number | null
}

type WorldBookTestResult = {
  response: WorldBookProcessResponse
  payload: {
    text: string
    world_book_ids: number[]
    scan_depth: number
    token_budget: number
    recursive_scanning: boolean
  }
}

const getReasonLabel = (reason: string) => {
  if (reason === "regex_match") return "Regex match"
  if (reason === "depth") return "Depth rule"
  return "Keyword match"
}

const normalizeWorldBookSetting = (
  value: unknown,
  fallback: number,
  min: number,
  max: number
) => {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return fallback
  return Math.max(min, Math.min(max, parsed))
}

const WorldBookTestMatchingModal: React.FC<WorldBookTestMatchingModalProps> = ({
  open,
  onClose,
  worldBooks,
  initialWorldBookId = null
}) => {
  const [selectedWorldBookId, setSelectedWorldBookId] = React.useState<number | null>(null)
  const [sampleText, setSampleText] = React.useState("")
  const [scanDepth, setScanDepth] = React.useState(3)
  const [tokenBudget, setTokenBudget] = React.useState(500)
  const [recursiveScanning, setRecursiveScanning] = React.useState(false)
  const [running, setRunning] = React.useState(false)
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null)
  const [result, setResult] = React.useState<WorldBookTestResult | null>(null)

  const testableWorldBooks = React.useMemo(
    () =>
      (worldBooks || [])
        .map((book) => ({
          ...book,
          id: Number(book?.id)
        }))
        .filter((book) => Number.isFinite(book.id) && book.id > 0),
    [worldBooks]
  )

  const selectedWorldBook = React.useMemo(
    () => testableWorldBooks.find((book) => book.id === selectedWorldBookId) || null,
    [selectedWorldBookId, testableWorldBooks]
  )

  const applyWorldBookDefaults = React.useCallback((book: Record<string, any> | null) => {
    if (!book) return
    setScanDepth(
      normalizeWorldBookSetting(book?.scan_depth, WORLD_BOOK_FORM_DEFAULTS.scan_depth, 1, 20)
    )
    setTokenBudget(
      normalizeWorldBookSetting(book?.token_budget, WORLD_BOOK_FORM_DEFAULTS.token_budget, 50, 5000)
    )
    setRecursiveScanning(Boolean(book?.recursive_scanning))
  }, [])

  React.useEffect(() => {
    if (!open) return
    const initialCandidateId = Number(initialWorldBookId)
    const nextWorldBookId =
      Number.isFinite(initialCandidateId) && initialCandidateId > 0
        ? initialCandidateId
        : testableWorldBooks[0]?.id || null
    setSelectedWorldBookId(nextWorldBookId)
    const nextWorldBook =
      testableWorldBooks.find((book) => book.id === nextWorldBookId) || null
    applyWorldBookDefaults(nextWorldBook)
    setErrorMessage(null)
  }, [applyWorldBookDefaults, initialWorldBookId, open, testableWorldBooks])

  React.useEffect(() => {
    if (!open) return
    applyWorldBookDefaults(selectedWorldBook)
  }, [applyWorldBookDefaults, open, selectedWorldBook])

  const handleRunTest = async () => {
    if (!selectedWorldBookId) {
      setErrorMessage("Select a world book to test.")
      return
    }
    const normalizedText = sampleText.trim()
    if (!normalizedText) {
      setErrorMessage("Provide sample text to test keyword matching.")
      return
    }

    setRunning(true)
    setErrorMessage(null)
    try {
      await tldwClient.initialize()
      const payload = {
        text: normalizedText,
        world_book_ids: [selectedWorldBookId],
        scan_depth: normalizeWorldBookSetting(scanDepth, 3, 1, 20),
        token_budget: normalizeWorldBookSetting(tokenBudget, 500, 50, 5000),
        recursive_scanning: Boolean(recursiveScanning)
      }
      const response = await tldwClient.processWorldBookContext(payload)
      setResult({ response, payload })
    } catch (error: any) {
      setErrorMessage(error?.message || "Failed to run keyword test.")
    } finally {
      setRunning(false)
    }
  }

  const diagnostics: WorldBookProcessDiagnostic[] = React.useMemo(() => {
    if (!result?.response || !Array.isArray(result.response.diagnostics)) return []
    return result.response.diagnostics
  }, [result])

  const tokenBudgetValue =
    typeof result?.response?.token_budget === "number"
      ? result.response.token_budget
      : result?.payload?.token_budget

  return (
    <Modal
      title="Test Matching"
      open={open}
      onCancel={onClose}
      footer={null}
      width={760}
      destroyOnHidden
    >
      <div className="space-y-3">
        <p className="text-xs text-text-muted">
          Paste sample chat text to test which entries trigger and how much budget is consumed.
        </p>

        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs text-text-muted">World Book</label>
            <Select
              value={selectedWorldBookId ?? undefined}
              onChange={(value) => setSelectedWorldBookId(Number(value))}
              aria-label="World book to test"
              placeholder="Select world book"
              options={testableWorldBooks.map((book) => ({
                label: String(book?.name || `World Book ${book.id}`),
                value: book.id
              }))}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-text-muted">Scan Depth</label>
            <InputNumber
              min={1}
              max={20}
              style={{ width: "100%" }}
              value={scanDepth}
              onChange={(value) => setScanDepth(normalizeWorldBookSetting(value, 3, 1, 20))}
              aria-label="Scan depth for keyword test"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-text-muted">Token Budget</label>
            <InputNumber
              min={50}
              max={5000}
              style={{ width: "100%" }}
              value={tokenBudget}
              onChange={(value) => setTokenBudget(normalizeWorldBookSetting(value, 500, 50, 5000))}
              aria-label="Token budget for keyword test"
            />
          </div>
          <div className="flex items-end pb-1">
            <div className="flex items-center gap-2 rounded border border-border px-3 py-2">
              <Switch
                checked={recursiveScanning}
                onChange={setRecursiveScanning}
                aria-label="Recursive scanning for keyword test"
              />
              <span className="text-xs text-text-muted">Recursive scanning</span>
            </div>
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs text-text-muted">Sample text</label>
          <Input.TextArea
            value={sampleText}
            onChange={(event) => setSampleText(event.target.value)}
            autoSize={{ minRows: 4, maxRows: 10 }}
            placeholder="Paste sample chat context to test world-book matching..."
            aria-label="Sample text for keyword test"
          />
        </div>

        <div className="flex items-center justify-end gap-2">
          <Button onClick={onClose}>Close</Button>
          <Button
            type="primary"
            loading={running}
            onClick={() => void handleRunTest()}
            aria-label="Run keyword test"
            disabled={testableWorldBooks.length === 0}
          >
            Run Test
          </Button>
        </div>

        {errorMessage && (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {errorMessage}
          </div>
        )}

        {result && (
          <div className="space-y-2">
            <Descriptions size="small" bordered column={2}>
              <Descriptions.Item label={LOREBOOK_METRIC_LABELS.entriesMatched}>
                {result.response.entries_matched}
              </Descriptions.Item>
              <Descriptions.Item label={LOREBOOK_METRIC_LABELS.booksUsed}>
                {result.response.books_used}
              </Descriptions.Item>
              <Descriptions.Item label={LOREBOOK_METRIC_LABELS.tokensUsed}>
                {result.response.tokens_used}
              </Descriptions.Item>
              <Descriptions.Item label={LOREBOOK_METRIC_LABELS.tokenBudget}>
                {typeof tokenBudgetValue === "number" ? tokenBudgetValue : "—"}
              </Descriptions.Item>
            </Descriptions>
            {(result.response.budget_exhausted ||
              Number(result.response.skipped_entries_due_to_budget || 0) > 0) && (
              <div className="rounded border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-text">
                Budget warning:{" "}
                {result.response.budget_exhausted
                  ? "Token budget is exhausted."
                  : `${result.response.skipped_entries_due_to_budget} entries were skipped by budget.`}
              </div>
            )}

            {diagnostics.length === 0 ? (
              <Empty description="No entries matched for this sample text." />
            ) : (
              <div className="max-h-72 space-y-2 overflow-auto pr-1">
                {diagnostics.map((diagnostic, index) => (
                  <div
                    key={`${diagnostic.entry_id ?? "entry"}-${index}`}
                    className="rounded border border-border px-3 py-2"
                  >
                    <p className="text-sm font-medium">
                      {getReasonLabel(String(diagnostic.activation_reason || ""))}
                      {diagnostic.keyword ? `: ${diagnostic.keyword}` : ""}
                    </p>
                    <p className="text-xs text-text-muted">
                      Entry #{diagnostic.entry_id ?? "?"} · {diagnostic.token_cost} tokens
                    </p>
                    {String(diagnostic.content_preview || "").trim().length > 0 && (
                      <p className="mt-1 whitespace-pre-wrap text-xs text-text-muted">
                        {diagnostic.content_preview}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}

            <div className="rounded border border-border bg-surface-secondary px-3 py-2">
              <p className="text-xs font-medium text-text">Need live-turn diagnostics?</p>
              <p className="text-xs text-text-muted">
                For per-turn injection logs and export, open a chat and use Lorebook Debug.
              </p>
              <a
                href={LOREBOOK_DEBUG_ENTRYPOINT_HREF}
                className="text-xs text-primary hover:underline"
                aria-label="Open chat lorebook debug panel"
              >
                Open Chat Debug Panel
              </a>
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
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
  const [openGlobalStats, setOpenGlobalStats] = React.useState(false)
  const [openTestMatching, setOpenTestMatching] = React.useState(false)
  const [testMatchingWorldBookId, setTestMatchingWorldBookId] = React.useState<number | null>(null)
  const [mergeOnConflict, setMergeOnConflict] = React.useState(false)
  const [importPreview, setImportPreview] = React.useState<{
    name?: string
    entryCount: number
    conflict?: boolean
    format?: WorldBookImportFormat
    warnings?: string[]
    settings?: {
      scanDepth?: number
      tokenBudget?: number
      recursiveScanning?: boolean
      enabled?: boolean
    }
    previewEntries?: Array<{
      keywords: string[]
      contentPreview: string
    }>
  } | null>(null)
  const [importPayload, setImportPayload] = React.useState<any | null>(null)
  const [importError, setImportError] = React.useState<string | null>(null)
  const [importFileName, setImportFileName] = React.useState<string | null>(null)
  const [statsFor, setStatsFor] = React.useState<any | null>(null)
  const [exportingId, setExportingId] = React.useState<number | null>(null)
  const [bulkExportMode, setBulkExportMode] = React.useState<"all" | "selected" | null>(null)
  const [duplicatingId, setDuplicatingId] = React.useState<number | null>(null)
  const [statsLoadingId, setStatsLoadingId] = React.useState<number | null>(null)
  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()
  const [entryForm] = Form.useForm()
  const [attachForm] = Form.useForm()
  const confirmDanger = useConfirmDanger()
  const deleteTimersRef = React.useRef<Record<number, any>>({})
  const matrixBaselineKeysRef = React.useRef<Set<string>>(new Set())
  const matrixPulseTimersRef = React.useRef<Record<string, any>>({})
  const matrixFeedbackTimerRef = React.useRef<any>(null)
  const [pendingDeleteIds, setPendingDeleteIds] = React.useState<number[]>([])
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
  const [listSearch, setListSearch] = React.useState("")
  const [enabledFilter, setEnabledFilter] = React.useState<"all" | "enabled" | "disabled">("all")
  const [attachmentFilter, setAttachmentFilter] = React.useState<"all" | "attached" | "unattached">("all")
  const [selectedWorldBookKeys, setSelectedWorldBookKeys] = React.useState<React.Key[]>([])
  const [bulkWorldBookAction, setBulkWorldBookAction] = React.useState<
    "enable" | "disable" | "delete" | null
  >(null)
  const [tableSort, setTableSort] = React.useState<{
    field?: "name" | "entry_count" | "enabled"
    order?: "ascend" | "descend" | null
  }>({})
  const [entryFilterPreset, setEntryFilterPreset] = React.useState<EntryFilterPreset>(
    DEFAULT_ENTRY_FILTER_PRESET
  )

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
    (worldBookId: number) => (attachmentsByBook && (attachmentsByBook as any)[worldBookId]) || [],
    [attachmentsByBook]
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
    mutationFn: (values: any) => editId != null ? tldwClient.updateWorldBook(editId, values) : Promise.resolve(null),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tldw:listWorldBooks'] }); setOpenEdit(false); editForm.resetFields(); setEditId(null) },
    onError: (e: any, values: any) =>
      notification.error({
        message: "Error",
        description: buildWorldBookMutationErrorMessage(e, {
          attemptedName: values?.name,
          fallback: "Failed to update world book"
        })
      })
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
  const duplicateWorldBook = React.useCallback(
    async (record: any) => {
      if (!record?.id || duplicatingId != null) return
      setDuplicatingId(record.id)
      try {
        await tldwClient.initialize()
        const duplicateName = buildDuplicateWorldBookName(record.name, (data || []) as any[])
        const created = await tldwClient.createWorldBook({
          name: duplicateName,
          description: record.description,
          scan_depth:
            typeof record.scan_depth === "number"
              ? record.scan_depth
              : WORLD_BOOK_FORM_DEFAULTS.scan_depth,
          token_budget:
            typeof record.token_budget === "number"
              ? record.token_budget
              : WORLD_BOOK_FORM_DEFAULTS.token_budget,
          recursive_scanning:
            typeof record.recursive_scanning === "boolean"
              ? record.recursive_scanning
              : WORLD_BOOK_FORM_DEFAULTS.recursive_scanning,
          enabled:
            typeof record.enabled === "boolean"
              ? record.enabled
              : WORLD_BOOK_FORM_DEFAULTS.enabled
        })

        const createdId = Number(created?.id)
        if (!Number.isFinite(createdId) || createdId <= 0) {
          throw new Error("Could not determine duplicated world book ID")
        }

        const entriesResponse = await tldwClient.listWorldBookEntries(record.id, false)
        const sourceEntries = Array.isArray(entriesResponse?.entries) ? entriesResponse.entries : []

        for (const entry of sourceEntries) {
          await tldwClient.addWorldBookEntry(createdId, {
            keywords: normalizeKeywords(entry?.keywords),
            content: String(entry?.content || ""),
            priority:
              typeof entry?.priority === "number"
                ? entry.priority
                : 0,
            enabled:
              typeof entry?.enabled === "boolean"
                ? entry.enabled
                : true,
            case_sensitive: !!entry?.case_sensitive,
            regex_match: !!entry?.regex_match,
            whole_word_match:
              typeof entry?.whole_word_match === "boolean"
                ? entry.whole_word_match
                : true,
            appendable:
              typeof entry?.appendable === "boolean"
                ? entry.appendable
                : Boolean(entry?.metadata?.appendable)
          })
        }

        qc.invalidateQueries({ queryKey: ["tldw:listWorldBooks"] })
        notification.success({
          message: "Duplicated",
          description: `Created "${duplicateName}" with ${sourceEntries.length} copied entries.`
        })
      } catch (e: any) {
        notification.error({
          message: "Duplicate failed",
          description: e?.message || "Failed to duplicate world book"
        })
      } finally {
        setDuplicatingId(null)
      }
    },
    [data, duplicatingId, notification, qc]
  )

  const exportJsonFile = React.useCallback((payload: unknown, fileName: string) => {
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = fileName
    anchor.click()
    URL.revokeObjectURL(url)
  }, [])

  const exportSingleWorldBook = React.useCallback(
    async (record: any) => {
      if (!record?.id) return
      setExportingId(record.id)
      try {
        const exported = await tldwClient.exportWorldBook(record.id)
        const safeName = String(record?.name || "world-book")
          .trim()
          .replace(/[^a-zA-Z0-9._-]+/g, "-")
          .replace(/^-+|-+$/g, "") || "world-book"
        exportJsonFile(exported, `${safeName}.json`)
      } catch (e: any) {
        notification.error({ message: "Export failed", description: e?.message })
      } finally {
        setExportingId(null)
      }
    },
    [exportJsonFile, notification]
  )

  const exportWorldBookBundle = React.useCallback(
    async (mode: "all" | "selected") => {
      if (bulkExportMode) return

      const source = Array.isArray(data) ? data : []
      const selectedIdSet = new Set(
        selectedWorldBookKeys
          .map((key) => Number(key))
          .filter((id) => Number.isFinite(id) && id > 0)
      )
      const targetBooks =
        mode === "all"
          ? source
          : source.filter((book: any) => selectedIdSet.has(Number(book?.id)))
      if (targetBooks.length === 0) return

      setBulkExportMode(mode)
      try {
        const exportedBooks = await Promise.all(
          targetBooks.map(async (book: any) => ({
            id: Number(book?.id),
            name: String(book?.name || ""),
            data: await tldwClient.exportWorldBook(book.id)
          }))
        )
        const timestamp = new Date().toISOString()
        const fileSafeDate = timestamp.slice(0, 10)
        exportJsonFile(
          {
            bundle_type: "tldw-world-books-export",
            bundle_version: 1,
            exported_at: timestamp,
            export_mode: mode,
            world_books: exportedBooks
          },
          `world-books-${mode}-${fileSafeDate}.json`
        )
        notification.success({
          message: mode === "all" ? "Exported all world books" : "Exported selected world books",
          description: `Downloaded ${exportedBooks.length} world books.`
        })
      } catch (e: any) {
        notification.error({
          message: "Export failed",
          description: e?.message || "Could not export world books."
        })
      } finally {
        setBulkExportMode(null)
      }
    },
    [bulkExportMode, data, exportJsonFile, notification, selectedWorldBookKeys]
  )

  const handleImportUpload = React.useCallback(
    async (file: File) => {
      const isJsonFile =
        file?.type === "application/json" || String(file?.name || "").toLowerCase().endsWith(".json")
      setImportFileName(file.name)
      if (!isJsonFile) {
        setImportError("Please select a .json file.")
        setImportPreview(null)
        setImportPayload(null)
        return false
      }
      try {
        const text = await file.text()
        const parsed = JSON.parse(text)
        const conversion = convertWorldBookImport(parsed)
        const validationError = validateWorldBookImportConversion(parsed, conversion)

        if (!conversion.payload) {
          setImportError(validationError || conversion.error || "Unsupported import format")
          setImportPreview(null)
          setImportPayload(null)
          return false
        }

        const payload = conversion.payload
        const name = payload?.world_book?.name
        const entries = Array.isArray(payload?.entries) ? payload.entries : []
        const entryCount = entries.length
        const conflict = !!(data || []).find((wb: any) => wb.name === name)
        const previewEntries = entries
          .slice(0, IMPORT_PREVIEW_ENTRY_LIMIT)
          .map((entry: any) => ({
            keywords: normalizeKeywordList(entry?.keywords),
            contentPreview: truncateImportPreviewContent(entry?.content)
          }))
        const worldBookSettings = payload?.world_book || {}
        setImportPreview({
          name,
          entryCount,
          conflict,
          format: conversion.format,
          warnings: conversion.warnings,
          settings: {
            scanDepth:
              typeof worldBookSettings?.scan_depth === "number"
                ? worldBookSettings.scan_depth
                : undefined,
            tokenBudget:
              typeof worldBookSettings?.token_budget === "number"
                ? worldBookSettings.token_budget
                : undefined,
            recursiveScanning:
              typeof worldBookSettings?.recursive_scanning === "boolean"
                ? worldBookSettings.recursive_scanning
                : undefined,
            enabled:
              typeof worldBookSettings?.enabled === "boolean"
                ? worldBookSettings.enabled
                : undefined
          },
          previewEntries
        })
        if (validationError) {
          setImportError(validationError)
          setImportPayload(null)
        } else {
          setImportError(null)
          setImportPayload(payload)
        }
      } catch (err: any) {
        setImportError(getWorldBookImportJsonErrorMessage(err))
        setImportPreview(null)
        setImportPayload(null)
      }
      return false
    },
    [data]
  )

  const renderAttachedCell = (record: any) => {
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
    const source = attachmentsByBook as Record<string, any> | undefined
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
  }, [attachmentKeyFor, attachmentsByBook])

  const handleOpenMatrix = React.useCallback(() => {
    initializeMatrixSession()
    setOpenMatrix(true)
  }, [initializeMatrixSession])

  const handleCloseMatrix = React.useCallback(() => {
    setOpenMatrix(false)
    initializeMatrixSession()
  }, [initializeMatrixSession])

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

  const filteredWorldBooks = React.useMemo(() => {
    const source = Array.isArray(data) ? data : []
    const query = listSearch.trim().toLowerCase()

    let next = source
    if (query) {
      next = next.filter((book: any) => {
        const name = String(book?.name || "").toLowerCase()
        const description = String(book?.description || "").toLowerCase()
        return name.includes(query) || description.includes(query)
      })
    }

    if (enabledFilter !== "all") {
      const mustBeEnabled = enabledFilter === "enabled"
      next = next.filter((book: any) => Boolean(book?.enabled) === mustBeEnabled)
    }

    if (attachmentFilter !== "all" && !attachmentsLoading) {
      next = next.filter((book: any) => {
        const attachedCount = ((attachmentsByBook as any)?.[book?.id] || []).length
        return attachmentFilter === "attached" ? attachedCount > 0 : attachedCount === 0
      })
    }

    return next
  }, [attachmentFilter, attachmentsByBook, attachmentsLoading, data, enabledFilter, listSearch])

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

  const clearListFilters = React.useCallback(() => {
    setListSearch("")
    setEnabledFilter("all")
    setAttachmentFilter("all")
  }, [])

  const openEntriesWithPreset = React.useCallback(
    (
      book: { id: number; name: string; entryCount?: number },
      preset: EntryFilterPreset = DEFAULT_ENTRY_FILTER_PRESET
    ) => {
      setEntryFilterPreset({ ...DEFAULT_ENTRY_FILTER_PRESET, ...(preset || {}) })
      setOpenEntries({ id: book.id, name: book.name, entryCount: book.entryCount })
    },
    []
  )

  const openEntriesFromStats = React.useCallback(
    (preset: EntryFilterPreset) => {
      const worldBookId = Number(statsFor?.world_book_id)
      if (!Number.isFinite(worldBookId) || worldBookId <= 0) return
      const worldBookName = String(statsFor?.name || `World Book ${worldBookId}`)
      const entryCount =
        typeof statsFor?.total_entries === "number" ? statsFor.total_entries : undefined
      setEntryFilterPreset({ ...DEFAULT_ENTRY_FILTER_PRESET, ...(preset || {}) })
      setStatsFor(null)
      setOpenEntries({ id: worldBookId, name: worldBookName, entryCount })
    },
    [statsFor]
  )

  const openEntriesFromGlobalStats = React.useCallback(
    (worldBookId: number, keyword?: string) => {
      const source = ((data || []) as any[]).find(
        (book: any) => Number(book?.id) === Number(worldBookId)
      )
      if (!source) return
      setOpenGlobalStats(false)
      setEntryFilterPreset({
        ...DEFAULT_ENTRY_FILTER_PRESET,
        searchText: String(keyword || "").trim()
      })
      setOpenEntries({
        id: Number(source.id),
        name: String(source.name || `World Book ${source.id}`),
        entryCount: typeof source.entry_count === "number" ? source.entry_count : undefined
      })
    },
    [data]
  )

  const openTestMatchingModal = React.useCallback((worldBookId?: number | null) => {
    if (typeof worldBookId === "number" && Number.isFinite(worldBookId) && worldBookId > 0) {
      setTestMatchingWorldBookId(worldBookId)
    } else {
      setTestMatchingWorldBookId(null)
    }
    setOpenTestMatching(true)
  }, [])

  const hasActiveListFilters =
    listSearch.trim().length > 0 || enabledFilter !== "all" || attachmentFilter !== "all"

  React.useEffect(() => {
    return () => {
      Object.values(deleteTimersRef.current).forEach((t) => clearTimeout(t))
      deleteTimersRef.current = {}
      Object.values(matrixPulseTimersRef.current).forEach((t) => clearTimeout(t))
      matrixPulseTimersRef.current = {}
      if (matrixFeedbackTimerRef.current) {
        clearTimeout(matrixFeedbackTimerRef.current)
        matrixFeedbackTimerRef.current = null
      }
    }
  }, [])

  const handleBulkWorldBookAction = async (operation: "enable" | "disable" | "delete") => {
    const selectedIds = selectedWorldBookKeys
      .map((key) => Number(key))
      .filter((id) => Number.isFinite(id) && id > 0)
    if (selectedIds.length === 0 || bulkWorldBookAction) return

    if (operation === "delete") {
      const ok = await confirmDanger({
        title: "Delete selected world books?",
        content: `This will permanently remove ${selectedIds.length} world books and their entries.`,
        okText: "Delete",
        cancelText: "Cancel"
      })
      if (!ok) return
    }

    setBulkWorldBookAction(operation)
    try {
      if (operation === "delete") {
        await Promise.all(selectedIds.map((id) => tldwClient.deleteWorldBook(id)))
      } else {
        const nextEnabled = operation === "enable"
        const booksById = new Map(((data || []) as any[]).map((book: any) => [book.id, book]))
        await Promise.all(
          selectedIds.map((id) => {
            const record = booksById.get(id)
            if (!record) return Promise.resolve(null)
            const values = toWorldBookFormValues(record)
            return tldwClient.updateWorldBook(id, {
              name: values.name,
              description: values.description,
              enabled: nextEnabled,
              scan_depth: values.scan_depth,
              token_budget: values.token_budget,
              recursive_scanning: values.recursive_scanning
            })
          })
        )
      }

      qc.invalidateQueries({ queryKey: ["tldw:listWorldBooks"] })
      setSelectedWorldBookKeys([])
      notification.success({
        message: "Bulk action complete",
        description:
          operation === "delete"
            ? `Deleted ${selectedIds.length} world books.`
            : `${operation === "enable" ? "Enabled" : "Disabled"} ${selectedIds.length} world books.`
      })
    } catch (e: any) {
      notification.error({
        message: "Bulk action failed",
        description: e?.message || "Could not complete world-book bulk operation."
      })
    } finally {
      setBulkWorldBookAction(null)
    }
  }

  const columns = [
    { title: '', key: 'icon', width: 40, render: () => <BookOpen className="w-4 h-4" /> },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      sorter: (a: any, b: any) => String(a?.name || '').localeCompare(String(b?.name || '')),
      sortOrder: tableSort.field === "name" ? tableSort.order : null
    },
    { title: 'Description', dataIndex: 'description', key: 'description', render: (v: string) => <span className="line-clamp-1">{v}</span> },
    { title: 'Last Modified', dataIndex: 'last_modified', key: 'last_modified', render: (v: unknown) => renderLastModifiedCell(v) },
    { title: 'Attached To', key: 'attached_to', render: (_: any, record: any) => renderAttachedCell(record) },
    { title: 'Budget', dataIndex: 'token_budget', key: 'token_budget', render: (v: unknown) => renderBudgetCell(v) },
    {
      title: 'Enabled',
      dataIndex: 'enabled',
      key: 'enabled',
      sorter: (a: any, b: any) => Number(Boolean(a?.enabled)) - Number(Boolean(b?.enabled)),
      sortOrder: tableSort.field === "enabled" ? tableSort.order : null,
      render: (v: boolean) => v ? <Tag color="green">Enabled</Tag> : <Tag color="volcano">Disabled</Tag>
    },
    {
      title: 'Entries',
      dataIndex: 'entry_count',
      key: 'entry_count',
      sorter: (a: any, b: any) => Number(a?.entry_count || 0) - Number(b?.entry_count || 0),
      sortOrder: tableSort.field === "entry_count" ? tableSort.order : null
    },
    { title: 'Actions', key: 'actions', render: (_: any, record: any) => (
      <div className="flex gap-2">
        <Tooltip title="Edit">
          <Button
            type="text"
            size="small"
            aria-label="Edit world book"
            icon={<Pen className="w-4 h-4" />}
            onClick={() => {
              setEditId(record.id)
              editForm.setFieldsValue(toWorldBookFormValues(record))
              setOpenEdit(true)
            }}
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
                { id: record.id, name: record.name, entryCount: record.entry_count },
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
            onClick={() => setOpenAttach(record.id)}
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
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Input
            allowClear
            placeholder="Search world books…"
            aria-label="Search world books"
            value={listSearch}
            onChange={(e) => setListSearch(e.target.value)}
            className="w-full min-w-[220px] md:w-72"
          />
          <Select
            value={enabledFilter}
            onChange={(value) => setEnabledFilter(value)}
            aria-label="Filter by enabled status"
            className="w-40"
            options={[
              { label: "All statuses", value: "all" },
              { label: "Enabled", value: "enabled" },
              { label: "Disabled", value: "disabled" }
            ]}
          />
          <Select
            value={attachmentFilter}
            onChange={(value) => setAttachmentFilter(value)}
            aria-label="Filter by attachment state"
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
            onClick={() => setOpenImport(true)}
          >
            Import
          </Button>
          <Button type="primary" onClick={() => setOpen(true)}>New World Book</Button>
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
          onChange={(_, __, sorter: any) => {
            const resolvedSorter = Array.isArray(sorter) ? sorter[0] : sorter
            const field = resolvedSorter?.field
            setTableSort({
              field:
                field === "name" || field === "entry_count" || field === "enabled"
                  ? field
                  : undefined,
              order:
                resolvedSorter?.order === "ascend" || resolvedSorter?.order === "descend"
                  ? resolvedSorter.order
                  : null
            })
          }}
          rowClassName={(record: any) => (record?.enabled === false ? "opacity-75" : "")}
        />
      )}

      <Modal title="Create World Book" open={open} onCancel={handleCloseCreate} footer={null}>
        <WorldBookForm
          mode="create"
          form={createForm}
          worldBooks={(data || []) as any[]}
          submitting={creating}
          onSubmit={createWB}
        />
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
          <details className="rounded border border-border px-3 py-2">
            <summary className="cursor-pointer text-sm font-medium">
              Format help
            </summary>
            <div className="mt-2 space-y-2 text-xs text-text-muted">
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
                <details className="pt-1" data-testid="import-preview-entries">
                  <summary className="cursor-pointer text-sm font-medium">
                    Preview first {importPreview.previewEntries?.length} entries
                  </summary>
                  <div className="mt-2 space-y-2">
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

      <Modal title="World Book Statistics" open={!!statsFor} onCancel={() => setStatsFor(null)} footer={null}>
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
                            <p className="text-xs text-danger">
                              Estimated token usage exceeds the configured budget.
                            </p>
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
        onClose={() => setOpenTestMatching(false)}
        worldBooks={Array.isArray(data) ? (data as any[]) : []}
        initialWorldBookId={testMatchingWorldBookId}
      />

      <Modal title="Edit World Book" open={openEdit} onCancel={handleCloseEdit} footer={null}>
        <WorldBookForm
          mode="edit"
          form={editForm}
          worldBooks={(data || []) as any[]}
          submitting={updating}
          currentWorldBookId={editId}
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
                  render: (_: any, record: any) => {
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

const EntryManager: React.FC<{
  worldBookId: number
  worldBookName?: string
  worldBooks: Array<{ id?: number; name?: string }>
  entryFilterPreset?: EntryFilterPreset
  form: any
}> = ({
  worldBookId,
  worldBookName,
  worldBooks,
  entryFilterPreset = DEFAULT_ENTRY_FILTER_PRESET,
  form
}) => {
  const readSessionBoolean = React.useCallback((key: string, fallback: boolean) => {
    try {
      const raw = sessionStorage.getItem(key)
      if (raw == null) return fallback
      return raw === "true"
    } catch {
      return fallback
    }
  }, [])
  const writeSessionBoolean = React.useCallback((key: string, value: boolean) => {
    try {
      sessionStorage.setItem(key, String(value))
    } catch {
      // noop
    }
  }, [])

  const qc = useQueryClient()
  const notification = useAntdNotification()
  const confirmDanger = useConfirmDanger()
  const [editingEntry, setEditingEntry] = React.useState<any | null>(null)
  const [editForm] = Form.useForm()
  const [bulkMode, setBulkMode] = React.useState(false)
  const [bulkText, setBulkText] = React.useState('')
  const [bulkAdding, setBulkAdding] = React.useState(false)
  const [bulkProgress, setBulkProgress] = React.useState<BulkAddProgress | null>(null)
  const [bulkFailures, setBulkFailures] = React.useState<BulkAddFailure[]>([])
  const [selectedRowKeys, setSelectedRowKeys] = React.useState<React.Key[]>([])
  const [bulkPriorityValue, setBulkPriorityValue] = React.useState(50)
  const [bulkPriorityPopoverOpen, setBulkPriorityPopoverOpen] = React.useState(false)
  const [bulkMoveTargetId, setBulkMoveTargetId] = React.useState<number | null>(null)
  const [bulkMoveStrategy, setBulkMoveStrategy] = React.useState<"skip_existing" | "duplicate">(
    "skip_existing"
  )
  const [bulkMovePopoverOpen, setBulkMovePopoverOpen] = React.useState(false)
  const [bulkMovePending, setBulkMovePending] = React.useState(false)
  const [entrySearch, setEntrySearch] = React.useState(entryFilterPreset.searchText)
  const [entryEnabledFilter, setEntryEnabledFilter] = React.useState<"all" | "enabled" | "disabled">(
    entryFilterPreset.enabledFilter
  )
  const [entryMatchFilter, setEntryMatchFilter] = React.useState<"all" | "regex" | "plain">(
    entryFilterPreset.matchFilter
  )
  const [addMatchingOptionsOpen, setAddMatchingOptionsOpen] = React.useState<boolean>(() =>
    readSessionBoolean("worldbooks:add-matching-options-open", false)
  )
  const [editMatchingOptionsOpen, setEditMatchingOptionsOpen] = React.useState<boolean>(() =>
    readSessionBoolean("worldbooks:edit-matching-options-open", false)
  )
  const addRegexMatch = Form.useWatch('regex_match', form)
  const addCaseSensitive = Form.useWatch('case_sensitive', form)
  const addWholeWord = Form.useWatch('whole_word_match', form)
  const addKeywordsWatch = Form.useWatch('keywords', form)
  const addContentWatch = Form.useWatch('content', form)
  const editRegexMatch = Form.useWatch('regex_match', editForm)
  const editCaseSensitive = Form.useWatch('case_sensitive', editForm)
  const editWholeWord = Form.useWatch('whole_word_match', editForm)
  const editKeywordsWatch = Form.useWatch('keywords', editForm)
  const editContentWatch = Form.useWatch('content', editForm)

  React.useEffect(() => {
    setEntryEnabledFilter(entryFilterPreset.enabledFilter)
    setEntryMatchFilter(entryFilterPreset.matchFilter)
    setEntrySearch(entryFilterPreset.searchText)
  }, [
    entryFilterPreset.enabledFilter,
    entryFilterPreset.matchFilter,
    entryFilterPreset.searchText,
    worldBookId
  ])

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
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tldw:listWorldBookEntries', worldBookId] }); form.resetFields() },
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
    const appendableValue =
      typeof entry?.appendable === "boolean"
        ? entry.appendable
        : Boolean(entry?.metadata?.appendable)
    editForm.setFieldsValue({
      keywords: entry.keywords || [],
      content: entry.content,
      priority: entry.priority,
      enabled: entry.enabled,
      appendable: appendableValue,
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
  const keywordConflictCount = React.useMemo(
    () => keywordIndex.filter((item) => item.conflict).length,
    [keywordIndex]
  )

  const filteredEntryData = React.useMemo(() => {
    const source = Array.isArray(data) ? data : []
    const query = entrySearch.trim().toLowerCase()
    let next = source

    if (query) {
      next = next.filter((entry: any) => {
        const content = String(entry?.content || "").toLowerCase()
        const keywords = normalizeKeywords(entry?.keywords).join(" ").toLowerCase()
        return content.includes(query) || keywords.includes(query)
      })
    }

    if (entryEnabledFilter !== "all") {
      const enabled = entryEnabledFilter === "enabled"
      next = next.filter((entry: any) => Boolean(entry?.enabled) === enabled)
    }

    if (entryMatchFilter !== "all") {
      const requiresRegex = entryMatchFilter === "regex"
      next = next.filter((entry: any) => Boolean(entry?.regex_match) === requiresRegex)
    }

    return next
  }, [data, entryEnabledFilter, entryMatchFilter, entrySearch])

  const filteredEntryIds = React.useMemo(
    () => normalizeBulkEntryIds(filteredEntryData.map((entry: any) => entry?.entry_id)),
    [filteredEntryData]
  )
  const selectedEntryIds = React.useMemo(
    () => normalizeBulkEntryIds(selectedRowKeys),
    [selectedRowKeys]
  )
  const hasSelectedEntries = selectedEntryIds.length > 0
  const canEscalateSelectAll = hasSelectedEntries && selectedEntryIds.length < filteredEntryIds.length
  const moveDestinationOptions = React.useMemo(
    () =>
      (worldBooks || [])
        .filter((book) => Number(book?.id) !== worldBookId)
        .map((book) => ({
          label: String(book?.name || `World Book ${book?.id}`),
          value: Number(book?.id)
        }))
        .filter((book) => Number.isFinite(book.value) && book.value > 0),
    [worldBookId, worldBooks]
  )

  const bulkParse = React.useMemo(() => parseBulkEntries(bulkText), [bulkText])

  const getSelectedEntriesForMove = React.useCallback(() => {
    const sourceEntries = Array.isArray(data) ? data : []
    const selectedSet = new Set(selectedEntryIds)
    return sourceEntries.filter((entry: any) => selectedSet.has(Number(entry?.entry_id)))
  }, [data, selectedEntryIds])

  const handleBulkAction = async (operation: "enable" | "disable" | "delete") => {
    if (!hasSelectedEntries) return
    if (operation === "delete") {
      const ok = await confirmDanger({
        title: "Delete selected entries?",
        content: `This will permanently remove ${selectedEntryIds.length} entries.`,
        okText: "Delete",
        cancelText: "Cancel"
      })
      if (!ok) return
    }
    try {
      const response = await bulkOperate({ entry_ids: selectedEntryIds, operation })
      const failedCount = Array.isArray(response?.failed_ids) ? response.failed_ids.length : 0
      const affectedCount = Number(response?.affected_count ?? selectedEntryIds.length - failedCount)

      if (failedCount > 0) {
        notification.warning({
          message: "Bulk action completed with errors",
          description: `${affectedCount} entries updated, ${failedCount} failed.`
        })
        return
      }

      notification.success({
        message: "Bulk action complete",
        description: `${affectedCount} entries updated.`
      })
    } catch {
      // Error notification is handled in the mutation onError callback.
    }
  }

  const handleSelectAllFilteredEntries = () => {
    if (filteredEntryIds.length === 0) return
    setSelectedRowKeys(filteredEntryIds)
  }

  const handleBulkSetPriority = async () => {
    const payload = buildBulkSetPriorityPayload(selectedEntryIds, bulkPriorityValue)
    if (payload.entry_ids.length === 0) return

    try {
      const response = await bulkOperate(payload)
      const failedCount = Array.isArray(response?.failed_ids) ? response.failed_ids.length : 0
      const affectedCount = Number(response?.affected_count ?? payload.entry_ids.length - failedCount)

      if (failedCount > 0) {
        notification.warning({
          message: "Bulk priority completed with errors",
          description: `${affectedCount} entries updated, ${failedCount} failed.`
        })
      } else {
        notification.success({
          message: "Bulk priority updated",
          description: `Set priority ${payload.priority} for ${affectedCount} entries.`
        })
      }

      setBulkPriorityPopoverOpen(false)
    } catch {
      // Error notification is handled in the mutation onError callback.
    }
  }

  const handleBulkMoveEntries = async () => {
    const destinationId = Number(bulkMoveTargetId)
    if (!Number.isFinite(destinationId) || destinationId <= 0) return

    const selectedEntries = getSelectedEntriesForMove()
    if (selectedEntries.length === 0) return

    const destinationBookName =
      moveDestinationOptions.find((book) => book.value === destinationId)?.label ||
      `World Book ${destinationId}`
    const ok = await confirmDanger({
      title: `Move ${selectedEntries.length} entries?`,
      content: `Entries will be moved from "${worldBookName || `World Book ${worldBookId}`}" to "${destinationBookName}".`,
      okText: "Move",
      cancelText: "Cancel"
    })
    if (!ok) return

    setBulkMovePending(true)
    try {
      const destinationEntriesResponse = await tldwClient.listWorldBookEntries(destinationId, false)
      const destinationEntries = Array.isArray(destinationEntriesResponse?.entries)
        ? destinationEntriesResponse.entries
        : []
      const destinationKeys = new Set(
        destinationEntries.map((entry: any) =>
          `${normalizeKeywordList(entry?.keywords).join("|")}::${String(entry?.content || "")}`
        )
      )

      let copiedCount = 0
      let skippedCount = 0
      const failedIds: number[] = []
      const copiedSourceIds: number[] = []

      for (const entry of selectedEntries) {
        const sourceEntryId = Number(entry?.entry_id)
        const normalizedKeywords = normalizeKeywordList(entry?.keywords)
        const content = String(entry?.content || "")
        const dedupeKey = `${normalizedKeywords.join("|")}::${content}`
        const destinationAlreadyHasEntry = destinationKeys.has(dedupeKey)
        if (bulkMoveStrategy === "skip_existing" && destinationAlreadyHasEntry) {
          skippedCount += 1
          continue
        }

        try {
          await tldwClient.addWorldBookEntry(destinationId, {
            keywords: normalizedKeywords,
            content,
            priority: clampBulkPriority(entry?.priority, 50),
            enabled: Boolean(entry?.enabled),
            case_sensitive: Boolean(entry?.case_sensitive),
            regex_match: Boolean(entry?.regex_match),
            whole_word_match:
              typeof entry?.whole_word_match === "boolean" ? entry.whole_word_match : true,
            appendable:
              typeof entry?.appendable === "boolean"
                ? entry.appendable
                : Boolean(entry?.metadata?.appendable)
          })
          copiedCount += 1
          if (Number.isFinite(sourceEntryId) && sourceEntryId > 0) copiedSourceIds.push(sourceEntryId)
          destinationKeys.add(dedupeKey)
        } catch {
          if (Number.isFinite(sourceEntryId) && sourceEntryId > 0) failedIds.push(sourceEntryId)
        }
      }

      let deletedCount = 0
      if (copiedSourceIds.length > 0) {
        const deleteResponse = await bulkOperate({ entry_ids: copiedSourceIds, operation: "delete" })
        const failedDeletes = Array.isArray(deleteResponse?.failed_ids) ? deleteResponse.failed_ids.length : 0
        const affectedDeletes = Number(deleteResponse?.affected_count ?? copiedSourceIds.length - failedDeletes)
        deletedCount = Math.max(0, affectedDeletes)
      }

      const failedCount = failedIds.length + Math.max(0, copiedCount - deletedCount)
      if (failedCount > 0 || skippedCount > 0) {
        notification.warning({
          message: "Move completed with warnings",
          description: `${deletedCount} moved, ${skippedCount} skipped, ${failedCount} failed.`
        })
      } else {
        notification.success({
          message: "Entries moved",
          description: `Moved ${deletedCount} entries to "${destinationBookName}".`
        })
      }

      setBulkMovePopoverOpen(false)
      setBulkMoveTargetId(null)
    } catch (error: any) {
      notification.error({
        message: "Move failed",
        description: error?.message || "Failed to move selected entries."
      })
    } finally {
      setBulkMovePending(false)
    }
  }

  const handleBulkAddEntries = async () => {
    if (bulkParse.entries.length === 0 || bulkParse.errors.length > 0) return
    setBulkAdding(true)
    setBulkFailures([])
    try {
      const result = await runBulkAddEntries({
        entries: bulkParse.entries,
        concurrency: DEFAULT_BULK_ADD_CONCURRENCY,
        addEntry: async (entry) => tldwClient.addWorldBookEntry(worldBookId, entry),
        onProgress: (progress) => setBulkProgress(progress)
      })

      setBulkFailures(result.failures)
      if (result.succeeded > 0) {
        qc.invalidateQueries({ queryKey: ['tldw:listWorldBookEntries', worldBookId] })
      }

      if (result.failed === 0) {
        notification.success({ message: `Added ${result.succeeded} entries` })
        setBulkText('')
      } else if (result.succeeded === 0) {
        notification.error({
          message: "Bulk add failed",
          description: "No entries were added. Review the failure summary below."
        })
      } else {
        notification.warning({
          message: "Bulk add completed with errors",
          description: `${result.succeeded} entries added, ${result.failed} failed.`
        })
      }
    } catch (error: any) {
      notification.error({ message: "Bulk add failed", description: error?.message || "Unexpected error" })
    } finally {
      setBulkAdding(false)
    }
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
          <div className="flex flex-wrap items-center gap-2">
            <Input
              allowClear
              value={entrySearch}
              onChange={(event) => setEntrySearch(event.target.value)}
              placeholder="Search entries…"
              aria-label="Search entries"
              className="w-full min-w-[220px] md:w-72"
            />
            <Select
              value={entryEnabledFilter}
              onChange={(value) => setEntryEnabledFilter(value)}
              aria-label="Filter entries by enabled status"
              className="w-40"
              options={[
                { label: "All entries", value: "all" },
                { label: "Enabled", value: "enabled" },
                { label: "Disabled", value: "disabled" }
              ]}
            />
            <Select
              value={entryMatchFilter}
              onChange={(value) => setEntryMatchFilter(value)}
              aria-label="Filter entries by match type"
              className="w-44"
              options={[
                { label: "All match types", value: "all" },
                { label: "Regex only", value: "regex" },
                { label: "Plain keywords", value: "plain" }
              ]}
            />
          </div>
          {hasSelectedEntries && (
            <div className="rounded border border-border p-2 space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-semibold">{selectedEntryIds.length} selected</span>
                <div className="flex flex-wrap items-center gap-2">
                  {canEscalateSelectAll && (
                    <Button
                      type="link"
                      size="small"
                      className="px-0"
                      onClick={handleSelectAllFilteredEntries}
                      aria-label={`Select all ${filteredEntryIds.length} entries`}
                    >
                      Select all {filteredEntryIds.length} entries
                    </Button>
                  )}
                  <Button
                    type="link"
                    size="small"
                    className="px-0"
                    onClick={() => setSelectedRowKeys([])}
                    aria-label="Clear selected entries"
                  >
                    Clear selection
                  </Button>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button size="small" loading={bulkPending} onClick={() => void handleBulkAction("enable")}>
                  Enable
                </Button>
                <Button size="small" loading={bulkPending} onClick={() => void handleBulkAction("disable")}>
                  Disable
                </Button>
                <Popover
                  trigger="click"
                  open={bulkMovePopoverOpen}
                  onOpenChange={setBulkMovePopoverOpen}
                  content={
                    <div className="space-y-2 w-64">
                      <p className="text-xs text-text-muted">Move selected entries to another world book.</p>
                      {moveDestinationOptions.length === 0 && (
                        <p className="text-xs text-text-muted">
                          Create another world book to enable move actions.
                        </p>
                      )}
                      {moveDestinationOptions.length > 0 && (
                        <>
                          <Select
                            placeholder="Destination world book"
                            value={bulkMoveTargetId ?? undefined}
                            onChange={(value) => setBulkMoveTargetId(Number(value))}
                            options={moveDestinationOptions}
                            aria-label="Bulk move destination"
                          />
                          <Select
                            value={bulkMoveStrategy}
                            onChange={(value) =>
                              setBulkMoveStrategy(value as "skip_existing" | "duplicate")
                            }
                            options={[
                              { label: "Skip existing entries", value: "skip_existing" },
                              { label: "Allow duplicates", value: "duplicate" }
                            ]}
                            aria-label="Bulk move conflict strategy"
                          />
                          <Button
                            size="small"
                            type="primary"
                            className="w-full"
                            loading={bulkMovePending}
                            disabled={!bulkMoveTargetId}
                            onClick={() => void handleBulkMoveEntries()}
                          >
                            Move Entries
                          </Button>
                        </>
                      )}
                    </div>
                  }
                >
                  <Button size="small" loading={bulkMovePending} disabled={moveDestinationOptions.length === 0}>
                    Move To
                  </Button>
                </Popover>
                <Popover
                  trigger="click"
                  open={bulkPriorityPopoverOpen}
                  onOpenChange={setBulkPriorityPopoverOpen}
                  content={
                    <div className="space-y-2 w-52">
                      <p className="text-xs text-text-muted">Set a single priority for all selected entries.</p>
                      <InputNumber
                        min={0}
                        max={100}
                        value={bulkPriorityValue}
                        onChange={(value) => setBulkPriorityValue(clampBulkPriority(value))}
                        style={{ width: "100%" }}
                        aria-label="Bulk priority value"
                      />
                      <Button
                        size="small"
                        type="primary"
                        className="w-full"
                        loading={bulkPending}
                        onClick={() => void handleBulkSetPriority()}
                      >
                        Apply Priority
                      </Button>
                    </div>
                  }
                >
                  <Button size="small" loading={bulkPending}>
                    Set Priority
                  </Button>
                </Popover>
                <Button size="small" danger loading={bulkPending} onClick={() => void handleBulkAction("delete")}>
                  Delete
                </Button>
              </div>
            </div>
          )}
          <p className="text-xs text-text-muted">
            Entry order is controlled by priority (0-100). Higher-priority entries are evaluated first.
          </p>
          <Table
            size="small"
            virtual
            pagination={false}
            scroll={{ y: 420, x: 900 }}
            rowKey={(r: any) => r.entry_id}
            rowSelection={{
              selectedRowKeys,
              onChange: (keys) => setSelectedRowKeys(keys)
            }}
            dataSource={filteredEntryData}
            locale={{
              emptyText: "No entries match the current filters."
            }}
            columns={[
              { title: 'Keywords', dataIndex: 'keywords', key: 'keywords', width: 200, render: (arr: string[]) => <div className="flex flex-wrap gap-1">{(arr||[]).map((k) => <Tag key={k}>{k}</Tag>)}</div> },
              { title: 'Content', dataIndex: 'content', key: 'content', render: (v: string) => <span className="line-clamp-2">{v}</span> },
              {
                title: 'Priority',
                dataIndex: 'priority',
                key: 'priority',
                width: 110,
                render: (value: number) => {
                  const band = getPriorityBand(value)
                  return <Tag color={getPriorityTagColor(band)}>{Number(value || 0)}/100</Tag>
                }
              },
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
            <summary
              className="cursor-pointer text-sm text-text-muted hover:text-text"
              aria-label={`Keyword Index${keywordConflictCount > 0 ? `, ${keywordConflictCount} conflicts` : ""}`}
            >
              Keyword Index{keywordConflictCount > 0 ? ` (${keywordConflictCount} conflicts)` : ""}
            </summary>
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
          <Form.Item
            name="keywords"
            label="Keywords"
            rules={[
              {
                validator: (_: any, value: unknown) => {
                  if (!editForm.getFieldValue("regex_match")) return Promise.resolve()
                  const message = validateRegexKeywords(value)
                  return message ? Promise.reject(new Error(message)) : Promise.resolve()
                }
              }
            ]}
          >
            <Select
              mode="tags"
              tokenSeparators={[","]}
              placeholder="Add keywords and press Enter"
            />
          </Form.Item>
          <KeywordPreview value={editKeywordsWatch} />
          <Form.Item name="content" label="Content" rules={[{ required: true }]}>
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
          </Form.Item>
          <p className="text-xs text-text-muted -mt-4 mb-3">{formatEntryContentStats(editContentWatch)}</p>
          <Form.Item
            name="priority"
            label={<LabelWithHelp label="Priority" help="Higher values = more important (0-100). Higher priority entries are selected first when token budget is limited." />}
          >
            <InputNumber style={{ width: '100%' }} min={0} max={100} />
          </Form.Item>
          <Form.Item name="enabled" label="Enabled" valuePropName="checked"><Switch /></Form.Item>
          <Form.Item
            name="appendable"
            label={
              <LabelWithHelp
                label="Appendable"
                help="When enabled, this entry's content is appended to other triggered content rather than replacing it."
              />
            }
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>
          <details
            className="mb-4"
            open={editMatchingOptionsOpen}
            onToggle={(event) => {
              const nextOpen = (event.currentTarget as HTMLDetailsElement).open
              setEditMatchingOptionsOpen(nextOpen)
              writeSessionBoolean("worldbooks:edit-matching-options-open", nextOpen)
            }}
          >
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
            <Form.Item
              name="keywords"
              label="Keywords"
              rules={[
                {
                  validator: (_: any, value: unknown) => {
                    if (!form.getFieldValue("regex_match")) return Promise.resolve()
                    const message = validateRegexKeywords(value)
                    return message ? Promise.reject(new Error(message)) : Promise.resolve()
                  }
                }
              ]}
            >
              <Select
                mode="tags"
                tokenSeparators={[","]}
                placeholder="Add keywords and press Enter"
              />
            </Form.Item>
            <KeywordPreview value={addKeywordsWatch} />
            <Form.Item name="content" label="Content" rules={[{ required: true }]}>
              <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
            </Form.Item>
            <p className="text-xs text-text-muted -mt-4 mb-3">{formatEntryContentStats(addContentWatch)}</p>
            <Form.Item
              name="priority"
              label={<LabelWithHelp label="Priority" help="Higher values = more important (0-100). Higher priority entries are selected first when token budget is limited." />}
            >
              <InputNumber style={{ width: '100%' }} min={0} max={100} placeholder="Default: 50" />
            </Form.Item>
            <Form.Item name="enabled" label="Enabled" valuePropName="checked"><Switch defaultChecked /></Form.Item>
            <Form.Item
              name="appendable"
              label={
                <LabelWithHelp
                  label="Appendable"
                  help="When enabled, this entry's content is appended to other triggered content rather than replacing it."
                />
              }
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
          <details
            className="mb-4"
            open={addMatchingOptionsOpen}
            onToggle={(event) => {
              const nextOpen = (event.currentTarget as HTMLDetailsElement).open
              setAddMatchingOptionsOpen(nextOpen)
              writeSessionBoolean("worldbooks:add-matching-options-open", nextOpen)
            }}
          >
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
            <details className="rounded border border-border p-2">
              <summary className="cursor-pointer text-sm text-text-muted hover:text-text">Supported formats</summary>
              <div className="mt-2 space-y-1 text-xs text-text-muted">
                {BULK_ENTRY_FORMAT_EXAMPLES.filter((format) =>
                  SUPPORTED_BULK_SEPARATORS.includes(format.separator)
                ).map((format) => (
                  <p key={format.separator}>
                    <code>{format.example}</code>
                  </p>
                ))}
              </div>
            </details>
            <Input.TextArea
              value={bulkText}
              onChange={(e) => {
                setBulkText(e.target.value)
                if (bulkFailures.length > 0) setBulkFailures([])
              }}
              autoSize={{ minRows: 4, maxRows: 10 }}
              placeholder="One per line: keyword1, keyword2 -> content"
              aria-label="Bulk entry input"
            />
            {bulkParse.errors.length > 0 && (
              <div className="text-sm text-danger space-y-1">
                {bulkParse.errors.map((err, i) => <p key={i}>{err}</p>)}
              </div>
            )}
            <div className="text-xs text-text-muted">Parsed entries: {bulkParse.entries.length}</div>
            {bulkProgress && (
              <div className="space-y-1" aria-live="polite">
                <Progress
                  size="small"
                  percent={
                    bulkProgress.total > 0
                      ? Math.round((bulkProgress.completed / bulkProgress.total) * 100)
                      : 0
                  }
                  status={bulkAdding ? "active" : bulkProgress.failed > 0 ? "exception" : "success"}
                />
                <p className="text-xs text-text-muted">
                  Bulk progress: {bulkProgress.completed} / {bulkProgress.total} ({bulkProgress.succeeded} succeeded, {bulkProgress.failed} failed)
                </p>
              </div>
            )}
            {bulkFailures.length > 0 && (
              <div className="rounded border border-border p-2 space-y-1">
                <p className="text-sm font-medium text-danger">Failed entries ({bulkFailures.length})</p>
                <div className="max-h-36 overflow-auto space-y-1 text-xs">
                  {bulkFailures.map((failure, index) => (
                    <p key={`${failure.line}-${index}`} className="text-danger">
                      Line {failure.line} ({failure.keywords.join(", ") || "no keywords"}): {failure.message}
                    </p>
                  ))}
                </div>
              </div>
            )}
            <Button
              type="primary"
              className="w-full"
              loading={bulkAdding}
              disabled={bulkParse.entries.length === 0 || bulkParse.errors.length > 0}
              onClick={handleBulkAddEntries}
            >
              Add Entries
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
