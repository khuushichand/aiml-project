# Family Guardrails Wizard Invite, Resume, and Tracker Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add invite-first dependent provisioning, explicit draft resume/edit entry, first-class tracker rows and actions, local setup analytics, and parity/CI hardening to the Family Guardrails Wizard without regressing the current existing-account flow.

**Architecture:** Extend the current wizard draft domain in `Guardian_DB` instead of bypassing it with raw AuthNZ primitives. Shift relationship and plan drafts to member-draft-based references so invite-first dependents can be configured before a real user exists. Add dedicated invite records plus preview/accept endpoints, then update the shared UI to use an explicit entry state and row-level tracker actions. Keep V1 owner-only editing, derive aggregate summaries from tracker rows, and make telemetry append-only and best-effort.

**Tech Stack:** FastAPI, Pydantic, SQLite/Guardian_DB migrations, AuthNZ registration codes and magic-link-compatible acceptance flows, React, Ant Design, Vitest, Playwright, pytest, Bandit, Loguru.

---

### Task 1: Extend Wizard Schemas and Guardian DB for Invite-First Member Drafts

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/family_wizard_schemas.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Guardian_DB.py`
- Test: `tldw_Server_API/tests/Guardian/test_family_wizard_schemas.py`
- Test: `tldw_Server_API/tests/Guardian/test_family_wizard_db.py`

**Step 1: Write the failing tests**

```python
def test_household_member_draft_supports_invite_first_dependents() -> None:
    payload = HouseholdMemberDraftCreate(
        role="dependent",
        display_name="Alex",
        email="alex@example.com",
        invite_required=True,
        account_mode="invite_new",
        provisioning_status="not_started",
    )
    assert payload.user_id is None
    assert payload.account_mode == "invite_new"


def test_guardian_db_creates_member_invite_and_lists_drafts(guardian_db) -> None:
    draft_id = guardian_db.create_household_draft(owner_user_id="guardian-1", mode="family", name="Home")
    member_id = guardian_db.add_household_member_draft(
        household_draft_id=draft_id,
        role="dependent",
        display_name="Alex",
        email="alex@example.com",
        invite_required=True,
        account_mode="invite_new",
        provisioning_status="not_started",
    )
    invite_id = guardian_db.create_household_member_invite(
        household_draft_id=draft_id,
        member_draft_id=member_id,
        delivery_channel="email",
        delivery_target="alex@example.com",
    )
    invite = guardian_db.get_household_member_invite(invite_id)
    assert invite["status"] == "ready"
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian/test_family_wizard_schemas.py tldw_Server_API/tests/Guardian/test_family_wizard_db.py`

Expected: FAIL with missing schema fields and missing DB methods/table columns.

**Step 3: Write minimal implementation**

```python
WizardAccountMode = Literal["existing_account", "invite_new"]
WizardProvisioningStatus = Literal[
    "not_started", "invite_ready", "sent", "accepted", "expired", "failed"
]

class HouseholdMemberDraftCreate(BaseModel):
    role: WizardMemberRole
    display_name: str = Field(..., min_length=1, max_length=120)
    user_id: str | None = None
    email: str | None = None
    invite_required: bool = True
    account_mode: WizardAccountMode = "existing_account"
    provisioning_status: WizardProvisioningStatus = "not_started"
    metadata: dict[str, Any] = Field(default_factory=dict)
