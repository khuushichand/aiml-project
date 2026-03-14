# Persona Assistant Setup Experience Polish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Polish Persona Garden assistant setup so incomplete personas are easier to resume, safer to retry, and clearer to use after completion.

**Architecture:** Extend persona setup metadata with per-run `completed_steps`, keep setup intent and handoff state route-owned in `sidepanel-persona.tsx`, add small presentation components for status and handoff, and replace generic wizard failure state with step-scoped setup outcomes. Keep all domain data in the existing persona profile, commands, connections, and live-session surfaces.

**Tech Stack:** FastAPI, Pydantic, React, TypeScript, Vitest, React Testing Library, Playwright, pytest.

---

### Task 1: Add `completed_steps` To Persona Setup Metadata

**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/persona.py`
- Modify: `tldw_Server_API/tests/Persona/test_persona_profiles_api.py`

**Step 1: Write the failing tests**

Add API coverage for setup metadata round-tripping a per-run completed-steps list.

Add tests like:

```python
def test_persona_profile_setup_completed_steps_round_trip(...):
    payload = {
        "name": "Setup Persona",
        "setup": {
            "status": "in_progress",
            "current_step": "commands",
            "completed_steps": ["persona", "voice"],
        },
    }
    ...
    assert response_json["setup"]["completed_steps"] == ["persona", "voice"]


def test_persona_profile_setup_can_reset_completed_steps_without_clearing_completion_fields(...):
    ...
    assert patched["setup"]["completed_steps"] == []
    assert patched["setup"]["current_step"] == "persona"
```

Use the existing persona profile create/get/patch coverage pattern.

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_profiles_api.py -q -k "completed_steps or reset_completed_steps"
```

Expected: FAIL because `PersonaSetupState` does not accept or return `completed_steps`.

**Step 3: Write minimal implementation**

In `tldw_Server_API/app/api/v1/schemas/persona.py`:

- extend `PersonaSetupState` with:

```python
completed_steps: list[PersonaSetupStep] = Field(default_factory=list)
```

- keep it normalized and default-empty
- do not add new backend tables or new setup endpoints in this task

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_profiles_api.py -q -k "completed_steps or reset_completed_steps"
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/persona.py tldw_Server_API/tests/Persona/test_persona_profiles_api.py
git commit -m "feat: add persona setup completed steps metadata"
```

### Task 2: Make Setup Progress And Intent Stable In The Route

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/hooks/usePersonaSetupWizard.ts`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing tests**

Add route tests for:

```tsx
it("captures setup intent target tab once and preserves it while setup remains active", async () => {
  ...
})

it("uses completed_steps to resume wizard progress instead of deriving completion from active tab", async () => {
  ...
})

it("sends expected_version when advancing setup state", async () => {
  ...
})
```

Assert:

- the route preserves the original requested tab while setup is in progress
- switching visible tabs during setup does not overwrite the stored intent target
- setup step transitions patch `setup` with `completed_steps`
- setup mutations include the latest persona profile version via `expected_version`

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: FAIL because the route still derives `postSetupTargetTab` from `activeTab` and does not track `completed_steps` or `expected_version`.

**Step 3: Write minimal implementation**

In `apps/packages/ui/src/routes/sidepanel-persona.tsx`:

- add route state for:
  - `savedPersonaProfileVersion`
  - `setupIntentTargetTab`
- capture `setupIntentTargetTab` when setup gating first activates
- replace ad-hoc setup patch payloads with a helper that accepts:
  - `current_step`
  - `completed_steps`
  - `status`
  - `last_test_type`
  - `completed_at`
- send `expected_version` on every setup profile patch
- update local saved version from each profile response

In `apps/packages/ui/src/hooks/usePersonaSetupWizard.ts`:

- stop owning the post-setup target tab
- keep the hook focused on `isSetupRequired` and `currentStep`

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS for the new route state tests.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/usePersonaSetupWizard.ts apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: stabilize persona setup intent and step progress"
```

### Task 3: Add The Progress Rail And Profiles Setup Status Card

**Status:** Complete

**Files:**
- Create: `apps/packages/ui/src/components/PersonaGarden/PersonaSetupStatusCard.tsx`
- Create: `apps/packages/ui/src/components/PersonaGarden/personaSetupProgress.ts`
- Create: `apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupStatusCard.test.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/AssistantSetupWizard.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/ProfilePanel.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx`

**Step 1: Write the failing tests**

Add component tests for:

```tsx
it("renders a progress rail with completed, current, and pending setup steps", () => {
  ...
})

