# Persona Setup No-Match Command Detour Implementation Plan

**Goal:** Let setup recover from `dry_run_no_match` by detouring into `Commands`, drafting a command from the unmatched phrase, and returning to the setup test step after save.

**Architecture:** Add route-owned setup detour state in `sidepanel-persona.tsx`, extend command draft state with a setup-aware source, add a dedicated command-saved callback in `CommandsPanel.tsx`, and add a `Create command from this phrase` action in `SetupTestAndFinishStep.tsx`. Keep the slice frontend-only and do not change backend setup metadata.

**Tech Stack:** React, TypeScript, Vitest, React Testing Library, Bun.

**Status:** Complete

---

### Task 1: Add The Setup No-Match Action To The Test Step

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/SetupTestAndFinishStep.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx`

**Step 1: Write the failing tests**

Add coverage like:

```tsx
it("renders a create-command action for dry-run no-match outcomes", () => {
  const onCreateCommandFromPhrase = vi.fn()

  render(
    <SetupTestAndFinishStep
      ...
      outcome={{ kind: "dry_run_no_match", heardText: "open the pod bay doors" }}
      onCreateCommandFromPhrase={onCreateCommandFromPhrase}
    />
  )

  fireEvent.click(screen.getByRole("button", { name: "Create command from this phrase" }))
  expect(onCreateCommandFromPhrase).toHaveBeenCalledWith("open the pod bay doors")
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx
```

Expected: FAIL because the step has no such action or callback.

**Step 3: Write minimal implementation**

In `SetupTestAndFinishStep.tsx`:

- add prop:

```ts
onCreateCommandFromPhrase?: (heardText: string) => void
```

- when `dry_run_no_match` is present, render:
  - button label: `Create command from this phrase`
  - click calls the new callback with `heardText`

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx
```

Expected: PASS.

### Task 2: Add Route-Owned Setup Detour State And Resume Logic

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing tests**

Add route coverage like:

```tsx
it("detours setup into commands for a dry-run no-match and returns to test after save", async () => {
  ...
  fireEvent.click(screen.getByRole("button", { name: "Create command from this phrase" }))
  expect(screen.queryByTestId("assistant-setup-overlay")).not.toBeInTheDocument()
  expect(screen.getByTestId("persona-commands-draft-banner")).toHaveTextContent(
    "Drafted from assistant setup"
  )

  fireEvent.click(screen.getByRole("button", { name: "Save command" }))

  await waitFor(() => {
    expect(screen.getByTestId("assistant-setup-current-step")).toHaveTextContent("test")
  })
  expect(screen.getByPlaceholderText("Try a spoken phrase")).toHaveValue(
    "open the pod bay doors"
  )
  expect(screen.getByText(/Command saved. Run the same phrase again/i)).toBeInTheDocument()
})
```

Also add coverage that reset/rerun clears the pending detour.

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: FAIL because setup gating cannot be bypassed and there is no resume state.

**Step 3: Write minimal implementation**

In `sidepanel-persona.tsx`:

- add route state:
  - `setupCommandDetour`
  - `setupNoMatchPhrase`
  - `setupTestResumeNote`
  - `draftCommandSource`
- add handler:

```ts
handleCreateCommandFromSetupNoMatch(heardText: string)
```

This should:

- set detour active
- persist the phrase
- feed the existing command draft path
- switch `activeTab` to `commands`

Adjust setup gating to render tabs when:

```ts
personaSetupWizard.isSetupRequired && !setupCommandDetour?.active
```

Pass the new action into `SetupTestAndFinishStep`.

On successful command save during an active detour:

- clear detour active state
- clear draft source
- return to setup overlay
- restore test phrase
- set resume note

Use a dedicated `onCommandSaved` callback and only auto-return when the saved command came from the setup-created draft flow.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS for the new detour/resume assertions.

### Task 3: Make Commands Drafts Source-Aware For Setup

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`

**Step 1: Write the failing tests**

Add component coverage like:

```tsx
it("renders setup-specific draft banner copy when the draft source is assistant setup", () => {
  ...
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx
```

Expected: FAIL because draft banners only know the Test Lab phrasing.

**Step 3: Write minimal implementation**

In `CommandsPanel.tsx`:

- keep `draftCommandPhrase?: string | null`
- add `draftCommandSource?: "test_lab" | "setup_no_match" | null`
- preserve existing assist behavior
- render source-specific banner text
- add optional callback:

```ts
onCommandSaved?: (savedCommandId: string, context: { fromDraft: boolean }) => void
```

Call it after successful save.

Update the route to pass phrase and source separately.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx
```

Expected: PASS.

### Task 4: Run Focused Regressions And Commit

**Status:** Complete

**Files:**
- Update: `Docs/Plans/2026-03-14-persona-setup-no-match-command-detour-implementation-plan.md`

**Step 1: Run focused coverage**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 2: Run broader setup sweep**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupStarterCommandsStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 3: Check hygiene**

Run:

```bash
git diff --check
```

Expected: no output.

**Step 4: Commit**

```bash
git add Docs/Plans/2026-03-14-persona-setup-no-match-command-detour-design.md Docs/Plans/2026-03-14-persona-setup-no-match-command-detour-implementation-plan.md apps/packages/ui/src/components/PersonaGarden/SetupTestAndFinishStep.tsx apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: add setup no-match command detour"
```
