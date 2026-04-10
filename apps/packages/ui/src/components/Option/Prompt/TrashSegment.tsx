import React, { useMemo, useState } from "react"
import { Input, Skeleton, Table, Tooltip } from "antd"
import { AlertTriangle, Trash2, Undo2 } from "lucide-react"
import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import type { Prompt } from "@/db/dexie/types"
import {
  filterTrashPromptsByName,
  getTrashDaysRemaining,
  getTrashRemainingSeverity
} from "./trash-prompts-utils"
import { usePromptWorkspace } from "./PromptWorkspaceProvider"
import { usePromptBulkActions } from "./hooks/usePromptBulkActions"
import { usePromptEditor } from "./hooks/usePromptEditor"
import { usePromptSync } from "./hooks/usePromptSync"
import type { PromptTableDensity } from "./PromptListTable"

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface TrashSegmentProps {
  tableDensity: PromptTableDensity
  sync: ReturnType<typeof usePromptSync>
  editor: ReturnType<typeof usePromptEditor>
  bulk: ReturnType<typeof usePromptBulkActions>
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TrashSegment({
  tableDensity,
  editor,
  bulk
}: TrashSegmentProps) {
  const {
    trashData,
    trashStatus,
    t,
    utils,
  } = usePromptWorkspace()

  const {
    confirmDanger,
    getPromptTexts,
  } = utils

  // ---- Local state ----

  const [trashSearchText, setTrashSearchText] = useState("")

  // ---- Derived data ----

  const filteredTrashData = useMemo(() => {
    if (!Array.isArray(trashData)) return []
    return filterTrashPromptsByName(trashData, trashSearchText)
  }, [trashData, trashSearchText])

  // ---- Helpers ----

  const formatDeletedAt = (timestamp: number | null | undefined) => {
    if (!timestamp) return ""
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
    if (diffDays === 0) return t("managePrompts.trash.today", { defaultValue: "Today" })
    if (diffDays === 1) return t("managePrompts.trash.yesterday", { defaultValue: "Yesterday" })
    if (diffDays < 7) return t("managePrompts.trash.daysAgo", { defaultValue: "{{count}} days ago", count: diffDays })
    return date.toLocaleDateString()
  }

  // ---- Render ----

  const trashCount = Array.isArray(trashData) ? trashData.length : 0
  const filteredTrashCount = filteredTrashData.length

  return (
    <div data-testid="prompts-trash">
      <div className="mb-6">
        {trashCount > 0 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-warn/10 rounded-md border border-warn/30">
              <div className="flex items-center gap-2">
                <AlertTriangle className="size-4 text-warn" />
                <span className="text-sm">
                  {t("managePrompts.trash.autoDeleteWarning", {
                    defaultValue: "Prompts in trash are automatically deleted after 30 days."
                  })}
                </span>
              </div>
              <button
                onClick={async () => {
                  const ok = await confirmDanger({
                    title: t("managePrompts.trash.emptyConfirmTitle", { defaultValue: "Empty Trash?" }),
                    content: t("managePrompts.trash.emptyConfirmContent", {
                      defaultValue: "This will permanently delete {{count}} prompts. This action cannot be undone.",
                      count: trashCount
                    }),
                    okText: t("managePrompts.trash.emptyTrash", { defaultValue: "Empty Trash" }),
                    cancelText: t("common:cancel", { defaultValue: "Cancel" }),
                    requireExactText: "DELETE",
                    requireExactTextLabel: t("managePrompts.trash.typeDeleteConfirm", {
                      defaultValue: "Type DELETE to confirm:"
                    }),
                    requireExactTextPlaceholder: "DELETE"
                  })
                  if (!ok) return
                  editor.emptyTrashMutation()
                }}
                disabled={editor.isEmptyingTrash}
                className="inline-flex items-center gap-1 px-2 py-1 text-sm rounded border border-danger/30 text-danger hover:bg-danger/10 disabled:opacity-50">
                <Trash2 className="size-3" />
                {t("managePrompts.trash.emptyTrash", { defaultValue: "Empty Trash" })}
              </button>
            </div>

            <Input
              value={trashSearchText}
              onChange={(event) => setTrashSearchText(event.target.value)}
              allowClear
              placeholder={t("managePrompts.trash.searchPlaceholder", {
                defaultValue: "Search deleted prompts..."
              })}
              style={{ width: 320, maxWidth: "100%" }}
              data-testid="prompts-trash-search"
            />

            {bulk.trashSelectedRowKeys.length > 0 && (
              <div className="flex flex-wrap items-center justify-between gap-2 p-2 rounded-md border border-primary/20 bg-primary/5">
                <span className="text-sm text-text-muted">
                  {t("managePrompts.bulk.selectedCount", {
                    defaultValue: "{{count}} selected",
                    count: bulk.trashSelectedRowKeys.length
                  })}
                </span>
                <button
                  type="button"
                  data-testid="prompts-trash-bulk-restore"
                  onClick={() =>
                    bulk.bulkRestorePrompts(
                      bulk.trashSelectedRowKeys.map((key) => String(key))
                    )
                  }
                  disabled={bulk.isBulkRestoring}
                  className="inline-flex items-center gap-1 px-3 py-1.5 text-sm rounded border border-primary/30 text-primary hover:bg-primary/10 disabled:opacity-50"
                >
                  <Undo2 className="size-3" />
                  {t("managePrompts.trash.restoreSelected", {
                    defaultValue: "Restore selected"
                  })}
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {trashStatus === "pending" && <Skeleton paragraph={{ rows: 8 }} />}

      {trashStatus === "success" && trashCount === 0 && (
        <FeatureEmptyState
          title={t("managePrompts.trash.emptyTitle", { defaultValue: "Trash is empty" })}
          description={t("managePrompts.trash.emptyDescription", {
            defaultValue: "Deleted prompts will appear here for 30 days before being permanently removed."
          })}
          examples={[
            t("managePrompts.trash.emptyExample1", {
              defaultValue: "You can restore deleted prompts at any time while they're in the trash."
            })
          ]}
        />
      )}

      {trashStatus === "success" && trashCount > 0 && (
        <>
          {filteredTrashCount === 0 ? (
            <div className="rounded-md border border-border p-4 text-sm text-text-muted">
              {t("managePrompts.trash.searchEmpty", {
                defaultValue: "No deleted prompts match your search."
              })}
            </div>
          ) : (
            <Table
              className={`prompts-table prompts-table-density-${tableDensity}`}
              size={tableDensity === "comfortable" ? "middle" : "small"}
              data-testid="prompts-trash-table"
              columns={[
                {
                  title: t("managePrompts.columns.title"),
                  dataIndex: "title",
                  key: "title",
                  render: (_: unknown, record: Prompt) => (
                    <div className="flex max-w-64 flex-col">
                      <span className="line-clamp-1 font-medium text-text-muted">
                        {record?.name || record?.title}
                      </span>
                      {record?.author && (
                        <span className="text-xs text-text-muted opacity-70">
                          {t("managePrompts.form.author.label", { defaultValue: "Author" })}: {record.author}
                        </span>
                      )}
                    </div>
                  )
                },
                {
                  title: t("managePrompts.columns.prompt", {
                    defaultValue: "Prompt"
                  }),
                  key: "contentPreview",
                  render: (_: unknown, record: Prompt) => {
                    const { systemText, userText } = getPromptTexts(record)
                    const preview = (
                      userText ||
                      systemText ||
                      (typeof record?.content === "string" ? record.content : "")
                    ).trim()

                    if (!preview) {
                      return (
                        <span className="text-xs text-text-muted opacity-70">
                          {t("managePrompts.trash.noPreview", {
                            defaultValue: "No content preview"
                          })}
                        </span>
                      )
                    }

                    return (
                      <Tooltip title={preview}>
                        <span className="line-clamp-2 max-w-[26rem] text-sm">
                          {preview}
                        </span>
                      </Tooltip>
                    )
                  }
                },
                {
                  title: t("managePrompts.trash.deletedAt", { defaultValue: "Deleted" }),
                  key: "deletedAt",
                  width: 140,
                  render: (_: unknown, record: Prompt) => (
                    <span className="text-sm text-text-muted">
                      {formatDeletedAt(record.deletedAt)}
                    </span>
                  )
                },
                {
                  title: t("managePrompts.trash.remaining", {
                    defaultValue: "Remaining"
                  }),
                  key: "remaining",
                  width: 140,
                  render: (_: unknown, record: Prompt) => {
                    const remainingDays = getTrashDaysRemaining(record.deletedAt)
                    const severity = getTrashRemainingSeverity(remainingDays)
                    const className =
                      severity === "danger"
                        ? "text-danger"
                        : severity === "warning"
                          ? "text-warn"
                          : "text-text-muted"
                    const label =
                      remainingDays <= 0
                        ? t("managePrompts.trash.remainingExpired", {
                            defaultValue: "Due now"
                          })
                        : `${remainingDays} ${
                            remainingDays === 1
                              ? t("managePrompts.trash.dayLeft", { defaultValue: "day left" })
                              : t("managePrompts.trash.daysLeft", { defaultValue: "days left" })
                          }`

                    return (
                      <span
                        className={`text-sm ${className}`}
                        data-testid={`prompts-trash-remaining-${record.id}`}
                      >
                        {label}
                      </span>
                    )
                  }
                },
                {
                  title: t("managePrompts.columns.actions"),
                  width: 160,
                  render: (_: unknown, record: Prompt) => (
                    <div className="flex items-center gap-2">
                      <Tooltip title={t("managePrompts.trash.restore", { defaultValue: "Restore" })}>
                        <button
                          type="button"
                          data-testid={`prompts-trash-restore-${record.id}`}
                          onClick={() => editor.restorePromptMutation(record.id)}
                          className="inline-flex items-center gap-1 px-2 py-1 text-sm rounded border border-primary/30 text-primary hover:bg-primary/10">
                          <Undo2 className="size-3" />
                          {t("managePrompts.trash.restore", { defaultValue: "Restore" })}
                        </button>
                      </Tooltip>
                      <Tooltip title={t("managePrompts.trash.deletePermanently", { defaultValue: "Delete permanently" })}>
                        <button
                          type="button"
                          onClick={async () => {
                            const ok = await confirmDanger({
                              title: t("managePrompts.trash.permanentDeleteTitle", { defaultValue: "Delete permanently?" }),
                              content: t("managePrompts.trash.permanentDeleteContent", {
                                defaultValue: "This prompt will be permanently deleted. This action cannot be undone."
                              }),
                              okText: t("common:delete", { defaultValue: "Delete" }),
                              cancelText: t("common:cancel", { defaultValue: "Cancel" })
                            })
                            if (!ok) return
                            editor.permanentDeletePromptMutation(record.id)
                          }}
                          className="text-text-muted hover:text-danger">
                          <Trash2 className="size-4" />
                        </button>
                      </Tooltip>
                    </div>
                  )
                }
              ]}
              dataSource={filteredTrashData}
              rowKey={(record) => record.id}
              rowSelection={{
                selectedRowKeys: bulk.trashSelectedRowKeys,
                onChange: (keys) => bulk.setTrashSelectedRowKeys(keys)
              }}
            />
          )}
        </>
      )}
    </div>
  )
}
