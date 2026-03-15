# Persona Voice Assistant Next Four Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the next four Persona Garden voice-command improvements in sequence: MCP tool picker, phrase-to-slot assist, persona-scoped assistant voice defaults, and persona-scoped command analytics.

**Architecture:** Keep the current persona-first model and extend the existing Persona Garden surfaces instead of adding a second assistant settings system. Reuse MCP discovery service calls, existing speech settings vocabulary, and the current voice analytics pipeline where possible, but do not couple Persona Garden picker state to the globally persisted MCP filters. Treat assistant defaults as persona-backed configuration plus an explicit resolution layer; do not silently mutate browser-wide voice settings. Voice analytics in this phase must count live runtime resolution only, never Test Lab dry-runs.

**Tech Stack:** React, TypeScript, TanStack Query, Vitest, FastAPI, Pydantic, ChaChaNotes SQLite DB helpers, pytest, Bandit.

---

### Task 1: Build A Shared MCP Tool Picker Component

**Files:**
- Create: `apps/packages/ui/src/components/PersonaGarden/McpToolPicker.tsx`
- Create: `apps/packages/ui/src/components/PersonaGarden/__tests__/McpToolPicker.test.tsx`
- Reference: `apps/packages/ui/src/services/tldw/mcp.ts`
- Modify: `apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx`
- Test: `apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx`

**Step 1: Write the failing test**

Add a new component test that proves the picker can:
- render healthy/loading/unavailable states from `useMcpTools`
- choose catalog -> module -> tool
- emit a concrete `tool_name`
- fall back to a manual text field when MCP is unavailable or the user explicitly switches to manual mode

Use a minimal prop shape like:

```tsx
type McpToolPickerProps = {
  value: string
  onChange: (toolName: string) => void
  disabled?: boolean
}
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run src/components/PersonaGarden/__tests__/McpToolPicker.test.tsx
```

Expected: FAIL because the component does not exist yet.

**Step 3: Write minimal implementation**

Create `McpToolPicker.tsx` that:
- uses local React Query state plus `fetchMcpToolCatalogsViaDiscovery`, `fetchMcpModulesViaDiscovery`, and `fetchMcpToolsViaDiscovery` with the existing fallback service functions from `services/tldw/mcp.ts`
- groups catalogs like the existing chat/playground MCP surfaces
- filters tools by selected catalog/module
- writes the selected tool’s canonical name back to `onChange`
- exposes a manual override path

Important constraint:
- do **not** read from or write to `useMcpToolsStore`
- do **not** reuse persisted MCP filter settings from chat/playground
- keep picker filters local to the Persona Garden command editor

Keep the first version simple:

```tsx
const selectedTool = tools.find((tool) => tool.name === value)
const visibleTools = tools.filter((tool) => matchesCatalogAndModule(tool, filters))
```

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run src/components/PersonaGarden/__tests__/McpToolPicker.test.tsx
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/McpToolPicker.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/McpToolPicker.test.tsx apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx
git commit -m "feat: add persona MCP tool picker"
```


### Task 2: Replace Raw MCP Tool Entry In Commands With The Picker

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx`
- Test: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.command-handoff.test.tsx`

**Step 1: Write the failing test**

Extend `CommandsPanel.test.tsx` to prove that:
- an `mcp_tool` command can be created from a picker selection instead of a freeform text box
- an existing `mcp_tool` command rehydrates into the picker
- the manual override path still works when MCP catalogs/tools are empty

Use expectations on the saved payload:

```tsx
expect(body.action_config).toEqual(
  expect.objectContaining({ tool_name: "notes.search" })
)
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx
```

Expected: FAIL because `CommandsPanel` still renders the raw `toolName` text input.

**Step 3: Write minimal implementation**

Update `CommandsPanel.tsx` so the `mcp_tool` branch renders `McpToolPicker` first and only shows the raw input when the user switches to manual mode or MCP is unavailable. Do not change the saved backend payload shape yet; keep `action_config.tool_name` exactly as it is now.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx src/routes/__tests__/sidepanel-persona.command-handoff.test.tsx
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.command-handoff.test.tsx
git commit -m "feat: wire MCP picker into persona commands"
```


