# Companion Quality And Trust Controls Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** Completed on 2026-03-10

**Goal:** Improve companion relevance, derivation quality, provenance inspection, and scoped trust controls without expanding beyond the explicit local-first model.

**Architecture:** Extend the personalization-domain companion model with per-user reflection settings, goal provenance, bounded query-aware ranking, dedicated provenance detail endpoints, and Jobs-backed rebuild flows. Keep the workspace summary lightweight and move destructive/rebuild work into scoped backend services with durable status.

**Tech Stack:** FastAPI, Pydantic, SQLite/WAL (`PersonalizationDB`), existing Jobs/APScheduler services, React/Next.js shared UI, Zustand, Vitest, Playwright, pytest.

## Execution Outcome

All seven tasks in this plan are complete.

Completed areas:

- companion profile reflection flags and goal provenance fields
- scoped purge and Jobs-backed rebuild flows
- bounded companion relevance ranking for persona/companion context
- expanded deterministic derivations and richer reflection inputs
- dedicated provenance detail endpoints
- workspace settings, provenance drawers, and scoped lifecycle controls
- milestone-level verification and doc finalization

Verification captured during execution:

- backend milestone suite: `38 passed`
- frontend milestone suite: `56 passed`
- extension companion Playwright suite: `3 passed`
- Bandit on `companion.py` plus `app/core/Personalization`: `0 findings`
- `git diff --check`: clean

Execution notes:

- the extension Playwright suite required running Chromium outside the filesystem sandbox because the sandboxed browser could not access its Crashpad path under `~/Library/Application Support`
- rebuild remains Jobs-backed and scoped to derived state
- full companion activity-ledger deletion is still intentionally out of scope for this milestone

---

### Task 1: Add Companion Profile And Goal Provenance Fields

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Personalization_DB.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/personalization.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/personalization.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/companion.py`
- Test: `tldw_Server_API/tests/Personalization/test_companion_profile_settings.py`
- Test: `tldw_Server_API/tests/Personalization/test_companion_goal_provenance.py`

**Step 1: Write the failing tests**

```python
def test_personalization_profile_exposes_companion_reflection_flags(client, personalization_db):
    personalization_db.update_profile(
        "1",
        enabled=1,
        companion_reflections_enabled=1,
        companion_daily_reflections_enabled=0,
        companion_weekly_reflections_enabled=1,
    )

    response = client.get("/api/v1/personalization/profile")

    assert response.status_code == 200
    payload = response.json()
    assert payload["companion_reflections_enabled"] is True
    assert payload["companion_daily_reflections_enabled"] is False
    assert payload["companion_weekly_reflections_enabled"] is True


def test_companion_goal_round_trip_preserves_origin_and_progress_mode(personalization_db):
    goal_id = personalization_db.create_companion_goal(
        user_id="1",
        title="Follow up on backlog",
        description=None,
        goal_type="manual",
        config={},
        progress={},
        status="active",
        origin_kind="manual",
        progress_mode="computed",
        derivation_key=None,
        evidence=[],
    )

    goal = personalization_db.update_companion_goal(goal_id, "1")

    assert goal["origin_kind"] == "manual"
    assert goal["progress_mode"] == "computed"
    assert goal["evidence"] == []
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/Personalization/test_companion_profile_settings.py \
  tldw_Server_API/tests/Personalization/test_companion_goal_provenance.py
```

Expected: FAIL because the profile flags and goal provenance fields do not exist yet.

**Step 3: Write minimal implementation**

- Add new profile columns in `PersonalizationDB`:
  - `companion_reflections_enabled INTEGER NOT NULL DEFAULT 1`
  - `companion_daily_reflections_enabled INTEGER NOT NULL DEFAULT 1`
  - `companion_weekly_reflections_enabled INTEGER NOT NULL DEFAULT 1`
- Extend companion goal storage with:
  - `origin_kind TEXT NOT NULL DEFAULT 'manual'`
  - `progress_mode TEXT NOT NULL DEFAULT 'manual'`
  - `derivation_key TEXT`
  - `evidence_json TEXT NOT NULL DEFAULT '[]'`
- Update the Pydantic response/request schemas to expose these fields.
- Update profile serialization and preference update paths in `personalization.py`.

**Step 4: Run tests to verify they pass**

Run the same pytest command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/DB_Management/Personalization_DB.py \
  tldw_Server_API/app/api/v1/schemas/personalization.py \
  tldw_Server_API/app/api/v1/endpoints/personalization.py \
  tldw_Server_API/app/api/v1/schemas/companion.py \
  tldw_Server_API/tests/Personalization/test_companion_profile_settings.py \
  tldw_Server_API/tests/Personalization/test_companion_goal_provenance.py
git commit -m "feat: add companion settings and goal provenance fields"
```

