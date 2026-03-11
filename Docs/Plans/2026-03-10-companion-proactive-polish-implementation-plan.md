# Companion Proactive Polish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve companion reflection delivery quality and add explicit follow-up prompts after reflection open and inside companion conversation, without adding ambient prompts or hidden capture.

**Architecture:** Extend the existing Jobs-backed reflection flow with persisted delivery-policy metadata and deterministic follow-up prompt generation. Expose those prompts through reflection detail and a dedicated companion conversation prompt source, then wire the UI to render prompt chips only on the reflection surface and `/companion/conversation`.

**Tech Stack:** FastAPI, Pydantic, SQLite/WAL (`PersonalizationDB`), Jobs/APScheduler, React, React Router, Vitest, Playwright, pytest.

---

### Task 1: Persist Reflection Delivery Metadata And Prompt Payloads

**Files:**
- Modify: `tldw_Server_API/app/core/Personalization/companion_reflection_jobs.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/companion.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/companion.py`
- Test: `tldw_Server_API/tests/Personalization/test_companion_reflection_jobs.py`
- Test: `tldw_Server_API/tests/Personalization/test_companion_api.py`

**Step 1: Write the failing tests**

```python
def test_companion_reflection_job_persists_delivery_metadata_and_prompts(companion_env):
    result = run_companion_reflection_job(
        user_id="1",
        cadence="daily",
        personalization_db=companion_env.personalization_db,
        collections_db=companion_env.collections_db,
    )

    reflection = companion_env.personalization_db.get_companion_activity_event("1", result["reflection_id"])

    assert reflection["metadata"]["delivery_decision"] == "delivered"
    assert reflection["metadata"]["theme_key"]
    assert reflection["metadata"]["signal_strength"] >= 1
    assert reflection["metadata"]["follow_up_prompts"]


def test_companion_reflection_detail_exposes_delivery_metadata_and_prompt_payload(client, companion_api_env):
    reflection_id = seed_companion_reflection_with_prompt_metadata(companion_api_env)

    response = client.get(f"/api/v1/companion/reflections/{reflection_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["delivery_decision"] == "delivered"
    assert payload["follow_up_prompts"][0]["prompt_text"]
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/Personalization/test_companion_reflection_jobs.py \
  tldw_Server_API/tests/Personalization/test_companion_api.py -k "reflection_detail or delivery_metadata"
```

Expected: FAIL because reflections do not yet persist delivery metadata or follow-up prompts.

**Step 3: Write minimal implementation**

- Extend reflection metadata generation in `companion_reflection_jobs.py` to include:
  - `delivery_decision`
  - `delivery_reason`
  - `theme_key`
  - `signal_strength`
  - `follow_up_prompts`
- Extend the companion reflection detail and item schemas in `companion.py`.
- Expose the new fields from the reflection detail endpoint.

**Step 4: Run tests to verify they pass**

Run the same pytest command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/Personalization/companion_reflection_jobs.py \
  tldw_Server_API/app/api/v1/schemas/companion.py \
  tldw_Server_API/app/api/v1/endpoints/companion.py \
  tldw_Server_API/tests/Personalization/test_companion_reflection_jobs.py \
  tldw_Server_API/tests/Personalization/test_companion_api.py
git commit -m "feat: persist companion reflection delivery metadata"
```

### Task 2: Add Deterministic Proactive Delivery Policy And Suppression

**Files:**
- Create: `tldw_Server_API/app/core/Personalization/companion_proactive.py`
- Modify: `tldw_Server_API/app/core/Personalization/companion_reflection_jobs.py`
- Modify: `tldw_Server_API/tests/Notifications/test_companion_reflection_notifications.py`
- Test: `tldw_Server_API/tests/Personalization/test_companion_proactive_policy.py`
- Test: `tldw_Server_API/tests/Notifications/test_companion_reflection_notifications.py`

**Step 1: Write the failing tests**

```python
def test_companion_proactive_policy_suppresses_low_signal_duplicate_theme():
    decision = classify_companion_reflection_delivery(
        cadence="daily",
        activity_count=2,
        theme_key="backlog-review",
        signal_strength=1.0,
        recent_reflections=[{"theme_key": "backlog-review", "signal_strength": 0.9, "delivery_decision": "delivered"}],
    )

    assert decision["delivery_decision"] == "suppressed"
    assert decision["delivery_reason"] == "duplicate_weak_delta"


def test_companion_reflection_job_persists_suppressed_reflection_without_notification(companion_env):
    result = run_companion_reflection_job(
        user_id="1",
        cadence="daily",
        personalization_db=companion_env.personalization_db,
        collections_db=companion_env.collections_db,
    )

    if result["status"] == "completed":
        assert result["delivery_decision"] == "suppressed"
        notifications = companion_env.collections_db.list_notifications(user_id=1)
        assert all(item["link_id"] != result["reflection_id"] for item in notifications["items"])
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/Personalization/test_companion_proactive_policy.py \
  tldw_Server_API/tests/Notifications/test_companion_reflection_notifications.py
