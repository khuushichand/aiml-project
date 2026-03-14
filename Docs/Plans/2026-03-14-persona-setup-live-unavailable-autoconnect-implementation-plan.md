# Persona Setup Live Unavailable Autoconnect Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Automatically start the normal live-session connection flow when setup detours into `Live Session` from a `live_unavailable` outcome.

**Architecture:** Patch only the route recovery handler in `sidepanel-persona.tsx` so `live_unavailable` reuses the existing `connect()` callback immediately after activating the live detour. Keep `live_failure` unchanged, add focused route tests first, and avoid any component or websocket contract changes.

**Tech Stack:** React, TypeScript, Vitest, React Testing Library, Bun.

**Status:** Complete

---

### Task 1: Add Red Tests For Live-Unavailable Autoconnect

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing tests**

Add focused route coverage like:

```tsx
it("auto-connects after a live_unavailable setup detour", async () => {
  ...
  fireEvent.click(screen.getByRole("button", { name: "Open Live Session to fix this" }))

  await waitFor(() => {
    expect(MockWebSocket.instances).toHaveLength(1)
  })
})
```

Also add:

```tsx
it("does not auto-connect again for a live_failure detour", async () => {
  ...
})
```

And:

```tsx
it("does not create a duplicate websocket when already connected", async () => {
  ...
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx -t "auto-connects after a live_unavailable setup detour"
```

Expected: FAIL because the current detour only switches tabs and does not call `connect()`.

**Step 3: Write minimal implementation**

Do nothing yet. This step is just the failing test stage.

**Step 4: Re-run to confirm the same failure**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx -t "auto-connects after a live_unavailable setup detour"
```

Expected: same FAIL.

### Task 2: Patch The Route Recovery Handler

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`

**Step 1: Implement the minimal route change**

In `handleRecoverSetupInLiveSession`:

- keep the existing detour state update
- after activating the detour, branch:

```ts
if (context.source === "live_unavailable" && !connected && !connecting) {
  void connect()
}
```

Do not change any component code or banner copy.

**Step 2: Run the focused failing test**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx -t "auto-connects after a live_unavailable setup detour"
```

Expected: PASS.

**Step 3: Run the related detour route tests**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx -t "setup live"
```

Expected: PASS for the detour-focused cases.

**Step 4: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: autoconnect setup live-unavailable detours"
```

### Task 3: Run Focused Regressions And Hygiene

**Status:** Complete

**Files:**
- Update: `Docs/Plans/2026-03-14-persona-setup-live-unavailable-autoconnect-implementation-plan.md`

**Step 1: Mark the plan complete**

Update this plan file so each task is marked complete.

**Step 2: Run focused route coverage**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 3: Run broader setup sweep**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupStarterCommandsStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 4: Check hygiene**

Run:

```bash
git diff --check
```

Expected: no output.

**Step 5: Run Bandit on touched UI scope**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/PersonaGarden apps/packages/ui/src/routes -f json -o /tmp/bandit_persona_setup_live_unavailable_autoconnect.json
```

Expected: `0` findings in the touched UI scope.

**Step 6: Commit plan closeout if needed**

```bash
git add Docs/Plans/2026-03-14-persona-setup-live-unavailable-autoconnect-implementation-plan.md
git commit -m "docs: mark setup live-unavailable autoconnect plan complete"
```

Expected: clean regressions, clean hygiene checks, and no unstaged changes.
