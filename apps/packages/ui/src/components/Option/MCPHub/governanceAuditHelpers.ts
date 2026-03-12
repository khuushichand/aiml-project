import type {
  McpHubGovernanceAuditFinding,
  McpHubGovernanceAuditFindingType,
  McpHubGovernanceAuditSeverity
} from "@/services/tldw/mcp-hub"

export type GovernanceAuditFilterState = {
  severity: "all" | McpHubGovernanceAuditSeverity
  finding_type: "all" | McpHubGovernanceAuditFindingType
  object_kind: "all" | string
  scope_type: "all" | string
  has_related_object_only: boolean
}

export type GovernanceAuditRelatedObjectFocus = {
  kind: string
  id: string
  label: string
}

export type GovernanceAuditRelatedObjectSummary = GovernanceAuditRelatedObjectFocus & {
  key: string
  count: number
  error_count: number
  warning_count: number
}

export type GovernanceAuditGroupedSection = {
  finding_type: McpHubGovernanceAuditFindingType
  items: McpHubGovernanceAuditFinding[]
}

export type GovernanceAuditCounts = {
  total: number
  error: number
  warning: number
}

export const FINDING_TYPE_ORDER: McpHubGovernanceAuditFindingType[] = [
  "assignment_validation_blocker",
  "workspace_source_readiness_warning",
  "shared_workspace_overlap_warning",
  "external_server_configuration_issue",
  "external_binding_issue"
]

export const FINDING_TYPE_LABELS: Record<McpHubGovernanceAuditFindingType, string> = {
  assignment_validation_blocker: "Assignment blockers",
  workspace_source_readiness_warning: "Multi-root readiness",
  shared_workspace_overlap_warning: "Shared workspace overlap",
  external_server_configuration_issue: "External config",
  external_binding_issue: "External binding issues"
}

export const OBJECT_KIND_LABELS: Record<string, string> = {
  policy_assignment: "Policy assignments",
  workspace_set_object: "Workspace sets",
  shared_workspace: "Shared workspaces",
  external_server: "External servers",
  permission_profile: "Permission profiles"
}

const _safeString = (value: unknown) => String(value || "").trim()

const _relatedObjectLabel = (item: McpHubGovernanceAuditFinding) =>
  _safeString(item.related_object_label) ||
  _safeString(item.related_object_id) ||
  "Unknown related object"

export const dedupeAuditValues = (values: string[]) =>
  Array.from(new Set(values.filter((value) => value.trim().length > 0))).sort((a, b) =>
    a.localeCompare(b)
  )

export const buildAuditCounts = (
  items: McpHubGovernanceAuditFinding[]
): GovernanceAuditCounts => ({
  total: items.length,
  error: items.filter((item) => item.severity === "error").length,
  warning: items.filter((item) => item.severity === "warning").length
})

export const summarizeRelatedObjects = (
  items: McpHubGovernanceAuditFinding[],
  limit = 5
): GovernanceAuditRelatedObjectSummary[] => {
  const summaries = new Map<string, GovernanceAuditRelatedObjectSummary>()
  for (const item of items) {
    const kind = _safeString(item.related_object_kind)
    const id = _safeString(item.related_object_id)
    if (!kind || !id) continue
    const key = `${kind}:${id}`
    const existing = summaries.get(key)
    if (existing) {
      existing.count += 1
      if (item.severity === "error") {
        existing.error_count += 1
      } else {
        existing.warning_count += 1
      }
      continue
    }
    summaries.set(key, {
      key,
      kind,
      id,
      label: _relatedObjectLabel(item),
      count: 1,
      error_count: item.severity === "error" ? 1 : 0,
      warning_count: item.severity === "warning" ? 1 : 0
    })
  }
  return Array.from(summaries.values())
    .sort((left, right) => {
      if (left.count !== right.count) return right.count - left.count
      if (left.error_count !== right.error_count) return right.error_count - left.error_count
      return left.label.localeCompare(right.label)
    })
    .slice(0, limit)
}

