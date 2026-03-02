# Family Guardrails Wizard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a full template-first Family Guardrails Wizard (WebUI + extension options) that supports household setup, pending-consent relationship flows, queued pre-acceptance policies, and activation tracking for one-guardian, two-guardian, and institutional households.

**Architecture:** Add a new wizard draft domain (API schemas, Guardian DB draft tables, service endpoints) and a materialization pipeline that converts queued plans into active supervised policies after dependent acceptance. Keep existing guardian/moderation pages as advanced surfaces, and add a dedicated wizard UI route in shared package UI so both WebUI and extension consume the same flow. Resolve shared-dependent policy conflicts with deterministic strictest-wins merging plus audit records.

**Tech Stack:** FastAPI, Pydantic, SQLite (Guardian_DB), React + Ant Design + React Query, Vitest, Playwright, pytest, Bandit.

---

## Execution Constraints

- Use **@using-git-worktrees** before implementation (dedicated worktree required).
- Use **@test-driven-development** for each code change.
- Use **@systematic-debugging** if any test fails unexpectedly.
- Use **@verification-before-completion** before completion claims.

### Task 1: Add Route Capability and Navigation Entry for Wizard

**Files:**
- Create: `apps/packages/ui/src/routes/option-family-guardrails-wizard.tsx`
- Modify: `apps/packages/ui/src/routes/route-capabilities.ts`
- Modify: `apps/packages/ui/src/routes/route-registry.tsx`
- Modify: `apps/packages/ui/src/components/Layouts/settings-nav.ts`
- Test: `apps/packages/ui/src/routes/__tests__/route-capabilities.test.ts`

**Step 1: Write the failing test**

```ts
it("enables family wizard when guardian capability exists even if self-monitoring is missing", () => {
  const caps = makeCapabilities({ hasGuardian: true, hasSelfMonitoring: false })
  expect(isRouteEnabledForCapabilities(FAMILY_WIZARD_SETTINGS_PATH, caps)).toBe(true)
})
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/routes/__tests__/route-capabilities.test.ts`
Expected: FAIL because `FAMILY_WIZARD_SETTINGS_PATH` and new gate logic do not exist.

**Step 3: Write minimal implementation**

```ts
export const FAMILY_WIZARD_SETTINGS_PATH = "/settings/family-guardrails"
export const isFamilyWizardAvailable = (caps?: ServerCapabilities | null) =>
  Boolean(caps?.hasGuardian)
```

Add a new options route and settings navigation item for `/settings/family-guardrails`.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/routes/__tests__/route-capabilities.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/option-family-guardrails-wizard.tsx \
  apps/packages/ui/src/routes/route-capabilities.ts \
  apps/packages/ui/src/routes/route-registry.tsx \
  apps/packages/ui/src/components/Layouts/settings-nav.ts \
  apps/packages/ui/src/routes/__tests__/route-capabilities.test.ts
git commit -m "feat(ui): add family wizard route and capability gate"
```

### Task 2: Add Wizard API Schemas

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/family_wizard_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/__init__.py`
- Test: `tldw_Server_API/tests/Guardian/test_family_wizard_schemas.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.api.v1.schemas.family_wizard_schemas import GuardrailPlanDraftCreate

def test_guardrail_plan_template_required():
    payload = {"dependent_user_id": "dep-1", "template_id": ""}
    GuardrailPlanDraftCreate(**payload)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian/test_family_wizard_schemas.py`
Expected: FAIL with import error (module does not exist).

**Step 3: Write minimal implementation**

```python
class GuardrailPlanDraftCreate(BaseModel):
    dependent_user_id: str
    template_id: str = Field(..., min_length=1)
    overrides: dict[str, Any] = Field(default_factory=dict)
```

Include schema models for:
- household draft
- members draft
- relationship draft
- guardrail plan draft
- activation summary

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian/test_family_wizard_schemas.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/family_wizard_schemas.py \
  tldw_Server_API/app/api/v1/schemas/__init__.py \
  tldw_Server_API/tests/Guardian/test_family_wizard_schemas.py
git commit -m "feat(api): add family wizard request and response schemas"
```

### Task 3: Extend Guardian DB With Draft Tables and CRUD

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Guardian_DB.py`
- Test: `tldw_Server_API/tests/Guardian/test_family_wizard_db.py`

