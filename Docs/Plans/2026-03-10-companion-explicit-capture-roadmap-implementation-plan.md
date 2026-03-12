# Companion Explicit-Capture Foundation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first usable `Companion` slice for `tldw_server` by adding a normalized explicit-capture activity ledger, per-user derived knowledge/goals, Jobs-backed reflections, and a dedicated API/UI surface without turning persona into the only storage layer.

**Architecture:** Keep storage inside the personalization domain and expose a new `companion` read/write surface for user-facing workflows. Reuse existing reading, watchlists, reminders, notifications, and persona systems as event sources; use Jobs for durable user-visible reflection generation; keep persona state per-persona and companion knowledge per-user.

**Tech Stack:** FastAPI, Pydantic, SQLite/WAL (`PersonalizationDB`), existing Jobs + APScheduler services, React/Next.js shared UI, Zustand, Vitest, Playwright, pytest.

---

## References To Read Before Starting

- `Docs/Plans/2026-03-10-companion-explicit-capture-roadmap-design.md`
- `tldw_Server_API/app/core/DB_Management/Personalization_DB.py`
- `tldw_Server_API/app/api/v1/endpoints/personalization.py`
- `tldw_Server_API/app/api/v1/endpoints/persona.py`
- `tldw_Server_API/app/api/v1/endpoints/reading.py`
- `tldw_Server_API/app/api/v1/endpoints/watchlists.py`
- `tldw_Server_API/app/api/v1/endpoints/notifications.py`
- `tldw_Server_API/app/services/personalization_consolidation.py`
- `tldw_Server_API/app/core/Collections/reading_digest_jobs.py`
- `tldw_Server_API/app/services/reading_digest_scheduler.py`
- `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- `apps/tldw-frontend/pages/reading.tsx`
- `apps/tldw-frontend/pages/notifications.tsx`

### Task 1: Add Companion Tables And DB Methods

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Personalization_DB.py`
- Test: `tldw_Server_API/tests/Personalization/test_companion_activity_db.py`

**Step 1: Write the failing test**

```python
def test_companion_activity_round_trip(db: PersonalizationDB) -> None:
    event_id = db.insert_companion_activity_event(
        user_id="1",
        event_type="reading.saved",
        source_type="reading_item",
        source_id="42",
        surface="reading",
        dedupe_key="reading.saved:42",
        tags=["research", "paper"],
        provenance={"source_ids": ["42"]},
        metadata={"title": "Example"}
    )

    rows, total = db.list_companion_activity_events("1", limit=10, offset=0)

    assert event_id
    assert total == 1
    assert rows[0]["event_type"] == "reading.saved"
    assert rows[0]["source_type"] == "reading_item"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Personalization/test_companion_activity_db.py
```

Expected: FAIL with missing `insert_companion_activity_event` / `list_companion_activity_events` methods or missing schema objects.

**Step 3: Write minimal implementation**

Add new tables and helpers in `PersonalizationDB`:

```python
CREATE TABLE IF NOT EXISTS companion_activity_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    surface TEXT NOT NULL,
    dedupe_key TEXT NOT NULL,
    tags TEXT,
    provenance_json TEXT NOT NULL,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, dedupe_key)
);

CREATE TABLE IF NOT EXISTS companion_knowledge_cards (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    card_type TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS companion_goals (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    goal_type TEXT NOT NULL,
    config_json TEXT NOT NULL,
    progress_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

Add matching DB methods:

```python
def insert_companion_activity_event(...): ...
def list_companion_activity_events(...): ...
def upsert_companion_knowledge_card(...): ...
def list_companion_knowledge_cards(...): ...
def create_companion_goal(...): ...
def list_companion_goals(...): ...
```

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Personalization/test_companion_activity_db.py
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/Personalization_DB.py tldw_Server_API/tests/Personalization/test_companion_activity_db.py
git commit -m "feat: add companion activity tables and db methods"
```

### Task 2: Add Activity Normalization Helpers And Reading/Persona Adapters

