# Persona Garden Live Voice Transport Implementation Plan

Execution Status: Completed

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Persona Garden Live Session voice persona-aware by upgrading the existing persona websocket audio scaffold into the real live voice transport, then add the Persona Garden-specific live voice controller and explicit text-only TTS degradation behavior.

**Architecture:** Keep all spoken turns inside `/api/v1/persona/stream`. Refactor the existing typed `user_message` path into a shared helper and route committed voice transcripts through that helper. Do not reuse the generic `/api/v1/audio/chat/stream` hook for Persona Garden. Persona voice defaults remain persona-backed configuration resolved locally in Persona Garden. Session-local `auto-resume` and `barge-in` overrides live only for the current live session. TTS failures must degrade to text-only mode with a non-fatal warning, not a terminal stream error.

**Tech Stack:** FastAPI, Pydantic, persona websocket stream, React, TypeScript, existing persona route components, Vitest, pytest, Bandit.

---

### Task 1: Refactor Typed Persona Turns Into A Shared Executor

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/persona.py`
- Test: `tldw_Server_API/tests/Persona/test_persona_ws.py`

**Step 1: Write the failing test**

Add a focused websocket regression proving that the typed `user_message` path still emits the same plan/notice flow after the refactor.

Expected assertions:

- `user_message` still produces `tool_plan`
- session-scoped persona policy and memory notices still appear
- no wire-format changes are introduced for existing typed flows

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q
```

Expected: FAIL once the test references the new helper expectations and the helper does not exist yet.

**Step 3: Write minimal implementation**

Refactor the current `mtype == "user_message"` branch into a shared helper such as:

```python
async def _handle_persona_user_turn(...):
    ...
```

Move into it only the logic that is common to typed and spoken turns:

- runtime context load
- session creation
- preference patching
- memory/companion/persona-state retrieval
- turn recording
- plan proposal/storage
- notice + `tool_plan` emission

Keep the outward event shapes unchanged.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/tests/Persona/test_persona_ws.py
git commit -m "refactor: share persona websocket turn execution"
```


### Task 2: Add Persona Websocket Voice Runtime Config And Commit Events

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/persona.py`
- Possibly modify: `tldw_Server_API/app/core/Persona/session_manager.py`
- Test: `tldw_Server_API/tests/Persona/test_persona_ws.py`

**Step 1: Write the failing test**

Add websocket tests covering:

- `voice_config` stores session-scoped runtime voice state
- `voice_commit` requires a valid `session_id`
- `voice_commit` reuses the shared persona turn executor and emits the same `tool_plan` flow as `user_message`

Use expectations like:

```python
assert notice_or_plan["session_id"] == session_id
assert tool_plan["event"] == "tool_plan"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q
```

Expected: FAIL because `voice_config` and `voice_commit` do not exist yet.

**Step 3: Write minimal implementation**

Add websocket handlers for:

- `voice_config`
- `voice_commit`

Store runtime-only values in session preferences or adjacent session runtime state:

- `voice_runtime.stt_language`
- `voice_runtime.stt_model`
- `voice_runtime.tts_provider`
- `voice_runtime.tts_voice`
- `voice_runtime.trigger_phrases`
- `voice_runtime.auto_resume`
- `voice_runtime.barge_in`
- `voice_runtime.text_only_due_to_tts_failure`

Do not persist these into persona profiles from the websocket path.

Route `voice_commit` into the shared turn helper from Task 1.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/app/core/Persona/session_manager.py tldw_Server_API/tests/Persona/test_persona_ws.py
git commit -m "feat: add persona websocket voice runtime events"
```


### Task 3: Replace Persona Audio Echo Behavior With Real Voice Commit Routing

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/persona.py`
- Test: `tldw_Server_API/tests/Persona/test_persona_ws.py`

**Step 1: Write the failing test**

Add websocket coverage proving that:

- `audio_chunk` can emit `partial_transcript`
- a subsequent `voice_commit` produces normal persona planning events
- the old placeholder `tts_text = "You said ..."` echo path is no longer the main completion path

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q
```

Expected: FAIL because the current `audio_chunk` flow still behaves like a scaffold.

**Step 3: Write minimal implementation**

Keep `audio_chunk` focused on transcript accumulation and transcript event emission. Remove or bypass the current placeholder direct TTS echo behavior for the real live path.

Implement a minimal transcript buffer keyed by `session_id` so:

- `audio_chunk` appends/updates transcript state
- `voice_commit` consumes the committed transcript
- the committed transcript is then processed through the shared persona turn executor

Preserve current per-session rate limiting and payload validation.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/tests/Persona/test_persona_ws.py
git commit -m "feat: route persona voice commits through live turn handling"
```


