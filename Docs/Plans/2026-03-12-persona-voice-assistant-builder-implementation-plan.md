# Persona Voice Assistant Builder Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the existing Persona module so each persona can own a voice-command library, reusable external connections, and a first-class test lab for deterministic voice actions with safe fallback to persona planning.

**Architecture:** Keep Persona as the only top-level assistant container. Extend the current voice-command stack so commands are persona-scoped and can be tested through a dry-run pipeline, then surface that capability inside the shared `sidepanel-persona` route as new `Commands`, `Test Lab`, and `Connections` tabs. Deterministic command matching runs first; when no command matches, the request falls back to the existing Persona planner/live session flow.

**Tech Stack:** FastAPI, Pydantic, SQLite via `CharactersRAGDB`, shared React route/components in `apps/packages/ui`, TanStack/route-local fetches via `tldwClient`, Vitest, pytest, Bandit.

---

## Pre-Work

Read these files before touching code:

- `Docs/Plans/2026-03-12-persona-voice-assistant-builder-design.md`
- `Docs/Product/Persona_Agent_Design.md`
- `tldw_Server_API/app/api/v1/endpoints/persona.py`
- `tldw_Server_API/app/api/v1/endpoints/voice_assistant.py`
- `tldw_Server_API/app/core/VoiceAssistant/db_helpers.py`
- `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- `apps/packages/ui/src/routes/sidepanel-persona.tsx`

Use TDD for each task. Keep commits small. Do not touch unrelated modified files in the worktree.

### Task 1: Add Persona-Scoped Voice Command Persistence

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Modify: `tldw_Server_API/app/core/VoiceAssistant/db_helpers.py`
- Modify: `tldw_Server_API/app/core/VoiceAssistant/schemas.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/voice_assistant_schemas.py`
- Test: `tldw_Server_API/tests/ChaChaNotesDB/test_persona_persistence_db.py`
- Create: `tldw_Server_API/tests/VoiceAssistant/test_persona_voice_command_persistence.py`

**Step 1: Write the failing persistence tests**

Add DB-level and helper-level tests that prove:

- a voice command can be created with `persona_id`
- listing commands can filter by `persona_id`
- the same user can have different commands under different personas
- command records can optionally reference `connection_id`
- commands without `persona_id` are treated as legacy rows and do not leak into persona-filtered queries

Example fixture shape to lock in:

```python
command = {
    "id": "cmd-1",
    "user_id": 1,
    "persona_id": "builder_bot",
    "name": "Search notes",
    "phrases": ["search notes for {topic}"],
    "action_type": "mcp_tool",
    "action_config": {"tool_name": "notes.search"},
    "priority": 10,
    "enabled": True,
    "requires_confirmation": False,
    "description": "Find notes by topic",
    "connection_id": None,
}
```

**Step 2: Run the targeted tests to verify failure**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/ChaChaNotesDB/test_persona_persistence_db.py -k voice -v
python -m pytest tldw_Server_API/tests/VoiceAssistant/test_persona_voice_command_persistence.py -v
```

Expected:

- failures for missing columns, missing filters, or missing helper arguments

**Step 3: Write the minimal persistence implementation**

Update the DB schema and helper contracts so persona scoping is a first-class attribute.

Concrete changes:

- add `persona_id` and `connection_id` columns to the voice-command storage table
- add an index that supports `(user_id, persona_id, enabled)` lookups
- update read/write helpers to accept `persona_id`
- extend internal schemas so `VoiceCommand` carries `persona_id` and optional `connection_id`
- extend API schemas to expose those fields without breaking legacy callers

Target signatures to implement:

```python
def save_voice_command(db, command: VoiceCommand) -> str: ...
def get_voice_command_db(db, command_id: str, user_id: int, persona_id: str | None = None): ...
def get_all_voice_commands(db, user_id: int, persona_id: str | None = None, include_disabled: bool = False): ...
```

**Step 4: Re-run the targeted tests**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/ChaChaNotesDB/test_persona_persistence_db.py -k voice -v
python -m pytest tldw_Server_API/tests/VoiceAssistant/test_persona_voice_command_persistence.py -v
```

Expected:

- all new tests pass

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
  tldw_Server_API/app/core/VoiceAssistant/db_helpers.py \
  tldw_Server_API/app/core/VoiceAssistant/schemas.py \
  tldw_Server_API/app/api/v1/schemas/voice_assistant_schemas.py \
  tldw_Server_API/tests/ChaChaNotesDB/test_persona_persistence_db.py \
  tldw_Server_API/tests/VoiceAssistant/test_persona_voice_command_persistence.py
git commit -m "feat: persist persona scoped voice commands"
```

