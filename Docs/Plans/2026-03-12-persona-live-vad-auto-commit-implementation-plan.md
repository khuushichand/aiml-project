# Persona Live VAD Auto-Commit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Persona Garden live voice default to server-side VAD auto-commit on `/api/v1/persona/stream`, while keeping explicit `voice_commit` as a manual fallback only.

**Architecture:** Extend the existing persona websocket live STT session state with a `SileroTurnDetector`, per-utterance commit/dedupe bookkeeping, and explicit commit notices. Then update the Persona Garden voice controller and `AssistantVoiceCard` so the client waits for server commit confirmation and only sends manual `voice_commit` in degraded/manual mode.

**Tech Stack:** FastAPI websocket endpoint, existing persona session manager/runtime, `SileroTurnDetector` from `Audio_Streaming_Unified`, React hook/controller state, Ant Design UI, pytest, Vitest.

---

### Task 1: Lock Backend Auto-Commit Behavior With Red Tests

**Files:**
- Modify: `tldw_Server_API/tests/Persona/test_persona_ws.py`
- Reference: `tldw_Server_API/app/api/v1/endpoints/persona.py`

**Step 1: Write the failing tests**

Add websocket tests for:

```python
def test_persona_audio_chunk_vad_auto_commit_routes_to_plan(monkeypatch):
    ...

def test_persona_voice_commit_is_ignored_after_vad_auto_commit(monkeypatch):
    ...

def test_persona_audio_chunk_warns_and_keeps_manual_mode_when_vad_unavailable(monkeypatch):
    ...
```

Use fake turn-detector/transcriber doubles so the tests prove:

- auto-commit can happen without a client `voice_commit`
- duplicate manual commit is ignored after auto-commit
- degraded manual mode emits a warning notice rather than failing the session
- trigger phrases are stripped server-side before the persona plan runs
- missing trigger phrases do not create persona turns

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q -k 'vad_auto_commit or manual_mode_when_vad_unavailable or ignored_after_vad_auto_commit'
```

Expected: failing assertions because persona websocket does not yet auto-commit spoken turns or emit degraded-mode notices.

**Step 3: Commit nothing yet**

Do not implement before you see the failures.

---

### Task 2: Implement Persona Websocket VAD Turn State

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/persona.py`
- Reference: `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Streaming_Unified.py`

**Step 1: Add session-local VAD/commit helpers**

In `persona.py`, add minimal helpers for:

- normalizing VAD config from `voice_config`
- creating a `SileroTurnDetector`
- normalizing/stripping trigger phrases server-side
- resetting one utterance after commit
- emitting one degraded-manual-mode warning per session
- committing a transcript snapshot with `commit_source`

Keep the state local to `persona_stream(...)`, for example:

```python
persona_live_turn_state_by_session: dict[str, dict[str, Any]] = {}
```

**Step 2: Wire `voice_config` into VAD session state**

When `voice_config` arrives:

- persist the normalized voice runtime
- rebuild the session turn detector
- clear current utterance state
- mark the session as not-yet-committed

Use server defaults if VAD fields are omitted, with VAD enabled by default for persona live sessions.

**Step 3: Wire `audio_chunk` into transcriber + turn detector**

Update the `audio_chunk` path so it:

- keeps the current transcriber-backed partial transcript flow
- also feeds the same normalized audio bytes into `SileroTurnDetector`
- auto-commits once when VAD marks the utterance complete
- emits a `notice` with `reason_code="VOICE_TURN_COMMITTED"` and `commit_source="vad_auto"`
- emits the commit notice before `_handle_persona_live_turn(...)` begins
- applies trigger detection/stripping on the server before routing the final transcript
- emits `VOICE_TRIGGER_NOT_HEARD` or `VOICE_EMPTY_COMMAND_AFTER_TRIGGER` when appropriate instead of creating a turn

Do not send a separate websocket protocol family if `notice` can carry the metadata cleanly.

