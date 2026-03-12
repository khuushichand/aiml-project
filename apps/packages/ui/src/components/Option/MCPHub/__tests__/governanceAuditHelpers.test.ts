import { describe, expect, it } from "vitest"

import { buildAuditInlineAction, buildAuditRemediationSteps } from "../governanceAuditHelpers"
import type { McpHubGovernanceAuditFinding } from "@/services/tldw/mcp-hub"

const makeFinding = (
  overrides: Partial<McpHubGovernanceAuditFinding>
): McpHubGovernanceAuditFinding => ({
  finding_type: "assignment_validation_blocker",
  severity: "error",
  scope_type: "user",
  scope_id: 1,
  object_kind: "policy_assignment",
  object_id: "1",
  object_label: "Researcher",
  message: "placeholder",
  details: {},
  navigate_to: {
    tab: "assignments",
    object_kind: "policy_assignment",
    object_id: "1"
  },
  ...overrides
})

describe("buildAuditRemediationSteps", () => {
  it("builds specific steps for assignment overlap blockers", () => {
    const result = buildAuditRemediationSteps(
      makeFinding({
        details: {
          conflicting_workspace_ids: ["workspace-alpha", "workspace-beta"]
        }
      })
    )

    expect(result.steps).toEqual([
      "Open the assignment configuration.",
      "Remove one conflicting workspace or change the path scope to a non-multi-root mode.",
      "Save again to re-run readiness validation."
    ])
    expect(result.note ?? null).toBeNull()
  })

  it("builds advisory readiness guidance with a note", () => {
    const result = buildAuditRemediationSteps(
      makeFinding({
        finding_type: "workspace_source_readiness_warning",
        severity: "warning",
        object_kind: "workspace_set_object",
        object_id: "51",
        object_label: "Primary Workspace Set",
        message: "May overlap with another trusted root in multi-root assignments.",
        navigate_to: {
          tab: "workspace-sets",
          object_kind: "workspace_set_object",
          object_id: "51"
        }
      })
    )

    expect(result.steps).toEqual([
      "Open the workspace source configuration.",
      "Review the overlapping or unresolved workspace members before using it for multi-root assignments.",
      "Re-check the assignment after updating the workspace source."
    ])
    expect(result.note).toBe("This affects multi-root readiness only.")
  })

  it("falls back to generic steps when structured detail is sparse", () => {
    const result = buildAuditRemediationSteps(
      makeFinding({
        finding_type: "external_binding_issue",
        object_kind: "permission_profile",
        message: "binding issue",
        navigate_to: {
          tab: "profiles",
          object_kind: "permission_profile",
          object_id: "9"
        }
      })
    )

    expect(result.steps).toEqual([
      "Open the linked MCP Hub object.",
      "Review the current configuration and any related object.",
      "Re-run the audit after updating the configuration."
    ])
  })
})

describe("buildAuditInlineAction", () => {
  it("returns a deterministic deactivate action for eligible external server findings", () => {
    const result = buildAuditInlineAction(
      makeFinding({
        finding_type: "external_server_configuration_issue",
        object_kind: "external_server",
        object_id: "docs-managed",
        object_label: "Docs Managed",
        message: "required_slot_secret_missing",
        navigate_to: {
          tab: "credentials",
          object_kind: "external_server",
          object_id: "docs-managed"
        }
      })
    )

    expect(result).toEqual({
      kind: "deactivate_external_server",
      label: "Deactivate server",
      object_id: "docs-managed",
      confirm_title: "Deactivate Docs Managed?",
      confirm_description:
        "This will disable the managed external server without changing secrets or bindings."
    })
  })

  it("returns null for non-eligible findings", () => {
    const result = buildAuditInlineAction(
      makeFinding({
        finding_type: "assignment_validation_blocker",
        object_kind: "policy_assignment"
      })
    )

    expect(result).toBeNull()
  })
})