**Step 1: Write the failing test**

```python
def test_create_and_load_household_draft(guardian_db):
    draft_id = guardian_db.create_household_draft(owner_user_id="u1", mode="family", name="Home")
    draft = guardian_db.get_household_draft(draft_id)
    assert draft is not None
    assert draft["mode"] == "family"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian/test_family_wizard_db.py::test_create_and_load_household_draft`
Expected: FAIL because methods/tables are missing.

**Step 3: Write minimal implementation**

```python
def create_household_draft(...):
    conn.execute("INSERT INTO guardian_household_drafts ...")

def get_household_draft(...):
    return conn.execute("SELECT * FROM guardian_household_drafts WHERE id=?", (...,)).fetchone()
```

Add new tables:
- `guardian_household_drafts`
- `guardian_household_member_drafts`
- `guardian_relationship_drafts`
- `guardian_guardrail_plan_drafts`
- `guardian_activation_runs`

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian/test_family_wizard_db.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/Guardian_DB.py \
  tldw_Server_API/tests/Guardian/test_family_wizard_db.py
git commit -m "feat(guardian-db): add family wizard draft persistence"
```

### Task 4: Add Family Wizard API Endpoints (Draft Lifecycle + Mapping)

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/family_wizard.py`
- Modify: `tldw_Server_API/app/api/v1/router.py`
- Test: `tldw_Server_API/tests/Guardian/test_family_wizard_endpoints.py`

**Step 1: Write the failing test**

```python
def test_create_household_draft_endpoint(client, auth_headers):
    res = client.post("/api/v1/guardian/wizard/drafts", json={"name": "Home", "mode": "family"}, headers=auth_headers)
    assert res.status_code == 201
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian/test_family_wizard_endpoints.py::test_create_household_draft_endpoint`
Expected: FAIL with 404 (route missing).

**Step 3: Write minimal implementation**

```python
@router.post("/guardian/wizard/drafts", status_code=201)
def create_draft(...):
    draft_id = db.create_household_draft(...)
    return {"id": draft_id, "status": "draft"}
```

Add endpoints for:
- create/get/update draft
- add/remove member drafts
- save relationship mapping
- save guardrail plans

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian/test_family_wizard_endpoints.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/family_wizard.py \
  tldw_Server_API/app/api/v1/router.py \
  tldw_Server_API/tests/Guardian/test_family_wizard_endpoints.py
git commit -m "feat(api): add family wizard draft endpoints"
```

### Task 5: Implement Queued Plan Materialization on Relationship Acceptance

**Files:**
- Create: `tldw_Server_API/app/core/Moderation/family_wizard_materializer.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/guardian_controls.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Guardian_DB.py`
- Test: `tldw_Server_API/tests/Guardian/test_family_wizard_materialization.py`

**Step 1: Write the failing test**

```python
def test_acceptance_materializes_queued_plans(db_fixture):
    # arrange pending relationship + queued draft plan
    # act accept relationship
    # assert supervised policy exists and activation run recorded
    assert db_fixture.list_policies_for_relationship(rel_id)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian/test_family_wizard_materialization.py`
Expected: FAIL because materializer hook is missing.

**Step 3: Write minimal implementation**

```python
def materialize_pending_plans_for_relationship(db, relationship_id, actor_user_id):
    plans = db.list_pending_plans_for_relationship(relationship_id)
    for plan in plans:
        db.create_policy(...)
    db.record_activation_run(...)
```

Call this in `POST /guardian/relationships/{id}/accept` after successful status transition.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian/test_family_wizard_materialization.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Moderation/family_wizard_materializer.py \
  tldw_Server_API/app/api/v1/endpoints/guardian_controls.py \
  tldw_Server_API/app/core/DB_Management/Guardian_DB.py \
  tldw_Server_API/tests/Guardian/test_family_wizard_materialization.py
git commit -m "feat(guardian): materialize queued plans on acceptance"
```

### Task 6: Add Shared-Dependent Conflict Resolution (Strictest-Wins)

**Files:**
- Create: `tldw_Server_API/app/core/Moderation/conflict_resolution.py`
- Modify: `tldw_Server_API/app/core/Moderation/supervised_policy.py`
- Test: `tldw_Server_API/tests/Guardian/test_policy_conflict_resolution.py`

**Step 1: Write the failing test**