```

```python
CREATE TABLE IF NOT EXISTS guardian_household_member_invites (
    id TEXT PRIMARY KEY,
    household_draft_id TEXT NOT NULL,
    member_draft_id TEXT NOT NULL,
    invite_token TEXT NOT NULL UNIQUE,
    registration_code TEXT,
    status TEXT NOT NULL DEFAULT 'ready',
    delivery_channel TEXT NOT NULL DEFAULT 'guardian_copy',
    delivery_target TEXT,
    sent_at TEXT,
    last_resent_at TEXT,
    expires_at TEXT,
    accepted_at TEXT,
    redeemed_by_user_id TEXT,
    failed_at TEXT,
    failure_reason TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

Add DB helpers:

- `create_household_member_invite`
- `get_household_member_invite`
- `list_household_member_invites`
- `list_household_drafts`

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian/test_family_wizard_schemas.py tldw_Server_API/tests/Guardian/test_family_wizard_db.py`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/family_wizard_schemas.py \
  tldw_Server_API/app/core/DB_Management/Guardian_DB.py \
  tldw_Server_API/tests/Guardian/test_family_wizard_schemas.py \
  tldw_Server_API/tests/Guardian/test_family_wizard_db.py
git commit -m "feat(guardian): add invite-first wizard draft data model"
```

### Task 2: Decouple Relationship and Plan Drafts from Immediate Dependent User IDs

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/family_wizard_schemas.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Guardian_DB.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/family_wizard.py`
- Test: `tldw_Server_API/tests/Guardian/test_family_wizard_endpoints.py`
- Test: `tldw_Server_API/tests/Guardian/test_family_wizard_materialization.py`

**Step 1: Write the failing tests**

```python
def test_relationship_mapping_allows_invite_first_dependent_without_runtime_relationship(client):
    draft_id = _create_draft(client)
    guardian_id = _create_guardian_member(client, draft_id, user_id="guardian-1")
    dependent_id = _create_dependent_member(
        client,
        draft_id,
        account_mode="invite_new",
        email="alex@example.com",
        user_id=None,
    )
    response = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/relationships",
        json={
            "guardian_member_draft_id": guardian_id,
            "dependent_member_draft_id": dependent_id,
            "relationship_type": "parent",
            "dependent_visible": True,
        },
    )
    assert response.status_code == 201
    assert response.json()["relationship_id"] is None
    assert response.json()["status"] == "pending_provisioning"


def test_guardrail_plan_can_be_saved_for_invite_first_dependent(client):
    # relationship_draft_id references dependent member draft, not resolved user
    response = client.post(
        f"/api/v1/guardian/wizard/drafts/{draft_id}/plans",
        json={
            "dependent_member_draft_id": dependent_id,
            "relationship_draft_id": relationship_draft_id,
            "template_id": "default-child-safe",
            "overrides": {"notify_context": "snippet"},
        },
    )
    assert response.status_code == 201
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian/test_family_wizard_endpoints.py -k "invite_first or plan_can_be_saved" tldw_Server_API/tests/Guardian/test_family_wizard_materialization.py`

Expected: FAIL because mapping still requires `user_id` and plans still require `dependent_user_id`.

**Step 3: Write minimal implementation**

```python
class GuardrailPlanDraftCreate(BaseModel):
    dependent_member_draft_id: str = Field(..., min_length=1)
    relationship_draft_id: str = Field(..., min_length=1)
    template_id: str = Field(..., min_length=1)
    overrides: dict[str, Any] = Field(default_factory=dict)
```

Change endpoint behavior:

- relationship mapping creates only a relationship draft before invite acceptance
- runtime `create_relationship(...)` happens only when a dependent has a resolved user
- plan drafts store `dependent_member_draft_id` and optional resolved `dependent_user_id`

Add a new relationship draft status such as `pending_provisioning`.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian/test_family_wizard_endpoints.py -k "invite_first or plan_can_be_saved" tldw_Server_API/tests/Guardian/test_family_wizard_materialization.py`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/family_wizard_schemas.py \
  tldw_Server_API/app/core/DB_Management/Guardian_DB.py \
  tldw_Server_API/app/api/v1/endpoints/family_wizard.py \
  tldw_Server_API/tests/Guardian/test_family_wizard_endpoints.py \
  tldw_Server_API/tests/Guardian/test_family_wizard_materialization.py
git commit -m "feat(guardian): decouple wizard drafts from immediate dependent user ids"
```

### Task 3: Add Draft Listing, Invite Provision/Resend/Reissue, and Tracker Endpoints

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/family_wizard_schemas.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Guardian_DB.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/family_wizard.py`
- Test: `tldw_Server_API/tests/Guardian/test_family_wizard_endpoints.py`
- Test: `tldw_Server_API/tests/Guardian/test_family_wizard_db.py`

**Step 1: Write the failing tests**

