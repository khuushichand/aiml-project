# Admin UI Monitoring Authority Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the admin monitoring page's local-only alert rules and client-only alert mutations with authoritative backend-backed policy, alert overlay state, and alert history.

**Architecture:** Add AuthNZ-backed control-plane persistence for admin alert rules, alert overlay state, and alert events. Expose admin mutation routes under `/admin/monitoring/...`, merge persisted overlay state into the existing runtime monitoring alert read path, and update the admin UI to consume only backend-confirmed rules, actions, and history.

**Tech Stack:** FastAPI, Pydantic v2, AuthNZ SQLite/PostgreSQL migrations, Loguru, Next.js/React, Vitest, pytest, Bandit.

**Execution Status:** Completed on March 10, 2026. Tasks 1 through 6 were implemented and verified in `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-monitoring-authority`.

---

### Task 1: Verify alert identity and create the backend merge service

**Files:**
- Create: `tldw_Server_API/app/services/admin_monitoring_alerts_service.py`
- Test: `tldw_Server_API/tests/Admin/test_admin_monitoring_alerts_service.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/monitoring_schemas.py`

**Step 1: Write the failing service tests**

Cover:
- stable alert identity uses the existing alert id if it is suitable
- fallback identity generation is deterministic for the same raw alert input
- overlay merge applies acknowledged, dismissed, assigned, snoozed, and escalated state
- dismissed alerts are still returned in a truthful backend shape if that is required by the current UI filters

```python
def test_merge_alert_overlay_applies_assignment_and_snooze():
    raw_alert = {"id": 7, "source": "watchlist", "text_snippet": "CPU high", "created_at": "2026-03-10T10:00:00Z"}
    overlay = {"alert_identity": "alert:7", "assigned_to_user_id": 12, "snoozed_until": "2026-03-10T11:00:00Z"}
    merged = merge_runtime_alert_with_overlay(raw_alert, overlay)
    assert merged["alert_identity"] == "alert:7"
    assert merged["assigned_to_user_id"] == 12
    assert merged["snoozed_until"] == "2026-03-10T11:00:00Z"
```

**Step 2: Run the service test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_monitoring_alerts_service.py -q`

Expected: FAIL because the service does not exist yet.

**Step 3: Implement the minimal merge service**

Add a small service that:
- computes backend alert identity
- documents whether raw runtime alert ids are stable enough
- merges runtime alert rows with overlay state
- maps merged output into the extended monitoring schema

Also extend `AlertItem` in `tldw_Server_API/app/api/v1/schemas/monitoring_schemas.py` to carry:
- `alert_identity`
- `assigned_to_user_id`
- `snoozed_until`
- `dismissed_at`
- `acknowledged_at`
- `escalated_severity`

**Step 4: Re-run the service test**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_monitoring_alerts_service.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/admin_monitoring_alerts_service.py \
  tldw_Server_API/app/api/v1/schemas/monitoring_schemas.py \
  tldw_Server_API/tests/Admin/test_admin_monitoring_alerts_service.py
git commit -m "feat(admin-monitoring): add alert identity and merge service"
```

### Task 2: Add AuthNZ persistence for rules, overlay state, and alert events

**Files:**
- Create: `tldw_Server_API/app/core/AuthNZ/repos/admin_monitoring_repo.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Test: `tldw_Server_API/tests/Admin/test_admin_monitoring_repo.py`
- Test: `tldw_Server_API/tests/AuthNZ/integration/test_authnz_admin_monitoring_repo_postgres.py`

**Step 1: Write the failing repository tests**

Cover:
- create/list/delete alert rules
- create/update/get overlay state by `alert_identity`
- append/list alert events with newest-first ordering
- store canonical backend user ids for assignments
- PostgreSQL and SQLite parity for the rule and event tables

```python
def test_upsert_alert_state_persists_assignment(repo):
    repo.upsert_alert_state(alert_identity="alert:7", assigned_to_user_id=12, updated_by_user_id=3)
    state = repo.get_alert_state("alert:7")
    assert state["assigned_to_user_id"] == 12