```

Expected: FAIL because proactive delivery policy and suppression are not implemented yet.

**Step 3: Write minimal implementation**

- Create `companion_proactive.py` with deterministic helpers for:
  - `theme_key`
  - `signal_strength`
  - `delivery_decision`
  - `delivery_reason`
- Update `run_companion_reflection_job(...)` to:
  - persist the decision on the reflection activity metadata
  - skip notification creation when the decision is `suppressed`
  - keep `low_priority` as persisted metadata/badging only for now
- Keep suppression theme-local and resettable on meaningful signal changes.

**Step 4: Run tests to verify they pass**

Run the same pytest command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/Personalization/companion_proactive.py \
  tldw_Server_API/app/core/Personalization/companion_reflection_jobs.py \
  tldw_Server_API/tests/Personalization/test_companion_proactive_policy.py \
  tldw_Server_API/tests/Notifications/test_companion_reflection_notifications.py
git commit -m "feat: add companion proactive delivery policy"
```

### Task 3: Add Companion Follow-Up Prompt Generation And Conversation Prompt Source

**Files:**
- Create: `tldw_Server_API/app/core/Personalization/companion_followups.py`
- Modify: `tldw_Server_API/app/core/Personalization/companion_context.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/companion.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/companion.py`
- Test: `tldw_Server_API/tests/Personalization/test_companion_followups.py`
- Test: `tldw_Server_API/tests/Persona/test_companion_context_ranking.py`
- Test: `tldw_Server_API/tests/Personalization/test_companion_api.py`

**Step 1: Write the failing tests**

```python
def test_build_companion_conversation_prompts_prefers_relevant_delivered_reflection():
    payload = build_companion_conversation_prompts(
        query="help me decide the next step on backlog review",
        delivered_reflections=[seed_reflection(theme_key="backlog-review")],
        suppressed_reflections=[],
        context_cards=[],
        context_goals=[],
        context_activity=[],
    )

    assert payload["prompt_source_kind"] == "reflection"
    assert payload["prompts"][0]["source_reflection_id"]


def test_companion_conversation_prompts_endpoint_returns_at_most_three_prompts(client, companion_api_env):
    response = client.get("/api/v1/companion/conversation-prompts", params={"query": "resume backlog review"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["prompts"]) <= 3
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/Personalization/test_companion_followups.py \
  tldw_Server_API/tests/Persona/test_companion_context_ranking.py \
  tldw_Server_API/tests/Personalization/test_companion_api.py -k "conversation_prompts"
```

Expected: FAIL because prompt generation and conversation prompt sourcing do not exist yet.

**Step 3: Write minimal implementation**

- Create `companion_followups.py` for deterministic prompt families and source ids.
- Add a companion endpoint for conversation prompt sourcing, for example:
  - `GET /api/v1/companion/conversation-prompts`
- Apply the source precedence:
  - delivered reflection
  - suppressed high-signal reflection
  - direct ranked companion context
- Return `prompt_source_kind`, `prompt_source_id`, and up to 3 prompts.

**Step 4: Run tests to verify they pass**

Run the same pytest command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/Personalization/companion_followups.py \
  tldw_Server_API/app/core/Personalization/companion_context.py \
  tldw_Server_API/app/api/v1/schemas/companion.py \
  tldw_Server_API/app/api/v1/endpoints/companion.py \
  tldw_Server_API/tests/Personalization/test_companion_followups.py \
  tldw_Server_API/tests/Persona/test_companion_context_ranking.py \
  tldw_Server_API/tests/Personalization/test_companion_api.py
git commit -m "feat: add companion follow-up prompt sourcing"
```

### Task 4: Add Reflection Follow-Up Prompts To The Workspace Surface

**Files:**
- Modify: `apps/packages/ui/src/services/companion.ts`
- Modify: `apps/packages/ui/src/components/Option/Companion/CompanionPage.tsx`
- Test: `apps/packages/ui/src/services/__tests__/companion.test.ts`
- Test: `apps/packages/ui/src/routes/__tests__/option-companion.test.tsx`
- Test: `apps/packages/ui/src/routes/__tests__/sidepanel-companion.test.tsx`

**Step 1: Write the failing tests**

```tsx
it("shows follow-up prompts when a reflection is opened", async () => {
  renderOptionCompanionPage()

  await user.click(await screen.findByRole("button", { name: /open reflection/i }))

  expect(await screen.findByText(/follow-up prompts/i)).toBeInTheDocument()
  expect(screen.getByRole("button", { name: /next concrete step/i })).toBeInTheDocument()
})


it("does not render standalone prompt chips on the default workspace surface", async () => {
  renderOptionCompanionPage()

  expect(screen.queryByText(/follow-up prompts/i)).not.toBeInTheDocument()
})
```

**Step 2: Run tests to verify they fail**

Run from `apps/packages/ui`:

```bash
bunx vitest run --config vitest.config.ts \
  src/services/__tests__/companion.test.ts \
  src/routes/__tests__/option-companion.test.tsx \
  src/routes/__tests__/sidepanel-companion.test.tsx
