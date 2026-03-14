# PR 890 Review Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close every current review issue on PR #890, resolve the `DIRTY` merge state, and leave the Persona Garden voice assistant branch merge-ready.

**Architecture:** Keep the existing Persona Garden architecture intact and apply targeted fixes in place. Group the work by review theme so related components, hooks, and tests move together: accessibility and inert-state fixes first, then persona-state safety and data-shape hardening, then hook and typed-path cleanup, and finally branch sync plus PR metadata updates.

**Tech Stack:** TypeScript, React 18, Vitest, Testing Library, Bun, shared `tldwClient` path helpers, Git, GitHub CLI, Python virtualenv and Bandit for touched backend Python scope only.

---

### Task 1: Lock in the reviewed accessibility and disconnected-session behavior

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/AssistantDefaultsPanel.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/SetupSafetyConnectionsStep.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/SetupStarterCommandsStep.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/SetupTestAndFinishStep.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/SetupStarterCommandsStep.test.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx`

**Step 1: Write the failing tests**

Add or extend tests that prove:

- the persona chooser is keyboard-activatable with `Enter` and `Space`
- session-only controls in `AssistantVoiceCard` are disabled when disconnected
- connection secret input uses `type="password"`
- connection-name and base-URL inputs expose accessible labels
- starter-command inputs are disabled while save is in flight and the phrase input has an accessible label
- the live-success message and Finish button render from one conditional wrapper

```tsx
await user.tab()
await user.keyboard("{Enter}")
expect(onUsePersona).toHaveBeenCalledWith(persona.id)

expect(screen.getByRole("checkbox", { name: /barge-in/i })).toBeDisabled()
expect(screen.getByLabelText(/connection secret/i)).toHaveAttribute("type", "password")
```

**Step 2: Run tests to verify they fail**

Run:

```bash
bunx vitest run src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx src/components/PersonaGarden/__tests__/SetupStarterCommandsStep.test.tsx src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx
```

Expected: FAIL with missing keyboard handlers, incorrect disabled state, or unlabeled/unmasked input assertions.

**Step 3: Write the minimal implementation**

Implement the reviewed fixes in the existing components:

```tsx
const sessionControlsDisabled = !connected

<button
  type="button"
  tabIndex={0}
  aria-pressed={isSelected}
  onKeyDown={(event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault()
      onUsePersona(persona.id)
    }
  }}
/>
```

**Step 4: Run tests to verify they pass**

Run the same `bunx vitest run ...` command again.

Expected: PASS for the touched accessibility and inert-state assertions.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/AssistantDefaultsPanel.tsx apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx apps/packages/ui/src/components/PersonaGarden/SetupSafetyConnectionsStep.tsx apps/packages/ui/src/components/PersonaGarden/SetupStarterCommandsStep.tsx apps/packages/ui/src/components/PersonaGarden/SetupTestAndFinishStep.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupStarterCommandsStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx
git commit -m "fix(persona): tighten accessibility and session guardrails"
```

### Task 2: Fix `McpToolPicker` stale-value handling and duplicate option keys

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/McpToolPicker.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/McpToolPicker.test.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/SetupStarterCommandsStep.test.tsx`
- Reference: `apps/packages/ui/src/services/tldw/path-utils.ts`

**Step 1: Write the failing tests**

Add tests that prove:

- a stale committed tool value is preserved by default when the module changes
- only the draft is cleared in manual mode
- a warning appears for stale committed values
- `autoClearStaleTool` opt-in mode calls `onChange("")`
- duplicate tool names from different sources still render without React-key collisions

```tsx
expect(onChange).not.toHaveBeenCalled()
expect(screen.getByText(/selected tool is no longer available/i)).toBeInTheDocument()
```

**Step 2: Run tests to verify they fail**

Run:

```bash
bunx vitest run src/components/PersonaGarden/__tests__/McpToolPicker.test.tsx src/components/PersonaGarden/__tests__/SetupStarterCommandsStep.test.tsx
```

Expected: FAIL because the current effect clears committed values and no stale warning exists.

**Step 3: Write the minimal implementation**

Add a local stale-warning flag, keep manual mode committed values intact, and switch keys to a composite identifier.

```tsx
const [showStaleToolWarning, setShowStaleToolWarning] = React.useState(false)

if (!matchingTool) {
  setDraftValue("")
  setShowStaleToolWarning(true)
  if (autoClearStaleTool) onChange("")
}
```

**Step 4: Run tests to verify they pass**

Run the same `bunx vitest run ...` command again.

Expected: PASS for stale-value and duplicate-option scenarios.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/McpToolPicker.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/McpToolPicker.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupStarterCommandsStep.test.tsx
git commit -m "fix(persona): preserve stale MCP selections until user action"
```

### Task 3: Remove stale persona actions from `CommandsPanel` and `ConnectionsPanel`

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/ConnectionsPanel.tsx`
- Modify: `apps/packages/ui/src/services/tldw/path-utils.ts` or other minimal shared path helper only if needed
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx`

