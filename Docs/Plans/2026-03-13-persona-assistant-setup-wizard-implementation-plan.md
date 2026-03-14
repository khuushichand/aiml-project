# Persona Assistant Setup Wizard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a persona-scoped first-run Assistant Setup wizard inside Persona Garden that requires explicit persona choice and one recorded successful test before setup is marked complete.

**Architecture:** Persist setup progress on the persona profile, gate the existing Persona Garden route with a setup overlay, and drive each step through existing persona resources instead of creating a parallel assistant model. Reuse current voice-default, command, connection, and test APIs wherever possible, and keep the wizard state machine in a dedicated hook rather than inline in the route.

**Tech Stack:** FastAPI, Pydantic, existing `CharactersRAGDB` persona storage, React, Ant Design, React Router, existing Persona Garden route/hooks, Vitest, pytest.

**Execution Status:** Complete

---

### Task 1: Add persona setup metadata to the backend profile model [Complete]

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/persona.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/persona.py`
- Test: `tldw_Server_API/tests/Persona/test_persona_profiles_api.py`

**Step 1: Write the failing test**

Add backend tests that:

- create a persona and assert the response contains a default setup object
- patch a persona with updated setup progress and assert round-trip persistence
- mark setup complete and assert `last_test_type` and `completed_at` are returned

Example assertions:

```python
assert payload["setup"]["status"] == "not_started"
assert payload["setup"]["current_step"] == "persona"
assert payload["setup"]["last_test_type"] is None
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_profiles_api.py -q
```

Expected: FAIL because the profile schema/response does not yet expose setup metadata.

**Step 3: Write minimal implementation**

Implement:

- a new setup schema in `persona.py`
- default setup values on persona create/list/get
- DB persistence in persona profile storage
- patch support for updating setup progress/completion

Keep the setup object small:

- `status`
- `version`
- `current_step`
- `completed_at`
- `last_test_type`

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_profiles_api.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/persona.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/tests/Persona/test_persona_profiles_api.py
git commit -m "feat: add persona setup metadata"
```

### Task 2: Add route-owned setup gating and baseline hook wiring [Complete]

**Files:**
- Create: `apps/packages/ui/src/hooks/usePersonaSetupWizard.ts`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Test: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing test**

Add route tests that:

- render the setup overlay when the selected persona profile has `setup.status !== "completed"`
- preserve the requested tab from route bootstrap
- stop gating when the persona reports `setup.status === "completed"`

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: FAIL because no setup overlay or gating exists yet.

**Step 3: Write minimal implementation**

Implement a small hook that derives:

- `isSetupRequired`
- `currentSetupStep`
- `postSetupTargetTab`
- step-advance helpers

In the route:

- load setup metadata from the selected persona profile
- preserve the requested tab from search/bootstrap
- render a setup overlay ahead of normal tab content when required

Do not inline another large state machine directly in the route body.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/usePersonaSetupWizard.ts apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: gate persona garden with assistant setup state"
```

### Task 3: Build the wizard shell and explicit persona-choice step [Complete]

**Files:**
- Create: `apps/packages/ui/src/components/PersonaGarden/AssistantSetupWizard.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx`

**Step 1: Write the failing test**

Add component tests that verify:

- the wizard shows a persona-choice step first
- an existing default persona must still be explicitly selected
- the user can choose `Create new persona` and submit a new persona name
- the wizard does not auto-advance without an explicit choice

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx
```

Expected: FAIL because the wizard shell and step do not exist.

**Step 3: Write minimal implementation**

Implement the wizard shell and step-one UI:

- list existing personas
- explicit `Use this persona`
- minimal `Create new persona` flow
- persist `setup.status = "in_progress"` and `current_step = "voice"` after success

Keep the wizard small and staged. Do not duplicate the full catalog route.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/AssistantSetupWizard.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx
git commit -m "feat: add explicit persona choice setup step"
```

### Task 4: Reuse saved voice defaults in the setup voice step [Complete]

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/AssistantDefaultsPanel.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/PersonaTurnDetectionControls.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/AssistantSetupWizard.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx`

**Step 1: Write the failing test**

Add tests that verify:

