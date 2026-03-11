import React from "react"
import { Select, Modal, Tooltip } from "antd"
import { Trash2 } from "lucide-react"
import { BlocklistSyntaxRef } from "./components/BlocklistSyntaxRef"
import { CATEGORY_SUGGESTIONS, ACTION_OPTIONS } from "./moderation-utils"
import type { useBlocklist } from "./hooks/useBlocklist"
import type { BlocklistLintItem } from "@/services/moderation"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BlocklistStudioPanelProps {
  blocklist: ReturnType<typeof useBlocklist>
  messageApi: { success: (msg: string) => void; error: (msg: string) => void; warning: (msg: string) => void }
}

type SubTab = "managed" | "raw"
type PhaseValue = "input" | "output" | "both"

const SUB_TABS: { key: SubTab; label: string }[] = [
  { key: "managed", label: "Managed Rules" },
  { key: "raw", label: "Raw Editor" }
]

const PHASE_OPTIONS: { value: PhaseValue; label: string }[] = [
  { value: "input", label: "Input" },
  { value: "output", label: "Output" },
  { value: "both", label: "Both" }
]

const PAGE_SIZE = 10

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Compose a blocklist grammar line from structured fields */
function composeLine(
  pattern: string,
  action: string,
  replacement: string,
  categories: string[],
  _phase: PhaseValue
): string {
  let line = pattern.trim()
  if (!line) return ""

  // action suffix
  if (action === "redact" && replacement) {
    line += ` -> redact:${replacement}`
  } else if (action && action !== "block") {
    line += ` -> ${action}`
  } else if (action === "block") {
    line += " -> block"
  }

  // categories
  if (categories.length > 0) {
    line += ` #${categories.join(",")}`
  }

  return line
}