### Task 2: Add Persona-Scoped Command, Connection, and Dry-Run APIs

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/persona.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/voice_assistant.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/persona.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/voice_assistant_schemas.py`
- Modify: `tldw_Server_API/app/core/VoiceAssistant/router.py`
- Modify: `tldw_Server_API/app/core/VoiceAssistant/intent_parser.py`
- Create: `tldw_Server_API/tests/Persona/test_persona_voice_commands_api.py`
- Create: `tldw_Server_API/tests/Persona/test_persona_connections_api.py`
- Create: `tldw_Server_API/tests/Persona/test_persona_command_test_api.py`

**Step 1: Write the failing API tests**

Add tests for these persona-scoped endpoints:

- `GET /api/v1/persona/profiles/{persona_id}/voice-commands`
- `POST /api/v1/persona/profiles/{persona_id}/voice-commands`
- `PUT /api/v1/persona/profiles/{persona_id}/voice-commands/{command_id}`
- `POST /api/v1/persona/profiles/{persona_id}/voice-commands/{command_id}/toggle`
- `DELETE /api/v1/persona/profiles/{persona_id}/voice-commands/{command_id}`
- `GET /api/v1/persona/profiles/{persona_id}/connections`
- `POST /api/v1/persona/profiles/{persona_id}/connections`
- `POST /api/v1/persona/profiles/{persona_id}/voice-commands/test`

Lock in the dry-run response shape:

```python
{
    "heard_text": "search notes for vector databases",
    "matched": True,
    "match_reason": "phrase_pattern",
    "command_id": "cmd-1",
    "command_name": "Search notes",
    "extracted_params": {"topic": "vector databases"},
    "planned_action": {
        "target_type": "mcp_tool",
        "target_name": "notes.search",
        "payload_preview": {"query": "vector databases"},
    },
    "safety_gate": {
        "classification": "read_only",
        "requires_confirmation": False,
        "reason": "persona_default",
    },
    "fallback_to_persona_planner": False,
}
```

Also add a no-match case that returns:

```python
{
    "matched": False,
    "fallback_to_persona_planner": True,
    "failure_phase": "no_match",
}
```

**Step 2: Run the failing API tests**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Persona/test_persona_voice_commands_api.py -v
python -m pytest tldw_Server_API/tests/Persona/test_persona_connections_api.py -v
python -m pytest tldw_Server_API/tests/Persona/test_persona_command_test_api.py -v
```

Expected:

- 404 or schema failures because the persona-scoped endpoints do not exist yet

**Step 3: Implement the minimal backend APIs**

Implementation rules:

- expose the new command and connection endpoints under Persona, not as a separate assistant module
- wrap or reuse existing voice assistant CRUD instead of duplicating matching logic
- keep connection secrets server-side and return only redacted metadata
- implement slot-based phrase testing only; do not add free-form LLM extraction in V1
- return explicit failure phases from dry-run results

Suggested new Pydantic shapes:

```python
class PersonaConnectionCreate(BaseModel):
    name: str
    base_url: str
    auth_type: str
    secret_ref: str | None = None
    headers_template: dict[str, str] = Field(default_factory=dict)
    timeout_ms: int = 15000

class PersonaCommandDryRunResponse(BaseModel):
    heard_text: str
    matched: bool
    match_reason: str | None = None
    command_id: str | None = None
    command_name: str | None = None
    extracted_params: dict[str, Any] = Field(default_factory=dict)
    planned_action: dict[str, Any] | None = None
    safety_gate: dict[str, Any] | None = None
    fallback_to_persona_planner: bool = False
    failure_phase: str | None = None
```

**Step 4: Re-run the API tests**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Persona/test_persona_voice_commands_api.py -v
python -m pytest tldw_Server_API/tests/Persona/test_persona_connections_api.py -v
python -m pytest tldw_Server_API/tests/Persona/test_persona_command_test_api.py -v
```

Expected:

- all new API tests pass

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/persona.py \
  tldw_Server_API/app/api/v1/endpoints/voice_assistant.py \
  tldw_Server_API/app/api/v1/schemas/persona.py \
  tldw_Server_API/app/api/v1/schemas/voice_assistant_schemas.py \
  tldw_Server_API/app/core/VoiceAssistant/router.py \
  tldw_Server_API/app/core/VoiceAssistant/intent_parser.py \
  tldw_Server_API/tests/Persona/test_persona_voice_commands_api.py \
  tldw_Server_API/tests/Persona/test_persona_connections_api.py \
  tldw_Server_API/tests/Persona/test_persona_command_test_api.py
git commit -m "feat: add persona scoped voice command apis"
```

### Task 3: Add Commands and Connections Tabs To Persona Garden

**Files:**
- Create: `apps/packages/ui/src/services/tldw/persona-assistant.ts`
- Create: `apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx`
- Create: `apps/packages/ui/src/components/PersonaGarden/ConnectionsPanel.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/utils/persona-garden-route.ts`
- Modify: `apps/packages/ui/src/components/PersonaGarden/PersonaGardenTabs.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona-locale-keys.test.ts`
- Modify: `apps/packages/ui/src/assets/locale/en/sidepanel.json`
- Modify: `apps/packages/ui/src/public/_locales/en/sidepanel.json`