- the voice step shows saved-default controls for future sessions
- saving the step updates `voice_defaults`
- the wizard advances only after a successful save

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx
```

Expected: FAIL because the wizard does not yet reuse these controls.

**Step 3: Write minimal implementation**

Extract or reuse the smallest shared controls needed for:

- trigger phrases
- STT/TTS defaults
- confirmation mode
- turn detection defaults

Keep the setup step focused on saved defaults for future sessions. Do not attach it to live-session state.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/AssistantDefaultsPanel.tsx apps/packages/ui/src/components/PersonaGarden/PersonaTurnDetectionControls.tsx apps/packages/ui/src/components/PersonaGarden/AssistantSetupWizard.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx
git commit -m "feat: add assistant setup voice defaults step"
```

### Task 5: Add the starter-commands step using existing persona command APIs [Complete]

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/AssistantSetupWizard.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx`

**Step 1: Write the failing test**

Add tests that verify:

- the wizard can add a starter command from a template
- MCP-backed suggestions can be shown or selected
- the user may continue with no command only after making an explicit choice

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx
```

Expected: FAIL because the wizard does not yet create starter commands.

**Step 3: Write minimal implementation**

Reuse current command-template logic and MCP picker support. The wizard should:

- offer a curated shortlist
- save through the existing persona voice-command endpoint
- avoid cloning the advanced editor

Persist `setup.current_step = "safety"` after the user either adds a command or explicitly chooses to continue without one.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/AssistantSetupWizard.tsx apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx
git commit -m "feat: add starter commands setup step"
```

### Task 6: Add the explicit safety-and-connections step [Complete]

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/AssistantSetupWizard.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/ConnectionsPanel.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx`

**Step 1: Write the failing test**

Add tests that verify:

- the step requires an explicit approval/confirmation choice
- optional connection creation works through existing APIs
- the user can explicitly choose “no external connections for now”
- the wizard persists `current_step = "test"` after success

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx
```

Expected: FAIL because the safety/connections step does not exist.

**Step 3: Write minimal implementation**

Implement:

- explicit confirmation-mode choice
- optional connection creation using current connection APIs
- a clear explicit “not now” path

Do not duplicate the full connections management surface.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/AssistantSetupWizard.tsx apps/packages/ui/src/components/PersonaGarden/ConnectionsPanel.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx
git commit -m "feat: add safety and connections setup step"
```

### Task 7: Add the required test-and-finish step with explicit test type recording [Complete]

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/persona.py`
- Modify: `tldw_Server_API/tests/Persona/test_persona_profiles_api.py`
- Modify: `apps/packages/ui/src/components/PersonaGarden/AssistantSetupWizard.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx`
- Test: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing test**

Add tests that verify:

- the wizard does not complete without a recorded success
- a successful dry-run can mark setup complete and stores `last_test_type = "dry_run"`
- a successful live-session turn can mark setup complete and stores `last_test_type = "live_session"`
- after completion, the route restores the preserved target tab

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_profiles_api.py -q
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: FAIL because setup completion is not yet tied to an explicit test outcome.

**Step 3: Write minimal implementation**

Implement:

- explicit test completion action in the wizard
- backend profile update support for `last_test_type` and `completed_at`
- route behavior to restore the intended tab after successful completion

Dry-run completion should reuse the existing persona command test endpoint. Live-session completion should hook into the current live persona success path rather than inventing a second transport.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_profiles_api.py -q
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/tests/Persona/test_persona_profiles_api.py apps/packages/ui/src/components/PersonaGarden/AssistantSetupWizard.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: require successful test for assistant setup completion"
```

### Task 8: Regression, verification, and docs cleanup [Complete]

**Files:**
- Modify: `Docs/Plans/2026-03-13-persona-assistant-setup-wizard-implementation-plan.md`
- Test: `tldw_Server_API/tests/Persona/test_persona_profiles_api.py`
- Test: `tldw_Server_API/tests/Persona/test_persona_command_test_api.py`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx`
- Test: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Run focused verification**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_profiles_api.py tldw_Server_API/tests/Persona/test_persona_command_test_api.py -q
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantSetupWizard.test.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 2: Run broader Persona Garden regression**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/PersonaGarden/__tests__ apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 3: Run security and consistency checks**

Run:

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/app/api/v1/schemas/persona.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py -f json -o /tmp/bandit_persona_setup_wizard.json
git diff --check
```

Expected: no new Bandit findings in touched code, and a clean diff check.

**Step 4: Mark the plan complete**

Update this plan file so each task reflects completed execution.

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-13-persona-assistant-setup-wizard-implementation-plan.md
git commit -m "docs: mark assistant setup wizard plan complete"
```