```python
def test_list_household_drafts_returns_owned_drafts(client):
    _create_named_draft(client, "Home")
    _create_named_draft(client, "School")
    response = client.get("/api/v1/guardian/wizard/drafts")
    assert response.status_code == 200
    assert [row["name"] for row in response.json()] == ["School", "Home"]


def test_tracker_endpoint_returns_row_level_blockers_and_actions(client):
    response = client.get(f"/api/v1/guardian/wizard/drafts/{draft_id}/tracker")
    row = response.json()["items"][0]
    assert row["invite_status"] == "expired"
    assert "invite_expired" in row["blocker_codes"]
    assert "reissue_invite" in row["available_actions"]


def test_reissue_invite_rotates_token_and_marks_old_invite_revoked(client):
    response = client.post(f"/api/v1/guardian/wizard/drafts/{draft_id}/invites/{invite_id}/reissue")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian/test_family_wizard_endpoints.py -k "list_household_drafts or tracker_endpoint or reissue_invite" tldw_Server_API/tests/Guardian/test_family_wizard_db.py -k "invite"`

Expected: FAIL because the list/tracker/reissue endpoints and DB helpers do not exist.

**Step 3: Write minimal implementation**

Add schemas such as:

```python
class HouseholdDraftListItem(HouseholdDraftResponse):
    guardian_count: int
    dependent_count: int
    active_count: int
    pending_count: int
    failed_count: int


class TrackerRowResponse(BaseModel):
    member_draft_id: str
    display_name: str
    account_mode: WizardAccountMode
    invite_status: str | None = None
    mapping_status: str
    relationship_status: str | None = None
    plan_status: WizardPlanStatus | None = None
    blocker_codes: list[str] = Field(default_factory=list)
    available_actions: list[str] = Field(default_factory=list)
```

Add endpoints:

- `GET /wizard/drafts`
- `POST /wizard/drafts/{draft_id}/dependents/provision`
- `GET /wizard/drafts/{draft_id}/tracker`
- `POST /wizard/drafts/{draft_id}/invites/{invite_id}/resend`
- `POST /wizard/drafts/{draft_id}/invites/{invite_id}/reissue`

Keep `POST /wizard/drafts/{draft_id}/invites/resend` for bulk resend, but implement it on top of invite records instead of member metadata.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian/test_family_wizard_endpoints.py -k "list_household_drafts or tracker_endpoint or reissue_invite" tldw_Server_API/tests/Guardian/test_family_wizard_db.py -k "invite"`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/family_wizard_schemas.py \
  tldw_Server_API/app/core/DB_Management/Guardian_DB.py \
  tldw_Server_API/app/api/v1/endpoints/family_wizard.py \
  tldw_Server_API/tests/Guardian/test_family_wizard_endpoints.py \
  tldw_Server_API/tests/Guardian/test_family_wizard_db.py
git commit -m "feat(guardian): add wizard draft list and tracker invite actions"
```

### Task 4: Implement Invite Preview/Accept and Materialization Pipeline

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Guardian_DB.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/family_wizard.py`
- Test: `tldw_Server_API/tests/Guardian/test_family_wizard_endpoints.py`
- Test: `tldw_Server_API/tests/Guardian/test_family_wizard_materialization.py`

**Step 1: Write the failing tests**

```python
def test_preview_invite_returns_delivery_and_household_context(client):
    response = client.get(f"/api/v1/guardian/wizard/invites/{invite_token}")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["household_name"] == "Home"


def test_accept_invite_claims_member_and_materializes_guardrails(client):
    response = client.post(
        f"/api/v1/guardian/wizard/invites/{invite_token}/accept",
        json={"resolved_user_id": "child-1"},
    )
    assert response.status_code == 200
    assert response.json()["relationship_status"] == "pending"
    assert response.json()["plan_status"] in {"queued", "active"}
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian/test_family_wizard_endpoints.py -k "preview_invite or accept_invite" tldw_Server_API/tests/Guardian/test_family_wizard_materialization.py`

Expected: FAIL because invite preview/accept endpoints and acceptance-triggered materialization do not exist.

**Step 3: Write minimal implementation**

```python
@router.get("/wizard/invites/{invite_token}", response_model=InvitePreviewResponse)
def preview_household_invite(...):
    ...