/** Detect whether a pattern string looks like a regex */
function isRegexPattern(pattern: string): boolean {
  const trimmed = pattern.trim()
  return trimmed.startsWith("/") && /\/[gimsxy]*$/.test(trimmed)
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const LintResultsTable: React.FC<{ items: BlocklistLintItem[] }> = ({ items }) => {
  if (items.length === 0) return null
  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <table className="w-full text-sm" data-testid="lint-results-table">
        <thead>
          <tr className="text-left text-text-muted bg-surface/50">
            <th className="px-3 py-2 font-medium">#</th>
            <th className="px-3 py-2 font-medium">Line</th>
            <th className="px-3 py-2 font-medium">Status</th>
            <th className="px-3 py-2 font-medium">Details</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => (
            <tr key={idx} className="border-t border-border">
              <td className="px-3 py-2 text-text-muted">{item.index}</td>
              <td className="px-3 py-2 font-mono text-xs max-w-[200px] truncate">{item.line}</td>
              <td className="px-3 py-2">
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                    item.ok
                      ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                      : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
                  }`}
                >
                  {item.ok ? "Valid" : "Error"}
                </span>
              </td>
              <td className="px-3 py-2 text-xs text-text-muted">
                {item.error || item.warning || (item.ok ? `${item.pattern_type ?? "literal"} / ${item.action ?? "block"}` : "")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const BlocklistStudioPanel: React.FC<BlocklistStudioPanelProps> = ({ blocklist, messageApi }) => {
  const [subTab, setSubTab] = React.useState<SubTab>("managed")
  const [page, setPage] = React.useState(1)

  // Add-rule form state
  const [pattern, setPattern] = React.useState("")
  const [action, setAction] = React.useState("block")
  const [replacement, setReplacement] = React.useState("")
  const [categories, setCategories] = React.useState<string[]>([])
  const [phase, setPhase] = React.useState<PhaseValue>("both")
  const [inlineLint, setInlineLint] = React.useState<BlocklistLintItem[] | null>(null)

  // Auto-load managed rules on mount
  React.useEffect(() => {
    void blocklist.loadManaged().catch((err) => {
      console.error("[ModerationPlayground] Failed to load managed blocklist:", err)
      messageApi.error("Failed to load managed blocklist")
    })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const composed = composeLine(pattern, action, replacement, categories, phase)

  const handleValidate = async () => {
    if (!composed) {
      messageApi.warning("Enter a pattern first")
      return
    }
    try {
      // Temporarily set the managed line to run lint
      blocklist.setManagedLine(composed)
      // Small delay to let state settle, then call lint
      await new Promise<void>((resolve) => {
        setTimeout(resolve, 0)
      })
      // Use direct lint approach — set line then call lint
      await blocklist.lintManagedLine()
      if (blocklist.managedLint) {
        setInlineLint(blocklist.managedLint.items)
      }
    } catch (err: any) {
      messageApi.error(err?.message || "Validation failed")
    }
  }

  // Keep inline lint in sync with managedLint
  React.useEffect(() => {
    if (blocklist.managedLint) {
      setInlineLint(blocklist.managedLint.items)
    }
  }, [blocklist.managedLint])

  const handleAddRule = async () => {
    if (!composed) {
      messageApi.warning("Enter a pattern first")
      return
    }
    try {
      blocklist.setManagedLine(composed)
      // Wait for state to propagate
      await new Promise<void>((resolve) => setTimeout(resolve, 0))
      await blocklist.appendManaged()
      messageApi.success("Rule added")
      // Reset form
      setPattern("")
      setAction("block")
      setReplacement("")
      setCategories([])
      setPhase("both")
      setInlineLint(null)
    } catch (err: any) {
      messageApi.error(err?.message || "Failed to add rule")
    }
  }

  const handleDelete = (itemId: number) => {
    Modal.confirm({
      title: "Delete rule?",
      content: "This action cannot be undone.",
      okText: "Delete",
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await blocklist.deleteManaged(itemId)
          messageApi.success("Rule deleted")
        } catch (err: any) {
          messageApi.error(err?.message || "Delete failed")
        }
      }
    })
  }

  // Pagination
  const totalItems = blocklist.managedItems.length
  const totalPages = Math.max(1, Math.ceil(totalItems / PAGE_SIZE))
  const pagedItems = blocklist.managedItems.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  // ---------------------------------------------------------------------------
  // Managed Rules view
  // ---------------------------------------------------------------------------

  const renderManaged = () => (
    <div className="space-y-6">
      {/* Add rule form */}
      <div className="border border-border rounded-lg p-4 space-y-4">
        <h4 className="text-sm font-semibold">Add Rule</h4>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {/* Pattern */}
          <div className="sm:col-span-2">
            <label className="block text-xs text-text-muted mb-1">Pattern</label>
            <input
              type="text"
              value={pattern}
              onChange={(e) => setPattern(e.target.value)}
              placeholder='Enter pattern or /regex/'
              className="w-full px-3 py-2 border border-border rounded-lg bg-bg text-text text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              data-testid="pattern-input"
            />
          </div>

          {/* Action */}
          <div>
            <label className="block text-xs text-text-muted mb-1">Action</label>
            <select
              value={action}
              onChange={(e) => setAction(e.target.value)}
              className="w-full px-3 py-2 border border-border rounded-lg bg-bg text-text text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              data-testid="action-select"
            >
              {ACTION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Replacement (only for redact) */}
          {action === "redact" && (
            <div>
              <label className="block text-xs text-text-muted mb-1">Replacement</label>
              <input
                type="text"
                value={replacement}
                onChange={(e) => setReplacement(e.target.value)}
                placeholder="[REDACTED]"
                className="w-full px-3 py-2 border border-border rounded-lg bg-bg text-text text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          )}

          {/* Categories */}
          <div className={action === "redact" ? "sm:col-span-2" : ""}>
            <label className="block text-xs text-text-muted mb-1">Categories</label>
            <Select
              mode="tags"
              value={categories}
              onChange={setCategories}
              placeholder="Select or type categories"
              className="w-full"
              options={CATEGORY_SUGGESTIONS.map((c) => ({ value: c.value, label: c.label }))}
              data-testid="categories-select"
            />
          </div>

          {/* Phase */}
          <div>
            <label className="block text-xs text-text-muted mb-1">Phase</label>
            <div className="flex rounded-lg border border-border overflow-hidden" role="group">
              {PHASE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setPhase(opt.value)}
                  className={`flex-1 px-3 py-2 text-sm font-medium transition-colors ${
                    phase === opt.value
                      ? "bg-blue-500 text-white"
                      : "bg-bg text-text-muted hover:text-text hover:bg-surface/50"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Composed preview */}
        {composed && (
          <div className="text-xs text-text-muted font-mono bg-surface/30 rounded px-3 py-2">
            Preview: <code>{composed}</code>
          </div>
        )}

        {/* Buttons */}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleValidate}
            disabled={blocklist.loading || !composed}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-border text-text hover:bg-surface/50 transition-colors disabled:opacity-50"
          >
            Validate
          </button>
          <button
            type="button"
            onClick={handleAddRule}
            disabled={blocklist.loading || !composed}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            Add rule
          </button>
        </div>

        {/* Inline lint results */}
        {inlineLint && inlineLint.length > 0 && (
          <div className="mt-2">
            <LintResultsTable items={inlineLint} />
          </div>
        )}
      </div>

      {/* Managed lint results */}
      {blocklist.managedLint && blocklist.managedLint.items.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold mb-2">Lint Results</h4>
          <LintResultsTable items={blocklist.managedLint.items} />
        </div>
      )}

      {/* Rules table */}
      <div>
        <h4 className="text-sm font-semibold mb-2">Current Rules</h4>
        {totalItems === 0 ? (
          <div className="border border-border rounded-lg p-8 text-center text-text-muted text-sm" data-testid="empty-rules">
            No rules loaded. Rules will appear here after loading the managed blocklist.
          </div>
        ) : (
          <>
            <div className="border border-border rounded-lg overflow-hidden">
              <table className="w-full text-sm" data-testid="rules-table">
                <thead>
                  <tr className="text-left text-text-muted bg-surface/50">
                    <th className="px-3 py-2 font-medium w-10">#</th>
                    <th className="px-3 py-2 font-medium">Pattern</th>
                    <th className="px-3 py-2 font-medium">Type</th>
                    <th className="px-3 py-2 font-medium">Action</th>
                    <th className="px-3 py-2 font-medium">Categories</th>
                    <th className="px-3 py-2 font-medium w-10"></th>
                  </tr>
                </thead>
                <tbody>
                  {pagedItems.map((item) => {
                    // Parse the line to extract info for display
                    const line = item.line.trim()
                    const patternPart = line.split(" -> ")[0]?.split(" #")[0] ?? line
                    const isRegex = isRegexPattern(patternPart)
                    const actionMatch = line.match(/-> (block|redact|warn)/)
                    const itemAction = actionMatch?.[1] ?? "block"
                    const catMatch = line.match(/#([\w,]+)\s*$/)
                    const itemCats = catMatch?.[1]?.split(",").filter(Boolean) ?? []

                    const actionColors: Record<string, string> = {
                      block: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
                      redact: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
                      warn: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300"
                    }

                    return (
                      <tr key={item.id} className="border-t border-border">
                        <td className="px-3 py-2 text-text-muted">{item.id}</td>
                        <td className="px-3 py-2 font-mono text-xs max-w-[200px] truncate">
                          <Tooltip title={patternPart}>{patternPart}</Tooltip>
                        </td>
                        <td className="px-3 py-2">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                              isRegex
                                ? "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300"
                                : "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300"
                            }`}
                          >
                            {isRegex ? "regex" : "literal"}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${actionColors[itemAction] ?? ""}`}
                          >
                            {itemAction}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex flex-wrap gap-1">
                            {itemCats.map((cat) => (
                              <span
                                key={cat}
                                className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-surface text-text-muted"
                              >
                                {cat}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="px-3 py-2">
                          <button
                            type="button"
                            onClick={() => handleDelete(item.id)}
                            className="p-1 text-text-muted hover:text-red-500 transition-colors"
                            aria-label={`Delete rule ${item.id}`}
                          >
                            <Trash2 size={14} />
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between mt-3">
                <span className="text-xs text-text-muted">
                  Page {page} of {totalPages} ({totalItems} rules)
                </span>
                <div className="flex gap-1">
                  <button
                    type="button"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1}
                    className="px-3 py-1 text-xs rounded border border-border hover:bg-surface/50 disabled:opacity-50"
                  >
                    Prev
                  </button>
                  <button
                    type="button"
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page >= totalPages}
                    className="px-3 py-1 text-xs rounded border border-border hover:bg-surface/50 disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}

            {/* Version footer */}
            {blocklist.managedVersion && (
              <div className="mt-2 text-xs text-text-muted">
                Version: <code>{blocklist.managedVersion.slice(0, 12)}</code>
              </div>
            )}
          </>
        )}
      </div>

      {/* Syntax reference */}
      <BlocklistSyntaxRef />
    </div>
  )

  // ---------------------------------------------------------------------------
  // Raw Editor view
  // ---------------------------------------------------------------------------

  const renderRaw = () => (
    <div className="space-y-4">
      {/* Warning banner */}
      <div className="p-3 border border-yellow-200 dark:border-yellow-800 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg text-sm text-yellow-800 dark:text-yellow-300">
        Raw file editing replaces all existing rules. Use with caution.
      </div>

      {/* Buttons */}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={async () => {
            try {
              await blocklist.loadRaw()
              messageApi.success("Blocklist loaded")
            } catch (err: any) {
              messageApi.error(err?.message || "Load failed")
            }
          }}
          disabled={blocklist.loading}
          className="px-4 py-2 text-sm font-medium rounded-lg border border-border text-text hover:bg-surface/50 transition-colors disabled:opacity-50"
        >
          Load blocklist
        </button>
        <button
          type="button"
          onClick={async () => {
            try {
              await blocklist.lintRaw()
              messageApi.success("Validation complete")
            } catch (err: any) {
              messageApi.error(err?.message || "Validation failed")
            }
          }}
          disabled={blocklist.loading}
          className="px-4 py-2 text-sm font-medium rounded-lg border border-border text-text hover:bg-surface/50 transition-colors disabled:opacity-50"
        >
          Validate all
        </button>
        <button
          type="button"
          onClick={async () => {
            try {
              await blocklist.saveRaw()
              messageApi.success("Blocklist saved")
            } catch (err: any) {
              messageApi.error(err?.message || "Save failed")
            }
          }}
          disabled={blocklist.loading}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          Save / Replace
        </button>
      </div>

      {/* TextArea */}
      <textarea
        value={blocklist.rawText}
        onChange={(e) => blocklist.setRawText(e.target.value)}
        rows={12}
        className="w-full px-3 py-2 border border-border rounded-lg bg-bg text-text font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
        placeholder="# Enter blocklist rules, one per line..."
        data-testid="raw-editor"
      />

      {/* Lint results */}
      {blocklist.rawLint && blocklist.rawLint.items.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold mb-2">
            Lint Results ({blocklist.rawLint.valid_count} valid, {blocklist.rawLint.invalid_count} invalid)
          </h4>
          <LintResultsTable items={blocklist.rawLint.items} />
        </div>
      )}

      {/* Syntax reference */}
      <BlocklistSyntaxRef />
    </div>
  )

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Sub-tab bar */}
      <div className="border-b border-border">
        <div className="flex overflow-x-auto -mb-px" role="tablist">
          {SUB_TABS.map((tab) => (
            <button
              key={tab.key}
              role="tab"
              aria-selected={subTab === tab.key}
              onClick={() => setSubTab(tab.key)}
              className={`
                px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors
                ${
                  subTab === tab.key
                    ? "border-blue-500 text-blue-600 dark:text-blue-400"
                    : "border-transparent text-text-muted hover:text-text hover:border-gray-300"
                }
              `}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      {subTab === "managed" ? renderManaged() : renderRaw()}
    </div>
  )
}

export default BlocklistStudioPanel
