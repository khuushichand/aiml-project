# Persona Live Voice Approval Motion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a strong landing pulse for `Jump to approval`, a smaller pulse for approval auto-advance, and a steady post-pulse highlight for the guided runtime approval row in Persona Garden Live Session.

**Architecture:** Keep all queue semantics in `sidepanel-persona.tsx`, add a route-owned highlight phase plus replay token for the active approval row, and render pulse/steady state through row data attributes and lightweight CSS that respects `prefers-reduced-motion`.

**Tech Stack:** React, TypeScript, Ant Design, Vitest, React Testing Library, CSS keyframes/utility classes.

---

### Task 1: Red-Test Primary Landing Pulse State
**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`

**Step 1: Write the failing tests**

Add route tests for:

```tsx
it("sets landing_primary on the active approval row when jump to approval is used")
it("replays the primary landing pulse when jump to approval is pressed again on the same row")
```

Assert:

- `data-highlight-phase="landing_primary"`
- `data-highlight-seq` increases when the jump is repeated

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "landing_primary|replays the primary landing pulse"
```

Expected: failures because the route does not yet track highlight phase or replay tokens.

**Step 3: Write minimal implementation**

In `sidepanel-persona.tsx`:

- add route-owned visual state:
  - `approvalHighlightPhase`
  - `approvalHighlightSequence`
  - phase timer ref
- set `landing_primary` and increment sequence in `handleJumpToRuntimeApproval()`
- expose `data-highlight-phase` and `data-highlight-seq` on the active row

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "landing_primary|replays the primary landing pulse"
```

Expected: the new primary-pulse route tests pass.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: add primary approval landing pulse state"
```

### Task 2: Red-Test Settle-To-Steady Behavior
**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`

**Step 1: Write the failing tests**

Add route tests for:

```tsx
it("settles the active approval row from landing_primary to steady after the pulse duration")
```

Use fake timers and assert:

- initial phase is `landing_primary`
- after the timer, phase becomes `steady`

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "settles the active approval row from landing_primary to steady"
```

Expected: failure because no settle timer exists yet.

**Step 3: Write minimal implementation**

In `sidepanel-persona.tsx`:

- add a phase timer helper
- settle the phase from `landing_primary` to `steady`
- clear/restart the timer when the pulse replays

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "settles the active approval row from landing_primary to steady"
```

Expected: the settle-to-steady test passes.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: settle approval landing pulse into steady highlight"
```

### Task 3: Red-Test Secondary Auto-Advance Pulse
**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`

**Step 1: Write the failing tests**

Add route tests for:

```tsx
it("sets landing_secondary on the next approval row when guidance auto-advances")
it("settles the auto-advanced row from landing_secondary to steady")
```

Use the existing approval-advance scenarios.

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "landing_secondary|auto-advances"
```

Expected: failures because advancement currently only updates `activeApprovalKey`.

**Step 3: Write minimal implementation**

In `sidepanel-persona.tsx`:

- when the active approval resolves and another pending approval remains, set:
  - new `activeApprovalKey`
  - `approvalHighlightPhase = "landing_secondary"`
  - increment replay token
- settle that phase to `steady` with the same timer helper

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "landing_secondary|auto-advances"
```

Expected: the secondary-pulse route tests pass.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: add secondary pulse for approval queue progression"
```

### Task 4: Add Motion Styling And Reduced-Motion Fallback
**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing tests**

Add a route-level assertion for:

```tsx
it("clears highlight phase state on disconnect and reconnect")
```

This keeps the styling state honest while motion is added.

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "clears highlight phase state"
```

Expected: failure if phase state survives cleanup paths.

**Step 3: Write minimal implementation**

In `sidepanel-persona.tsx`:

- add lightweight keyframe classes or embedded route-scoped styles for:
  - `landing_primary`
  - `landing_secondary`
  - `steady`
- add reduced-motion overrides
- clear phase state and timers during disconnect/reconnect/session reset

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "clears highlight phase state"
```

Expected: cleanup tests pass with the new motion state in place.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: animate guided approval rows with reduced-motion fallback"
```

### Task 5: Verify The Slice
**Status:** Complete

**Files:**
- Verify touched route and docs from Tasks 1-4

**Step 1: Run focused approval-motion verification**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "landing_primary|replays the primary landing pulse|settles the active approval row|landing_secondary|auto-advances|clears highlight phase state"
```

Expected: approval-motion route coverage passes.

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
git add Docs/Plans/2026-03-13-persona-live-voice-approval-motion-design.md Docs/Plans/2026-03-13-persona-live-voice-approval-motion-implementation-plan.md apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: add approval landing motion to persona live voice"
```