it("shows an in-progress setup status card with resume and reset actions", () => {
  ...
})

it("shows a completed setup status card with completion path and rerun action", () => {
  ...
})
```

Assert:

- the wizard renders five steps
- completed steps are driven by `completed_steps`
- the profile card shows `Not started`, `In progress`, and `Completed` states correctly

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupStatusCard.test.tsx
```

Expected: FAIL because the progress rail and setup status card do not exist.

**Step 3: Write minimal implementation**

Create `apps/packages/ui/src/components/PersonaGarden/personaSetupProgress.ts` with helpers like:

```ts
export const PERSONA_SETUP_STEPS = ["persona", "voice", "commands", "safety", "test"] as const

export function buildPersonaSetupProgress(...) {
  return ...
}
```

Create `PersonaSetupStatusCard.tsx` to render:

- current setup state
- completion path/date
- `Start setup`, `Resume setup`, `Reset setup`, or `Rerun setup`

Modify `AssistantSetupWizard.tsx` to accept:

- `progressItems`
- `stepSummaries`

Modify `ProfilePanel.tsx` to render the new status card above `AssistantDefaultsPanel`.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupStatusCard.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/PersonaSetupStatusCard.tsx apps/packages/ui/src/components/PersonaGarden/personaSetupProgress.ts apps/packages/ui/src/components/PersonaGarden/ProfilePanel.tsx apps/packages/ui/src/components/PersonaGarden/AssistantSetupWizard.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupStatusCard.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx
git commit -m "feat: add persona setup progress rail and status card"
```

### Task 4: Add Reset/Rerun Actions And Step-Scoped Error State

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/SetupStarterCommandsStep.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/SetupSafetyConnectionsStep.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/SetupStarterCommandsStep.test.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing tests**

Add route/component tests for:

```tsx
it("resets setup metadata without deleting existing persona resources", async () => {
  ...
})

it("reruns completed setup from the persona step with cleared completed_steps", async () => {
  ...
})

it("renders a step-local starter-command error with retry affordance", () => {
  ...
})

it("renders a step-local safety-step error while keeping the explicit skip path available", () => {
  ...
})
```

Assert:

- reset/rerun only mutate setup metadata
- setup steps render their own failure copy
- retry buttons call the step callback again

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupStarterCommandsStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx
```

Expected: FAIL because the route still uses one generic wizard error and has no reset/rerun actions.

**Step 3: Write minimal implementation**

In `sidepanel-persona.tsx`:

- add route handlers:
  - `handleStartSetup`
  - `handleResumeSetup`
  - `handleResetSetup`
  - `handleRerunSetup`
- normalize route state into:

```ts
type SetupStepErrors = {
  persona?: string | null
  voice?: string | null
  commands?: string | null
  safety?: string | null
  test?: string | null
}
```

- clear only the affected step error when retrying that step

In `SetupStarterCommandsStep.tsx` and `SetupSafetyConnectionsStep.tsx`:

- accept `error?: string | null`
- render step-local error copy
- keep the explicit non-destructive continue paths available

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupStarterCommandsStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/components/PersonaGarden/SetupStarterCommandsStep.tsx apps/packages/ui/src/components/PersonaGarden/SetupSafetyConnectionsStep.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupStarterCommandsStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: add setup reset and step-scoped error handling"
```

### Task 5: Add Structured Test Outcomes And Unified Post-Setup Handoff

**Status:** Complete

**Files:**
- Create: `apps/packages/ui/src/components/PersonaGarden/PersonaSetupHandoffCard.tsx`
- Create: `apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/SetupTestAndFinishStep.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing tests**

Add coverage for:

```tsx
it("renders a dry-run no-match outcome with a forward action", () => {
  ...
})

it("renders a live-unavailable outcome separately from live-success", () => {
  ...
})

it("shows a post-setup handoff card on the captured target tab after completion", async () => {
  ...
})

it("removes the old live-only setup completion card from the composer path", async () => {
  ...
})
```