**Files:**
- Create: `tldw_Server_API/app/core/Personalization/__init__.py`
- Create: `tldw_Server_API/app/core/Personalization/companion_activity.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/reading.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/persona.py`
- Test: `tldw_Server_API/tests/Personalization/test_companion_activity_adapters.py`
- Test: `tldw_Server_API/tests/Collections/test_companion_reading_activity_bridge.py`
- Test: `tldw_Server_API/tests/Persona/test_companion_persona_activity_bridge.py`

**Step 1: Write the failing tests**

```python
def test_record_reading_saved_event_builds_expected_envelope() -> None:
    payload = build_companion_activity_event(
        event_type="reading.saved",
        source_type="reading_item",
        source_id="42",
        surface="reading",
        tags=["research"],
        provenance={"source_ids": ["42"]}
    )

    assert payload["event_type"] == "reading.saved"
    assert payload["dedupe_key"] == "reading.saved:reading_item:42"


def test_persona_tool_result_is_recorded_with_provenance(...) -> None:
    ...
    assert row["event_type"] == "persona.tool_result"
    assert row["provenance"]["session_id"] == "session-123"
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/Personalization/test_companion_activity_adapters.py \
  tldw_Server_API/tests/Collections/test_companion_reading_activity_bridge.py \
  tldw_Server_API/tests/Persona/test_companion_persona_activity_bridge.py
```

Expected: FAIL because normalization helpers and bridge calls do not exist yet.

**Step 3: Write minimal implementation**

Create `companion_activity.py` with a narrow adapter API:

```python
def build_companion_activity_event(...)-> dict[str, Any]:
    return {
        "event_type": event_type,
        "source_type": source_type,
        "source_id": str(source_id),
        "surface": surface,
        "dedupe_key": dedupe_key or f"{event_type}:{source_type}:{source_id}",
        "tags": sorted(set(tags or [])),
        "provenance": provenance or {},
        "metadata": metadata or {},
    }


def record_companion_activity(db: PersonalizationDB, user_id: str, **payload: Any) -> str:
    return db.insert_companion_activity_event(user_id=user_id, **payload)
```

Call it from explicit user actions only:

- reading save/update/highlight/note endpoints in `reading.py`
- persona session start, message persistence summary, and tool outcome persistence in `persona.py`

Do not mutate persona state docs from these events.

**Step 4: Run tests to verify they pass**

Run the same pytest command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/Personalization/__init__.py \
  tldw_Server_API/app/core/Personalization/companion_activity.py \
  tldw_Server_API/app/api/v1/endpoints/reading.py \
  tldw_Server_API/app/api/v1/endpoints/persona.py \
  tldw_Server_API/tests/Personalization/test_companion_activity_adapters.py \
  tldw_Server_API/tests/Collections/test_companion_reading_activity_bridge.py \
  tldw_Server_API/tests/Persona/test_companion_persona_activity_bridge.py
git commit -m "feat: record companion activity from reading and persona flows"
```

### Task 3: Add Watchlists/Reminders Adapters And Derived Knowledge Consolidation

**Files:**
- Create: `tldw_Server_API/app/core/Personalization/companion_derivations.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/watchlists.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/reminders.py`
- Modify: `tldw_Server_API/app/services/personalization_consolidation.py`
- Test: `tldw_Server_API/tests/Personalization/test_companion_derivations.py`
- Test: `tldw_Server_API/tests/Watchlists/test_companion_watchlists_activity_bridge.py`
- Test: `tldw_Server_API/tests/Notifications/test_companion_reminders_activity_bridge.py`

**Step 1: Write the failing tests**

```python
def test_consolidation_builds_project_focus_card_from_recent_activity(db: PersonalizationDB) -> None:
    ...
    cards = derive_companion_knowledge_cards(db, user_id="1")
    assert any(card["card_type"] == "project_focus" for card in cards)


def test_reminder_completion_records_companion_event(...) -> None:
    ...
    assert rows[0]["event_type"] == "reminder.completed"
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/Personalization/test_companion_derivations.py \
  tldw_Server_API/tests/Watchlists/test_companion_watchlists_activity_bridge.py \
  tldw_Server_API/tests/Notifications/test_companion_reminders_activity_bridge.py