### Task 2: Add Scoped Companion Purge And Rebuild Services

**Files:**
- Create: `tldw_Server_API/app/core/Personalization/companion_lifecycle.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/companion.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/companion.py`
- Modify: `tldw_Server_API/app/core/Personalization/companion_reflection_jobs.py`
- Test: `tldw_Server_API/tests/Personalization/test_companion_lifecycle.py`
- Test: `tldw_Server_API/tests/Notifications/test_companion_reflection_notifications.py`

**Step 1: Write the failing tests**

```python
def test_purge_reflections_removes_activity_and_linked_notifications(companion_env):
    reflection_id = seed_reflection(companion_env)

    result = purge_companion_scope(
        user_id="1",
        scope="reflections",
        personalization_db=companion_env.personalization_db,
        collections_db=companion_env.collections_db,
    )

    assert result["deleted_counts"]["reflections"] == 1
    assert result["deleted_counts"]["notifications"] == 1
    rows, _ = companion_env.personalization_db.list_companion_activity_events("1", limit=50, offset=0)
    assert all(row["id"] != reflection_id for row in rows)


def test_rebuild_job_recomputes_cards_without_touching_manual_goals(companion_env):
    manual_goal_id = seed_manual_goal(companion_env)

    result = rebuild_companion_scope(
        user_id="1",
        scope="knowledge",
        personalization_db=companion_env.personalization_db,
    )

    assert result["status"] == "completed"
    goals = companion_env.personalization_db.list_companion_goals("1")
    assert any(goal["id"] == manual_goal_id and goal["origin_kind"] == "manual" for goal in goals)
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/Personalization/test_companion_lifecycle.py \
  tldw_Server_API/tests/Notifications/test_companion_reflection_notifications.py
```

Expected: FAIL because scoped lifecycle services and endpoints do not exist yet.

**Step 3: Write minimal implementation**

- Create `companion_lifecycle.py` with scoped operations:
  - `purge_companion_scope(...)`
  - `rebuild_companion_scope(...)`
- Supported scopes:
  - `knowledge`
  - `reflections`
  - `derived_goals`
  - `goal_progress`
- Reflection purge must remove both:
  - `companion_reflection_generated` activity rows
  - linked `companion_reflection` notifications
- Rebuild must preserve:
  - manual goals
  - raw explicit companion activity
- Add API endpoints in `companion.py` for scoped purge and rebuild.
- Make rebuild run through the Jobs system when work is more than a single bounded operation.

**Step 4: Run tests to verify they pass**

Run the same pytest command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/Personalization/companion_lifecycle.py \
  tldw_Server_API/app/api/v1/endpoints/companion.py \
  tldw_Server_API/app/api/v1/schemas/companion.py \
  tldw_Server_API/app/core/Personalization/companion_reflection_jobs.py \
  tldw_Server_API/tests/Personalization/test_companion_lifecycle.py \
  tldw_Server_API/tests/Notifications/test_companion_reflection_notifications.py
git commit -m "feat: add scoped companion purge and rebuild flows"
```

### Task 3: Add Bounded Query-Aware Companion Ranking

**Files:**
- Create: `tldw_Server_API/app/core/Personalization/companion_relevance.py`
- Modify: `tldw_Server_API/app/core/Personalization/companion_context.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/persona.py`
- Test: `tldw_Server_API/tests/Personalization/test_companion_relevance.py`
- Test: `tldw_Server_API/tests/Persona/test_companion_context_ranking.py`

**Step 1: Write the failing tests**

```python
def test_rank_companion_candidates_prefers_query_matching_goal_and_card():
    ranked = rank_companion_candidates(
        query="help me resume the backlog review",
        cards=[{"id": "card-1", "title": "Backlog review", "summary": "Weekly backlog pass"}],
        goals=[{"id": "goal-1", "title": "Resume backlog review", "description": None}],
        activity_rows=[{"id": "evt-1", "metadata": {"title": "Watched a video"}}],
    )

    assert ranked["goal_ids"][0] == "goal-1"
    assert ranked["card_ids"][0] == "card-1"


def test_load_companion_context_falls_back_when_scores_are_weak(companion_context_env):
    payload = load_companion_context(user_id="1", query="totally unrelated")

    assert payload["mode"] in {"ranked", "recent_fallback"}
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/Personalization/test_companion_relevance.py \
  tldw_Server_API/tests/Persona/test_companion_context_ranking.py