```

**Step 2: Run the repository test to verify it fails**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_monitoring_repo.py -q`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ/integration/test_authnz_admin_monitoring_repo_postgres.py -q`

Expected: FAIL because the repo and schema do not exist yet.

**Step 3: Add AuthNZ migrations**

Add tables for:
- `admin_alert_rules`
- `admin_alert_state`
- `admin_alert_events`

Schema requirements:
- rules store metric/operator/threshold/duration/severity/enabled plus created/updated metadata
- state stores `alert_identity` and overlay fields
- events are append-only and indexed by `alert_identity` and `created_at`

**Step 4: Add the minimal repo**

Implement:
- `ensure_schema()`
- `list_rules()`
- `create_rule(...)`
- `delete_rule(...)`
- `get_rule(...)`
- `list_alert_states(alert_identities: list[str])`
- `upsert_alert_state(...)`
- `append_alert_event(...)`
- `list_alert_events(...)`

**Step 5: Re-run the repository tests**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_monitoring_repo.py -q`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ/integration/test_authnz_admin_monitoring_repo_postgres.py -q`

Expected: PASS

**Step 6: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/repos/admin_monitoring_repo.py \
  tldw_Server_API/app/core/AuthNZ/migrations.py \
  tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py \
  tldw_Server_API/tests/Admin/test_admin_monitoring_repo.py \
  tldw_Server_API/tests/AuthNZ/integration/test_authnz_admin_monitoring_repo_postgres.py
git commit -m "feat(admin-monitoring): add control-plane persistence"
```

### Task 3: Add admin monitoring schemas and control-plane mutation routes

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/admin/admin_monitoring.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/admin/__init__.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/admin_schemas.py`
- Test: `tldw_Server_API/tests/Admin/test_admin_monitoring_api.py`
- Modify: `tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py`

**Step 1: Write the failing API tests**

Cover:
- `GET /admin/monitoring/alert-rules`
- `POST /admin/monitoring/alert-rules`
- `DELETE /admin/monitoring/alert-rules/{rule_id}`
- `POST /admin/monitoring/alerts/{alert_identity}/assign`
- `POST /admin/monitoring/alerts/{alert_identity}/snooze`
- `POST /admin/monitoring/alerts/{alert_identity}/escalate`
- `GET /admin/monitoring/alerts/history`

```python
async def test_assign_alert_updates_overlay_and_returns_event(client):
    response = client.post("/api/v1/admin/monitoring/alerts/alert:7/assign", json={"assigned_to_user_id": 12})
    assert response.status_code == 200
    assert response.json()["item"]["assigned_to_user_id"] == 12
```

**Step 2: Run the API test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_monitoring_api.py -q`

Expected: FAIL because the routes do not exist yet.

**Step 3: Add admin monitoring schemas**

Add request/response schemas for:
- alert rule list/create/delete
- alert assignment
- alert snooze
- alert escalate
- alert history list

Use `admin_schemas.py` because these are admin control-plane routes.

**Step 4: Add admin routes**

Create `admin_monitoring.py` and include it from `admin/__init__.py`.

Each mutation route should:
- persist authoritative state through the repo/service
- append a dedicated alert event
- emit admin audit events
- fail closed on persistence errors

**Step 5: Update OpenAPI contract tests**

Assert the new `/admin/monitoring/...` routes exist and point at the correct request/response schemas.

**Step 6: Re-run the API and OpenAPI tests**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_monitoring_api.py -q`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py -q`

Expected: PASS

**Step 7: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/admin/admin_monitoring.py \
  tldw_Server_API/app/api/v1/endpoints/admin/__init__.py \
  tldw_Server_API/app/api/v1/schemas/admin_schemas.py \
  tldw_Server_API/tests/Admin/test_admin_monitoring_api.py \
  tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py
git commit -m "feat(admin-monitoring): add admin control-plane routes"
```

### Task 4: Merge overlay state into runtime monitoring alerts and align acknowledge/dismiss semantics

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/monitoring.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/monitoring_schemas.py`
- Modify: `tldw_Server_API/app/services/admin_monitoring_alerts_service.py`
- Test: `tldw_Server_API/tests/Admin/test_monitoring_alerts_overlay_integration.py`

