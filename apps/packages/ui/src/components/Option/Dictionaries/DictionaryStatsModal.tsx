import React from "react"
import { Descriptions, Modal, Tag } from "antd"
import { formatRelativeTimestamp } from "./listUtils"

type DictionaryStatsModalProps = {
  open: boolean
  stats: any | null
  onClose: () => void
}

export function DictionaryStatsModal({
  open,
  stats,
  onClose
}: DictionaryStatsModalProps) {
  return (
    <Modal title="Dictionary Statistics" open={open} onCancel={onClose} footer={null}>
      {stats && (
        <div className="space-y-3">
          <Descriptions size="small" bordered column={1}>
            <Descriptions.Item label="ID">{stats.dictionary_id}</Descriptions.Item>
            <Descriptions.Item label="Name">{stats.name}</Descriptions.Item>
            <Descriptions.Item label="Total Entries">{stats.total_entries}</Descriptions.Item>
            <Descriptions.Item label="Regex Entries">{stats.regex_entries}</Descriptions.Item>
            <Descriptions.Item label="Literal Entries">{stats.literal_entries}</Descriptions.Item>
            <Descriptions.Item label="Enabled Entries">
              {toDisplayStatNumber(stats.enabled_entries)}
            </Descriptions.Item>
            <Descriptions.Item label="Disabled Entries">
              {toDisplayStatNumber(stats.disabled_entries)}
            </Descriptions.Item>
            <Descriptions.Item label="Probabilistic Entries">
              {toDisplayStatNumber(stats.probabilistic_entries)}
            </Descriptions.Item>
            <Descriptions.Item label="Timed Effect Entries">
              {toDisplayStatNumber(stats.timed_effect_entries)}
            </Descriptions.Item>
            <Descriptions.Item label="Unused Entries">
              {toDisplayStatNumber(stats.zero_usage_entries)}
            </Descriptions.Item>
            <Descriptions.Item label="Pattern Conflicts">
              {toDisplayStatNumber(stats.pattern_conflict_count)}
            </Descriptions.Item>
            <Descriptions.Item label="Groups">{toDisplayGroupSummary(stats.groups)}</Descriptions.Item>
            <Descriptions.Item label="Average Probability">
              {toDisplayProbabilitySummary(stats.average_probability)}
            </Descriptions.Item>
            <Descriptions.Item label="Default Token Budget">
              {toDisplayTokenBudgetSummary(stats.default_token_budget)}
            </Descriptions.Item>
            <Descriptions.Item label="Created">
              {formatRelativeTimestamp(stats.created_at)}
            </Descriptions.Item>
            <Descriptions.Item label="Updated">
              {formatRelativeTimestamp(stats.updated_at)}
            </Descriptions.Item>
            <Descriptions.Item label="Last Used">
              {formatRelativeTimestamp(stats.last_used)}
            </Descriptions.Item>
            <Descriptions.Item label="Total Usage Count">
              {toDisplayStatNumber(stats.total_usage_count)}
            </Descriptions.Item>
          </Descriptions>

          {Array.isArray(stats.entry_usage) && stats.entry_usage.length > 0 && (
            <div className="space-y-2">
              <div className="text-xs font-medium text-text">Entry usage snapshot</div>
              <div className="space-y-1 rounded border border-border bg-surface2/40 p-2">
                {stats.entry_usage.slice(0, 6).map((item: any) => (
                  <div
                    key={`entry-usage-${item?.entry_id}`}
                    className="flex items-center justify-between gap-2 text-xs"
                  >
                    <span className="truncate font-mono text-text">
                      {item?.pattern || `Entry ${item?.entry_id}`}
                    </span>
                    <span className="shrink-0 text-text-muted">
                      {toDisplayStatNumber(item?.usage_count)} uses
                      {item?.last_used_at
                        ? ` · last ${formatRelativeTimestamp(item.last_used_at)}`
                        : ""}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="space-y-2">
            <div className="text-xs font-medium text-text">Recent activity</div>
            {Array.isArray(stats.recent_activity) && stats.recent_activity.length > 0 ? (
              <div className="space-y-2 rounded border border-border bg-surface2/40 p-2">
                {stats.recent_activity.map((event: any, index: number) => (
                  <div
                    key={`dictionary-activity-${event?.id ?? index}`}
                    className="space-y-1 rounded border border-border/70 bg-surface p-2 text-xs"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-text">{formatRelativeTimestamp(event?.created_at)}</span>
                      <span className="text-text-muted">
                        {toDisplayStatNumber(event?.replacements)} replacements ·{" "}
                        {toDisplayStatNumber(event?.iterations)} iterations
                        {event?.token_budget_used
                          ? ` · budget ${toDisplayStatNumber(event.token_budget_used)}`
                          : ""}
                      </span>
                    </div>
                    <div className="text-text-muted">
                      Chat: {String(event?.chat_id || "Preview/API call")}
                    </div>
                    <div className="text-text-muted">
                      Entries: {formatActivityEntriesUsed(event?.entries_used)}
                    </div>
                    <div className="space-y-1">
                      <div className="text-text">
                        <span className="font-medium">Before:</span>{" "}
                        {String(event?.original_text_preview || "—")}
                      </div>
                      <div className="text-text">
                        <span className="font-medium">After:</span>{" "}
                        {String(event?.processed_text_preview || "—")}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-text-muted">
                No transformation activity recorded yet.
              </div>
            )}
          </div>
          <div className="space-y-2">
            <div className="text-xs font-medium text-text">Pattern conflicts</div>
            {Array.isArray(stats.pattern_conflicts) && stats.pattern_conflicts.length > 0 ? (
              <div className="space-y-1 rounded border border-border bg-surface2/40 p-2">
                {stats.pattern_conflicts.slice(0, 8).map((item: any, index: number) => (
                  <div
                    key={`pattern-conflict-${item?.entry_id_a}-${item?.entry_id_b}-${index}`}
                    className="space-y-0.5 text-xs"
                  >
                    <div className="flex items-center gap-2">
                      <Tag color={toPatternConflictTagColor(item?.severity)}>
                        {String(item?.severity || "low").toUpperCase()}
                      </Tag>
                      <span className="text-text">{item?.reason || "Potential overlap detected."}</span>
                    </div>
                    <div className="font-mono text-text-muted">
                      {item?.pattern_a || "—"} {"\u2194"} {item?.pattern_b || "—"}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-text-muted">
                No potential conflicts detected.
              </div>
            )}
          </div>
        </div>
      )}
    </Modal>
  )
}

function toDisplayStatNumber(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value)
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return String(parsed)
  }
  return "0"
}

function toDisplayGroupSummary(value: unknown): string {
  if (!Array.isArray(value)) return "—"
  const groups = value
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter((item) => item.length > 0)
  if (!groups.length) return "—"
  return groups.join(", ")
}

function toDisplayProbabilitySummary(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value.toFixed(2)
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      return parsed.toFixed(2)
    }
  }
  return "0.00"
}

function toDisplayTokenBudgetSummary(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value) && value > 0) {
    return `${Math.floor(value)} tokens`
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value)
    if (Number.isFinite(parsed) && parsed > 0) {
      return `${Math.floor(parsed)} tokens`
    }
  }
  return "Not set"
}

function formatActivityEntriesUsed(value: unknown): string {
  if (!Array.isArray(value)) return "—"
  const normalized = value
    .map((item) => Number(item))
    .filter((item) => Number.isInteger(item) && item > 0)
  if (!normalized.length) return "—"
  return normalized.join(", ")
}

function toPatternConflictTagColor(value: unknown): string {
  const normalized = String(value || "").toLowerCase()
  if (normalized === "high") return "red"
  if (normalized === "medium") return "orange"
  return "blue"
}
