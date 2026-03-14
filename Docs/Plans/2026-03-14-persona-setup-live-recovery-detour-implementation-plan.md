# Persona Setup Live Recovery Detour Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let setup recover from `live_unavailable` and `live_failure` by detouring into the real `Live Session` tab, then resuming `Test and finish` automatically on success or manually on demand.

**Architecture:** Add route-owned `setupLiveDetour` and `setupLiveReturnNote` state in `sidepanel-persona.tsx`, extend `SetupTestAndFinishStep.tsx` with outcome-specific live recovery actions, and reuse the existing awaited setup live-response path for auto-return. Keep the slice frontend-only and avoid changing websocket contracts.

**Tech Stack:** React, TypeScript, Vitest, React Testing Library, Bun.

---

### Task 1: Add Live Recovery Actions To The Setup Test Step

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/SetupTestAndFinishStep.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx`

**Step 1: Write the failing tests**

Add coverage like:

```tsx
it("renders a live recovery action for live_unavailable", () => {
  const onRecoverInLiveSession = vi.fn()

  render(
    <SetupTestAndFinishStep
      ...
      outcome={{ kind: "live_unavailable" }}
      onRecoverInLiveSession={onRecoverInLiveSession}
    />
  )

  fireEvent.click(screen.getByRole("button", { name: "Open Live Session to fix this" }))
  expect(onRecoverInLiveSession).toHaveBeenCalledWith({
    source: "live_unavailable",
    text: ""
  })
})
```

And:

```tsx
it("renders a live recovery action for live_failure", () => {
  const onRecoverInLiveSession = vi.fn()

  render(
    <SetupTestAndFinishStep
      ...
      outcome={{
        kind: "live_failure",
        text: "summarize my assistant setup",
        message: "Socket send failed"
      }}
      onRecoverInLiveSession={onRecoverInLiveSession}
    />
  )

  fireEvent.click(screen.getByRole("button", { name: "Try again in Live Session" }))
  expect(onRecoverInLiveSession).toHaveBeenCalledWith({
    source: "live_failure",
    text: "summarize my assistant setup"
  })
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx
```

Expected: FAIL because the step has no live recovery callback or buttons.

**Step 3: Write minimal implementation**

In `SetupTestAndFinishStep.tsx`:

- add prop:

```ts
onRecoverInLiveSession?: (context: {
  source: "live_unavailable" | "live_failure"
  text: string
}) => void
```

- when `live_unavailable` is present, render:
  - button label: `Open Live Session to fix this`
  - click calls the callback with `{ source: "live_unavailable", text: "" }`

- when `live_failure` is present, render:
  - button label: `Try again in Live Session`
  - click calls the callback with the failed `text`

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx
```

Expected: PASS.

### Task 2: Add Route-Owned Live Detour State And Manual Return

**Files:**
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing tests**

Add route coverage like:

```tsx
it("detours setup into live for live_unavailable and returns manually", async () => {
  ...
  fireEvent.click(screen.getByRole("button", { name: "Open Live Session to fix this" }))

  await waitFor(() => {
    expect(screen.queryByTestId("assistant-setup-overlay")).not.toBeInTheDocument()
  })

  expect(screen.getByText("Finish this live test, then return to setup.")).toBeInTheDocument()

  fireEvent.click(screen.getByRole("button", { name: "Return to setup" }))

  await waitFor(() => {
    expect(screen.getByTestId("assistant-setup-current-step")).toHaveTextContent("test")
  })
  expect(
    screen.getByText("Live session is still available if you want to retry.")
  ).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: FAIL because there is no setup live detour state or live recovery banner.

**Step 3: Write minimal implementation**

In `sidepanel-persona.tsx`:

- add route state:
  - `setupLiveDetour`
  - `setupLiveReturnNote`
- add handler:

```ts
handleRecoverSetupInLiveSession({
  source,
  text
})
```

This should:

- set `setupLiveDetour`
- clear any old `setupLiveReturnNote`
- switch `activeTab` to `live`

Also add:

```ts
handleReturnToSetupFromLiveDetour()
```

This should:

- clear `setupLiveDetour`
- clear `setupWizardAwaitingLiveResponseRef.current`
- restore the setup overlay
- set `setupLiveReturnNote` to `Live session is still available if you want to retry.`

Update setup gating to render the wizard only when:

```ts
personaSetupWizard.isSetupRequired &&
!setupCommandDetour &&
!setupLiveDetour
```

Render a small live recovery banner while `setupLiveDetour` is active with:

- text: `Finish this live test, then return to setup.`
- button: `Return to setup`

Pass `onRecoverInLiveSession` into `SetupTestAndFinishStep`.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS for the new manual live detour assertions.

### Task 3: Auto-Return After Successful Setup Live Response

**Files:**
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing tests**

Add route coverage like:

```tsx
it("auto-returns setup from live detour after a successful setup live response", async () => {
  ...
  fireEvent.click(screen.getByRole("button", { name: "Try again in Live Session" }))

  // trigger the awaited setup live response through the existing websocket path

  await waitFor(() => {
    expect(screen.getByTestId("assistant-setup-current-step")).toHaveTextContent("test")
  })

  expect(
    screen.getByText("Live session responded. Finish setup when you're ready.")
  ).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Finish with live session" })).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: FAIL because live success does not currently clear a detour or restore setup automatically.

**Step 3: Write minimal implementation**

In the existing setup-live-response handling path in `sidepanel-persona.tsx`:

- when the route consumes the awaited setup live response successfully:
  - if `setupLiveDetour` is active:
    - clear `setupLiveDetour`
    - set `setupLiveReturnNote = "Live session responded. Finish setup when you're ready."`
  - keep the current `setupTestOutcome = { kind: "live_success", ... }`

Use `setupWizardLastLiveTextRef.current` when building the resumed note/outcome context.

Make sure this path only fires once for the awaited setup live response.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

### Task 4: Clear Live Detour On Setup Reset Or Rerun

**Files:**
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing test**

Add coverage like:

```tsx
it("clears the setup live detour when setup is reset", async () => {
  ...
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: FAIL because reset/rerun does not yet clear setup live detour state.

**Step 3: Write minimal implementation**

In the existing setup reset/rerun paths:

- clear `setupLiveDetour`
- clear `setupLiveReturnNote`
- clear `setupWizardAwaitingLiveResponseRef.current`

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

### Task 5: Run Focused Regressions And Commit

**Files:**
- Update: `Docs/Plans/2026-03-14-persona-setup-live-recovery-detour-implementation-plan.md`

**Step 1: Run focused coverage**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
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

**Step 4: Run Bandit on touched UI scope**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/PersonaGarden apps/packages/ui/src/routes -f json -o /tmp/bandit_persona_setup_live_recovery_detour.json
```

Expected: `0` findings in the touched UI scope.

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-14-persona-setup-live-recovery-detour-design.md Docs/Plans/2026-03-14-persona-setup-live-recovery-detour-implementation-plan.md apps/packages/ui/src/components/PersonaGarden/SetupTestAndFinishStep.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: add setup live recovery detour"
```

Expected: clean focused regressions, clean `git diff --check`, and one feature commit.