**Step 1: Write the failing tests**

Add tests that prove:

- command editor state is cleared when persona context becomes invalid
- command and connection lists do not remain actionable for the previous persona
- connection reloads keep existing rows visible while loading a new active persona
- malformed connection payload items are filtered out
- delete requires confirmation and aborts cleanly on cancel

```tsx
window.confirm = vi.fn(() => false)
await user.click(screen.getByRole("button", { name: /delete/i }))
expect(fetchWithAuth).not.toHaveBeenCalled()
```

**Step 2: Run tests to verify they fail**

Run:

```bash
bunx vitest run src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx
```

Expected: FAIL because the current panels retain stale state, cast payloads directly, or delete immediately.

**Step 3: Write the minimal implementation**

Implement fail-closed persona invalidation, payload guards, confirmation, and typed path conversion with the smallest shared helper change necessary.

```tsx
if (!isActive || !selectedPersonaId) {
  setConnections([])
  setFormState(DEFAULT_FORM_STATE)
  return
}

const nextRows = Array.isArray(payload) ? payload.filter(isPersonaConnection) : []
const path = toAllowedPath(`/api/v1/persona/profiles/${encodeURIComponent(selectedPersonaId)}/connections`)
```

**Step 4: Run tests to verify they pass**

Run the same `bunx vitest run ...` command again.

Expected: PASS for stale-state clearing, no-flicker reload behavior, guarded payload parsing, and delete confirmation.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx apps/packages/ui/src/components/PersonaGarden/ConnectionsPanel.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx apps/packages/ui/src/services/tldw/path-utils.ts
git commit -m "fix(persona): harden command and connection persona state"
```

### Task 4: Fix analytics-field alignment, immutable templates, and turn-detection editing

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/CommandAnalyticsSummary.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/PersonaTurnDetectionControls.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/PersonaTurnDetectionFeedbackCard.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/personaStarterCommandTemplates.ts`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/CommandAnalyticsSummary.test.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx`
- Test: `apps/packages/ui/src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx`

**Step 1: Write the failing tests**

Add tests that prove:

- analytics rendering reads `total_committed_turns`
- replacing the analytics object recomputes recent sessions
- percent formatting clamps to `0%` through `100%`
- normalized turn-detection values cannot go negative
- numeric inputs allow temporary draft strings like `"0."` until blur
- starter command templates return cloned `phrases` and `slotMap` objects

```tsx
fireEvent.change(vadInput, { target: { value: "0." } })
expect(vadInput).toHaveValue("0.")
fireEvent.blur(vadInput)
expect(onVadThresholdChange).toHaveBeenCalledWith(0)
```

**Step 2: Run tests to verify they fail**

Run:

```bash
bunx vitest run src/components/PersonaGarden/__tests__/CommandAnalyticsSummary.test.tsx src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx
```

Expected: FAIL because the wrong analytics field is read, drafts are coerced too early, or template data is still shared.

**Step 3: Write the minimal implementation**

Align types and switch numeric controls to draft strings that parse on blur.

```tsx
const [vadThresholdDraft, setVadThresholdDraft] = React.useState(String(values.vadThreshold ?? 0))

const commitVadThreshold = () => {
  const parsed = Number.parseFloat(vadThresholdDraft)
  onVadThresholdChange(Number.isFinite(parsed) ? Math.max(0, parsed) : values.vadThreshold)
}
```

**Step 4: Run tests to verify they pass**

Run the same `bunx vitest run ...` command again.

Expected: PASS for analytics alignment, clamping, draft-entry behavior, and template immutability.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/CommandAnalyticsSummary.tsx apps/packages/ui/src/components/PersonaGarden/PersonaTurnDetectionControls.tsx apps/packages/ui/src/components/PersonaGarden/PersonaTurnDetectionFeedbackCard.tsx apps/packages/ui/src/components/PersonaGarden/personaStarterCommandTemplates.ts apps/packages/ui/src/components/PersonaGarden/__tests__/CommandAnalyticsSummary.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx apps/packages/ui/src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx
git commit -m "fix(persona): align analytics and turn detection state"
```

### Task 5: Clean up hook behavior, typed paths, and setup gating

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/TestLabPanel.tsx`
- Modify: `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`
- Modify: `apps/packages/ui/src/hooks/usePersonaSetupWizard.ts`
- Modify: `apps/packages/ui/src/hooks/useResolvedPersonaVoiceDefaults.tsx`
- Modify: `apps/packages/ui/src/services/tldw/path-utils.ts` or `apps/packages/ui/src/services/tldw/openapi-guard.ts` only if required
- Test: `apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx`
- Test: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx`
- Test: `apps/packages/ui/src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx`

**Step 1: Write the failing tests**

Add tests that prove:

- `stopBrowserSpeech` logs a failure instead of swallowing it
- the setup wizard still becomes required after loading completes when setup is `null`
- resolved voice defaults do not normalize the same persona phrases twice
- the Test Lab rerun effect does not retrigger from `heardText` churn
- dynamic persona test endpoints use the typed allowed-path helper instead of `as any`

```tsx
vi.spyOn(console, "error").mockImplementation(() => {})
speechSynthesis.cancel.mockImplementation(() => {
  throw new Error("cancel failed")
})
expect(console.error).toHaveBeenCalledWith(
  "stopBrowserSpeech: speechSynthesis.cancel failed",
  expect.any(Error)
)
```

**Step 2: Run tests to verify they fail**

Run:

```bash
bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx
```

Expected: FAIL because the current hooks still swallow errors, gate the wizard incorrectly, or rerun effects too often.

**Step 3: Write the minimal implementation**

Use refs for rerun tokens, cache normalized phrases locally, and route dynamic persona paths through `toAllowedPath`.

```tsx
const testPath = toAllowedPath(
  `/api/v1/persona/profiles/${encodeURIComponent(selectedPersonaId)}/voice-commands/test`
)

catch (err) {
  console.error("stopBrowserSpeech: speechSynthesis.cancel failed", err)
}
```

**Step 4: Run tests to verify they pass**

Run the same `bunx vitest run ...` command again.

Expected: PASS for hook cleanup, rerun guarding, and setup gating.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/TestLabPanel.tsx apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx apps/packages/ui/src/hooks/usePersonaSetupWizard.ts apps/packages/ui/src/hooks/useResolvedPersonaVoiceDefaults.tsx apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx apps/packages/ui/src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx apps/packages/ui/src/services/tldw/path-utils.ts apps/packages/ui/src/services/tldw/openapi-guard.ts
git commit -m "fix(persona): clean up hook guards and typed paths"
```

### Task 6: Run the focused verification suite and security checks

**Files:**
- Verify: `apps/packages/ui/src/components/PersonaGarden/**`
- Verify: `apps/packages/ui/src/hooks/**`
- Verify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Verify only if touched: `tldw_Server_API/app/api/v1/schemas/persona.py`
- Verify only if touched: `tldw_Server_API/app/api/v1/schemas/voice_assistant_schemas.py`

**Step 1: Run the focused frontend suite**

```bash
bunx vitest run src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx src/components/PersonaGarden/__tests__/CommandAnalyticsSummary.test.tsx src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx src/components/PersonaGarden/__tests__/McpToolPicker.test.tsx src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx src/components/PersonaGarden/__tests__/SetupStarterCommandsStep.test.tsx src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 2: Run any backend tests only if Python schema files changed**

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py -q
```

Expected: PASS or SKIP if no backend Python files were touched for this remediation.

**Step 3: Run Bandit only if backend Python files changed**

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/schemas/persona.py tldw_Server_API/app/api/v1/schemas/voice_assistant_schemas.py -f json -o /tmp/bandit_pr890_review_remediation.json
```

Expected: no new findings in touched Python files.

**Step 4: Review the worktree**

```bash
git status --short
git diff --stat
```

Expected: only intentional remediation files are modified.

**Step 5: Commit any final verification-only follow-up**

```bash
git add <only-if-you-made-follow-up-edits>
git commit -m "test(persona): close PR 890 review verification gaps"
```

### Task 7: Sync with `dev`, clear the merge state, and update the PR metadata

**Files:**
- Modify: conflicted files produced by merging `origin/dev` into `codex/persona-voice-assistant-builder`
- Update externally: PR #890 description

**Step 1: Fetch and merge the latest base branch**

```bash
git fetch origin dev
git merge origin/dev
```

Expected: either a clean merge or a bounded set of conflicts in active Persona Garden files.

**Step 2: Resolve conflicts and rerun the affected verification slice**

```bash
bunx vitest run src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS after conflict resolution.

**Step 3: Confirm the branch is mergeable locally**

```bash
git status --short
git log --oneline --decorate -n 5
```

Expected: clean worktree and a recent merge commit from `origin/dev`.

**Step 4: Update the PR description to match actual verification**

Use GitHub CLI or the web UI to:

- mark the required Validation checkboxes truthfully
- complete the applicable UX and accessibility checklist items
- keep the test plan aligned with the commands actually run

CLI path if preferred:

```bash
gh pr view 890 --repo rmusser01/tldw_server --json body --jq .body > /tmp/pr890_body.md
$EDITOR /tmp/pr890_body.md
gh pr edit 890 --repo rmusser01/tldw_server --body-file /tmp/pr890_body.md
```

**Step 5: Push and verify the PR state**

```bash
git push origin codex/persona-voice-assistant-builder
gh pr view 890 --repo rmusser01/tldw_server --json mergeStateStatus,reviewDecision,statusCheckRollup,url
```

Expected: `mergeStateStatus` is no longer `DIRTY`, review comments are resolved or ready to resolve, and the PR metadata reflects the completed validation.
