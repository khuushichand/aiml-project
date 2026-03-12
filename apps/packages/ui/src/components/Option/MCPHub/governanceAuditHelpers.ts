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

export type GovernanceAuditRemediation = {
  steps: string[]
  note?: string | null
}

export type GovernanceAuditInlineAction = {
  kind: "deactivate_external_server"
  label: string
  object_id: string
  confirm_title?: string | null
  confirm_description?: string | null
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

const _arrayValues = (value: unknown): string[] =>
  Array.isArray(value)
    ? value.map((item) => String(item || "").trim()).filter((item) => item.length > 0)
    : []

const _messageToken = (item: McpHubGovernanceAuditFinding) => _safeString(item.message).toLowerCase()

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

export const buildAuditRemediationSteps = (
  item: McpHubGovernanceAuditFinding
): GovernanceAuditRemediation => {
  const details = (item.details ?? {}) as Record<string, unknown>
  const conflictingWorkspaceIds = _arrayValues(details.conflicting_workspace_ids)
  const unresolvedWorkspaceIds = _arrayValues(details.unresolved_workspace_ids)
  const missingSlotNames =
    _arrayValues(details.missing_slot_names).length > 0
      ? _arrayValues(details.missing_slot_names)
      : _arrayValues(details.required_slot_names)
  const relatedLabel = _safeString(item.related_object_label)
  const messageToken = _messageToken(item)

  if (item.finding_type === "assignment_validation_blocker") {
    if (conflictingWorkspaceIds.length > 0) {
      return {
        steps: [
          "Open the assignment configuration.",
          "Remove one conflicting workspace or change the path scope to a non-multi-root mode.",
          "Save again to re-run readiness validation."
        ]
      }
    }
    if (unresolvedWorkspaceIds.length > 0) {
      return {
        steps: [
          "Open the assignment workspace source.",
          "Correct or remove the unresolved workspace ids.",
          "Save again to re-run readiness validation."
        ]
      }
    }
  }

  if (item.finding_type === "workspace_source_readiness_warning") {
    return {
      steps: [
        "Open the workspace source configuration.",
        "Review the overlapping or unresolved workspace members before using it for multi-root assignments.",
        "Re-check the assignment after updating the workspace source."
      ],
      note: "This affects multi-root readiness only."
    }
  }

  if (item.finding_type === "shared_workspace_overlap_warning") {
    return {
      steps: [
        "Open the shared workspace configuration.",
        "Review the overlapping root against the visible shared workspace set before using it in multi-root assignments.",
        "Re-run the audit after adjusting the shared workspace registry entry."
      ],
      note: "This affects multi-root readiness only."
    }
  }

  if (item.finding_type === "external_server_configuration_issue") {
    if (
      missingSlotNames.length > 0 ||
      messageToken.includes("required_slot_secret_missing") ||
      messageToken.includes("missing secret")
    ) {
      return {
        steps: [
          "Open the managed external server.",
          "Configure the missing credential slot secret.",
          "Re-run the audit or revisit assignment bindings if the server remains non-executable."
        ]
      }
    }
    if (
      messageToken.includes("invalid auth template") ||
      messageToken.includes("auth_template_invalid") ||
      messageToken.includes("unsupported_template_transport_target")
    ) {
      return {
        steps: [
          "Open the managed external server.",
          "Fix the auth template mappings for the current transport.",
          "Re-run the audit after saving the template."
        ]
      }
    }
    if (messageToken.includes("no auth template")) {
      return {
        steps: [
          "Open the managed external server.",
          "Add an auth template that matches the current transport and credential slots.",
          "Re-run the audit after saving the server configuration."
        ]
      }
    }
  }

  if (item.finding_type === "external_binding_issue" && (item.object_kind === "policy_assignment" || relatedLabel)) {
    return {
      steps: [
        "Open the affected assignment.",
        `Review the assignment-effective binding${relatedLabel ? ` and the related object '${relatedLabel}'.` : "."}`,
        "Re-run the audit after updating the binding or related configuration."
      ]
    }
  }

  return {
    steps: [
      "Open the linked MCP Hub object.",
      "Review the current configuration and any related object.",
      "Re-run the audit after updating the configuration."
    ]
  }
}

export const buildAuditInlineAction = (
  item: McpHubGovernanceAuditFinding
): GovernanceAuditInlineAction | null => {
  const objectId = _safeString(item.object_id)
  const objectLabel = _safeString(item.object_label) || objectId
  if (
    item.finding_type !== "external_server_configuration_issue" ||
    item.object_kind !== "external_server" ||
    !objectId
  ) {
    return null
  }
  return {
    kind: "deactivate_external_server",
    label: "Deactivate server",
    object_id: objectId,
    confirm_title: `Deactivate ${objectLabel}?`,
    confirm_description:
      "This will disable the managed external server without changing secrets or bindings."
  }
}

type GovernanceAuditExportItem = McpHubGovernanceAuditFinding & {
  suggested_steps: string[]
  suggestion_note: string | null
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
      const remediation = buildAuditRemediationSteps(finding)
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
      if (remediation.steps.length > 0) {
        lines.push("- Suggested next steps:")
        remediation.steps.forEach((step, index) => {
          lines.push(`  ${index + 1}. ${step}`)
        })
      }
      if (remediation.note) {
        lines.push(`- Note: ${remediation.note}`)
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
  items: items.map<GovernanceAuditExportItem>((item) => {
    const remediation = buildAuditRemediationSteps(item)
    return {
      ...item,
      suggested_steps: remediation.steps,
      suggestion_note: remediation.note ?? null
    }
  })
})
