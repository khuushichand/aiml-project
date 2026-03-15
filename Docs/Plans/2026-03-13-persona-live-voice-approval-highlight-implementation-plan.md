# Persona Live Voice Approval Highlight Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add route-owned approval-row guidance so `Jump to approval` highlights a specific runtime approval, advances to the next pending approval after resolution, and briefly confirms the final answered approval before clearing.

**Architecture:** Keep queue ownership in `sidepanel-persona.tsx`, add `activeApprovalKey` plus a transient `resolvedApprovalSnapshot`, derive the Live summary from the active guided row, and target jump/focus to a keyed runtime approval row instead of the card root.

**Tech Stack:** React, TypeScript, Ant Design, Vitest, React Testing Library.

---

### Task 1: Red-Test Guided Approval Highlighting

**Files:**
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`

**Step 1: Write the failing tests**

Add route tests for:

```tsx
it("highlights the first pending approval row after jump to approval")
it("keeps the current highlighted approval when a new approval arrives")
it("derives the live approval summary from the highlighted approval")
```

Use runtime approval websocket payloads with at least two distinct approval keys.

Assert:

- the targeted row has `data-highlighted="true"`
- the row shows `Needs your approval`
- the Live summary text matches the highlighted row instead of always following
  `pendingApprovals[0]`

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "highlights the first pending approval row|keeps the current highlighted approval|derives the live approval summary"
```

Expected: failures because the route does not yet track an active approval key or
render row-level highlight state.

**Step 3: Write minimal implementation**

In `sidepanel-persona.tsx`:

- add `activeApprovalKey`
- derive an `activePendingApproval` from `pendingApprovals`
- update `pendingApprovalSummary` to prefer `activePendingApproval`
- set `activeApprovalKey` in `handleJumpToRuntimeApproval()`
- add row-level `data-approval-key` and `data-highlighted`
- render a `Needs your approval` badge on the highlighted row

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "highlights the first pending approval row|keeps the current highlighted approval|derives the live approval summary"
```

Expected: the new highlight-focused route tests pass.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: guide active runtime approvals in persona live session"
```

### Task 2: Red-Test Row-Targeted Jump And Focus

**Files:**
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`

**Step 1: Write the failing tests**

Add route tests for:

```tsx
it("scrolls and focuses the highlighted approval row instead of only the card root")
it("falls back to the card root if the active row ref is unavailable")
```

Mock `scrollIntoView` and assert the active approval row is the primary target.

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "scrolls and focuses the highlighted approval row|falls back to the card root"
```

Expected: failures because jump still only targets the card root.

**Step 3: Write minimal implementation**

In `sidepanel-persona.tsx`:

- add a keyed row-ref registry for approval rows
- update `handleJumpToRuntimeApproval()` to locate the active row
- scroll the active row into view
- focus that row’s approve button when possible
- fall back to the card root only if the row ref is missing

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "scrolls and focuses the highlighted approval row|falls back to the card root"
```

Expected: row-targeted jump behavior passes under test.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: target active approval row from live jump action"
```

### Task 3: Red-Test Queue Advancement And Answered Fade

**Files:**
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`

**Step 1: Write the failing tests**

Add route tests for:

```tsx
it("moves the highlight to the next pending approval after the active one is approved")
it("moves the highlight to the next pending approval after the active one is denied")
it("shows a transient answered banner after the last highlighted approval is resolved")
it("clears a stale answered snapshot if the same approval key reappears")
```

Use fake timers for the answered fade assertion.

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "moves the highlight to the next pending approval|shows a transient answered banner|clears a stale answered snapshot"
```

Expected: failures because the route currently removes approvals without snapshot
state or fade timing.

**Step 3: Write minimal implementation**

In `sidepanel-persona.tsx`:

- add `resolvedApprovalSnapshot`
- add a fade timer ref and cleanup logic
- when the active approval is resolved, capture the snapshot before queue removal
- if another pending approval remains, clear the snapshot and advance
- if none remain, render `Answered: {tool}` temporarily and clear it after the timer
- clear a snapshot immediately if the same approval key reappears

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "moves the highlight to the next pending approval|shows a transient answered banner|clears a stale answered snapshot"
```

Expected: advancement and answered-fade tests pass.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: advance and fade guided runtime approvals"
```

### Task 4: Red-Test Session Cleanup

**Files:**
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`

**Step 1: Write the failing tests**

Add route tests for:

```tsx
it("clears approval guidance on disconnect")
it("clears approval guidance on reconnect/session reset")
```

Assert that:

- `data-highlighted` rows disappear
- the answered banner is removed
- the next session starts clean

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "clears approval guidance on disconnect|clears approval guidance on reconnect"
```

Expected: failures because the new guidance state does not exist or is not yet
cleared consistently.

**Step 3: Write minimal implementation**

In `sidepanel-persona.tsx`:

- clear `activeApprovalKey`
- clear `resolvedApprovalSnapshot`
- clear any fade timer on disconnect, reconnect, and force-close cleanup paths

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "clears approval guidance on disconnect|clears approval guidance on reconnect"
```

Expected: cleanup tests pass.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "fix: clear guided approval state on persona session reset"
```

### Task 5: Verify The Slice

**Files:**
- Verify touched route and docs from Tasks 1-4

**Step 1: Run focused approval-highlight verification**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: approval guidance tests pass cleanly.

**Step 2: Run broader Persona Garden regression coverage**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx src/components/PersonaGarden/__tests__/PersonaGardenPanels.i18n.test.tsx src/components/PersonaGarden/__tests__/ExemplarImportPanel.test.tsx src/components/PersonaGarden/__tests__/VoiceExamplesPanel.test.tsx src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx src/routes/__tests__/sidepanel-persona.blocker.test.tsx src/routes/__tests__/sidepanel-persona.command-handoff.test.tsx src/routes/__tests__/sidepanel-persona-locale-keys.test.ts
```

Expected: Persona Garden route and panel regressions remain green.

**Step 3: Run diff sanity check**

Run:

```bash
git diff --check
```

Expected: no whitespace or merge-marker problems.

**Step 4: Final commit**

```bash
git add Docs/Plans/2026-03-13-persona-live-voice-approval-highlight-design.md Docs/Plans/2026-03-13-persona-live-voice-approval-highlight-implementation-plan.md apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: highlight guided runtime approvals in persona live voice"
```