**Step 1: Write the failing integration tests**

Cover:
- `GET /monitoring/alerts` returns merged overlay state
- acknowledge/read writes through the same overlay state model
- dismiss maps to `dismissed_at` state instead of destructive deletion semantics
- alert history list returns only backend-confirmed events

```python
async def test_monitoring_alerts_include_backend_assignment(client, seeded_alert_state):
    response = client.get("/api/v1/monitoring/alerts")
    assert response.status_code == 200
    assert response.json()["items"][0]["assigned_to_user_id"] == 12
```

**Step 2: Run the integration test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_monitoring_alerts_overlay_integration.py -q`

Expected: FAIL because the read path does not merge overlay state yet.

**Step 3: Update the monitoring read path**

In `monitoring.py`:
- load raw runtime alerts from `TopicMonitoringDB`
- compute/attach `alert_identity`
- load matching overlay state from the admin repo/service
- return merged alerts

Also align the acknowledge/dismiss behavior so backend state is authoritative instead of purely local semantics.

**Step 4: Re-run the integration tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_monitoring_alerts_overlay_integration.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/monitoring.py \
  tldw_Server_API/app/api/v1/schemas/monitoring_schemas.py \
  tldw_Server_API/app/services/admin_monitoring_alerts_service.py \
  tldw_Server_API/tests/Admin/test_monitoring_alerts_overlay_integration.py
git commit -m "feat(admin-monitoring): merge overlay state into alert reads"
```

### Task 5: Replace admin-ui local rules and client-only alert actions

**Files:**
- Modify: `admin-ui/lib/api-client.ts`
- Modify: `admin-ui/app/monitoring/types.ts`
- Modify: `admin-ui/app/monitoring/use-alert-rules.ts`
- Modify: `admin-ui/app/monitoring/use-alert-actions.ts`
- Modify: `admin-ui/app/monitoring/load-state-utils.ts`
- Modify: `admin-ui/app/monitoring/use-monitoring-page-controller.ts`
- Modify: `admin-ui/app/monitoring/components/MonitoringManagementPanels.tsx`
- Modify: `admin-ui/lib/monitoring-alerts.ts`
- Modify: `admin-ui/app/monitoring/use-alert-rules.test.tsx`
- Modify: `admin-ui/app/monitoring/use-alert-actions.test.tsx`
- Modify: `admin-ui/app/monitoring/components/MonitoringManagementPanels.test.tsx`
- Modify: `admin-ui/app/monitoring/__tests__/page.test.tsx`
- Modify: `admin-ui/app/monitoring/load-state-utils.test.ts`

**Step 1: Rewrite the failing frontend tests first**

Change tests so they assert:
- rules load from backend, not local storage
- create/delete rule mutations call backend APIs
- assign/snooze/escalate call backend APIs instead of mutating local state
- no local-only disclaimer is rendered
- reload uses backend history instead of synthesized client history when available

**Step 2: Run the frontend tests to verify they fail**

Run:
- `bunx vitest run app/monitoring/use-alert-rules.test.tsx`
- `bunx vitest run app/monitoring/use-alert-actions.test.tsx`
- `bunx vitest run app/monitoring/components/MonitoringManagementPanels.test.tsx`
- `bunx vitest run app/monitoring/load-state-utils.test.ts`

Expected: FAIL because the hooks still use local storage and client-only state.

**Step 3: Add the client API methods and update types**

Add admin API client methods for:
- list/create/delete rules
- assign/snooze/escalate alerts
- fetch alert history if implemented as a separate route

Update admin monitoring types so backend overlay fields map cleanly into `SystemAlert`.

**Step 4: Replace local-only hook behavior**

Update:
- `use-alert-rules.ts`
- `use-alert-actions.ts`
- `load-state-utils.ts`
- `use-monitoring-page-controller.ts`

Requirements:
- no browser-local rules persistence
- no synthetic assign/snooze/escalate history entries on failed backend calls
- success state only after backend confirmation
- remove local merge logic that exists only to preserve client-only mutations