**Step 1: Write the failing UI tests**

Cover these cases:

- `Commands` is the default persona tab for normal assistant-building use
- the route can deep-link with `?persona_id=builder_bot&tab=commands`
- starter template CTA is visible
- command list renders safety badges and last-test state
- `Connections` tab renders saved connections and test buttons

Example tab bootstrap assertion:

```tsx
render(<SidepanelPersona />)
expect(screen.getByRole("tab", { name: /commands/i })).toHaveAttribute("aria-selected", "true")
expect(screen.getByText("Create your first command")).toBeInTheDocument()
```

**Step 2: Run the failing UI tests**

Run:

```bash
cd apps/packages/ui
bunx vitest run \
  src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx \
  src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx \
  src/routes/__tests__/sidepanel-persona.test.tsx \
  src/routes/__tests__/sidepanel-persona-locale-keys.test.ts
```

Expected:

- failures because the tabs, service module, and components do not exist yet

**Step 3: Implement the minimal UI**

Concrete changes:

- add a `persona-assistant.ts` service module with typed calls for commands, connections, and dry-run test results
- add `CommandsPanel` with:
  - command list
  - filters
  - template CTA
  - create/edit drawer or inline editor shell
- add `ConnectionsPanel` with:
  - connection list
  - create/edit shell
  - connection test action
- wire both panels into `sidepanel-persona.tsx`
- add new tab keys to `persona-garden-route.ts`
- preserve the current Persona route instead of creating a new top-level route
- add English locale keys first, then mirror required keys anywhere the locale test expects them

Service signatures to implement:

```ts
export async function listPersonaVoiceCommands(personaId: string): Promise<PersonaVoiceCommand[]> { ... }
export async function upsertPersonaVoiceCommand(personaId: string, payload: PersonaVoiceCommandInput): Promise<PersonaVoiceCommand> { ... }
export async function listPersonaConnections(personaId: string): Promise<PersonaConnection[]> { ... }
```

**Step 4: Re-run the UI tests**

Run:

```bash
cd apps/packages/ui
bunx vitest run \
  src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx \
  src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx \
  src/routes/__tests__/sidepanel-persona.test.tsx \
  src/routes/__tests__/sidepanel-persona-locale-keys.test.ts
```

Expected:

- all new tests pass

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/persona-assistant.ts \
  apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx \
  apps/packages/ui/src/components/PersonaGarden/ConnectionsPanel.tsx \
  apps/packages/ui/src/routes/sidepanel-persona.tsx \
  apps/packages/ui/src/utils/persona-garden-route.ts \
  apps/packages/ui/src/components/PersonaGarden/PersonaGardenTabs.tsx \
  apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx \
  apps/packages/ui/src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx \
  apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx \
  apps/packages/ui/src/routes/__tests__/sidepanel-persona-locale-keys.test.ts \
  apps/packages/ui/src/assets/locale/en/sidepanel.json \
  apps/packages/ui/src/public/_locales/en/sidepanel.json
git commit -m "feat: add persona command and connection tabs"
```

### Task 4: Add Test Lab And Persona-Planner Fallback Visibility

**Files:**
- Create: `apps/packages/ui/src/components/PersonaGarden/TestLabPanel.tsx`
- Modify: `apps/packages/ui/src/services/tldw/persona-assistant.ts`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/PersonaGardenTabs.tsx`
- Modify: `tldw_Server_API/app/api/v1/endpoints/persona.py`
- Modify: `tldw_Server_API/app/core/VoiceAssistant/router.py`
- Create: `apps/packages/ui/src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Create: `tldw_Server_API/tests/Persona/test_persona_voice_command_fallback.py`

**Step 1: Write the failing tests**

Add UI and backend tests for:

- dry-run pipeline renders `Heard`, `Matched`, `Extracted`, `Planned Action`, `Safety Gate`, `Execution Result`
- no-match response explicitly shows fallback to persona planner
- a matched command does not show planner fallback
- ambiguous or disabled-command cases surface the correct failure phase

Example UI expectation:

```tsx
expect(screen.getByText("Heard")).toBeInTheDocument()
expect(screen.getByText("Matched")).toBeInTheDocument()
expect(screen.getByText("Fallback to persona planner")).toBeInTheDocument()
```

**Step 2: Run the failing tests**

Run:

```bash
cd apps/packages/ui
bunx vitest run \
  src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx \
  src/routes/__tests__/sidepanel-persona.test.tsx
```

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Persona/test_persona_voice_command_fallback.py -v
```

Expected:

- failures because the test lab tab and fallback visibility do not exist yet

**Step 3: Implement the minimal Test Lab and fallback contract**

Concrete changes:

- add `TestLabPanel` to the persona route
- call the dry-run endpoint through `persona-assistant.ts`
- render per-phase diagnostics instead of a single status blob
- make the fallback state explicit in both UI copy and returned JSON
- keep live persona session behavior intact; this task is about visibility and handoff, not replacing the planner

Minimal UI state shape:

```ts
type PersonaCommandDryRunResult = {
  heardText: string
  matched: boolean
  matchReason?: string | null
  extractedParams: Record<string, unknown>
  plannedAction?: Record<string, unknown> | null
  safetyGate?: Record<string, unknown> | null
  fallbackToPersonaPlanner: boolean
  failurePhase?: string | null
}
```

**Step 4: Re-run the tests**

Run:

```bash
cd apps/packages/ui
bunx vitest run \
  src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx \
  src/routes/__tests__/sidepanel-persona.test.tsx
```

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Persona/test_persona_voice_command_fallback.py -v
```

Expected:

- all new tests pass

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/TestLabPanel.tsx \
  apps/packages/ui/src/services/tldw/persona-assistant.ts \
  apps/packages/ui/src/routes/sidepanel-persona.tsx \
  apps/packages/ui/src/components/PersonaGarden/PersonaGardenTabs.tsx \
  apps/packages/ui/src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx \
  apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx \
  tldw_Server_API/app/api/v1/endpoints/persona.py \
  tldw_Server_API/app/core/VoiceAssistant/router.py \
  tldw_Server_API/tests/Persona/test_persona_voice_command_fallback.py
git commit -m "feat: add persona command test lab"
```

### Task 5: Verification, Security Scan, And Documentation

**Files:**
- Modify: `Docs/Product/Persona_Agent_Design.md`
- Modify: `Docs/Product/STT-LLM-TTS-PRD.md` if it references persona voice flow behavior directly
- Modify: `apps/packages/ui/src/assets/locale/*/sidepanel.json` as needed
- Modify: `apps/packages/ui/src/public/_locales/*/sidepanel.json` as needed

**Step 1: Update product docs**

Document:

- persona-bound command libraries
- deterministic command fast-path before planner fallback
- reusable connection records
- safe-by-default external action policy

Keep the docs concise and consistent with the approved design doc.

**Step 2: Run the full targeted verification set**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Persona/test_persona_profiles_api.py \
  tldw_Server_API/tests/Persona/test_persona_voice_commands_api.py \
  tldw_Server_API/tests/Persona/test_persona_connections_api.py \
  tldw_Server_API/tests/Persona/test_persona_command_test_api.py \
  tldw_Server_API/tests/Persona/test_persona_voice_command_fallback.py \
  tldw_Server_API/tests/VoiceAssistant/test_persona_voice_command_persistence.py \
  tldw_Server_API/tests/ChaChaNotesDB/test_persona_persistence_db.py -v
```

Run:

```bash
cd apps/packages/ui
bunx vitest run \
  src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx \
  src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx \
  src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx \
  src/routes/__tests__/sidepanel-persona.test.tsx \
  src/routes/__tests__/sidepanel-persona-locale-keys.test.ts
```

Run:

```bash
cd apps/packages/ui
bun run lint
```

Expected:

- pytest passes
- vitest passes
- lint passes

**Step 3: Run Bandit on touched backend scope**

Run:

```bash
source .venv/bin/activate
python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/persona.py \
  tldw_Server_API/app/api/v1/endpoints/voice_assistant.py \
  tldw_Server_API/app/core/VoiceAssistant \
  tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
  -f json -o /tmp/bandit_persona_voice_assistant.json
```

Expected:

- no new high-severity findings in touched code

If Bandit reports new findings in touched code, fix them before finalizing.

**Step 4: Sanity-check the final git diff**

Run:

```bash
git status --short
git diff --stat
```

Expected:

- only intended files are changed
- no unrelated workspace files were reverted or modified

**Step 5: Final commit**

```bash
git add Docs/Product/Persona_Agent_Design.md Docs/Product/STT-LLM-TTS-PRD.md \
  apps/packages/ui/src/assets/locale apps/packages/ui/src/public/_locales
git add tldw_Server_API apps/packages/ui
git commit -m "feat: add persona voice assistant builder"
```

## Notes For The Implementer

- Do not create a new assistant-profile model.
- Do not add raw-secret fields to the command editor or API.
- Do not let command safety drift from persona policy defaults.
- Prefer `defaultValue` fallback strings during early UI work, but finish locale keys before calling the route complete.
- Preserve current persona live-session behavior while adding the new tabs.

## Suggested Execution Order

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5

Plan complete and saved to `Docs/Plans/2026-03-12-persona-voice-assistant-builder-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
