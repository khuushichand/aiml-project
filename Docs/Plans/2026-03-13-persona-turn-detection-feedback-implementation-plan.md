# Persona Turn Detection Feedback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add persona-scoped live-session tuning feedback so `Profiles -> Assistant Defaults` can show recent turn-detection behavior, exact settings snapshots, and conservative suggestions grounded in recent session summaries.

**Architecture:** Introduce a new backend live-session summary store keyed by persona `session_id`, capture a session-start turn-detection snapshot from live `voice_config`, add a best-effort client flush path for recovery counters, expand the persona analytics API with `recent_live_sessions`, and render a dedicated tuning-feedback card under saved turn-detection defaults in Persona Garden Profiles.

**Tech Stack:** FastAPI, Pydantic, SQLite, existing voice analytics helpers, React, TypeScript, Ant Design, Vitest, React Testing Library, pytest.

---

### Task 1: Red-Test Persona Analytics Schema For Recent Live Sessions

**Files:**
- Modify: `tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/persona.py`

**Step 1: Write the failing tests**

Extend persona analytics API coverage with assertions for a new
`recent_live_sessions` field.

Add tests for:

```python
def test_persona_voice_analytics_includes_recent_live_sessions(...):
    ...

def test_persona_voice_analytics_recent_live_sessions_exposes_turn_detection_snapshot(...):
    ...
```

Assert each recent session item includes:

- `session_id`
- `started_at`
- `ended_at`
- `auto_commit_enabled`
- `vad_threshold`
- `min_silence_ms`
- `turn_stop_secs`
- `min_utterance_secs`
- `turn_detection_changed_during_session`
- `total_committed_turns`
- `vad_auto_commit_count`
- `manual_commit_count`
- `manual_mode_required_count`
- `text_only_tts_count`
- `listening_recovery_count`
- `thinking_recovery_count`

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py -q
```

Expected: failures because the response schema does not yet expose
`recent_live_sessions`.

**Step 3: Write minimal implementation**

In `tldw_Server_API/app/api/v1/schemas/persona.py`:

- add a `PersonaLiveVoiceSessionSummary` response model
- extend the voice analytics response model with:
  - existing aggregate `live_voice`
  - new `recent_live_sessions: list[PersonaLiveVoiceSessionSummary]`

Keep the existing aggregate live-voice shape intact so current UI consumers do
not break.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py -q
```

Expected: schema-level analytics tests pass.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/persona.py tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py
git commit -m "feat: add persona live session analytics schema"
```

### Task 2: Red-Test Backend Live Voice Session Summary Persistence

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Modify: `tldw_Server_API/app/core/VoiceAssistant/db_helpers.py`
- Modify: `tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py`
- Modify: `tldw_Server_API/tests/Persona/test_persona_ws.py`

**Step 1: Write the failing tests**

Add backend coverage for:

```python
def test_persona_live_voice_session_summary_snapshots_first_voice_config(...):
    ...

def test_persona_live_voice_session_summary_marks_mid_session_turn_detection_changes(...):
    ...

def test_persona_live_voice_session_summary_counts_commit_sources_and_degraded_modes(...):
    ...
```

Assert:

- the first live `voice_config` creates the session summary row
- the stored settings snapshot stays stable after later tuning changes
- later tuning changes set `turn_detection_changed_during_session = True`
- VAD/manual commit counts and degraded counters increment correctly
- `ended_at` is set on cleanup

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q -k "session_summary or turn_detection_changed or degraded"
```

Expected: failures because there is no session-summary persistence yet.

**Step 3: Write minimal implementation**

In `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`:

- add a new `persona_live_voice_session_summaries` table
- add helpers to:
  - upsert/create a session summary row
  - snapshot first-session turn-detection settings
  - mark `turn_detection_changed_during_session`
  - increment commit/degraded counters
  - finalize `ended_at`
  - list recent summaries for analytics

In `tldw_Server_API/app/core/VoiceAssistant/db_helpers.py`:

- wrap the new DB helpers for the persona websocket/analytics layer

In `tldw_Server_API/app/api/v1/endpoints/persona.py`:

- wire persona live websocket lifecycle events to the new helpers

Keep V1 attribution simple:

- store one row per live `session_id`
- snapshot settings only once
- mark mixed sessions instead of segmenting them

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q -k "session_summary or turn_detection_changed or degraded"
```

Expected: new session-summary persistence tests pass.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/app/core/VoiceAssistant/db_helpers.py tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py tldw_Server_API/tests/Persona/test_persona_ws.py
git commit -m "feat: persist persona live voice session summaries"
```

### Task 3: Red-Test Client Recovery Flush Endpoint

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/persona.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/persona.py`
- Modify: `tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py`

**Step 1: Write the failing tests**

Add API tests for:

```python
def test_persona_live_voice_session_update_accepts_recovery_counts(...):
    ...

def test_persona_live_voice_session_update_is_idempotent(...):
    ...
```

Assert that:

- `PUT /api/v1/persona/profiles/{persona_id}/voice-analytics/live-sessions/{session_id}`
  updates `listening_recovery_count` and `thinking_recovery_count`
- repeated PUTs overwrite or safely upsert the client-owned counters
- optional finalization can set `ended_at` without duplicating rows

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py -q -k "live_voice_session_update or recovery_counts"
```

Expected: failures because the endpoint and request schema do not yet exist.

**Step 3: Write minimal implementation**

In `tldw_Server_API/app/api/v1/schemas/persona.py`:

- add a request model for live session analytics updates with:
  - `listening_recovery_count`
  - `thinking_recovery_count`
  - optional `finalize`
  - optional `ended_at`

In `tldw_Server_API/app/api/v1/endpoints/persona.py`:

- add the `PUT` endpoint
- upsert only the client-owned counters and optional finalization fields
- keep it safe to call multiple times for the same session

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py -q -k "live_voice_session_update or recovery_counts"
```

Expected: recovery-flush endpoint tests pass.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/app/api/v1/schemas/persona.py tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py
git commit -m "feat: add persona live session recovery flush api"
```

### Task 4: Red-Test Profiles Analytics Loading And Best-Effort Recovery Flush

**Files:**
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Modify: `apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx`

**Step 1: Write the failing tests**

Add route/controller tests for:

```tsx
it("loads persona voice analytics when the Profiles tab is active")
it("flushes live recovery counts before reconnecting the live session")
it("flushes live recovery counts on disconnect")
it("flushes live recovery counts on unmount as a best effort")
```

Assert:

- `Profiles` now triggers the persona analytics request
- the recovery flush body contains:
  - `session_id`
  - `listening_recovery_count`
  - `thinking_recovery_count`
- reconnect/disconnect do not block on the flush succeeding

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx -t "Profiles tab is active|flushes live recovery counts"
```

Expected: failures because Profiles does not fetch analytics and no recovery
flush path exists yet.

**Step 3: Write minimal implementation**

In `apps/packages/ui/src/routes/sidepanel-persona.tsx`:

- expand the analytics query condition to include `Profiles`
- add a small best-effort flush helper that calls the new backend endpoint
- call it on:
  - disconnect
  - recovery-driven reconnect
  - route cleanup/unmount

In `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`:

- expose read accessors for:
  - `listeningRecoveryCount`
  - `thinkingRecoveryCount`
  - current live `sessionId` if needed by the route wiring

Keep this best-effort:

- swallow non-fatal flush errors into existing warning/debug paths
- do not prevent reconnect/disconnect

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx -t "Profiles tab is active|flushes live recovery counts"
```

