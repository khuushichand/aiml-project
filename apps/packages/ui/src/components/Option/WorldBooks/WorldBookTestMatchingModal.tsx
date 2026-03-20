import { Button, Descriptions, Empty, InputNumber, Modal, Select, Switch } from "antd"
import React from "react"
import {
  tldwClient,
  type WorldBookProcessDiagnostic,
  type WorldBookProcessResponse
} from "@/services/tldw/TldwApiClient"
import { Input } from "antd"
import { WORLD_BOOK_FORM_DEFAULTS } from "./worldBookFormUtils"
import {
  ACCESSIBLE_SWITCH_TEXT_PROPS,
  getReasonLabel,
  LOREBOOK_DEBUG_ENTRYPOINT_HREF,
  LOREBOOK_METRIC_LABELS,
  loadSavedTestMatchingSample,
  MODAL_BODY_SCROLL_STYLE,
  normalizeWorldBookSetting,
  persistTestMatchingSample
} from "./worldBookManagerUtils"

export type WorldBookTestMatchingModalProps = {
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

export const WorldBookTestMatchingModal: React.FC<WorldBookTestMatchingModalProps> = ({
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
    (): Array<Record<string, any> & { id: number }> =>
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
    setSampleText(loadSavedTestMatchingSample())
    setErrorMessage(null)
  }, [applyWorldBookDefaults, initialWorldBookId, open, testableWorldBooks])

  React.useEffect(() => {
    if (!open) return
    applyWorldBookDefaults(selectedWorldBook)
  }, [applyWorldBookDefaults, open, selectedWorldBook])

  React.useEffect(() => {
    if (!open) return
    persistTestMatchingSample(sampleText)
  }, [open, sampleText])

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
      styles={{ body: MODAL_BODY_SCROLL_STYLE }}
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
                {...ACCESSIBLE_SWITCH_TEXT_PROPS}
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
                {typeof tokenBudgetValue === "number" ? tokenBudgetValue : "\u2014"}
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