```

Expected: FAIL because no bounded ranking layer exists yet.

**Step 3: Write minimal implementation**

- Create `companion_relevance.py` with deterministic lexical scoring.
- Only score bounded candidate pools:
  - active cards
  - active or paused goals
  - recent explicit activity window
- Update `load_companion_context(...)` to accept the live query and return:
  - selected lines
  - selected IDs
  - whether the result was ranked or fallback
- Update persona conversation planning to pass the live user message into context loading.

**Step 4: Run tests to verify they pass**

Run the same pytest command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/Personalization/companion_relevance.py \
  tldw_Server_API/app/core/Personalization/companion_context.py \
  tldw_Server_API/app/api/v1/endpoints/persona.py \
  tldw_Server_API/tests/Personalization/test_companion_relevance.py \
  tldw_Server_API/tests/Persona/test_companion_context_ranking.py
git commit -m "feat: add bounded query-aware companion ranking"
```

### Task 4: Expand Deterministic Knowledge Derivation And Reflection Inputs

**Files:**
- Modify: `tldw_Server_API/app/core/Personalization/companion_derivations.py`
- Modify: `tldw_Server_API/app/services/personalization_consolidation.py`
- Modify: `tldw_Server_API/app/core/Personalization/companion_reflection_jobs.py`
- Test: `tldw_Server_API/tests/Personalization/test_companion_derivations.py`
- Test: `tldw_Server_API/tests/Personalization/test_companion_reflection_jobs.py`

**Step 1: Write the failing tests**

```python
def test_derive_companion_knowledge_cards_emits_multiple_card_families(companion_derivations_env):
    seed_focus_and_stale_activity(companion_derivations_env)

    cards = derive_companion_knowledge_cards(companion_derivations_env.db, user_id="1")
    card_types = {card["card_type"] for card in cards}

    assert "project_focus" in card_types
    assert "stale_followup" in card_types


def test_reflection_payload_includes_goal_and_stale_work_signals(companion_reflection_env):
    result = run_companion_reflection_job(user_id="1", cadence="daily")

    assert result["status"] == "completed"
    reflection = get_latest_reflection(companion_reflection_env)
    assert any(item["kind"] == "knowledge_card" for item in reflection["metadata"]["evidence"])
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/Personalization/test_companion_derivations.py \
  tldw_Server_API/tests/Personalization/test_companion_reflection_jobs.py
```

Expected: FAIL because derivations and reflections are still too narrow.

**Step 3: Write minimal implementation**

- Extend derivation to emit bounded, deterministic card families:
  - `project_focus`
  - `topic_focus`
  - `stale_followup`
  - `source_focus`
  - `active_goal_signal`
- Keep each card evidence-backed and bounded.
- Update reflection synthesis to incorporate:
  - strongest cards
  - stale/open signals
  - active goal state
  - recent explicit change events
- Do not introduce opaque model-based inference in this milestone.

**Step 4: Run tests to verify they pass**

Run the same pytest command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/Personalization/companion_derivations.py \
  tldw_Server_API/app/services/personalization_consolidation.py \
  tldw_Server_API/app/core/Personalization/companion_reflection_jobs.py \
  tldw_Server_API/tests/Personalization/test_companion_derivations.py \
  tldw_Server_API/tests/Personalization/test_companion_reflection_jobs.py
git commit -m "feat: expand companion derivations and reflection inputs"
```

### Task 5: Add Provenance Detail Endpoints

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/companion.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/companion.py`
- Test: `tldw_Server_API/tests/Personalization/test_companion_api.py`

**Step 1: Write the failing tests**

```python
def test_companion_reflection_detail_returns_provenance_and_evidence(client, companion_api_env):
    reflection_id = seed_reflection(companion_api_env)

    response = client.get(f"/api/v1/companion/reflections/{reflection_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == reflection_id
    assert payload["provenance"]["source_event_ids"]
    assert payload["evidence"]


def test_companion_knowledge_detail_returns_evidence_rows(client, companion_api_env):
    card_id = seed_card(companion_api_env)

    response = client.get(f"/api/v1/companion/knowledge/{card_id}")

    assert response.status_code == 200
    assert response.json()["id"] == card_id
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Personalization/test_companion_api.py
```

Expected: FAIL because item detail endpoints do not exist yet.

**Step 3: Write minimal implementation**

- Add detail response schemas for:
  - activity detail
  - knowledge detail
  - reflection detail
- Implement dedicated read endpoints instead of overloading the workspace snapshot.
- Enforce the same consent and rate-limit model as the existing companion endpoints.

**Step 4: Run tests to verify they pass**

Run the same pytest command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/api/v1/schemas/companion.py \
  tldw_Server_API/app/api/v1/endpoints/companion.py \
  tldw_Server_API/tests/Personalization/test_companion_api.py