**Step 5: Remove the local-only disclaimer**

Update `MonitoringManagementPanels.tsx` and its tests to remove the copy about alert rules being stored locally.

**Step 6: Re-run the frontend tests**

Run:
- `bunx vitest run app/monitoring/use-alert-rules.test.tsx app/monitoring/use-alert-actions.test.tsx app/monitoring/components/MonitoringManagementPanels.test.tsx app/monitoring/load-state-utils.test.ts app/monitoring/__tests__/page.test.tsx`

Expected: PASS

**Step 7: Commit**

```bash
git add admin-ui/lib/api-client.ts \
  admin-ui/app/monitoring/types.ts \
  admin-ui/app/monitoring/use-alert-rules.ts \
  admin-ui/app/monitoring/use-alert-actions.ts \
  admin-ui/app/monitoring/load-state-utils.ts \
  admin-ui/app/monitoring/use-monitoring-page-controller.ts \
  admin-ui/app/monitoring/components/MonitoringManagementPanels.tsx \
  admin-ui/lib/monitoring-alerts.ts \
  admin-ui/app/monitoring/use-alert-rules.test.tsx \
  admin-ui/app/monitoring/use-alert-actions.test.tsx \
  admin-ui/app/monitoring/components/MonitoringManagementPanels.test.tsx \
  admin-ui/app/monitoring/__tests__/page.test.tsx \
  admin-ui/app/monitoring/load-state-utils.test.ts
git commit -m "feat(admin-ui): make monitoring actions authoritative"
```

### Task 6: Run verification and finish the branch

**Files:**
- Modify only if verification exposes real defects

**Step 1: Run the targeted backend suite**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Admin/test_admin_monitoring_alerts_service.py \
  tldw_Server_API/tests/Admin/test_admin_monitoring_repo.py \
  tldw_Server_API/tests/AuthNZ/integration/test_authnz_admin_monitoring_repo_postgres.py \
  tldw_Server_API/tests/Admin/test_admin_monitoring_api.py \
  tldw_Server_API/tests/Admin/test_monitoring_alerts_overlay_integration.py \
  tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py -q
```

Expected: PASS

**Step 2: Run the targeted frontend suite**

Run:

```bash
bunx vitest run \
  app/monitoring/use-alert-rules.test.tsx \
  app/monitoring/use-alert-actions.test.tsx \
  app/monitoring/components/MonitoringManagementPanels.test.tsx \
  app/monitoring/load-state-utils.test.ts \
  app/monitoring/__tests__/page.test.tsx
```

Expected: PASS

**Step 3: Run frontend static checks for the touched scope**

Run:

```bash
bun run typecheck
bunx eslint \
  app/monitoring/use-alert-rules.ts \
  app/monitoring/use-alert-actions.ts \
  app/monitoring/load-state-utils.ts \
  app/monitoring/use-monitoring-page-controller.ts \
  app/monitoring/components/MonitoringManagementPanels.tsx \
  lib/api-client.ts \
  lib/monitoring-alerts.ts
```

Expected: PASS

**Step 4: Run Bandit on the touched backend scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/services/admin_monitoring_alerts_service.py \
  tldw_Server_API/app/core/AuthNZ/repos/admin_monitoring_repo.py \
  tldw_Server_API/app/api/v1/endpoints/admin/admin_monitoring.py \
  tldw_Server_API/app/api/v1/endpoints/monitoring.py \
  tldw_Server_API/app/api/v1/schemas/admin_schemas.py \
  tldw_Server_API/app/api/v1/schemas/monitoring_schemas.py \
  -f json -o /tmp/bandit_admin_monitoring_authority.json
```

Expected: `0` findings in changed code

**Step 5: Commit any verification-driven fixes**

```bash
git add <touched files>
git commit -m "fix(admin-monitoring): resolve verification issues"
```

**Step 6: Final branch check**

Run:

```bash
git status --short
git log --oneline --decorate -n 5
```

Expected:
- clean worktree
- clear commit history for the monitoring-authority block