```python
def test_strictest_wins_for_shared_dependent():
    merged = resolve_conflicts([
        {"action": "warn"},
        {"action": "block"}
    ])
    assert merged["action"] == "block"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian/test_policy_conflict_resolution.py`
Expected: FAIL because resolver is missing.

**Step 3: Write minimal implementation**

```python
ACTION_ORDER = {"notify": 1, "warn": 2, "redact": 3, "block": 4}

def resolve_conflicts(policies):
    return max(policies, key=lambda p: ACTION_ORDER.get(p.get("action"), 0))
```

Wire resolver into supervised policy overlay generation and audit metadata.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian/test_policy_conflict_resolution.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Moderation/conflict_resolution.py \
  tldw_Server_API/app/core/Moderation/supervised_policy.py \
  tldw_Server_API/tests/Guardian/test_policy_conflict_resolution.py
git commit -m "feat(guardian): add strictest-wins shared-dependent conflict resolver"
```

### Task 7: Add Frontend Family Wizard Service Client

**Files:**
- Create: `apps/packages/ui/src/services/family-wizard.ts`
- Test: `apps/packages/ui/src/services/__tests__/family-wizard.test.ts`

**Step 1: Write the failing test**

```ts
it("calls create draft endpoint", async () => {
  await createHouseholdDraft({ name: "Home", mode: "family" })
  expect(bgRequestMock).toHaveBeenCalledWith(
    expect.objectContaining({ path: "/api/v1/guardian/wizard/drafts", method: "POST" })
  )
})
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/services/__tests__/family-wizard.test.ts`
Expected: FAIL because service module does not exist.

**Step 3: Write minimal implementation**

```ts
export async function createHouseholdDraft(body: CreateHouseholdDraftBody) {
  return bgRequest({ path: toAllowedPath("/api/v1/guardian/wizard/drafts"), method: "POST", body })
}
```

Include client methods for all wizard steps and activation tracker fetch.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/services/__tests__/family-wizard.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/family-wizard.ts \
  apps/packages/ui/src/services/__tests__/family-wizard.test.ts
git commit -m "feat(ui): add family wizard API client"
```

### Task 8: Build Wizard UI Shell and Stepper

**Files:**
- Create: `apps/packages/ui/src/components/Option/Settings/FamilyGuardrailsWizard.tsx`
- Modify: `apps/packages/ui/src/assets/locale/en/settings.json`
- Test: `apps/packages/ui/src/components/Option/Settings/__tests__/FamilyGuardrailsWizard.test.tsx`

**Step 1: Write the failing test**

```tsx
it("renders all core wizard steps", () => {
  render(<FamilyGuardrailsWizard />)
  expect(screen.getByText("Household Basics")).toBeInTheDocument()
  expect(screen.getByText("Invite + Acceptance Tracker")).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/components/Option/Settings/__tests__/FamilyGuardrailsWizard.test.tsx`
Expected: FAIL because component is missing.

**Step 3: Write minimal implementation**

```tsx
export function FamilyGuardrailsWizard() {
  return <Steps items={[{ title: "Household Basics" }, { title: "Invite + Acceptance Tracker" }]} />
}
```

Expand to full 8-step flow with React Query integration and save/resume state.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/components/Option/Settings/__tests__/FamilyGuardrailsWizard.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Settings/FamilyGuardrailsWizard.tsx \
  apps/packages/ui/src/assets/locale/en/settings.json \
  apps/packages/ui/src/components/Option/Settings/__tests__/FamilyGuardrailsWizard.test.tsx
git commit -m "feat(ui): add family guardrails wizard stepper flow"
```

### Task 9: Implement Templates, Acceptance Tracker, and Bulk Operations

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Settings/FamilyGuardrailsWizard.tsx`
- Modify: `apps/packages/ui/src/services/family-wizard.ts`
- Test: `apps/packages/ui/src/components/Option/Settings/__tests__/FamilyGuardrailsWizard.test.tsx`

**Step 1: Write the failing test**

```tsx
it("shows mixed activation statuses for pending and active dependents", async () => {
  render(<FamilyGuardrailsWizard />)
  expect(await screen.findByText("Queued until acceptance")).toBeInTheDocument()
  expect(await screen.findByText("Active")).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/components/Option/Settings/__tests__/FamilyGuardrailsWizard.test.tsx`
