# Persona Live Voice Approval Clarity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Show a compact approval-waiting summary in the Persona Garden Live card and add an in-panel jump to the existing runtime approval controls.

**Architecture:** Keep approval state in `sidepanel-persona.tsx`, derive a summary from `pendingApprovals`, pass it into `AssistantVoiceCard`, and use a ref-based jump handler to scroll and focus the existing `runtimeApprovalCard`.

**Tech Stack:** React, TypeScript, Ant Design, Vitest, React Testing Library.

---

### Task 1: Red-Test The Live Card Approval Summary

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx`

**Step 1: Write the failing tests**

Add component tests for:

```tsx
it("renders approval summary text in the current action block")
it("prefers approval summary over active tool status")
it("calls onJumpToApproval when the jump button is pressed")
```

Use summary text such as:

- `Waiting for approval: search_notes`
- `Waiting for approval: search_notes (+1 more)`

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx
```

Expected: failures because the Live card does not yet accept approval-summary props.

**Step 3: Write minimal implementation**

In `AssistantVoiceCard.tsx`:

- add `pendingApprovalSummary` and `onJumpToApproval`
- render the approval summary in the existing status area
- make approval summary override `activeToolStatus`
- render a `Jump to approval` button only when summary exists

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx
```

Expected: the new component tests pass.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx
git commit -m "feat: show approval summary in live voice card"
```

### Task 2: Red-Test Route Summary Derivation And Jump

**Files:**
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`

**Step 1: Write the failing tests**

Add route tests for:

```tsx
it("shows a live approval summary when runtime approval is required")
it("updates the live approval summary as the approval queue changes")
it("jumps to the runtime approval card from the live voice card")
```

Use real route behavior by driving:

- approval-producing `tool_result` websocket payloads
- approve/deny actions that remove queue entries

For the jump test:

- mock `scrollIntoView`
- verify the runtime approval card root is targeted
- verify the first actionable approval button receives focus when possible

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "approval summary|jumps to the runtime approval card"
```

Expected: failures because no summary or jump behavior exists yet.

**Step 3: Write minimal implementation**

In `sidepanel-persona.tsx`:

- derive `pendingApprovalSummary` from `pendingApprovals`
- add a ref and `data-testid` to the runtime approval card root
- add `handleJumpToRuntimeApproval()`
- pass summary and jump handler into `AssistantVoiceCard`
- keep queue ownership and approval submission logic unchanged

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx
```

Expected: route and component approval-clarity tests pass together.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: add live approval jump in persona session"
```

### Task 3: Verify The Slice

**Files:**
- Verify touched route and component files from Tasks 1-2

**Step 1: Run targeted verification**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: the focused approval-clarity suites pass.

**Step 2: Run broader Persona Garden regression coverage**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx src/components/PersonaGarden/__tests__/PersonaGardenPanels.i18n.test.tsx src/components/PersonaGarden/__tests__/ExemplarImportPanel.test.tsx src/components/PersonaGarden/__tests__/VoiceExamplesPanel.test.tsx src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx src/routes/__tests__/sidepanel-persona.blocker.test.tsx src/routes/__tests__/sidepanel-persona.command-handoff.test.tsx src/routes/__tests__/sidepanel-persona-locale-keys.test.ts
```

Expected: Persona Garden regressions stay green.

**Step 3: Run diff sanity check**

Run:

```bash
git diff --check
```

Expected: no whitespace or merge-marker problems.

**Step 4: Final commit**

```bash
git add Docs/Plans/2026-03-13-persona-live-voice-approval-clarity-design.md Docs/Plans/2026-03-13-persona-live-voice-approval-clarity-implementation-plan.md apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: add approval clarity to persona live voice"
```
