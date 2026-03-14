# Persona Setup Handoff Tightening And Analytics Implementation Plan

Execution Status: Complete

Closeout Notes:
- Tasks 1 through 7 are implemented on `codex/persona-voice-assistant-builder`.
- Backend and frontend regressions passed during closeout.
- The updated Playwright setup spec was executed in this environment, but the run was skipped because extension launch was unavailable here.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Tighten the Persona Garden post-setup handoff so it survives into real first use, and add setup-specific analytics that measure setup completion, recovery, and first post-setup success.

**Architecture:** Extend persona setup state with a durable `run_id`, add a separate append-only `persona_setup_events` model and summary endpoint on the backend, then teach `sidepanel-persona.tsx` to emit setup events and keep the handoff alive until a successful post-setup action collapses it into a compact banner. Keep analytics separate from live voice/runtime analytics and keep same-tab handoff behavior anchor-free in V1.

**Tech Stack:** FastAPI, Pydantic, SQLite/PostgreSQL DB helpers, React, TypeScript, Vitest, React Testing Library, Playwright, Bun.

---

### Task 1: Add Setup `run_id` To Persona Setup State

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/persona.py`
- Modify: `tldw_Server_API/tests/Persona/test_persona_profiles_api.py`

**Step 1: Write the failing backend tests**

Add coverage proving `run_id` is preserved through persona profile operations:

```python
def test_persona_profile_setup_run_id_round_trips(client, auth_headers):
    create_resp = client.post(
        "/api/v1/persona/profiles",
        json={
            "id": "garden-helper",
            "name": "Garden Helper",
            "setup": {
                "status": "in_progress",
                "run_id": "setup-run-1",
                "current_step": "commands",
                "completed_steps": ["persona", "voice"],
            },
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["setup"]["run_id"] == "setup-run-1"
```

Also add a PATCH/update assertion for reset/rerun shape.

**Step 2: Run the targeted test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_profiles_api.py -q -k run_id
```

Expected: FAIL because `PersonaSetupState` does not yet include `run_id`.

**Step 3: Add the minimal schema support**

In `persona.py`, extend `PersonaSetupState`:

```python
class PersonaSetupState(BaseModel):
    status: PersonaSetupStatus = "not_started"
    version: int = Field(default=1, ge=1)
    run_id: str | None = Field(default=None, min_length=1, max_length=200)
    current_step: PersonaSetupStep = "persona"
    completed_steps: list[PersonaSetupStep] = Field(default_factory=list)
    completed_at: str | None = None
    last_test_type: PersonaSetupTestType | None = None
```

Do not add extra setup fields in this task.

**Step 4: Re-run the targeted test**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_profiles_api.py -q -k run_id
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/persona.py tldw_Server_API/tests/Persona/test_persona_profiles_api.py
git commit -m "feat: add persona setup run ids"
```

### Task 2: Add Backend Setup Analytics Event Persistence And Summary API

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/persona.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/persona.py`
- Create: `tldw_Server_API/tests/Persona/test_persona_setup_analytics_api.py`

**Step 1: Write the failing backend API tests**

Add tests that prove:

- events can be appended to a setup run
- deterministic `event_key` dedupes once-only events
- the summary endpoint returns recent runs and aggregate counts

Example:

```python
def test_persona_setup_events_dedupe_by_event_key(client, auth_headers):
    persona_id = "garden-helper"
    body = {
        "event_id": "evt-1",
        "event_key": "step_viewed:test",
        "run_id": "setup-run-1",
        "event_type": "step_viewed",
        "step": "test",
    }

    first = client.post(
        f"/api/v1/persona/profiles/{persona_id}/setup-events",
        json=body,
        headers=auth_headers,
    )
    second = client.post(
        f"/api/v1/persona/profiles/{persona_id}/setup-events",
        json={**body, "event_id": "evt-2"},
        headers=auth_headers,
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["deduped"] is True
```

Add a summary test that expects `completion_rate`, `most_common_dropoff_step`,
and `recent_runs`.

**Step 2: Run the new backend tests to verify they fail**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_setup_analytics_api.py -q
```

Expected: FAIL because the DB table and endpoints do not exist yet.

**Step 3: Add DB table and helpers**

In `ChaChaNotes_DB.py`, add:

- `_ensure_persona_setup_events_table()`
- `record_persona_setup_event(...)`
- `list_persona_setup_events(...)`
- `get_persona_setup_analytics_summary(...)`

Recommended schema:

```sql
CREATE TABLE IF NOT EXISTS persona_setup_events (
    event_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    persona_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_key TEXT,
    step TEXT,
    completion_type TEXT,
    detour_source TEXT,
    action_target TEXT,
    metadata_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

Also add a partial unique index for `(persona_id, run_id, event_key)` where
`event_key IS NOT NULL`.

**Step 4: Add API schemas and endpoints**

In `tldw_Server_API/app/api/v1/schemas/persona.py`, add:

- `PersonaSetupEventType`
- `PersonaSetupEventCreate`
- `PersonaSetupEventWriteResponse`
- `PersonaSetupAnalyticsRunSummary`
- `PersonaSetupAnalyticsSummary`
- `PersonaSetupAnalyticsResponse`

In `tldw_Server_API/app/api/v1/endpoints/persona.py`, add:

- `POST /api/v1/persona/profiles/{persona_id}/setup-events`
- `GET /api/v1/persona/profiles/{persona_id}/setup-analytics`

Keep the event write endpoint append-only and idempotent on `event_key`.

**Step 5: Re-run the new backend tests**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_setup_analytics_api.py -q
```

Expected: PASS.

**Step 6: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/app/api/v1/schemas/persona.py tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/tests/Persona/test_persona_setup_analytics_api.py
git commit -m "feat: add persona setup analytics events"
```

### Task 3: Add Route-Level Setup Analytics Emission

**Files:**
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Create: `apps/packages/ui/src/services/tldw/persona-setup-analytics.ts`
- Create: `apps/packages/ui/src/services/tldw/__tests__/persona-setup-analytics.test.ts`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing frontend tests**

Add helper tests for deterministic event-key construction:

```ts
it("builds stable event keys for once-only setup events", () => {
  expect(buildSetupEventKey({
    runId: "setup-run-1",
    eventType: "step_viewed",
    step: "test"
  })).toBe("step_viewed:test")
})
```

In the route suite, add a test that completes setup and asserts setup analytics
POSTs are sent for:

- `setup_completed`
- `handoff_action_clicked`
- `first_post_setup_action`

**Step 2: Run the targeted frontend tests to verify they fail**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/services/tldw/__tests__/persona-setup-analytics.test.ts src/routes/__tests__/sidepanel-persona.test.tsx -t "setup analytics|stable event keys"
```

Expected: FAIL because no setup analytics helper or route emission exists.

**Step 3: Add the helper**

Create `persona-setup-analytics.ts` with:

- `buildSetupEventKey(...)`
- `postPersonaSetupEvent(...)`
- tiny event payload normalizers

Keep it small and route-facing only.

**Step 4: Wire route emission**

In `sidepanel-persona.tsx`:

- emit `setup_started` when a new `run_id` is created for a setup run
- emit `step_viewed` on step changes with once-only `event_key`
- emit `step_completed` on successful step transitions
- emit `step_error` from step-local failure handlers
- emit `retry_clicked` from step retry actions
- emit `detour_started` / `detour_returned`
- emit `setup_completed` on completion

Use best-effort writes and do not block UX.

**Step 5: Re-run the targeted frontend tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/services/tldw/__tests__/persona-setup-analytics.test.ts src/routes/__tests__/sidepanel-persona.test.tsx -t "setup analytics|stable event keys"
```

Expected: PASS.

**Step 6: Commit**

```bash
git add apps/packages/ui/src/services/tldw/persona-setup-analytics.ts apps/packages/ui/src/services/tldw/__tests__/persona-setup-analytics.test.ts apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: emit persona setup analytics events"
```

### Task 4: Tighten Handoff Recommendation And Retargeting

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/PersonaSetupHandoffCard.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing handoff tests**

Add component coverage for recommended next-step rendering:

```tsx
it("prioritizes trying a live turn after dry-run completion", () => {
  render(
    <PersonaSetupHandoffCard
      ...
      completionType="dry_run"
      reviewSummary={{
        starterCommands: { mode: "added", count: 3 },
        confirmationMode: "destructive_only",
        connection: { mode: "created", name: "Slack" },
      }}
    />
  )

  expect(screen.getByText("Try your first live turn")).toBeInTheDocument()
})
```

Add route coverage for:

- same-tab handoff action keeps the card visible
- cross-tab handoff action retargets the card to the destination tab

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx -t "handoff|recommended next step"
```

Expected: FAIL because the current card has no recommended action model and the
route clears the handoff on any action.

**Step 3: Implement the tighter handoff model**

In `sidepanel-persona.tsx`:

- extend `setupHandoff` with:
  - `runId`
  - `recommendedAction`
  - `consumedAction`
  - `compact`
- replace `openSetupHandoffTab()` so it:
  - keeps the handoff on same-tab actions
  - retargets `targetTab` on cross-tab actions
  - does not clear the handoff immediately

In `PersonaSetupHandoffCard.tsx`:

- add a `Recommended next step` section
- keep starter-pack review rows below it
- render a compact variant when `compact` is true

**Step 4: Re-run the targeted tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx -t "handoff|recommended next step"
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/PersonaSetupHandoffCard.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: tighten persona setup handoff actions"
```

### Task 5: Collapse Handoff On First Successful Post-Setup Action

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/ProfilePanel.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/ConnectionsPanel.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing route tests**

Add route coverage like:

```tsx
it("collapses the setup handoff after the first successful post-setup action", async () => {
  ...
  fireEvent.click(screen.getByRole("button", { name: "Review commands" }))
  ...
  fireEvent.click(screen.getByTestId("persona-commands-save"))

  await waitFor(() => {
    expect(screen.getByText("Setup complete")).toBeInTheDocument()
  })
})
```

Add one test for each meaningful post-setup action family only if needed.
Prefer one representative happy path plus unit-level callback coverage.

**Step 2: Run the targeted route test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "collapses the setup handoff"
```

Expected: FAIL because the route has no consumed-action model yet.

**Step 3: Add success callbacks**

Wire route callbacks for:

- `CommandsPanel.onCommandSaved` -> `command_saved`
- `ConnectionsPanel` save success -> `connection_saved`
- `ConnectionsPanel` test success -> `connection_test_succeeded`
- `AssistantDefaultsPanel` or `ProfilePanel` save success -> `voice_defaults_saved`
- dry-run match path -> `dry_run_match`
- live assistant response after handoff -> `live_response_received`

On the first such success for the current `runId`:

- emit `first_post_setup_action`
- set `setupHandoff.compact = true`
- set `setupHandoff.consumedAction`

Do not emit or collapse twice.

**Step 4: Re-run the targeted route test**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "collapses the setup handoff"
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx apps/packages/ui/src/components/PersonaGarden/ProfilePanel.tsx apps/packages/ui/src/components/PersonaGarden/ConnectionsPanel.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: collapse setup handoff after first success"
```

### Task 6: Add Setup Analytics Summary Endpoint Coverage And One E2E Flow

**Files:**
- Modify: `tldw_Server_API/tests/Persona/test_persona_setup_analytics_api.py`
- Modify: `apps/extension/tests/e2e/persona-assistant-setup.spec.ts`

**Step 1: Add summary-focused backend assertions**

Extend the backend analytics tests to assert:

- `completion_rate`
- `most_common_dropoff_step`
- `handoff_click_rate`
- `first_post_setup_action_rate`

for a small seeded mix of setup runs.

**Step 2: Add one Playwright scenario**

Add a flow to `persona-assistant-setup.spec.ts` that:

- finishes setup
- sees the handoff card on the target tab
- takes the recommended next action
- verifies the compact `Setup complete` banner appears afterward

**Step 3: Run the new targeted tests**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_setup_analytics_api.py -q
cd apps/extension && bunx playwright test tests/e2e/persona-assistant-setup.spec.ts --reporter=line
```

Expected: PASS.

**Step 4: Commit**

```bash
git add tldw_Server_API/tests/Persona/test_persona_setup_analytics_api.py apps/extension/tests/e2e/persona-assistant-setup.spec.ts
git commit -m "test: cover persona setup handoff analytics flow"
```

### Task 7: Run Regressions, Security Checks, And Close Out

**Files:**
- Update: `Docs/Plans/2026-03-14-persona-setup-handoff-tightening-and-analytics-implementation-plan.md`

**Step 1: Mark this plan complete**

Update task statuses in this plan file after implementation.

**Step 2: Run focused backend tests**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_profiles_api.py tldw_Server_API/tests/Persona/test_persona_setup_analytics_api.py -q
```

Expected: PASS.

**Step 3: Run focused frontend tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/services/tldw/__tests__/persona-setup-analytics.test.ts src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 4: Run broader setup sweep**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx src/components/PersonaGarden/__tests__/SetupStarterCommandsStep.test.tsx src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 5: Run security and hygiene checks**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/schemas/persona.py tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py apps/packages/ui/src/components/PersonaGarden apps/packages/ui/src/routes apps/packages/ui/src/services/tldw -f json -o /tmp/bandit_persona_setup_handoff_analytics.json
git diff --check
```

Expected:

- Bandit reports no new findings in touched code
- `git diff --check` returns no output

**Step 6: Commit plan closeout if needed**

```bash
git add Docs/Plans/2026-03-14-persona-setup-handoff-tightening-and-analytics-implementation-plan.md
git commit -m "docs: mark setup handoff analytics plan complete"
```

Expected: clean regressions, clean security checks, and a clean worktree.
