import React from "react"
import { Button, Input, Popover, Tag, Tooltip } from "antd"
import { Check, CheckCircle2, ChevronDown, ChevronUp, Pen, Play, Trash2, X } from "lucide-react"
import { DICTIONARY_ENTRY_COLUMN_RESPONSIVE } from "../entryListUtils"

type InlineEditableEntryField = "pattern" | "replacement"

type InlineEditState = {
  entryId: number
  field: InlineEditableEntryField
  value: string
  initialValue: string
}

type UseDictionaryEntryTableColumnsParams = {
  inlineEdit: InlineEditState | null
  setInlineEdit: React.Dispatch<React.SetStateAction<InlineEditState | null>>
  inlineEditError: string | null
  setInlineEditError: (value: string | null) => void
  inlineEditSaving: boolean
  cancelInlineEdit: () => void
  saveInlineEdit: () => Promise<void> | void
  startInlineEdit: (entry: any, field: InlineEditableEntryField) => void
  entryPriorityById: Map<number, number>
  reorderBusyEntryId: number | null
  canReorderEntries: boolean
  orderedEntryCount: number
  onMoveEntry: (entryId: number, direction: -1 | 1) => Promise<void> | void
  testingEntryId: number | null
  setTestingEntryId: (entryId: number | null) => void
  inlineTestInput: string
  setInlineTestInput: (value: string) => void
  inlineTestResult: string | null
  setInlineTestResult: (value: string | null) => void
  onOpenEditEntry: (entry: any) => void
  onDeleteEntry: (entry: any) => Promise<void> | void
}

function toSafeNonNegativeInteger(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    return 0
  }
  return Math.floor(value)
}

function runInlineEntryTest(entry: any, input: string): string {
  try {
    let result = input
    if (entry?.type === "regex") {
      const regexMatch = String(entry?.pattern || "").match(/^\/(.*)\/([gimsuvy]*)$/)
      const regex = regexMatch
        ? new RegExp(regexMatch[1], regexMatch[2])
        : new RegExp(String(entry?.pattern || ""), entry?.case_sensitive ? "" : "i")
      result = input.replace(regex, String(entry?.replacement || ""))
    } else {
      const flags = entry?.case_sensitive ? "g" : "gi"
      const escapedPattern = String(entry?.pattern || "").replace(
        /[.*+?^${}()|[\]\\]/g,
        "\\$&"
      )
      result = input.replace(
        new RegExp(escapedPattern, flags),
        String(entry?.replacement || "")
      )
    }
    return result
  } catch (e: any) {
    return `Error: ${e?.message || "Failed to test entry"}`
  }
}