### Task 4: Add Explicit Text-Only TTS Degradation Contract

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/persona.py`
- Test: `tldw_Server_API/tests/Persona/test_persona_ws.py`

**Step 1: Write the failing test**

Add a websocket test proving that when TTS generation fails for a committed spoken turn:

- assistant text still arrives
- a warning notice with `reason_code == "TTS_UNAVAILABLE_TEXT_ONLY"` is emitted
- the stream does not terminate
- no fatal error event is required for the turn

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q
```

Expected: FAIL because persona websocket does not yet have this explicit degraded-mode contract.

**Step 3: Write minimal implementation**

Wrap persona websocket TTS emission so provider/validation/synthesis errors:

- emit a warning notice
- mark session runtime state as `text_only_due_to_tts_failure = true`
- continue to emit text/assistant events

Do not close the websocket for this case.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/tests/Persona/test_persona_ws.py
git commit -m "feat: add persona text-only TTS fallback"
```


### Task 5: Build Persona Garden Live Voice Controller

**Files:**
- Create: `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`
- Create: `apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Possibly modify: `apps/packages/ui/src/services/persona-stream.ts`
- Test: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing test**

Add controller and route tests proving:

- resolved persona defaults are sent as `voice_config`
- client-side trigger detection gates transcript commit
- session-local `auto-resume` and `barge-in` overrides reset on disconnect
- the controller never reads or writes global `useVoiceChatSettings`

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: FAIL because the controller hook does not exist yet.

**Step 3: Write minimal implementation**

Create a Persona-specific controller that:

- consumes `useResolvedPersonaVoiceDefaults`
- owns session-local `autoResume` and `bargeIn`
- sends `voice_config` after connect and when resolved runtime values change
- streams `audio_chunk`
- accumulates `partial_transcript`
- sends `voice_commit`
- plays `tts_audio` binary chunks
- reacts to `TTS_UNAVAILABLE_TEXT_ONLY`

Important constraints:

- do not reuse `useVoiceChatStream`
- do not mutate browser-global voice settings

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/services/persona-stream.ts apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: add persona live voice controller"
```


### Task 6: Add Live Session Assistant Voice Card And Session-Local Toggles

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/LiveSessionPanel.tsx`
- Create or modify: `apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaGardenPanels.i18n.test.tsx`
- Create or modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx`

**Step 1: Write the failing test**

Add UI tests proving:

- resolved trigger/STT/TTS values render read-only
- `auto-resume` and `barge-in` render as session-only controls
- warning state renders when voice falls back to text-only

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx src/components/PersonaGarden/__tests__/PersonaGardenPanels.i18n.test.tsx
```

Expected: FAIL because the Live Session panel does not expose this voice UI yet.

**Step 3: Write minimal implementation**

Extend `LiveSessionPanel` with an `Assistant Voice` card that consumes the new controller state and renders:

- read-only trigger phrases
- read-only STT language/model
- read-only TTS provider/voice
- live toggle controls for session-only overrides
- current voice mode
- text-only warning banner

Keep the copy explicit that editing defaults still lives under `Profile -> Assistant Defaults`.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx src/components/PersonaGarden/__tests__/PersonaGardenPanels.i18n.test.tsx
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/LiveSessionPanel.tsx apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaGardenPanels.i18n.test.tsx
git commit -m "feat: add persona live assistant voice controls"
```


### Task 7: Verification, Security, And Final Plan Cleanup

**Files:**
- Modify only if required by test fixes
- Keep: `Docs/Plans/2026-03-12-persona-garden-live-voice-transport-design.md`
- Keep: `Docs/Plans/2026-03-12-persona-garden-live-voice-transport-implementation-plan.md`

**Step 1: Run backend verification**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py tldw_Server_API/tests/Persona/test_persona_profiles_api.py tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py -q
```

Expected: PASS

**Step 2: Run frontend verification**

Run:

```bash
bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx src/components/PersonaGarden/__tests__/PersonaGardenPanels.i18n.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx src/routes/__tests__/sidepanel-persona.blocker.test.tsx src/routes/__tests__/sidepanel-persona.command-handoff.test.tsx
```

Expected: PASS

**Step 3: Run static verification**

Run:

```bash
source .venv/bin/activate && python -m py_compile tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/app/core/Persona/session_manager.py
git diff --check
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/app/core/Persona/session_manager.py -f json -o /tmp/bandit_persona_live_voice_transport.json
```

Expected: no new Bandit findings in touched code

**Step 4: Final commit**

```bash
git add Docs/Plans/2026-03-12-persona-garden-live-voice-transport-design.md Docs/Plans/2026-03-12-persona-garden-live-voice-transport-implementation-plan.md
git add -A
git commit -m "feat: add persona live voice transport"
```