### Task 3: Add Phrase-To-Slot Assist For Drafted Commands

**Files:**
- Create: `apps/packages/ui/src/utils/persona-command-drafts.ts`
- Create: `apps/packages/ui/src/utils/__tests__/persona-command-drafts.test.ts`
- Modify: `apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/TestLabPanel.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx`

**Step 1: Write the failing test**

Add a pure utility test for deterministic suggestions like:

```ts
expect(buildDraftAssist("search notes for model context protocol")).toEqual(
  expect.objectContaining({
    suggestedPhrase: "search notes for {topic}",
    suggestedSlotMap: { query: "topic" }
  })
)
```

Also add a `CommandsPanel` test proving that a drafted command:
- shows one or more suggestion chips
- applies a suggestion into `phrasesText`
- updates `slotMapText`

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run src/utils/__tests__/persona-command-drafts.test.ts src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx
```

Expected: FAIL because the helper and UI do not exist yet.

**Step 3: Write minimal implementation**

Create a deterministic helper only. Do not use LLM inference. Start with simple cue-word patterns:
- `for {topic}`
- `about {topic}`
- `with {content}`
- numeric duration phrases like `10 minutes` -> `{duration}`

Shape:

```ts
type DraftAssist = {
  suggestedPhrase: string
  suggestedSlotMap: Record<string, string>
  label: string
}
```

In `CommandsPanel.tsx`, render suggestion chips only when the form came from Test Lab draft flow and `actionType` is `mcp_tool` or `custom`.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run src/utils/__tests__/persona-command-drafts.test.ts src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/utils/persona-command-drafts.ts apps/packages/ui/src/utils/__tests__/persona-command-drafts.test.ts apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx apps/packages/ui/src/components/PersonaGarden/TestLabPanel.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx
git commit -m "feat: add phrase-to-slot assist for persona command drafts"
```


### Task 4: Extend Persona Profiles With Voice Defaults

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/persona.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/persona.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Test: `tldw_Server_API/tests/Persona/test_persona_profiles_api.py`

**Step 1: Write the failing test**

Add persona profile API tests that prove `GET /api/v1/persona/profiles/{persona_id}` and `PUT /api/v1/persona/profiles/{persona_id}` can round-trip a new `voice_defaults` object:

```python
assert payload["voice_defaults"]["stt_language"] == "en-US"
assert payload["voice_defaults"]["confirmation_mode"] == "always"
assert payload["voice_defaults"]["voice_chat_trigger_phrases"] == ["hey helper"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_profiles_api.py -q
```

Expected: FAIL because the schema and DB do not expose `voice_defaults`.

**Step 3: Write minimal implementation**

Add a nested schema:

```python
class PersonaVoiceDefaults(BaseModel):
    stt_language: str | None = None
    stt_model: str | None = None
    tts_provider: str | None = None
    tts_voice: str | None = None
    confirmation_mode: Literal["always", "destructive_only", "never"] | None = None
    voice_chat_trigger_phrases: list[str] = Field(default_factory=list)
    auto_resume: bool | None = None
    barge_in: bool | None = None
```

Persist it by adding one JSON column to `persona_profiles` in `ChaChaNotes_DB.py` rather than scattering many new columns. Update create/get/update profile flows and the profile-to-response serializer in `persona.py`.

