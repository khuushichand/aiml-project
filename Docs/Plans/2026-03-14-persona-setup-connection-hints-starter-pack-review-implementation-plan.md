# Persona Setup Connection Hints And Starter Pack Review Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add shallow connection validation hints to the setup safety step and expand the post-setup handoff into a starter-pack review surface.

**Architecture:** Keep all changes frontend-only. Add local validation and hint derivation to `SetupSafetyConnectionsStep.tsx`, capture a transient `setupReviewSummary` in `sidepanel-persona.tsx`, and expand `PersonaSetupHandoffCard.tsx` to render that summary plus jump actions. Do not add backend persistence for the review data, and do not turn the setup step into a full connection editor.

**Tech Stack:** React, TypeScript, Vitest, React Testing Library, Bun.

---

### Task 1: Add Shallow Connection Validation Hints To The Setup Step

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/SetupSafetyConnectionsStep.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx`

**Step 1: Write the failing tests**

Add tests like:

```tsx
it("blocks continue when the base url is malformed", () => {
  render(<SetupSafetyConnectionsStep saving={false} onContinue={vi.fn()} />)
  fireEvent.click(screen.getByRole("button", { name: "Never ask" }))
  fireEvent.click(screen.getByRole("button", { name: "Add one connection now" }))
  fireEvent.change(screen.getByLabelText("Connection name"), {
    target: { value: "Slack Alerts" }
  })
  fireEvent.change(screen.getByLabelText("Base URL"), {
    target: { value: "not-a-url" }
  })
  expect(screen.getByText("Enter a valid http or https URL.")).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Save safety and connection" })).toBeDisabled()
})

it("shows a non-blocking note for endpoint urls with a path", () => {
  ...
  expect(screen.getByText(/includes a path/i)).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Save safety and connection" })).toBeEnabled()
})

it("warns when bearer auth has no secret but still allows continue", () => {
  ...
})

it("does not offer custom header auth in setup", () => {
  ...
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx
```

Expected: FAIL because the setup step only validates non-empty fields and still exposes `custom_header`.

**Step 3: Write minimal implementation**

In `SetupSafetyConnectionsStep.tsx`:

- add a small helper to parse `Base URL` with `new URL(...)`
- accept only `http:` and `https:`
- derive:
  - `urlError`
  - `urlNote`
  - `authHint`
- keep continue enabled only when the URL is valid
- remove:

```tsx
<option value="custom_header">Custom header</option>
```

- add inline UI for:
  - malformed URL error
  - endpoint note for path/query/fragment
  - bearer/no-auth hint text

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/SetupSafetyConnectionsStep.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx
git commit -m "feat: add setup connection validation hints"
```

### Task 2: Capture Starter-Pack Review Summary In The Route

**Files:**
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing tests**

Add route tests like:

```tsx
it("captures starter command and safety choices into a setup review summary", async () => {
  ...
  expect(screen.getByTestId("persona-setup-handoff-card")).toHaveTextContent(
    "Added 3 starter commands"
  )
  expect(screen.getByTestId("persona-setup-handoff-card")).toHaveTextContent(
    "Ask for destructive actions"
  )
  expect(screen.getByTestId("persona-setup-handoff-card")).toHaveTextContent(
    "Connection added: Slack Alerts"
  )
})

it("records skipped starter commands and skipped connections explicitly", async () => {
  ...
})
```

Assert that the handoff content comes from the setup run, not from a re-fetch of persona resources.

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: FAIL because `setupHandoff` currently stores only `targetTab` and `completionType`.

**Step 3: Write minimal implementation**

In `sidepanel-persona.tsx`:

- extend the route-owned handoff types:

```ts
type SetupReviewSummary = {
  starterCommands: { mode: "added"; count: number } | { mode: "skipped" }
  confirmationMode: PersonaConfirmationMode | null
  connection: { mode: "created"; name: string } | { mode: "skipped" }
}
```

- add route state for an in-progress `setupReviewSummaryDraft`
- update the starter command step handlers to record:
  - `added` with count
  - `skipped`
- update `handleSetupSafetyStepContinue(...)` to record:
  - `confirmationMode`
  - `connection.created` with name
  - or `connection.skipped`
- freeze that summary into `setupHandoff` inside `completePersonaSetup(...)`

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS for the new handoff-summary assertions.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: capture persona setup review summary"
```

### Task 3: Expand The Handoff Card Into A Starter-Pack Review Surface

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/PersonaSetupHandoffCard.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing tests**

Add component tests like:

```tsx
it("renders starter pack review rows for commands, approval mode, and connection", () => {
  render(
    <PersonaSetupHandoffCard
      targetTab="commands"
      completionType="dry_run"
      reviewSummary={{
        starterCommands: { mode: "added", count: 3 },
        confirmationMode: "destructive_only",
        connection: { mode: "created", name: "Slack Alerts" }
      }}
      ...
    />
  )

  expect(screen.getByText("Starter pack review")).toBeInTheDocument()
  expect(screen.getByText("Added 3 starter commands")).toBeInTheDocument()
  expect(screen.getByText("Ask for destructive actions")).toBeInTheDocument()
  expect(screen.getByText("Connection added: Slack Alerts")).toBeInTheDocument()
})

it("exposes an open connections action from the review section", () => {
  ...
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: FAIL because the handoff card does not accept `reviewSummary` or `onOpenConnections`.

**Step 3: Write minimal implementation**

In `PersonaSetupHandoffCard.tsx`:

- add props:
  - `reviewSummary`
  - `onOpenConnections`
- render:
  - `Starter pack review`
  - summary/action rows for commands, approval mode, and connection
- keep the existing completion line and bottom actions

In `sidepanel-persona.tsx`:

- pass `reviewSummary` from `setupHandoff`
- wire:

```ts
onOpenConnections={() => openSetupHandoffTab("connections")}
```

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/PersonaSetupHandoffCard.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: expand persona setup handoff review"
```

### Task 4: Run Focused Regression Coverage

**Files:**
- No source changes required unless regressions are found

**Step 1: Run the focused setup suites**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 2: Run the broader Persona Garden regression sweep**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupStatusCard.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupStarterCommandsStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 3: Check for whitespace / patch issues**

Run:

```bash
git diff --check
```

Expected: no output.

**Step 4: Commit any final test-driven fixups**

```bash
git add apps/packages/ui/src/components/PersonaGarden/SetupSafetyConnectionsStep.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx apps/packages/ui/src/components/PersonaGarden/PersonaSetupHandoffCard.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "test: cover persona setup connection hints and review handoff"
```
