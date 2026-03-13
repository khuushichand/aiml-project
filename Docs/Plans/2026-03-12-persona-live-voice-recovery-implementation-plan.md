# Persona Garden Live Voice Recovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Persona Garden-only recovery handling for stuck live voice turns, with explicit recovery actions for listening and thinking states.

**Architecture:** Extend the existing `usePersonaLiveVoiceController` with timer-driven recovery sub-state and action handlers, surface that state in `AssistantVoiceCard`, and wire reconnect behavior through `sidepanel-persona` so only the live voice transport/session is refreshed. Keep the first slice client-side and leave the persona websocket contract unchanged.

**Tech Stack:** React hooks, Ant Design UI, Persona Garden route state, Vitest, Testing Library.

---

### Task 1: Lock Listening Recovery With Red Tests

**Files:**
- Modify: `apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx`
- Reference: `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`

**Step 1: Write the failing tests**

Add focused hook tests for:

```tsx
it("shows listening recovery after 4 seconds with transcript but no commit")
it("keep listening dismisses and restarts listening recovery")
it("reset turn clears heard transcript and returns to idle")
```

Use fake timers so the tests prove the recovery panel is driven by time plus controller state, not by network mocks.

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx
```

Expected: failures because the controller has no recovery sub-state or listening timeout behavior yet.

**Step 3: Write minimal implementation**

In `usePersonaLiveVoiceController.tsx`, add:

- `recoveryMode`
- timer refs for listening recovery
- handlers for `keepListening()` and `resetTurn()`

Make `resetTurn()` stop the mic, clear transcript state, clear timers, and return to `idle`.

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx
```

Expected: the new listening-recovery tests pass.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx
git commit -m "feat: add live voice listening recovery state"
```

### Task 2: Lock Thinking Recovery With Red Tests

**Files:**
- Modify: `apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx`
- Reference: `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`

**Step 1: Write the failing tests**

Add focused hook tests for:

```tsx
it("shows thinking recovery after 8 seconds after commit with no assistant progress")
it("assistant progress clears thinking recovery")
it("send text manually uses lastCommittedText")
```

The tests should drive the controller with:

- `VOICE_TURN_COMMITTED`
- timer advancement
- `assistant_delta`

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx
```

Expected: failures because thinking recovery and `sendTextManually()` do not exist yet.

**Step 3: Write minimal implementation**

Update `usePersonaLiveVoiceController.tsx` to:

- start an 8-second recovery timer on `VOICE_TURN_COMMITTED`
- clear that timer on `assistant_delta`, `tts_audio`, and text-only completion notices
- add `waitOnRecovery()` and `sendTextManually()` handlers
- use `lastCommittedText` as the source for `sendTextManually()`

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx
```

Expected: the new thinking-recovery tests pass.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx
git commit -m "feat: add live voice thinking recovery actions"
```

### Task 3: Surface Recovery UI In Assistant Voice Card

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`

**Step 1: Write the failing UI tests**

Add UI assertions for:

```tsx
it("renders listening recovery copy and actions")
it("renders thinking recovery copy and actions")
```

Use the existing Persona Garden Live Session test surface instead of creating a new card-only test file.

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx
```

Expected: failures because `AssistantVoiceCard` does not render a recovery panel yet.

**Step 3: Write minimal implementation**

Update `AssistantVoiceCard.tsx` to render a recovery panel below warnings when `recoveryMode !== "none"`, with the correct copy and buttons for:

- `listening_stuck`
- `thinking_stuck`

Thread the new hook state/handlers through `sidepanel-persona.tsx`:

- `onKeepListening`
- `onResetTurn`
- `onWaitOnRecovery`
- `onSendTextManually`
- `onReconnectVoiceSession`

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx
```

Expected: hook and UI recovery tests pass together.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx
git commit -m "feat: add persona live voice recovery panel"
```

### Task 4: Wire Reconnect Through Persona Garden Route

**Files:**
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`

**Step 1: Write the failing route test**

Add a route test for:

```tsx
it("reconnects only the live voice session when recovery requests reconnect")
```

The test should prove persona selection and the rest of Persona Garden state remain intact while the live websocket/session path reconnects.

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: failure because the route does not yet expose a dedicated recovery reconnect action.

**Step 3: Write minimal implementation**

Add a route-level handler in `sidepanel-persona.tsx` that:

- clears live recovery UI state through the hook callback path
- refreshes only the persona live websocket/session connection
- preserves the selected persona and broader tab state

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx
```

Expected: reconnect coverage passes and existing live-session behavior remains green.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: reconnect persona live voice from recovery panel"
```

### Task 5: Verification And Final Commit

**Files:**
- Verify touched files from Tasks 1-4

**Step 1: Run targeted frontend verification**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: all touched recovery suites pass.

**Step 2: Run broader Persona Garden verification**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx src/components/PersonaGarden/__tests__/CommandAnalyticsSummary.test.tsx src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: no Persona Garden regressions.

**Step 3: Run hygiene checks**

Run:

```bash
git diff --check
```

Expected: no whitespace or conflict-marker issues.

**Step 4: Commit**

```bash
git add apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: add persona live voice stuck-turn recovery"
```