Scope guard:
- this task only makes persona defaults persistable and retrievable
- it does **not** overwrite the user’s browser-wide speech settings

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_profiles_api.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/persona.py tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/tests/Persona/test_persona_profiles_api.py
git commit -m "feat: persist persona voice defaults"
```


### Task 5: Surface Assistant Defaults In Persona Garden

**Files:**
- Create: `apps/packages/ui/src/components/PersonaGarden/AssistantDefaultsPanel.tsx`
- Create: `apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx`
- Create: `apps/packages/ui/src/hooks/useResolvedPersonaVoiceDefaults.tsx`
- Create: `apps/packages/ui/src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/ProfilePanel.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Reference: `apps/packages/ui/src/hooks/useVoiceChatSettings.tsx`
- Reference: `apps/packages/ui/src/hooks/useSttSettings.tsx`

**Step 1: Write the failing test**

Add UI tests proving that:
- profile data loads `voice_defaults`
- the user can edit assistant defaults for the selected persona
- saving calls the existing persona profile `PUT` route
- a resolution hook merges `persona.voice_defaults -> local browser defaults -> hardcoded fallbacks`
- the form explains that persona defaults are separate from browser-wide fallback settings

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: FAIL because the panel and route wiring do not exist yet.

**Step 3: Write minimal implementation**

Preferred UI shape:
- keep this inside Persona Garden, not `/settings/speech`
- add an `Assistant Defaults` card under Profile first
- fields should map directly onto `voice_defaults`

The first version should cover:
- STT language
- TTS provider + voice
- confirmation mode
- trigger phrases
- auto-resume
- barge-in

Reuse existing setting vocabulary from `useVoiceChatSettings.tsx` and `useSttSettings.tsx` so names stay consistent.

Important constraint:
- Persona Garden does not currently own a dedicated audio transport consumer the way chat/playground does.
- Therefore this phase must ship a real `useResolvedPersonaVoiceDefaults` hook and a clear preview of effective values.
- Only wire live runtime overrides into a consumer if the implementation touches a persona-owned voice/session hook in the same slice; otherwise keep runtime application explicitly deferred rather than pretending the new settings are already active everywhere.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/AssistantDefaultsPanel.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/components/PersonaGarden/ProfilePanel.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: add persona assistant defaults panel"
```


### Task 6: Make Voice Analytics Persona-Scoped And Fallback-Aware

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Modify: `tldw_Server_API/app/core/VoiceAssistant/db_helpers.py`
- Modify: `tldw_Server_API/app/core/VoiceAssistant/router.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/persona.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/persona.py`
- Test: `tldw_Server_API/tests/Persona/test_persona_voice_commands_api.py`
- Test: `tldw_Server_API/tests/Persona/test_persona_command_test_api.py`
- Create: `tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py`

**Step 1: Write the failing test**

Add backend tests that prove:
- voice command events carry `persona_id`
- planner fallbacks are logged distinctly from direct command matches
- a new persona endpoint returns command usage, error counts, and fallback counts for that persona only
- dry-run/Test Lab traffic does not increment analytics

Suggested endpoint shape:

```python
GET /api/v1/persona/profiles/{persona_id}/voice-analytics?days=7
```

Suggested response shape:

```python
{
    "persona_id": "research_assistant",
    "summary": {...},
    "commands": [...],
    "fallbacks": {...}
}
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py -q
```

Expected: FAIL because the persona endpoint and persona-aware event model do not exist yet.

**Step 3: Write minimal implementation**

Database/model changes:
- add `persona_id` column to `voice_command_events`
- add a compact outcome discriminator such as `resolution_type` with values like `direct_command` and `planner_fallback`
- write those values in `record_voice_command_event(...)`
- update router call sites so both direct commands and planner fallbacks are recorded

Analytics semantics:
- record analytics from live router execution only
- do not record `POST /profiles/{persona_id}/voice-commands/test`
- historical rows without `persona_id` remain valid for user-wide analytics but are ignored by the persona endpoint

Endpoint changes:
- keep existing `/api/v1/voice/analytics` for user-wide analytics
- add a persona endpoint in `persona.py` that filters on `persona_id`

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py tldw_Server_API/tests/Persona/test_persona_voice_commands_api.py tldw_Server_API/tests/Persona/test_persona_command_test_api.py -q
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/app/core/VoiceAssistant/db_helpers.py tldw_Server_API/app/core/VoiceAssistant/router.py tldw_Server_API/app/api/v1/schemas/persona.py tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py tldw_Server_API/tests/Persona/test_persona_voice_commands_api.py tldw_Server_API/tests/Persona/test_persona_command_test_api.py
git commit -m "feat: add persona voice analytics"
```