@router.post("/wizard/invites/{invite_token}/accept", response_model=InviteAcceptResponse)
def accept_household_invite(...):
    invite = db.get_active_invite_by_token(invite_token)
    member = db.resolve_invited_member(invite["member_draft_id"], resolved_user_id=user_id)
    relationship = db.materialize_relationship_draft(invite["member_draft_id"])
    db.materialize_guardrail_plans_for_member(invite["member_draft_id"], resolved_user_id=user_id)
```

Implementation rules:

- invite acceptance is idempotent
- registration code remains server-side
- accepted invites update invite/member/relationship/plan timestamps

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian/test_family_wizard_endpoints.py -k "preview_invite or accept_invite" tldw_Server_API/tests/Guardian/test_family_wizard_materialization.py`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/Guardian_DB.py \
  tldw_Server_API/app/api/v1/endpoints/family_wizard.py \
  tldw_Server_API/tests/Guardian/test_family_wizard_endpoints.py \
  tldw_Server_API/tests/Guardian/test_family_wizard_materialization.py
git commit -m "feat(guardian): add wizard invite acceptance and materialization flow"
```

### Task 5: Update Shared Wizard Service Layer for Entry State, Tracker, and Invite Actions

**Files:**
- Modify: `apps/packages/ui/src/services/family-wizard.ts`
- Test: `apps/packages/ui/src/services/__tests__/family-wizard.test.ts`

**Step 1: Write the failing tests**

```typescript
it("lists household drafts", async () => {
  await listHouseholdDrafts()
  expect(bgRequestMock).toHaveBeenCalledWith(
    expect.objectContaining({
      path: "/api/v1/guardian/wizard/drafts",
      method: "GET",
    })
  )
})

it("reissues an invite by invite id", async () => {
  await reissueHouseholdInvite("draft-1", "invite-1")
  expect(bgRequestMock).toHaveBeenCalledWith(
    expect.objectContaining({
      path: "/api/v1/guardian/wizard/drafts/draft-1/invites/invite-1/reissue",
      method: "POST",
    })
  )
})
```

**Step 2: Run tests to verify they fail**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/services/__tests__/family-wizard.test.ts`

Expected: FAIL because the service methods and response shapes do not exist.

**Step 3: Write minimal implementation**

```typescript
export async function listHouseholdDrafts(): Promise<HouseholdDraftListItem[]> { ... }
export async function getHouseholdTracker(draftId: string): Promise<TrackerResponse> { ... }
export async function provisionDependentInvites(
  draftId: string,
  body: ProvisionDependentInvitesBody
): Promise<ProvisionDependentInvitesResponse> { ... }
export async function resendHouseholdInvite(draftId: string, inviteId: string): Promise<InviteActionResponse> { ... }
export async function reissueHouseholdInvite(draftId: string, inviteId: string): Promise<InviteActionResponse> { ... }
```

Update TypeScript types to reflect:

- member `account_mode`
- member `provisioning_status`
- tracker row timestamps/blockers/actions
- draft listing summaries

**Step 4: Run tests to verify they pass**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/services/__tests__/family-wizard.test.ts`

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/family-wizard.ts \
  apps/packages/ui/src/services/__tests__/family-wizard.test.ts
git commit -m "feat(ui): add family wizard draft and invite service methods"
```

### Task 6: Add Explicit Entry State, Invite-First Dependent Mode, and Tracker Row Actions to the Shared Wizard UI

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Settings/FamilyGuardrailsWizard.tsx`
- Test: `apps/packages/ui/src/components/Option/Settings/__tests__/FamilyGuardrailsWizard.test.tsx`

**Step 1: Write the failing tests**

```typescript
it("shows explicit start, resume, and edit entry actions when no initial draft is supplied", async () => {
  render(<FamilyGuardrailsWizard />)
  expect(screen.getByRole("button", { name: "Start new household" })).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Resume latest draft" })).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Edit existing household" })).toBeInTheDocument()
})

