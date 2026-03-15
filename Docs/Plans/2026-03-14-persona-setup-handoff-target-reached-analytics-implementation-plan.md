# Persona Setup Handoff Target Reached Analytics Implementation Plan

**Goal:** Record when setup handoff actions actually land on their intended
panel sections, and extend persona setup analytics summaries with reach metrics.

**Architecture:** Keep this slice analytics-only. Emit a route-owned
`handoff_target_reached` event when a handoff focus token is consumed, dedupe
it by concrete target identity, and aggregate both run-level and per-target
reach metrics in the existing setup analytics summary.

**Tech Stack:** React, TypeScript, Vitest, FastAPI, Pydantic, SQLite, Pytest.

---

### Task 1: Extend Setup Analytics Event Types And Keys

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/persona-setup-analytics.ts`
- Modify: `apps/packages/ui/src/services/tldw/__tests__/persona-setup-analytics.test.ts`
- Modify: `tldw_Server_API/app/api/v1/schemas/persona.py`

**Step 1: Write the failing frontend key tests**

Add tests proving:

- `handoff_target_reached` builds a stable key from `actionTarget`
- `connections.saved_connections` can include item identity

Example:

```ts
expect(
  buildSetupEventKey({
    eventType: "handoff_target_reached",
    actionTarget: "commands.command_form"
  })
).toBe("handoff_target_reached:commands.command_form")
```

And:

```ts
expect(
  buildSetupEventKey({
    eventType: "handoff_target_reached",
    actionTarget: "connections.saved_connections",
    metadata: { connection_id: "conn-123" }
  })
).toBe("handoff_target_reached:connections.saved_connections:conn-123")
```

**Step 2: Run the focused frontend service tests**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/services/tldw/__tests__/persona-setup-analytics.test.ts
```

Expected: FAIL until the helper supports the new event type.

**Step 3: Extend the shared event types**

Add `handoff_target_reached` to:

- frontend `PersonaSetupAnalyticsEventType`
- backend `PersonaSetupEventType`

Extend the frontend helper so `buildSetupEventKey(...)` accepts:

- `actionTarget`
- `metadata`

for this event type and returns the target-aware key.

**Step 4: Re-run the focused frontend tests**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/services/tldw/__tests__/persona-setup-analytics.test.ts
```

Expected: PASS.

### Task 2: Emit Route-Owned `handoff_target_reached`

**Files:**
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing route tests**

Add tests proving:

- consuming a matching handoff token posts `handoff_target_reached`
- repeated consume paths do not post duplicate events

Use existing handoff-target route flows and assert on setup-event POST bodies.

**Step 2: Run the focused route tests**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "handoff_target_reached|does not duplicate handoff target reach"
```

Expected: FAIL until the route emits the new event.

**Step 3: Add route-side snapshot emission**

In `sidepanel-persona.tsx`:

- snapshot the matched `setupHandoffFocusRequest` before clearing it
- build:
  - `actionTarget = ${tab}.${section}`
  - metadata from optional item detail plus current handoff context
- emit `handoff_target_reached`
- clear the request afterward

Do not emit for `live`.

**Step 4: Re-run the focused route tests**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "handoff_target_reached|does not duplicate handoff target reach"
```

Expected: PASS.

### Task 3: Extend Backend Setup Analytics Aggregation

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/persona.py`
- Modify: `tldw_Server_API/tests/Persona/test_persona_setup_analytics_api.py`

**Step 1: Write the failing backend tests**

Add API coverage proving:

- the endpoint accepts `handoff_target_reached`
- summaries include:
  - run-level `handoff_target_reached`
  - `handoff_target_reach_rate`
  - `handoff_target_reached_counts`

**Step 2: Run the focused backend tests**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/tldw_Server_API/tests/Persona/test_persona_setup_analytics_api.py -q
```

Expected: FAIL until the backend schema and aggregation are updated.

**Step 3: Update backend summaries**

In the setup analytics aggregation:

- track run-level `handoff_target_reached`
- track unique reached targets per run
- accumulate summary counts by `action_target`
- compute `handoff_target_reach_rate` as:
  - `runs_with_target_reached / runs_with_handoff_clicked`

Extend the response schemas to expose the new fields.

**Step 4: Re-run the focused backend tests**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/tldw_Server_API/tests/Persona/test_persona_setup_analytics_api.py -q
```

Expected: PASS.

### Task 4: Run Final Verification

**Files:**
- Modify: `Docs/Plans/2026-03-14-persona-setup-handoff-target-reached-analytics-implementation-plan.md`

**Step 1: Run focused frontend verification**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui && bunx vitest run src/services/tldw/__tests__/persona-setup-analytics.test.ts src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 2: Run focused backend verification**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/tldw_Server_API/tests/Persona/test_persona_setup_analytics_api.py -q
```

Expected: PASS.

**Step 3: Run static verification**

Run:

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder diff --check
```

Then:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui/src/routes /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/apps/packages/ui/src/services/tldw /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/tldw_Server_API/app/api/v1/schemas /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/persona-voice-assistant-builder/tldw_Server_API/app/core/DB_Management -f json -o /tmp/bandit_persona_handoff_target_reached.json
```

Expected:

- `git diff --check` clean
- no new Bandit findings in changed source files

**Step 4: Mark the plan complete and commit**

Add a top-line completion note to this plan, then commit the slice.

