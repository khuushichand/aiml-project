# Persona Live Voice Processing Notice Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a delayed persona-live `VOICE_TURN_PROCESSING` notice that silently resets the live voice recovery timer when a committed voice turn is healthy but quiet before first visible progress.

**Architecture:** Add a backend per-session delayed task for committed voice turns, cancel it only on progress signals the client already honors, then update the live voice hook to treat the notice as silent progress and suppress it from the visible Persona route log.

**Tech Stack:** FastAPI websocket endpoint, asyncio tasks, React hooks, Vitest, pytest.

---

### Task 1: Lock Backend Delayed Notice With Red Tests

**Files:**
- Modify: `tldw_Server_API/tests/Persona/test_persona_ws.py`
- Reference: `tldw_Server_API/app/api/v1/endpoints/persona.py`

**Step 1: Write the failing tests**

Add focused websocket tests for:

```python
def test_persona_voice_commit_emits_processing_notice_after_quiet_delay(...):
def test_persona_voice_processing_notice_suppressed_by_tool_plan_progress(...):
def test_persona_voice_processing_notice_suppressed_by_assistant_delta_progress(...):
```

Monkeypatch the processing-notice delay constant to a very small value so the tests stay fast and deterministic.

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q -k "processing_notice"
```

Expected: failures because `VOICE_TURN_PROCESSING` does not exist yet.

**Step 3: Write minimal implementation**

In `persona.py`, add:

- a module-level processing delay constant
- a per-session task map
- helpers:
  - `_schedule_persona_live_processing_notice(session_id)`
  - `_cancel_persona_live_processing_notice(session_id)`
  - `_mark_persona_live_processing_progress(session_id)`

Schedule the delayed notice from `_commit_persona_live_turn()` after `VOICE_TURN_COMMITTED`.

Cancel it only on:

- `assistant_delta`
- `tool_plan`
- `tool_call`
- `tool_result`
- `TTS_UNAVAILABLE_TEXT_ONLY`
- cancel/cleanup/error paths for the active voice turn

Do not cancel it on generic info notices like memory-context notices.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q -k "processing_notice"
```

Expected: the new backend tests pass.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/tests/Persona/test_persona_ws.py
git commit -m "feat: add persona live processing notice"
```

### Task 2: Lock Cleanup And Cancel Semantics

**Files:**
- Modify: `tldw_Server_API/tests/Persona/test_persona_ws.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/persona.py`

**Step 1: Write the failing test**

Add a backend test for:

```python
def test_persona_voice_processing_notice_cleared_on_cancel_or_disconnect(...):
```

It should prove a pending delayed notice does not fire after session cleanup.

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q -k "processing_notice_cleared"
```

Expected: failure because cleanup does not yet cancel the task.

**Step 3: Write minimal implementation**

Cancel and clear pending processing notice state on:

- websocket disconnect cleanup
- explicit `cancel`
- new top-level turn start for the same session when needed

Make task cleanup resilient to:

- `asyncio.CancelledError`
- websocket send failures after disconnect

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q -k "processing_notice"
```

Expected: all processing-notice backend tests pass together.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/tests/Persona/test_persona_ws.py
git commit -m "fix: cancel stale persona processing notices"
```

### Task 3: Teach The Hook Silent Progress With Red Tests

**Files:**
- Modify: `apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx`
- Modify: `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`

**Step 1: Write the failing tests**

Add focused hook tests for:

```tsx
it("re-arms thinking recovery when VOICE_TURN_PROCESSING arrives")
it("still enters thinking_stuck after a renewed quiet window")
```

Drive the hook with:

- `VOICE_TURN_COMMITTED`
- fake timer advancement
- `VOICE_TURN_PROCESSING`
- more fake timer advancement

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx
```

Expected: failures because the hook ignores `VOICE_TURN_PROCESSING`.

**Step 3: Write minimal implementation**

In `usePersonaLiveVoiceController.tsx`:

- recognize `notice.reason_code === "VOICE_TURN_PROCESSING"`
- if still in `thinking`, call the same timer re-arm path used by other silent progress
- do not change warning text or visible state

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx
```

Expected: the new hook tests pass.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx
git commit -m "feat: rearm live recovery on processing notice"
```

### Task 4: Suppress Route Log Noise With Red Test

**Files:**
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`

**Step 1: Write the failing test**

Add a route test for:

```tsx
it("does not append VOICE_TURN_PROCESSING into the visible persona log")
```

The test should still route the notice through the live voice controller path.

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "VOICE_TURN_PROCESSING"
```

Expected: failure because all notices are currently appended to the visible log.

**Step 3: Write minimal implementation**

In `sidepanel-persona.tsx`, when handling `eventType === "notice"`:

- skip `appendLog(...)` if `reason_code === "VOICE_TURN_PROCESSING"`
- still let `liveVoiceController.handlePayload(...)` run first

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx
```

Expected: route suppression and hook handling both pass.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: suppress processing notices in persona logs"
```

### Task 5: Verification And Final Commit

**Files:**
- Verify touched backend and frontend files from Tasks 1-4

**Step 1: Run targeted backend verification**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q -k "processing_notice or voice_commit"
```

Expected: backend processing-notice coverage passes.

**Step 2: Run targeted frontend verification**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: hook and route coverage pass together.

**Step 3: Run hygiene checks**

Run:

```bash
source .venv/bin/activate && python -m py_compile tldw_Server_API/app/api/v1/endpoints/persona.py
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/persona.py -f json -o /tmp/bandit_persona_processing_notice.json
git diff --check
```

Expected:

- `py_compile` passes
- Bandit reports no new findings in touched backend code
- `git diff --check` passes

**Step 4: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/tests/Persona/test_persona_ws.py apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: add persona live processing progress notice"
```