it("allows invite-new dependents without requiring a user id", async () => {
  // move to dependent step, switch row mode to Invite new dependent,
  // leave user id blank, continue successfully
})

it("shows reissue action for expired tracker rows", async () => {
  expect(screen.getByRole("button", { name: "Reissue invite for alex" })).toBeInTheDocument()
})
```

**Step 2: Run tests to verify they fail**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/Settings/__tests__/FamilyGuardrailsWizard.test.tsx`

Expected: FAIL because the component still auto-resumes, requires dependent user IDs, and has no reissue action.

**Step 3: Write minimal implementation**

Implementation targets:

- replace silent `getLatestHouseholdDraft()` mount effect with explicit entry UI
- add draft list modal/panel for edit selection
- add dependent row `account_mode`
- require `user_id` only for `existing_account`
- add tracker button routing:
  - `resend`
  - `reissue`
  - `fix mapping`
  - `review template`
  - `copy invite link`

Representative component state:

```typescript
const [entryMode, setEntryMode] = useState<"entry" | "wizard">("entry")
const [draftList, setDraftList] = useState<HouseholdDraftListItem[]>([])
const [trackerRows, setTrackerRows] = useState<TrackerRowResponse[]>([])
```

**Step 4: Run tests to verify they pass**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/Settings/__tests__/FamilyGuardrailsWizard.test.tsx`

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Settings/FamilyGuardrailsWizard.tsx \
  apps/packages/ui/src/components/Option/Settings/__tests__/FamilyGuardrailsWizard.test.tsx
git commit -m "feat(ui): add family wizard entry state and invite-first tracker UX"
```

### Task 7: Add Local Wizard Setup Analytics and Summary Read Path

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Guardian_DB.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/family_wizard.py`
- Create: `apps/packages/ui/src/utils/family-wizard-telemetry.ts`
- Test: `tldw_Server_API/tests/Guardian/test_family_wizard_analytics.py`
- Test: `apps/packages/ui/src/utils/__tests__/family-wizard-telemetry.test.ts`
- Modify: `apps/packages/ui/src/components/Option/Settings/FamilyGuardrailsWizard.tsx`

**Step 1: Write the failing tests**

```python
def test_family_wizard_analytics_summary_reports_dropoff_and_completion(db):
    db.append_family_wizard_event(...)
    summary = db.get_family_wizard_analytics_summary(owner_user_id="guardian-1", days=30)
    assert summary["completion_rate"] >= 0
    assert "most_common_dropoff_step" in summary
```

```typescript
it("emits wizard step completion events best-effort", async () => {
  await trackFamilyWizardTelemetry({
    type: "step_completed",
    runId: "run-1",
    stepId: "dependents",
  })
  expect(bgRequestMock).toHaveBeenCalled()
})
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian/test_family_wizard_analytics.py`

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/utils/__tests__/family-wizard-telemetry.test.ts`

Expected: FAIL because the analytics store/helper do not exist.

**Step 3: Write minimal implementation**

Backend:

```python
@router.post("/wizard/analytics/events")
def append_family_wizard_event(...): ...

@router.get("/wizard/analytics/summary")
def get_family_wizard_analytics_summary(...): ...
```

Frontend helper:

```typescript
export const trackFamilyWizardTelemetry = async (event: FamilyWizardTelemetryEvent) => {
  try {
    await bgRequest({ path: "/api/v1/guardian/wizard/analytics/events", method: "POST", body: event })
  } catch (error) {
    console.warn("[family-wizard-telemetry] Failed to record telemetry event", error)
  }
}
```

Emit events from the wizard on:

- start
- resume/edit selection
- step completed
- validation failure
- invite provision/resend/reissue
- finish

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian/test_family_wizard_analytics.py`

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/utils/__tests__/family-wizard-telemetry.test.ts`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/Guardian_DB.py \
  tldw_Server_API/app/api/v1/endpoints/family_wizard.py \
  tldw_Server_API/tests/Guardian/test_family_wizard_analytics.py \
  apps/packages/ui/src/utils/family-wizard-telemetry.ts \
  apps/packages/ui/src/utils/__tests__/family-wizard-telemetry.test.ts \
  apps/packages/ui/src/components/Option/Settings/FamilyGuardrailsWizard.tsx