**Step 4: Keep manual `voice_commit` as fallback-only**

Update `voice_commit` handling so it:

- commits the current snapshot only if that utterance has not already been committed
- emits `VOICE_COMMIT_IGNORED_ALREADY_COMMITTED` when the same utterance was already auto-committed
- uses `commit_source="manual"` for the success path
- runs the same server-side trigger detection/stripping logic as the auto-commit path

**Step 5: Run backend tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q -k 'vad_auto_commit or manual_mode_when_vad_unavailable or ignored_after_vad_auto_commit'
```

Expected: the new backend tests pass.

**Step 6: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/tests/Persona/test_persona_ws.py
git commit -m "feat: add persona live vad auto-commit"
```

---

### Task 3: Lock Frontend Controller Behavior With Red Tests

**Files:**
- Modify: `apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx`
- Reference: `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`
- Reference: `apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx`

**Step 1: Write the failing hook/UI tests**

Add tests that prove:

```tsx
it("does not send routine voice_commit when listening stops")
it("enters thinking only after VOICE_TURN_COMMITTED notice")
it("stops mic capture when the server commit notice arrives")
it("uses manual Send now when the session is in degraded manual mode")
it("renders the manual-send affordance and degraded warning state")
```

Use the existing mocked websocket + `useMicStream` harness in `usePersonaLiveVoiceController.test.tsx`.

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx
```

Expected: failures because the hook still sends `voice_commit` on stop-listening and the card does not expose manual-send state yet.

**Step 3: Commit nothing yet**

Do not change implementation before seeing the red tests.

---

### Task 4: Update Persona Garden Live Voice Controller And Card

**Files:**
- Modify: `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx`

**Step 1: Change controller commit ownership**

In `usePersonaLiveVoiceController`:

- stop sending `voice_commit` from `stopListening()`
- keep `stopListening()` focused on mic capture only
- add a dedicated `sendNow()` action that stops mic capture first when necessary, then sends manual `voice_commit`
- enter `thinking` and update `lastCommittedText` only when handling a server commit notice

Treat `VOICE_COMMIT_IGNORED_ALREADY_COMMITTED` as informational, not as an error state.

**Step 2: Track degraded manual mode**

Expose hook state such as:

```ts
manualCommitAvailable: boolean
manualModeOnly: boolean
sendNow: () => void
```

Set manual-mode state from server warning/notice payloads rather than from browser heuristics. Prefer stable reason codes like `VOICE_MANUAL_MODE_REQUIRED` and `VOICE_TURN_COMMITTED` instead of parsing warning text.

**Step 3: Update the Assistant Voice card**

Add a manual `Send now` button and copy that makes the mode explicit:

- normal mode: server auto-commit is active
- degraded mode: manual send required

Thread the new hook fields through `sidepanel-persona.tsx`.

**Step 4: Run frontend tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: the new tests pass and the existing sidepanel persona route test stays green.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx
git commit -m "feat: add persona live manual voice fallback"
```

---

### Task 5: Run Full Verification And Final Harden Pass

**Files:**
- Verify touched backend/frontend files from Tasks 2 and 4

**Step 1: Run backend verification**

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q
```

Expected: full persona websocket file passes.

**Step 2: Run frontend verification**

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: targeted Persona Garden live voice/frontend route tests pass.

**Step 3: Run hygiene/security checks**

```bash
source .venv/bin/activate && python -m py_compile tldw_Server_API/app/api/v1/endpoints/persona.py
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/persona.py -f json -o /tmp/bandit_persona_live_vad_auto_commit.json
git diff --check
```

Expected:

- `py_compile` passes
- Bandit reports no new findings in the touched backend scope
- `git diff --check` is clean

**Step 4: Commit final polish if needed**

If verification required code changes:

```bash
git add <touched files>
git commit -m "test: harden persona live vad auto-commit flow"
```

Otherwise, do not create an extra no-op commit.
