# Persona Live Voice Tool Processing Status Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add tool-aware live status text plus unified delayed processing notices so Persona Garden live voice keeps a recovery path during slow tool-backed turns.

**Architecture:** Reuse the existing persona websocket delayed-notice mechanism instead of adding a second scheduler, extend it to support `VOICE_TOOL_EXECUTION_PROCESSING`, then teach the live voice hook and card to show current tool activity and re-arm recovery after both `tool_call` and `tool_result`.

**Tech Stack:** FastAPI websocket endpoint, asyncio tasks, React hooks, React components, Vitest, pytest.

---

### Task 1: Red-Test The Unified Backend Scheduler

**Files:**
- Modify: `tldw_Server_API/tests/Persona/test_persona_ws.py`
- Reference: `tldw_Server_API/app/api/v1/endpoints/persona.py`

**Step 1: Write the failing tests**

Add focused websocket tests for:

```python
def test_persona_tool_call_emits_tool_processing_notice_after_quiet_delay(...):
def test_persona_tool_processing_notice_suppressed_by_tool_result(...):
def test_persona_processing_notice_refactor_keeps_voice_turn_processing_behavior(...):
```

Monkeypatch the processing delay constant to a very small value.

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q -k "tool_processing_notice or voice_turn_processing"
```

Expected: failures because `VOICE_TOOL_EXECUTION_PROCESSING` does not exist yet and the scheduler is not generic.

**Step 3: Write minimal implementation**

In `persona.py`:

- refactor the existing delayed notice helper into a generic scheduler
- keep one per-session task map
- allow scheduling notices with custom `reason_code`, `message`, and metadata
- schedule `VOICE_TOOL_EXECUTION_PROCESSING` after `tool_call`
- keep `VOICE_TURN_PROCESSING` behavior intact after commit

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q -k "tool_processing_notice or voice_turn_processing"
```

Expected: the new backend notice tests pass.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/tests/Persona/test_persona_ws.py
git commit -m "feat: add persona tool processing notices"
```

### Task 2: Red-Test Post-Tool-Result Recovery Safety

**Files:**
- Modify: `apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx`
- Modify: `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`

**Step 1: Write the failing tests**

Add focused hook tests for:

```tsx
it("sets activeToolStatus and re-arms thinking recovery on tool_call")
it("re-arms thinking recovery when VOICE_TOOL_EXECUTION_PROCESSING arrives")
it("clears activeToolStatus and re-arms recovery on tool_result")
it("clears activeToolStatus and recovery on approval tool_result")
```

Drive the hook with `VOICE_TURN_COMMITTED`, `tool_call`, delayed notices, and `tool_result` payloads.

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx
```

Expected: failures because the hook has no active tool status and currently clears recovery on `tool_call` and `tool_result`.

**Step 3: Write minimal implementation**

In `usePersonaLiveVoiceController.tsx`:

- add `activeToolStatus`
- derive the status text from `tool` and `why`
- re-arm thinking recovery on `tool_call`
- handle `VOICE_TOOL_EXECUTION_PROCESSING` as silent progress
- clear `activeToolStatus` on `tool_result`, `assistant_delta`, `tts_audio`, reset, reconnect, and disconnect
- re-arm recovery after non-approval `tool_result` when still `thinking`

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx
```

Expected: the new hook tests pass.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx
git commit -m "feat: track tool progress in live voice controller"
```

### Task 3: Red-Test The Live Card Status Line

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantVoiceCard.test.tsx`

**Step 1: Write the failing tests**

Add component tests for:

```tsx
it("renders the current action line while thinking with active tool status")
it("hides the current action line when active tool status is empty")
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/AssistantVoiceCard.test.tsx
```

Expected: failures because the card does not render tool status yet.

**Step 3: Write minimal implementation**

In `AssistantVoiceCard.tsx`:

- add an `activeToolStatus` prop
- render a compact `Current action` block only when `state === "thinking"` and status text exists

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/AssistantVoiceCard.test.tsx
```

Expected: the new card tests pass.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantVoiceCard.test.tsx
git commit -m "feat: show current live tool action"
```

### Task 4: Red-Test Route Log Suppression

**Files:**
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`

**Step 1: Write the failing test**

Add a route test for:

```tsx
it("does not append tool processing notices into the visible persona log")
```

Cover both:

- `VOICE_TURN_PROCESSING`
- `VOICE_TOOL_EXECUTION_PROCESSING`

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "tool processing notices"
```

Expected: failure because the route still appends generic notices.

**Step 3: Write minimal implementation**

In `sidepanel-persona.tsx`:

- continue passing notice payloads to `liveVoiceController.handlePayload(...)`
- suppress `appendLog(...)` for both processing notice reason codes

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx src/components/PersonaGarden/__tests__/AssistantVoiceCard.test.tsx
```

Expected: route, hook, and card tests all pass together.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: suppress live processing notices in persona logs"
```

### Task 5: Verify The Whole Slice

**Files:**
- Verify touched backend and frontend files from Tasks 1-4

**Step 1: Run targeted backend verification**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q -k "processing_notice or tool_processing_notice"
```

Expected: all backend notice tests pass.

**Step 2: Run targeted frontend verification**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx src/components/PersonaGarden/__tests__/AssistantVoiceCard.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: all targeted frontend tests pass.

**Step 3: Run broader Persona Garden regression coverage**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx src/components/PersonaGarden/__tests__/PersonaGardenPanels.i18n.test.tsx src/components/PersonaGarden/__tests__/ExemplarImportPanel.test.tsx src/components/PersonaGarden/__tests__/VoiceExamplesPanel.test.tsx src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx src/routes/__tests__/sidepanel-persona.blocker.test.tsx src/routes/__tests__/sidepanel-persona.command-handoff.test.tsx src/routes/__tests__/sidepanel-persona-locale-keys.test.ts
```

Expected: Persona Garden regressions remain green.

**Step 4: Run backend compile and security checks**

Run:

```bash
source .venv/bin/activate && python -m py_compile tldw_Server_API/app/api/v1/endpoints/persona.py
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/persona.py -f json -o /tmp/bandit_persona_tool_processing_status.json
```

Expected: compile passes and Bandit reports no new findings in the touched backend file.

**Step 5: Final commit**

```bash
git add Docs/Plans/2026-03-13-persona-live-voice-tool-processing-status-design.md Docs/Plans/2026-03-13-persona-live-voice-tool-processing-status-implementation-plan.md tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/tests/Persona/test_persona_ws.py apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantVoiceCard.test.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: add live tool progress status for persona voice"
```