Expected: Profiles loading and best-effort flush tests pass.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx
git commit -m "feat: load persona tuning analytics in profiles"
```

### Task 5: Red-Test Assistant Defaults Tuning Feedback Card

**Files:**
- Create: `apps/packages/ui/src/components/PersonaGarden/PersonaTurnDetectionFeedbackCard.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/AssistantDefaultsPanel.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`

**Step 1: Write the failing tests**

Add Assistant Defaults UI tests for:

```tsx
it("shows no tuning suggestion yet when recent eligible data is sparse")
it("shows a healthy-state suggestion when recent sessions look stable")
it("suggests trying Fast when manual sends stay high across eligible sessions")
it("suggests checking auto-commit availability before changing thresholds")
it("marks mixed sessions and excludes them from recommendation heuristics")
```

Assert the card renders:

- current signal metrics
- recent session rows with derived preset labels
- mixed-session marker when `turn_detection_changed_during_session` is true
- conservative suggestion copy only when data thresholds are met

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx -t "tuning suggestion|Recent live tuning feedback|mixed sessions"
```

Expected: failures because the feedback card does not yet exist.

**Step 3: Write minimal implementation**

Create `apps/packages/ui/src/components/PersonaGarden/PersonaTurnDetectionFeedbackCard.tsx`
to render:

- `Current signal`
- `Suggested adjustment`
- `Recent sessions`

In `apps/packages/ui/src/components/PersonaGarden/AssistantDefaultsPanel.tsx`:

- render the new card below saved turn-detection defaults
- feed it persona analytics data from the route

In `apps/packages/ui/src/routes/sidepanel-persona.tsx`:

- pass the analytics payload into `AssistantDefaultsPanel`

Keep recommendation logic local and documented:

- require minimum recent-session and committed-turn thresholds
- exclude mixed sessions from heuristics
- prefer degraded/manual-mode warnings over threshold suggestions
- keep copy conservative and explainable

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx -t "tuning suggestion|Recent live tuning feedback|mixed sessions"
```

Expected: feedback card tests pass.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/PersonaTurnDetectionFeedbackCard.tsx apps/packages/ui/src/components/PersonaGarden/AssistantDefaultsPanel.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx
git commit -m "feat: add persona turn detection feedback card"
```

### Task 6: Verification And Final Cleanup

**Files:**
- Review all touched files from Tasks 1-5

**Step 1: Run focused backend verification**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py tldw_Server_API/tests/Persona/test_persona_ws.py -q
```

Expected: backend session-summary, API, and websocket analytics tests pass.

**Step 2: Run focused frontend verification**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: tuning feedback, flush, and Profiles analytics tests pass.

**Step 3: Run broader Persona Garden regression coverage**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx src/components/PersonaGarden/__tests__/PersonaGardenPanels.i18n.test.tsx src/components/PersonaGarden/__tests__/ExemplarImportPanel.test.tsx src/components/PersonaGarden/__tests__/VoiceExamplesPanel.test.tsx src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx src/routes/__tests__/sidepanel-persona.blocker.test.tsx src/routes/__tests__/sidepanel-persona.command-handoff.test.tsx src/routes/__tests__/sidepanel-persona-locale-keys.test.ts
```

Expected: no regressions in Persona Garden.

**Step 4: Run backend safety and syntax verification**

Run:

```bash
source .venv/bin/activate && python -m py_compile tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/app/api/v1/schemas/persona.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/app/core/VoiceAssistant/db_helpers.py
```

Expected: touched backend files compile cleanly.

Run:

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/app/api/v1/schemas/persona.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/app/core/VoiceAssistant/db_helpers.py -f json -o /tmp/bandit_persona_turn_detection_feedback.json
```

Expected: no new findings in touched backend code.

**Step 5: Final diff hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors and only intended changes remain.

**Step 6: Final commit**

```bash
git add <all touched files>
git commit -m "feat: add persona turn detection tuning feedback"
```

### Notes

- Keep the recommendation engine heuristic-only and conservative.
- Do not let current-session feedback claim causal certainty the telemetry cannot
  support.
- Preserve existing command/test-lab analytics behavior while adding
  Profiles-side tuning feedback.