```

Expected: FAIL because no derivation helpers or watchlists/reminders bridges exist.

**Step 3: Write minimal implementation**

Create derivation helpers:

```python
def derive_companion_knowledge_cards(db: PersonalizationDB, user_id: str) -> list[dict[str, Any]]:
    events, _ = db.list_companion_activity_events(user_id, limit=500, offset=0)
    return [
        {
            "card_type": "project_focus",
            "title": "Current focus",
            "summary": summary_text,
            "evidence": evidence_rows,
            "score": score,
        }
    ]
```

Wire consolidation:

```python
cards = derive_companion_knowledge_cards(db, user_id)
for card in cards:
    db.upsert_companion_knowledge_card(user_id=user_id, **card)
```

Add explicit event recording in:

- watchlist item/output creation flows in `watchlists.py`
- reminder completion or due-notification creation flow in `reminders.py`

**Step 4: Run tests to verify they pass**

Run the same pytest command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/Personalization/companion_derivations.py \
  tldw_Server_API/app/api/v1/endpoints/watchlists.py \
  tldw_Server_API/app/api/v1/endpoints/reminders.py \
  tldw_Server_API/app/services/personalization_consolidation.py \
  tldw_Server_API/tests/Personalization/test_companion_derivations.py \
  tldw_Server_API/tests/Watchlists/test_companion_watchlists_activity_bridge.py \
  tldw_Server_API/tests/Notifications/test_companion_reminders_activity_bridge.py
git commit -m "feat: derive companion knowledge and record watchlist reminder activity"
```