git commit -m "feat(guardian): add local family wizard setup analytics"
```

### Task 8: Harden WebUI/Extension Parity and Wire Family Wizard Checks into CI

**Files:**
- Create: `apps/tldw-frontend/__tests__/extension/route-registry.family-guardrails.test.ts`
- Modify: `apps/tldw-frontend/e2e/page-mapping.ts`
- Modify: `apps/tldw-frontend/e2e/workflows/family-guardrails-wizard.spec.ts`
- Modify: `apps/tldw-frontend/package.json`
- Modify: `.github/workflows/frontend-required.yml`

**Step 1: Write the failing tests**

```typescript
describe("extension route registry family guardrails parity", () => {
  it("registers the family guardrails options route", () => {
    expect(extensionRouteRegistrySource).toMatch(/path:\s*"\/settings\/family-guardrails"/)
  })
})
```

Add Playwright assertions for:

- explicit entry screen
- resume/edit flow
- bulk resend
- row-level resend/reissue

**Step 2: Run tests to verify they fail**

Run: `cd apps/tldw-frontend && bunx vitest run __tests__/extension/route-registry.family-guardrails.test.ts`

Run: `cd apps/tldw-frontend && bunx playwright test e2e/workflows/family-guardrails-wizard.spec.ts --reporter=line`

Expected: FAIL because the parity test file and new wizard interactions are not yet wired.

**Step 3: Write minimal implementation**

Add script(s):

```json
"test:family-guardrails:parity": "vitest run __tests__/extension/route-registry.family-guardrails.test.ts",
"e2e:family-guardrails": "playwright test e2e/workflows/family-guardrails-wizard.spec.ts --reporter=line"
```

Update `frontend-required.yml` to run targeted family wizard checks when relevant
paths change:

- shared UI family wizard component
- family wizard service
- extension route file
- family wizard e2e/parity tests

**Step 4: Run tests to verify they pass**

Run: `cd apps/tldw-frontend && bun run test:family-guardrails:parity`

Run: `cd apps/tldw-frontend && bun run e2e:family-guardrails`

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/tldw-frontend/__tests__/extension/route-registry.family-guardrails.test.ts \
  apps/tldw-frontend/e2e/page-mapping.ts \
  apps/tldw-frontend/e2e/workflows/family-guardrails-wizard.spec.ts \
  apps/tldw-frontend/package.json \
  .github/workflows/frontend-required.yml
git commit -m "test(frontend): harden family guardrails parity and CI coverage"
```

### Task 9: Final Verification, Security Scan, and Docs Touch-Up

**Files:**
- Modify: `Docs/User_Guides/WebUI_Extension/Family_Guardrails_Wizard_Guide.md`
- Modify: `Docs/Plans/2026-03-18-family-guardrails-wizard-invite-resume-design.md`

**Step 1: Update the user guide**

Document:

- explicit start/resume/edit entry state
- link-existing vs invite-new dependent setup
- resend vs reissue behavior
- tracker row meanings

**Step 2: Run targeted verification**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Guardian`

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/Settings/__tests__/FamilyGuardrailsWizard.test.tsx ../packages/ui/src/services/__tests__/family-wizard.test.ts __tests__/extension/route-registry.family-guardrails.test.ts`

Run: `cd apps/tldw-frontend && bunx playwright test e2e/workflows/family-guardrails-wizard.spec.ts --reporter=line`

Expected: PASS.

**Step 3: Run Bandit on touched backend paths**

Run: `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/family_wizard.py tldw_Server_API/app/core/DB_Management/Guardian_DB.py tldw_Server_API/app/api/v1/schemas/family_wizard_schemas.py -f json -o /tmp/bandit_family_wizard.json`

Expected: no new findings in touched code.

**Step 4: Self-review and commit docs**

```bash
git add Docs/User_Guides/WebUI_Extension/Family_Guardrails_Wizard_Guide.md \
  Docs/Plans/2026-03-18-family-guardrails-wizard-invite-resume-design.md
git commit -m "docs(guardian): update family wizard guide for invite-first flow"
```