git commit -m "feat: add companion provenance detail endpoints"
```

### Task 6: Add Workspace Settings, Provenance Drawers, And Purge/Rebuild Controls

**Files:**
- Modify: `apps/packages/ui/src/services/companion.ts`
- Modify: `apps/packages/ui/src/components/Option/Companion/CompanionPage.tsx`
- Test: `apps/packages/ui/src/services/__tests__/companion.test.ts`
- Test: `apps/packages/ui/src/routes/__tests__/option-companion.test.tsx`
- Test: `apps/packages/ui/src/routes/__tests__/sidepanel-companion.test.tsx`
- Test: `apps/extension/tests/e2e/companion.spec.ts`

**Step 1: Write the failing tests**

```tsx
it("shows companion settings and persists reflection toggles", async () => {
  renderOptionCompanionPage()

  expect(await screen.findByRole("heading", { name: /settings/i })).toBeInTheDocument()
  await user.click(screen.getByLabelText(/daily reflections/i))

  expect(mockUpdatePreferences).toHaveBeenCalledWith(
    expect.objectContaining({ companion_daily_reflections_enabled: false })
  )
})


it("opens a provenance drawer for a reflection", async () => {
  renderOptionCompanionPage()

  await user.click(await screen.findByRole("button", { name: /view provenance/i }))

  expect(await screen.findByText(/source event ids/i)).toBeInTheDocument()
})
```

**Step 2: Run tests to verify they fail**

Run:

```bash
bunx vitest run --config vitest.config.ts \
  apps/packages/ui/src/services/__tests__/companion.test.ts \
  apps/packages/ui/src/routes/__tests__/option-companion.test.tsx \
  apps/packages/ui/src/routes/__tests__/sidepanel-companion.test.tsx
```

Expected: FAIL because the settings/provenance/purge UI does not exist yet.

**Step 3: Write minimal implementation**

- Extend `companion.ts` with:
  - settings update calls
  - provenance detail fetches
  - scoped purge actions
  - scoped rebuild actions and job status reads
- Update `CompanionPage.tsx` to add:
  - settings section
  - provenance drill-down affordances
  - destructive confirmation UI
  - rebuild progress/status rendering
- Keep the sidepanel variant honest about which actions are available there.

**Step 4: Run tests to verify they pass**

Run the same Vitest command from Step 2, then run:

```bash
TLDW_E2E_SERVER_URL=127.0.0.1:8000 \
TLDW_E2E_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY \
bunx playwright test apps/extension/tests/e2e/companion.spec.ts --reporter=line
```

Expected: PASS

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/services/companion.ts \
  apps/packages/ui/src/components/Option/Companion/CompanionPage.tsx \
  apps/packages/ui/src/services/__tests__/companion.test.ts \
  apps/packages/ui/src/routes/__tests__/option-companion.test.tsx \
  apps/packages/ui/src/routes/__tests__/sidepanel-companion.test.tsx \
  apps/extension/tests/e2e/companion.spec.ts
git commit -m "feat: add companion settings provenance and lifecycle controls"
```

### Task 7: Run Final Verification And Update Docs

**Files:**
- Modify: `Docs/Plans/2026-03-10-companion-quality-trust-controls-design.md`
- Modify: `Docs/Plans/2026-03-10-companion-quality-trust-controls-implementation-plan.md`

**Step 1: Run backend verification**

Run:

```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/Personalization/test_companion_profile_settings.py \
  tldw_Server_API/tests/Personalization/test_companion_goal_provenance.py \
  tldw_Server_API/tests/Personalization/test_companion_lifecycle.py \
  tldw_Server_API/tests/Personalization/test_companion_relevance.py \
  tldw_Server_API/tests/Personalization/test_companion_derivations.py \
  tldw_Server_API/tests/Personalization/test_companion_reflection_jobs.py \
  tldw_Server_API/tests/Personalization/test_companion_api.py \
  tldw_Server_API/tests/Persona/test_companion_context_ranking.py \
  tldw_Server_API/tests/Notifications/test_companion_reflection_notifications.py
```

Expected: PASS

**Step 2: Run frontend verification**

Run:

```bash
bunx vitest run --config vitest.config.ts \
  apps/packages/ui/src/services/__tests__/companion.test.ts \
  apps/packages/ui/src/routes/__tests__/option-companion.test.tsx \
  apps/packages/ui/src/routes/__tests__/sidepanel-companion.test.tsx \
  apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS

**Step 3: Run security and diff checks**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/companion.py \
  tldw_Server_API/app/core/Personalization \
  -f json -o /tmp/bandit_companion_quality.json

git diff --check
```

Expected: no new Bandit findings in touched code, and clean diff check output.

**Step 4: Update plan/doc status notes**

- Mark completed tasks and any deferred follow-ups.
- Record any intentional limitations discovered during execution.

**Step 5: Commit**

```bash
git add \
  Docs/Plans/2026-03-10-companion-quality-trust-controls-design.md \
  Docs/Plans/2026-03-10-companion-quality-trust-controls-implementation-plan.md
git commit -m "docs: finalize companion quality and trust controls plan"
```