### Task 4: Add Companion API Schemas And Endpoints

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/companion.py`
- Create: `tldw_Server_API/app/api/v1/endpoints/companion.py`
- Modify: `tldw_Server_API/app/main.py`
- Test: `tldw_Server_API/tests/Personalization/test_companion_api.py`

**Step 1: Write the failing test**

```python
def test_companion_activity_endpoint_returns_provenance(client, auth_headers) -> None:
    response = client.get("/api/v1/companion/activity?limit=10", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "provenance" in payload["items"][0]
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Personalization/test_companion_api.py
```

Expected: FAIL with missing route/module import.

**Step 3: Write minimal implementation**

Create schemas for:

```python
class CompanionActivityItem(BaseModel):
    id: str
    event_type: str
    source_type: str
    source_id: str
    surface: str
    tags: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

class CompanionKnowledgeCard(BaseModel): ...
class CompanionGoal(BaseModel): ...
class CompanionReflectionItem(BaseModel): ...
```

Add initial endpoints:

- `GET /api/v1/companion/activity`
- `GET /api/v1/companion/knowledge`
- `GET /api/v1/companion/goals`
- `POST /api/v1/companion/goals`
- `PATCH /api/v1/companion/goals/{goal_id}`

Keep storage inside `PersonalizationDB`; do not create a separate database service.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Personalization/test_companion_api.py
```

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/api/v1/schemas/companion.py \
  tldw_Server_API/app/api/v1/endpoints/companion.py \
  tldw_Server_API/app/main.py \
  tldw_Server_API/tests/Personalization/test_companion_api.py
git commit -m "feat: add companion api surface"
```

### Task 5: Add Jobs-Backed Reflection Generation And Notification Delivery

**Files:**
- Create: `tldw_Server_API/app/core/Personalization/companion_reflection_jobs.py`
- Create: `tldw_Server_API/app/core/Personalization/companion_reflection_jobs_worker.py`
- Create: `tldw_Server_API/app/services/companion_reflection_scheduler.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/notifications.py`
- Modify: `tldw_Server_API/app/main.py`
- Test: `tldw_Server_API/tests/Personalization/test_companion_reflection_jobs.py`
- Test: `tldw_Server_API/tests/Notifications/test_companion_reflection_notifications.py`

**Step 1: Write the failing tests**

```python
def test_companion_reflection_job_creates_notification_and_persists_reflection(...) -> None:
    result = run_companion_reflection_job(payload)
    assert result["status"] == "completed"
    assert result["reflection_id"]
    assert notification.kind == "companion_reflection"


def test_companion_reflection_job_skips_when_quiet_hours_active(...) -> None:
    ...
    assert result["status"] == "skipped"
    assert result["reason"] == "quiet_hours"
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/Personalization/test_companion_reflection_jobs.py \
  tldw_Server_API/tests/Notifications/test_companion_reflection_notifications.py
```

Expected: FAIL because the job module and scheduler do not exist.

**Step 3: Write minimal implementation**

Follow the existing Jobs pattern used by reading digests:

```python
def run_companion_reflection_job(user_id: str, cadence: str) -> dict[str, Any]:
    cards = db.list_companion_knowledge_cards(user_id)
    activity, _ = db.list_companion_activity_events(user_id, limit=100, offset=0)
    if quiet_hours_active(profile):
        return {"status": "skipped", "reason": "quiet_hours"}
    reflection = build_reflection(cards=cards, activity=activity)
    notification_service.create_notification(...)
    return {"status": "completed", "reflection_id": reflection_id}
```

Scheduler rule:

- APScheduler enqueues reflection Jobs only
- execution happens in the companion Jobs worker

Do not execute user-visible reflection work directly inside the scheduler.

**Step 4: Run tests to verify they pass**

Run the same pytest command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/Personalization/companion_reflection_jobs.py \
  tldw_Server_API/app/core/Personalization/companion_reflection_jobs_worker.py \
  tldw_Server_API/app/services/companion_reflection_scheduler.py \
  tldw_Server_API/app/api/v1/endpoints/notifications.py \
  tldw_Server_API/app/main.py \
  tldw_Server_API/tests/Personalization/test_companion_reflection_jobs.py \
  tldw_Server_API/tests/Notifications/test_companion_reflection_notifications.py
git commit -m "feat: add jobs-backed companion reflections"
```

### Task 6: Build The Companion Workspace In The WebUI

**Files:**
- Create: `apps/packages/ui/src/services/companion.ts`
- Create: `apps/packages/ui/src/components/Option/Companion/CompanionPage.tsx`
- Create: `apps/packages/ui/src/routes/option-companion.tsx`
- Modify: `apps/packages/ui/src/routes/route-registry.tsx`
- Create: `apps/tldw-frontend/pages/companion.tsx`
- Test: `apps/packages/ui/src/services/__tests__/companion.test.ts`
- Test: `apps/packages/ui/src/routes/__tests__/option-companion.test.tsx`

**Step 1: Write the failing tests**

```tsx
it("renders activity, knowledge, reflections, and goals tabs", async () => {
  render(<OptionCompanion />)
  expect(screen.getByRole("tab", { name: /activity/i })).toBeInTheDocument()
  expect(screen.getByRole("tab", { name: /knowledge/i })).toBeInTheDocument()
  expect(screen.getByRole("tab", { name: /reflections/i })).toBeInTheDocument()
  expect(screen.getByRole("tab", { name: /goals/i })).toBeInTheDocument()
})
```

**Step 2: Run tests to verify they fail**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/services/__tests__/companion.test.ts \
  apps/packages/ui/src/routes/__tests__/option-companion.test.tsx
```

Expected: FAIL because the service, route, and page do not exist.

**Step 3: Write minimal implementation**

Add a small typed client:

```ts
export async function listCompanionActivity() {
  return tldwClient.fetchWithAuth("/api/v1/companion/activity", { method: "GET" })
}
```

Build a simple page with:

- Activity tab
- Knowledge tab
- Reflections tab
- Goals tab
- provenance chips/expanders on reflected and derived items

Do not merge this into `sidepanel-persona.tsx`; keep `Companion` separate from `Persona`.

**Step 4: Run tests to verify they pass**

Run the same Vitest command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/services/companion.ts \
  apps/packages/ui/src/components/Option/Companion/CompanionPage.tsx \
  apps/packages/ui/src/routes/option-companion.tsx \
  apps/packages/ui/src/routes/route-registry.tsx \
  apps/tldw-frontend/pages/companion.tsx \
  apps/packages/ui/src/services/__tests__/companion.test.ts \
  apps/packages/ui/src/routes/__tests__/option-companion.test.tsx
git commit -m "feat: add companion workspace"
```

### Task 7: Add Extension Quick-Capture Hooks And E2E Coverage

**Files:**
- Modify: `apps/tldw-frontend/extension/routes/sidepanel-chat.tsx`
- Create: `apps/tldw-frontend/extension/routes/sidepanel-companion.tsx`
- Modify: `apps/tldw-frontend/extension/routes/route-registry.tsx`
- Test: `apps/tldw-frontend/__tests__/extension/route-registry.companion.test.ts`
- Test: `apps/tldw-frontend/e2e/workflows/companion.spec.ts`

**Step 1: Write the failing tests**

```tsx
it("registers the companion route in the extension sidepanel", () => {
  expect(sidepanelRoutes.some((route) => route.path === "/companion")).toBe(true)
})
```

```ts
test("saves selected page text into companion activity", async ({ page }) => {
  await page.goto("/companion")
  await expect(page.getByTestId("companion-activity-list")).toBeVisible()
})
```

**Step 2: Run tests to verify they fail**

Run:

```bash
bunx vitest run apps/tldw-frontend/__tests__/extension/route-registry.companion.test.ts
```

Then:

```bash
TLDW_E2E_SERVER_URL=127.0.0.1:8000 TLDW_E2E_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY bunx playwright test apps/tldw-frontend/e2e/workflows/companion.spec.ts --reporter=line
```

Expected: FAIL because the route and flow do not exist yet.

**Step 3: Write minimal implementation**

Add a dedicated sidepanel route and a narrow quick-capture action:

```ts
const selected = (bgMsg.text || bgMsg.payload?.selectionText || "").trim()
await companionClient.recordExplicitCapture({
  event_type: "extension.selection_saved",
  source_type: "browser_selection",
  source_id: crypto.randomUUID(),
  surface: "extension",
  metadata: { selection: selected, url }
})
```

Keep the action explicit:

- save selection to companion
- summarize page into companion
- ask companion about current page

Do not add passive page monitoring.

**Step 4: Run tests to verify they pass**

Run the same Vitest and Playwright commands from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  apps/tldw-frontend/extension/routes/sidepanel-chat.tsx \
  apps/tldw-frontend/extension/routes/sidepanel-companion.tsx \
  apps/tldw-frontend/extension/routes/route-registry.tsx \
  apps/tldw-frontend/__tests__/extension/route-registry.companion.test.ts \
  apps/tldw-frontend/e2e/workflows/companion.spec.ts
git commit -m "feat: add explicit companion capture in extension"
```

## Final Verification

Run after all tasks:

```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/Personalization/test_companion_activity_db.py \
  tldw_Server_API/tests/Personalization/test_companion_activity_adapters.py \
  tldw_Server_API/tests/Personalization/test_companion_derivations.py \
  tldw_Server_API/tests/Personalization/test_companion_api.py \
  tldw_Server_API/tests/Personalization/test_companion_reflection_jobs.py \
  tldw_Server_API/tests/Collections/test_companion_reading_activity_bridge.py \
  tldw_Server_API/tests/Watchlists/test_companion_watchlists_activity_bridge.py \
  tldw_Server_API/tests/Notifications/test_companion_reminders_activity_bridge.py \
  tldw_Server_API/tests/Notifications/test_companion_reflection_notifications.py \
  tldw_Server_API/tests/Persona/test_companion_persona_activity_bridge.py
```

```bash
bunx vitest run \
  apps/packages/ui/src/services/__tests__/companion.test.ts \
  apps/packages/ui/src/routes/__tests__/option-companion.test.tsx \
  apps/tldw-frontend/__tests__/extension/route-registry.companion.test.ts
```

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/core/Personalization \
  tldw_Server_API/app/api/v1/endpoints/companion.py \
  tldw_Server_API/app/api/v1/schemas/companion.py \
  tldw_Server_API/app/core/DB_Management/Personalization_DB.py \
  -f json -o /tmp/bandit_companion_foundation.json
```

```bash
TLDW_E2E_SERVER_URL=127.0.0.1:8000 TLDW_E2E_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY bunx playwright test apps/tldw-frontend/e2e/workflows/companion.spec.ts --reporter=line
```

Expected:

- pytest PASS
- vitest PASS
- bandit reports no new findings in touched scope
- playwright PASS