### Task 7: Surface Command Analytics In Commands And Test Lab

**Files:**
- Create: `apps/packages/ui/src/components/PersonaGarden/CommandAnalyticsSummary.tsx`
- Create: `apps/packages/ui/src/components/PersonaGarden/__tests__/CommandAnalyticsSummary.test.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/TestLabPanel.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx`

**Step 1: Write the failing test**

Add UI tests proving that:
- the Commands tab shows a summary card with totals, success rate, and fallback rate
- each command row can show recent invocation count / failure badge / last used
- Test Lab can mention the last matching command’s recent health, not just raw dry-run data

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run src/components/PersonaGarden/__tests__/CommandAnalyticsSummary.test.tsx src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx
```

Expected: FAIL because the UI does not fetch or render persona voice analytics yet.

**Step 3: Write minimal implementation**

Add one route-level fetch in `sidepanel-persona.tsx` or one panel-local fetch if that keeps the code smaller. The first UI version should prefer readability over dense charts:
- summary cards
- command-row badges
- a compact fallback health note

Do not add chart libraries.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run src/components/PersonaGarden/__tests__/CommandAnalyticsSummary.test.tsx src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/CommandAnalyticsSummary.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/CommandAnalyticsSummary.test.tsx apps/packages/ui/src/components/PersonaGarden/CommandsPanel.tsx apps/packages/ui/src/components/PersonaGarden/TestLabPanel.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: show persona command analytics"
```


### Task 8: Full Regression, Security Check, And Cleanup

**Files:**
- Modify: `Docs/Plans/2026-03-12-persona-voice-assistant-next-four-implementation-plan.md`
- Verify only: touched UI and backend files above

**Step 1: Run the targeted frontend regression**

Run:

```bash
bunx vitest run src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx src/components/PersonaGarden/__tests__/PersonaGardenPanels.i18n.test.tsx src/components/PersonaGarden/__tests__/ExemplarImportPanel.test.tsx src/components/PersonaGarden/__tests__/VoiceExamplesPanel.test.tsx src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx src/components/PersonaGarden/__tests__/CommandAnalyticsSummary.test.tsx src/components/PersonaGarden/__tests__/McpToolPicker.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx src/routes/__tests__/sidepanel-persona.blocker.test.tsx src/routes/__tests__/sidepanel-persona.command-handoff.test.tsx src/routes/__tests__/sidepanel-persona-locale-keys.test.ts
```

Expected: PASS

**Step 2: Run the targeted backend regression**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_profiles_api.py tldw_Server_API/tests/Persona/test_persona_voice_commands_api.py tldw_Server_API/tests/Persona/test_persona_command_test_api.py tldw_Server_API/tests/Persona/test_persona_connections_api.py tldw_Server_API/tests/Persona/test_persona_voice_analytics_api.py -q
```

Expected: PASS

**Step 3: Run Bandit on the touched backend scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/app/api/v1/schemas/persona.py tldw_Server_API/app/core/VoiceAssistant/db_helpers.py tldw_Server_API/app/core/VoiceAssistant/router.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py -f json -o /tmp/bandit_persona_voice_phase2.json
```

Expected: no new findings in touched code

**Step 4: Update the plan status**

Mark each task complete in this file.

**Step 5: Final commit**

```bash
git add <all touched implementation files>
git commit -m "<final feature commit for the last slice>"
```