export const groupAuditFindings = (
  items: McpHubGovernanceAuditFinding[]
): GovernanceAuditGroupedSection[] => {
  const groups = new Map<McpHubGovernanceAuditFindingType, McpHubGovernanceAuditFinding[]>()
  for (const findingType of FINDING_TYPE_ORDER) {
    groups.set(findingType, [])
  }
  for (const item of items) {
    groups.get(item.finding_type)?.push(item)
  }
  return FINDING_TYPE_ORDER.map((findingType) => ({
    finding_type: findingType,
    items: (groups.get(findingType) || []).sort((left, right) => {
      if (left.severity !== right.severity) {
        return left.severity === "error" ? -1 : 1
      }
      return String(left.object_label || "").localeCompare(String(right.object_label || ""))
    })
  }))
}

type GovernanceAuditReportInput = {
  generated_at: string
  items: McpHubGovernanceAuditFinding[]
  filters: GovernanceAuditFilterState
  counts: GovernanceAuditCounts
  related_object_focus?: GovernanceAuditRelatedObjectFocus | null
  related_summaries?: GovernanceAuditRelatedObjectSummary[]
}

export const buildAuditMarkdownReport = ({
  generated_at,
  items,
  filters,
  counts,
  related_object_focus,
  related_summaries = []
}: GovernanceAuditReportInput): string => {
  const lines: string[] = [
    "# MCP Hub Governance Audit",
    "",
    `Generated at: ${generated_at}`,
    "",
    "## Summary",
    `- Findings: ${counts.total}`,
    `- Errors: ${counts.error}`,
    `- Warnings: ${counts.warning}`,
    "",
    "## Active filters",
    `- Severity: ${filters.severity}`,
    `- Finding type: ${filters.finding_type}`,
    `- Object kind: ${filters.object_kind}`,
    `- Scope: ${filters.scope_type}`,
    `- Has related object only: ${filters.has_related_object_only ? "yes" : "no"}`
  ]
  if (related_object_focus) {
    lines.push(
      `- Related object focus: ${related_object_focus.label} (${related_object_focus.kind})`
    )
  }
  lines.push("")
  if (related_summaries.length > 0) {
    lines.push("## Top related objects in current filtered findings")
    for (const summary of related_summaries) {
      lines.push(
        `- ${summary.label} (${summary.kind}): ${summary.count} finding${summary.count === 1 ? "" : "s"}`
      )
    }
    lines.push("")
  }
  for (const section of groupAuditFindings(items)) {
    if (section.items.length === 0) continue
    lines.push(
      `## ${FINDING_TYPE_LABELS[section.finding_type]} (${section.items.length})`,
      ""
    )
    for (const finding of section.items) {
      lines.push(`### ${finding.object_label}`, `- Severity: ${finding.severity}`)
      lines.push(`- Object kind: ${finding.object_kind}`)
      lines.push(`- Scope: ${finding.scope_type}${finding.scope_id != null ? `/${finding.scope_id}` : ""}`)
      lines.push(`- Message: ${finding.message}`)
      if (_safeString(finding.related_object_label) || _safeString(finding.related_object_id)) {
        lines.push(
          `- Related to: ${_relatedObjectLabel(finding)}${
            _safeString(finding.related_object_kind)
              ? ` (${_safeString(finding.related_object_kind)})`
              : ""
          }`
        )
      }
      lines.push("")
    }
  }
  return lines.join("\n")
}

export const buildAuditJsonExport = ({
  generated_at,
  items,
  filters,
  counts,
  related_object_focus
}: GovernanceAuditReportInput) => ({
  generated_at,
  filters,
  related_object_focus:
    related_object_focus == null
      ? null
      : {
          kind: related_object_focus.kind,
          id: related_object_focus.id,
          label: related_object_focus.label
        },
  counts,
  items
})