Expected: FAIL because tracker/status rendering is incomplete.

**Step 3: Write minimal implementation**

```tsx
<Tag color={status === "pending" ? "gold" : "green"}>
  {status === "pending" ? "Queued until acceptance" : "Active"}
</Tag>
```

Add:
- template cards and apply action
- bulk template apply
- acceptance tracker actions (refresh, resend invite)

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/components/Option/Settings/__tests__/FamilyGuardrailsWizard.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Settings/FamilyGuardrailsWizard.tsx \
  apps/packages/ui/src/services/family-wizard.ts \
  apps/packages/ui/src/components/Option/Settings/__tests__/FamilyGuardrailsWizard.test.tsx
git commit -m "feat(ui): add templates and acceptance tracker to family wizard"
```

### Task 10: Add WebUI + Extension Parity E2E and Docs

**Files:**
- Modify: `apps/extension/tests/e2e/page-inventory.ts`
- Modify: `apps/tldw-frontend/e2e/page-mapping.ts`
- Modify: `apps/tldw-frontend/e2e/smoke/page-inventory.ts`
- Create: `apps/tldw-frontend/e2e/workflows/family-guardrails-wizard.spec.ts`
- Create: `Docs/User_Guides/WebUI_Extension/Family_Guardrails_Wizard_Guide.md`
- Modify: `Docs/User_Guides/WebUI_Extension/Family_Guardian_Setup.md`

**Step 1: Write the failing test**

```ts
test("family wizard route is present and reachable", async ({ page }) => {
  await page.goto("/settings/family-guardrails")
  await expect(page.getByText("Family Guardrails Wizard")).toBeVisible()
})
```

**Step 2: Run test to verify it fails**

Run: `bunx playwright test apps/tldw-frontend/e2e/workflows/family-guardrails-wizard.spec.ts --reporter=line`
Expected: FAIL if route or content is missing.

**Step 3: Write minimal implementation**

Add route inventories and test mappings for both web and extension, and publish wizard-first user guide with links from existing guardian setup docs.

**Step 4: Run tests to verify they pass**

Run:
- `bunx playwright test apps/tldw-frontend/e2e/workflows/family-guardrails-wizard.spec.ts --reporter=line`
- `bunx playwright test apps/tldw-frontend/e2e/smoke/all-pages.spec.ts --grep "settings|guardian|moderation" --reporter=line`

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/extension/tests/e2e/page-inventory.ts \
  apps/tldw-frontend/e2e/page-mapping.ts \
  apps/tldw-frontend/e2e/smoke/page-inventory.ts \
  apps/tldw-frontend/e2e/workflows/family-guardrails-wizard.spec.ts \
  Docs/User_Guides/WebUI_Extension/Family_Guardrails_Wizard_Guide.md \
  Docs/User_Guides/WebUI_Extension/Family_Guardian_Setup.md
git commit -m "test+docs: add family wizard parity e2e coverage and user guide"
```

### Task 11: Full Verification and Security Gate

**Files:**
- Modify if needed based on findings in touched paths only.

**Step 1: Run focused backend tests**

Run:
`source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Guardian/test_family_wizard_* tldw_Server_API/tests/Guardian/test_policy_conflict_resolution.py`

Expected: PASS.

**Step 2: Run focused frontend unit tests**

Run:
`bunx vitest run apps/packages/ui/src/components/Option/Settings/__tests__/FamilyGuardrailsWizard.test.tsx apps/packages/ui/src/routes/__tests__/route-capabilities.test.ts apps/packages/ui/src/services/__tests__/family-wizard.test.ts`

Expected: PASS.

**Step 3: Run Bandit on touched backend scope**

Run:
`source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/family_wizard.py tldw_Server_API/app/core/DB_Management/Guardian_DB.py tldw_Server_API/app/core/Moderation/family_wizard_materializer.py tldw_Server_API/app/core/Moderation/conflict_resolution.py -f json -o /tmp/bandit_family_wizard.json`

Expected: JSON report generated, no new high-severity findings in touched code.

**Step 4: Fix findings if present and re-run verification**

Run the same three verification commands again.
Expected: PASS.

**Step 5: Final commit (only if fixes were required)**

```bash
git add <touched_files>
git commit -m "fix(security): resolve family wizard verification findings"
```

