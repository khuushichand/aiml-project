# PR 890 Review Remediation Design

**Date:** 2026-03-13
**PR:** [#890](https://github.com/rmusser01/tldw_server/pull/890)
**Branch:** `codex/persona-voice-assistant-builder`

## Goal

Close every currently open PR issue for #890 in one coordinated remediation pass, including:

- current CodeRabbit review comments
- the `DIRTY` merge state against `dev`
- the incomplete PR template and validation checklist items

## Context

PR #890 adds a large Persona Garden voice assistant builder and setup wizard surface. The branch currently spans a broad frontend and backend footprint, but the open issues are concentrated in a smaller set of Persona Garden frontend components and a few data-shape and typed-path edges. The branch is also behind or divergent from `dev`, which leaves the PR in a non-mergeable state.

The remediation should fix the current review feedback without redesigning the feature. The preferred approach is to preserve the existing architecture and patch behavior in place, with targeted tests for each regression class.

## Non-Goals

- redesigning the Persona Garden voice assistant feature set
- broad API client refactors beyond the paths needed for the reviewed components
- unrelated cleanup in the rest of the PR or repository

## Design Summary

The remediation will be executed as one coordinated pass on `codex/persona-voice-assistant-builder`, grouped into four workstreams.

### 1. UI correctness and accessibility

Patch the reviewed components in place so they remain consistent with the current feature design while satisfying accessibility and interaction expectations.

This includes:

- keyboard activation and ARIA state for persona chooser interactions
- accessible labels for currently unlabeled setup inputs
- masking connection secrets with `type="password"`
- disabling session-only controls whenever no live session is connected
- preventing silent committed-value clearing in `McpToolPicker` and surfacing stale-tool warnings instead
- keeping setup-step controls inert while async save actions are in flight
- removing duplicated conditional rendering in setup completion messaging

### 2. State safety and data-shape hardening

Persona-scoped panels should fail closed when the selected persona changes or the panel becomes inactive.

This includes:

- clearing stale commands, connections, load flags, and editor state when `CommandsPanel` context becomes invalid
- preserving `ConnectionsPanel` state during in-flight reloads to avoid flicker, while still fully resetting when the panel is inactive or lacks a selected persona
- validating fetched connection rows at runtime before storing them in state
- adding explicit delete confirmation for saved connections
- making starter command templates immutable and returning defensive copies
- aligning the live analytics frontend type with the backend field name
- tightening numeric normalization and clamping for turn-detection feedback values

### 3. Hook behavior and typed-path cleanup

Low-level hook and API-client edges should be made explicit and safe without changing the feature model.

This includes:

- replacing `as any` fetch path casts with typed allowed paths or minimal path-union extensions
- converting turn-detection numeric inputs to local string drafts with parse-on-blur behavior
- tightening `useEffect` and `useMemo` dependencies to avoid missed recomputation or needless reruns
- documenting loop-safety in `McpToolPicker`
- logging speech-cancel failures instead of swallowing them silently
- removing redundant normalization calls in resolved voice-default computation
- correcting the setup-required condition so "not yet loaded" state does not suppress the wizard

### 4. Branch and PR hygiene

After code and tests are stable, the branch should be synchronized with current `dev` and the PR metadata should be brought into a merge-ready state.

This includes:

- syncing `codex/persona-voice-assistant-builder` with `dev`
- resolving merge conflicts and rerunning the affected verification slice
- confirming the PR is no longer `DIRTY`
- updating the PR description so required validation and UX checklist items reflect the actual verification performed

## Files In Scope

Primary frontend scope:

- `apps/packages/ui/src/components/PersonaGarden/AssistantDefaultsPanel.tsx`
- `apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx`
- `apps/packages/ui/src/components/PersonaGarden/CommandAnalyticsSummary.tsx`
- `apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx`
- `apps/packages/ui/src/components/PersonaGarden/ConnectionsPanel.tsx`
- `apps/packages/ui/src/components/PersonaGarden/McpToolPicker.tsx`
- `apps/packages/ui/src/components/PersonaGarden/PersonaTurnDetectionControls.tsx`
- `apps/packages/ui/src/components/PersonaGarden/PersonaTurnDetectionFeedbackCard.tsx`
- `apps/packages/ui/src/components/PersonaGarden/SetupSafetyConnectionsStep.tsx`
- `apps/packages/ui/src/components/PersonaGarden/SetupStarterCommandsStep.tsx`
- `apps/packages/ui/src/components/PersonaGarden/SetupTestAndFinishStep.tsx`
- `apps/packages/ui/src/components/PersonaGarden/TestLabPanel.tsx`
- `apps/packages/ui/src/components/PersonaGarden/personaStarterCommandTemplates.ts`
- matching component tests under `apps/packages/ui/src/components/PersonaGarden/__tests__/`

Primary hook and shared-typing scope:

- `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`
- `apps/packages/ui/src/hooks/usePersonaSetupWizard.ts`
- `apps/packages/ui/src/hooks/useResolvedPersonaVoiceDefaults.tsx`
- any shared API client type definitions required to support typed persona routes
- matching hook and route tests

Potential backend/schema touch points:

- backend schema files only where needed to verify or reflect the reviewed frontend field shape

## Data Flow Decisions

- Persona-scoped state should never remain actionable after persona context is lost or changed.
- Async reloads should avoid visible flicker when the existing data is still valid for the active persona.
- Committed user choices should not be cleared implicitly because an MCP catalog or module selection changed.
- Numeric text inputs should allow normal editing behavior first and only coerce to numbers at validation boundaries.

## Error Handling

- malformed connection payload items are dropped before entering React state
- failed loads should surface the existing translated error paths
- delete flows should abort cleanly on user cancellation
- speech synthesis cancellation failures should be logged with context for debugging
- invalid numeric drafts should fall back to the last valid value rather than corrupting persisted settings

## Testing Strategy

Expand the existing Persona Garden component and hook tests instead of introducing a new test harness.

Coverage should include:

- keyboard interaction and ARIA assertions
- disabled-state behavior for disconnected or saving flows
- stale-value warning behavior in `McpToolPicker`
- stale persona-state clearing and invalidation behavior
- runtime payload validation and delete confirmation in `ConnectionsPanel`
- draft numeric input editing and parse-on-blur behavior
- analytics field alignment and defensive normalization
- effect and memo dependency behavior where regressions are testable

Verification should be staged:

1. run focused frontend tests for touched Persona Garden components and hooks
2. run package typecheck or lint commands that already exist for this workspace, if available
3. run Bandit on the touched scope with the project virtual environment
4. sync the branch with `dev`, resolve conflicts, and rerun the affected verification slice

## Acceptance Criteria

- every current CodeRabbit review comment on PR #890 is addressed in code or PR metadata
- no reviewed component can act on stale persona-scoped state
- reviewed inputs are accessible, appropriately masked, and disabled when they should be inert
- reviewed hooks no longer depend on unsafe casts, silent failure paths, or brittle dependency lists
- the branch merges cleanly with `dev`
- the PR description reflects the completed validation work

## Risks and Mitigations

**Risk:** The branch already has unrelated uncommitted work in its dedicated worktree.
**Mitigation:** Limit the remediation to the reviewed files and stage only intentional changes.

**Risk:** Syncing with `dev` late can reopen component tests.
**Mitigation:** Keep fixes narrow, then rerun the affected frontend slice after merge conflict resolution.

**Risk:** Typed path cleanup may require shared API type changes.
**Mitigation:** Extend only the minimal route definitions needed for the reviewed endpoints.