Assert:

- dry-run success/no-match/failure render different copy
- live unavailable/live sent/live success render different copy
- completion creates a transient handoff card on the target tab
- the old composer-specific setup completion card no longer renders

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: FAIL because the step only knows raw strings and no handoff card exists.

**Step 3: Write minimal implementation**

In `sidepanel-persona.tsx`:

- add a route-owned setup test outcome model
- add `setupHandoff` state
- set `setupHandoff` when setup completes
- remove `setupLiveCompletionCard`

In `SetupTestAndFinishStep.tsx`:

- replace raw success/error booleans with a structured `outcome` prop
- render distinct next actions for:
  - dry-run no match
  - dry-run failure
  - live unavailable
  - live sent
  - live success

Create `PersonaSetupHandoffCard.tsx` with tab-aware actions and dismiss support.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/PersonaSetupHandoffCard.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx apps/packages/ui/src/components/PersonaGarden/SetupTestAndFinishStep.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: add setup test outcomes and post-setup handoff"
```

### Task 6: Add Browser-Level Coverage For Happy Path And Retry Flow

**Status:** Not Started

**Files:**
- Create: `apps/extension/tests/e2e/persona-assistant-setup.spec.ts`
- Modify: `apps/extension/tests/e2e/utils/mock-server.ts`
- Modify: `apps/extension/tests/e2e/utils/connection.ts`

**Step 1: Write the failing test**

Add two Playwright scenarios:

```ts
test("persona assistant setup can resume and finish with dry run", async ({ page }) => {
  ...
})

test("persona assistant setup can recover from a starter-command or dry-run failure", async ({ page }) => {
  ...
})
```

Scenario 1 should verify:

- incomplete persona is gated into setup
- progress rail updates across steps
- completion lands on the intended target tab
- handoff card appears

Scenario 2 should verify:

- one setup step fails
- the step-local error renders
- retry succeeds
- setup still completes

**Step 2: Run test to verify it fails**

Run:

```bash
bunx playwright test apps/extension/tests/e2e/persona-assistant-setup.spec.ts --reporter=line
```

Expected: FAIL because the flow and selectors do not yet exist.

**Step 3: Write minimal implementation**

Use the existing extension-side E2E utilities to:

- seed an incomplete persona response
- drive Persona Garden into setup gating
- stub one failure response for the retry scenario
- keep selectors stable with `data-testid` where needed

Avoid covering every branch in Playwright. The goal is one happy path and one retry path only.

**Step 4: Run tests to verify they pass**

Run:

```bash
bunx playwright test apps/extension/tests/e2e/persona-assistant-setup.spec.ts --reporter=line
```

Expected: PASS.

Then run focused regressions:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupStatusCard.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupStarterCommandsStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupSafetyConnectionsStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/SetupTestAndFinishStep.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/PersonaSetupHandoffCard.test.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_profiles_api.py -q
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/schemas/persona.py -f json -o /tmp/bandit_persona_setup_experience.json
git diff --check
```

Expected:

- Playwright PASS
- Vitest PASS
- pytest PASS
- Bandit clean for touched backend schema scope
- `git diff --check` clean

**Step 5: Commit**

```bash
git add apps/extension/tests/e2e/persona-assistant-setup.spec.ts apps/extension/tests/e2e/utils/mock-server.ts apps/extension/tests/e2e/utils/connection.ts
git commit -m "test: add persona setup wizard e2e coverage"
```

### Task 7: Final PR2 Verification And Plan Closeout

**Files:**
- Modify: `Docs/Plans/2026-03-13-persona-assistant-setup-experience-polish-implementation-plan.md`

**Step 1: Mark each task complete**

Update this plan file so each task is marked complete as it lands.

**Step 2: Run final verification**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__ apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_profiles_api.py -q
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/schemas/persona.py -f json -o /tmp/bandit_persona_setup_experience_final.json
git diff --check
```

Expected:

- Persona Garden setup suites PASS
- backend persona profile tests PASS
- Bandit clean on touched backend scope
- no diff-check issues

**Step 3: Commit the closeout**

```bash
git add Docs/Plans/2026-03-13-persona-assistant-setup-experience-polish-implementation-plan.md
git commit -m "docs: mark setup experience polish plan complete"
```
