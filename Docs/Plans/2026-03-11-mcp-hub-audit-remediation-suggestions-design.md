# MCP Hub Audit Remediation Suggestions Design

Date: 2026-03-11
Status: Implemented

## Goal

Extend the MCP Hub `Audit` tab with deterministic, read-only remediation
guidance for each concrete finding.

This slice is intentionally narrow:

- read-only only
- deterministic only
- client-side only
- no inline mutation actions
- no AI-generated guidance

## Scope

This slice covers:

- a `Suggested next steps` block for audit findings
- 2-3 concise ordered steps per finding
- optional advisory note text where needed
- one shared pure remediation helper used by both UI and export
- inclusion of remediation guidance in current client-side Markdown/JSON exports

This slice does not cover:

- backend-supplied suggestion text
- inline fix buttons
- heuristic risk scoring
- saved remediation state
- generated or model-written advice

## Review Corrections

### 1. UI and export must share one remediation helper

The current audit tab already centralizes grouping/export formatting in
`governanceAuditHelpers.ts`.

This slice should add one pure helper, for example:

- `buildAuditRemediationSteps(finding)`

Both the row renderer and export helpers must use the exact same output so the
UI and exported reports stay aligned.

### 2. Remediation must distinguish blockers from advisories

The audit feed includes both:

- hard blockers
- advisory multi-root-readiness warnings

The remediation helper must support an optional note such as:

- `This affects multi-root readiness only.`

That note should render distinctly from the primary ordered steps.

### 3. Sparse findings need a strict fallback path

Some findings have limited structure. When there is not enough detail for a
specialized suggestion, the helper should still return a safe generic fallback:

1. Open the linked MCP Hub object
2. Review the current configuration and any related object
3. Re-run the audit after updating the configuration

### 4. Prefer structured details over message matching

Suggestion rules should resolve in this order:

1. `finding_type`
2. explicit `details` keys
3. `object_kind`
4. message token fallback only when no stronger structure exists

This keeps the rules more stable than string-matching on display text alone.

### 5. Related-object usage must stay secondary

When `related_object_*` exists, the helper may include guidance like:

- `Review the related workspace set 'Primary Workspace Set'.`

But it should keep the primary object as the main remediation target and treat
the related object as supporting context.

### 6. Keep the row presentation compact

The remediation block should remain secondary to the finding row:

- max 3 steps
- no nested bullets
- optional one-line note
- no extra action buttons

### 7. If included in export, the JSON shape must be explicit

If this slice extends the current client-side export output, each exported item
should include:

- `suggested_steps: string[]`
- `suggestion_note?: string | null`

That keeps JSON and Markdown outputs aligned with the UI.

## Remediation Model

Each finding row may render:

- `Suggested next steps`
  1. ...
  2. ...
  3. ...
- optional advisory note

The helper output should be:

```ts
type GovernanceAuditRemediation = {
  steps: string[]
  note?: string | null
}
```

Rules:

- show the block only when at least one step exists
- steps are concise and imperative
- steps are deterministic and local to the finding data

## Rule Structure

Use a pure client-side helper in `governanceAuditHelpers.ts`.

Recommended API:

- `buildAuditRemediationSteps(finding): GovernanceAuditRemediation`

Resolution order:

1. base rules by `finding_type`
2. refine from `details`
3. refine from `object_kind`
4. fall back to generic steps

### Example Specialized Cases

#### Assignment overlap blocker

When `details.conflicting_workspace_ids` exists:

1. Open the assignment configuration.
2. Remove one conflicting workspace or change the path scope to a non-multi-root mode.
3. Save again to re-run readiness validation.

#### Assignment unresolved workspace

When `details.unresolved_workspace_ids` exists:

1. Open the assignment workspace source.
2. Correct or remove the unresolved workspace ids.
3. Save again to re-run readiness validation.

#### Workspace-source readiness advisory

1. Open the workspace source configuration.
2. Review the overlapping or unresolved workspace members before using it for multi-root assignments.
3. Re-check the assignment after updating the workspace source.

Note:
- `This affects multi-root readiness only.`

#### Missing external slot secret

1. Open the managed external server.
2. Configure the missing credential slot secret.
3. Re-run the audit or revisit assignment bindings if the server remains non-executable.

#### Invalid auth template

1. Open the managed external server.
2. Fix the auth template mappings for the current transport.
3. Re-run the audit after saving the template.

#### External binding issue

1. Open the affected assignment.
2. Review the assignment-effective binding and the related server state.
3. Re-run the audit after updating the binding or server configuration.

### Generic fallback

When no specialized case matches:

1. Open the linked MCP Hub object.
2. Review the current configuration and any related object.
3. Re-run the audit after updating the configuration.

## UI Presentation

The remediation block should render inline within each finding row, beneath:

- the main finding message
- the optional `Related to: ...` label

Rendering:

- compact ordered list
- optional `Text type="secondary"` note
- no extra controls

The existing `Open` action remains the only interactive remediation affordance.

## Export Inclusion

Because export is already client-side and derived from the same loaded finding
set, this slice should include remediation output in export as well.

### JSON

Each exported finding item should include:

- `suggested_steps`
- `suggestion_note`

### Markdown

Each finding section should add:

- `Suggested next steps`
- optional note

This keeps the shared report actionable without adding backend changes.

## Testing

### Frontend helper tests

Add tests for:

- overlap blocker remediation
- unresolved workspace remediation
- advisory readiness remediation with note
- missing external secret remediation
- invalid auth template remediation
- fallback remediation

### UI tests

Add or update tests for:

- remediation block renders under findings
- advisory notes render distinctly
- `Open` behavior remains unchanged
- export output includes remediation guidance

## Recommendation

Keep this slice purely client-side and deterministic:

- generate remediation steps from existing finding data
- render them inline in the audit view
- include them in the current export helpers

That gives the audit view actionable guidance without introducing a second
editing surface or new backend coupling.