```

Expected: FAIL because the reflection surface does not yet render follow-up prompts.

**Step 3: Write minimal implementation**

- Extend `companion.ts` reflection types with:
  - delivery metadata
  - follow-up prompt payloads
- Update `CompanionPage.tsx` to:
  - treat reflection open as a distinct reflection detail surface
  - render follow-up prompts only after a reflection is opened
  - keep provenance as supporting explanation, not the only access path
- Do not render standalone prompt chips on the workspace home.

**Step 4: Run tests to verify they pass**

Run the same Vitest command from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/services/companion.ts \
  apps/packages/ui/src/components/Option/Companion/CompanionPage.tsx \
  apps/packages/ui/src/services/__tests__/companion.test.ts \
  apps/packages/ui/src/routes/__tests__/option-companion.test.tsx \
  apps/packages/ui/src/routes/__tests__/sidepanel-companion.test.tsx
git commit -m "feat: add companion reflection follow-up prompts"
```

### Task 5: Add Companion Conversation Prompt Chips

**Files:**
- Modify: `apps/packages/ui/src/services/companion.ts`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Test: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Test: `apps/packages/ui/src/services/__tests__/companion.test.ts`
- Test: `apps/extension/tests/e2e/companion.spec.ts`

**Step 1: Write the failing tests**

```tsx
it("renders companion conversation prompt chips and inserts text into the draft", async () => {
  renderCompanionConversation()

  const chip = await screen.findByRole("button", { name: /next concrete step/i })
  await user.click(chip)

  expect(screen.getByRole("textbox")).toHaveValue("What is the next concrete step")
})


it("does not auto-send when a companion prompt chip is clicked", async () => {
  renderCompanionConversation()

  await user.click(await screen.findByRole("button", { name: /summarize what changed/i }))

  expect(mockWebSocketSend).not.toHaveBeenCalled()
})
```

**Step 2: Run tests to verify they fail**

Run from `apps/packages/ui`:

```bash
bunx vitest run --config vitest.config.ts \
  src/services/__tests__/companion.test.ts \
  src/routes/__tests__/sidepanel-persona.test.tsx
```

Then run from `apps/extension`:

```bash
bunx playwright test tests/e2e/companion.spec.ts --reporter=line
```

Expected: FAIL because companion conversation prompt chips do not exist yet.

**Step 3: Write minimal implementation**

- Extend the companion service with a conversation prompt fetch call.
- Update `sidepanel-persona.tsx` in companion mode to:
  - request prompt chips when companion conversation is active
  - render up to 3 chips
  - insert the prompt into the draft only
  - avoid auto-send and avoid logging prompt insertion as activity

**Step 4: Run tests to verify they pass**

Run the same Vitest and Playwright commands from Step 2.

Expected: PASS

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/services/companion.ts \
  apps/packages/ui/src/routes/sidepanel-persona.tsx \
  apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx \
  apps/packages/ui/src/services/__tests__/companion.test.ts \
  apps/extension/tests/e2e/companion.spec.ts
git commit -m "feat: add companion conversation follow-up prompts"
```

### Task 6: Run Final Verification And Update Docs

**Files:**
- Modify: `Docs/Plans/2026-03-10-companion-proactive-polish-design.md`
- Modify: `Docs/Plans/2026-03-10-companion-proactive-polish-implementation-plan.md`
- Modify: `Docs/Plans/2026-03-10-companion-proactive-polish-placeholder.md`

**Step 1: Run backend verification**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/Personalization/test_companion_reflection_jobs.py \
  tldw_Server_API/tests/Personalization/test_companion_proactive_policy.py \
  tldw_Server_API/tests/Personalization/test_companion_followups.py \
  tldw_Server_API/tests/Personalization/test_companion_api.py \
  tldw_Server_API/tests/Persona/test_companion_context_ranking.py \
  tldw_Server_API/tests/Notifications/test_companion_reflection_notifications.py
```

Expected: PASS

**Step 2: Run frontend verification**

Run from `apps/packages/ui`:

```bash
bunx vitest run --config vitest.config.ts \
  src/services/__tests__/companion.test.ts \
  src/routes/__tests__/option-companion.test.tsx \
  src/routes/__tests__/sidepanel-companion.test.tsx \
  src/routes/__tests__/sidepanel-persona.test.tsx
```

Then run from `apps/extension`:

```bash
bunx playwright test tests/e2e/companion.spec.ts --reporter=line
```

Expected: PASS

**Step 3: Run security and diff checks**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/companion.py \
  tldw_Server_API/app/core/Personalization \
  -f json -o /tmp/bandit_companion_proactive_polish.json

git diff --check
```

Expected: no new Bandit findings in touched code, and clean diff output.

**Step 4: Update status notes**

- Mark this design and plan complete.
- Update the proactive placeholder to point at the active design and plan.
- Record any deferred follow-ups that remain out of scope.

**Step 5: Commit**

```bash
git add \
  Docs/Plans/2026-03-10-companion-proactive-polish-design.md \
  Docs/Plans/2026-03-10-companion-proactive-polish-implementation-plan.md \
  Docs/Plans/2026-03-10-companion-proactive-polish-placeholder.md
git commit -m "docs: finalize companion proactive polish plan"
```