export function useDictionaryEntryTableColumns({
  inlineEdit,
  setInlineEdit,
  inlineEditError,
  setInlineEditError,
  inlineEditSaving,
  cancelInlineEdit,
  saveInlineEdit,
  startInlineEdit,
  entryPriorityById,
  reorderBusyEntryId,
  canReorderEntries,
  orderedEntryCount,
  onMoveEntry,
  testingEntryId,
  setTestingEntryId,
  inlineTestInput,
  setInlineTestInput,
  inlineTestResult,
  setInlineTestResult,
  onOpenEditEntry,
  onDeleteEntry
}: UseDictionaryEntryTableColumnsParams): any[] {
  return React.useMemo(
    () => [
      {
        title: "Pattern",
        dataIndex: "pattern",
        key: "pattern",
        render: (value: string, record: any) => {
          const entryId = Number(record?.id)
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
                        current ? { ...current, value: event.target.value } : current
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
                    aria-label={`Inline edit pattern for ${record.pattern}`}
                  />
                  <button
                    type="button"
                    className="min-w-[28px] min-h-[28px] flex items-center justify-center rounded border border-border text-success hover:bg-success/10"
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => {
                      void saveInlineEdit()
                    }}
                    disabled={inlineEditSaving}
                    aria-label={`Save pattern edit for ${record.pattern}`}
                  >
                    <Check className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    className="min-w-[28px] min-h-[28px] flex items-center justify-center rounded border border-border text-text-muted hover:bg-surface2"
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={cancelInlineEdit}
                    disabled={inlineEditSaving}
                    aria-label={`Cancel pattern edit for ${record.pattern}`}
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
              onClick={() => startInlineEdit(record, "pattern")}
              disabled={inlineEditSaving}
              aria-label={`Inline edit pattern ${record.pattern}`}
            >
              <span className="font-mono text-xs truncate">{value}</span>
              {record.type === "regex" && (
                <Tag color="blue" className="ml-1 text-[10px]">
                  regex
                </Tag>
              )}
            </button>
          )
        }
      },
      {
        title: "Replacement",
        dataIndex: "replacement",
        key: "replacement",
        render: (value: string, record: any) => {
          const entryId = Number(record?.id)
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
                        current ? { ...current, value: event.target.value } : current
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
                    aria-label={`Inline edit replacement for ${record.pattern}`}
                  />
                  <button
                    type="button"
                    className="min-w-[28px] min-h-[28px] flex items-center justify-center rounded border border-border text-success hover:bg-success/10"
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => {
                      void saveInlineEdit()
                    }}
                    disabled={inlineEditSaving}
                    aria-label={`Save replacement edit for ${record.pattern}`}
                  >
                    <Check className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    className="min-w-[28px] min-h-[28px] flex items-center justify-center rounded border border-border text-text-muted hover:bg-surface2"
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={cancelInlineEdit}
                    disabled={inlineEditSaving}
                    aria-label={`Cancel replacement edit for ${record.pattern}`}
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
              onClick={() => startInlineEdit(record, "replacement")}
              disabled={inlineEditSaving}
              aria-label={`Inline edit replacement ${record.pattern}`}
            >
              <span className="truncate">{value}</span>
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
          return <Tag color={normalized === "regex" ? "blue" : "default"}>{normalized}</Tag>
        }
      },
      {
        title: "Probability",
        dataIndex: "probability",
        key: "probability",
        responsive: DICTIONARY_ENTRY_COLUMN_RESPONSIVE.probability,
        render: (value: number | null | undefined) => {
          const safeValue = typeof value === "number" && Number.isFinite(value) ? value : 1
          return <span className="text-xs font-mono">{safeValue.toFixed(2)}</span>
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
        title: "Usage",
        dataIndex: "usage_count",
        key: "usage_count",
        responsive: DICTIONARY_ENTRY_COLUMN_RESPONSIVE.usage,
        render: (value: number | null | undefined) => {
          const usageCount = toSafeNonNegativeInteger(value)
          return (
            <div className="flex items-center gap-1">
              <span className="text-xs font-mono">{usageCount}</span>
              {usageCount === 0 && <Tag className="text-[10px]">Unused</Tag>}
            </div>
          )
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
            priority < orderedEntryCount &&
            !isBusy

          return (
            <div className="flex items-center gap-1">
              <button
                type="button"
                className="min-w-[28px] min-h-[28px] flex items-center justify-center rounded border border-border text-text-muted hover:bg-surface2 disabled:opacity-50"
                aria-label={`Move entry ${entry?.pattern || entryId} up`}
                onClick={() => {
                  void onMoveEntry(entryId, -1)
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
                  void onMoveEntry(entryId, 1)
                }}
                disabled={!canMoveDown}
              >
                <ChevronDown className="w-3.5 h-3.5" />
              </button>
              <span className="min-w-[2ch] text-right text-xs font-mono">{priority ?? "—"}</span>
            </div>
          )
        }
      },
      {
        title: "Enabled",
        dataIndex: "enabled",
        key: "enabled",
        width: 80,
        render: (value: boolean) =>
          value ? (
            <Tag color="green" icon={<CheckCircle2 className="w-3 h-3 inline mr-1" />}>
              On
            </Tag>
          ) : (
            <Tag>Off</Tag>
          )
      },
      {
        title: "Actions",
        key: "actions",
        width: 180,
        render: (_: any, record: any) => (
          <div className="flex gap-1 items-center">
            <Popover
              trigger="click"
              open={testingEntryId === record.id}
              onOpenChange={(open) => {
                if (open) {
                  setTestingEntryId(record.id)
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
                    onChange={(event) => setInlineTestInput(event.target.value)}
                    onPressEnter={() => {
                      if (!inlineTestInput.trim()) return
                      setInlineTestResult(runInlineEntryTest(record, inlineTestInput))
                    }}
                  />
                  <Button
                    size="small"
                    type="primary"
                    className="w-full"
                    onClick={() => {
                      if (!inlineTestInput.trim()) return
                      setInlineTestResult(runInlineEntryTest(record, inlineTestInput))
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
                  aria-label={`Test entry ${record.pattern}`}
                >
                  <Play className="w-4 h-4" />
                </button>
              </Tooltip>
            </Popover>

            <Tooltip title="Edit entry">
              <button
                className="min-w-[36px] min-h-[36px] flex items-center justify-center text-text-muted hover:text-text hover:bg-surface2 rounded-md transition-colors"
                onClick={() => onOpenEditEntry(record)}
                aria-label={`Edit entry ${record.pattern}`}
              >
                <Pen className="w-4 h-4" />
              </button>
            </Tooltip>

            <Tooltip title="Delete entry">
              <button
                className="min-w-[36px] min-h-[36px] flex items-center justify-center text-danger hover:bg-danger/10 rounded-md transition-colors"
                onClick={() => {
                  void onDeleteEntry(record)
                }}
                aria-label={`Delete entry ${record.pattern}`}
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </Tooltip>
          </div>
        )
      }
    ],
    [
      canReorderEntries,
      cancelInlineEdit,
      entryPriorityById,
      inlineEdit,
      inlineEditError,
      inlineEditSaving,
      inlineTestInput,
      inlineTestResult,
      onDeleteEntry,
      onMoveEntry,
      onOpenEditEntry,
      orderedEntryCount,
      reorderBusyEntryId,
      saveInlineEdit,
      setInlineEdit,
      setInlineEditError,
      setInlineTestInput,
      setInlineTestResult,
      setTestingEntryId,
      startInlineEdit,
      testingEntryId
    ]
  )
}
