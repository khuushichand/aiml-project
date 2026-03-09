# Persona Garden Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build `Persona Garden` as the branded advanced persona workspace for WebUI and extension, keep `My Chat Identity` separate from persona, and add a character-to-persona creation flow where personas become independent after creation.

**Architecture:** Keep the existing shared `/persona` route and websocket workflow intact, but reorganize it into a clearer `Persona Garden` workspace with explicit sections. Treat persona creation as a fork from a character snapshot: persist provenance metadata for audit/display, but do not keep live inheritance from the source character. Keep normal chat semantics unchanged in this pass.

**Tech Stack:** React, TypeScript, shared route components in `apps/packages/ui`, Next.js page shims in `apps/tldw-frontend`, WXT extension routes, FastAPI, Pydantic, ChaChaNotes SQLite/PostgreSQL DB layer, Vitest, Playwright, pytest, Bandit.

---

### Task 1: Rebrand `/persona` as Persona Garden Without Breaking Live Session Behavior

**Files:**
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Modify: `apps/packages/ui/src/components/Sidepanel/Chat/SidepanelHeaderSimple.tsx`
- Modify: `apps/packages/ui/src/data/settings-index.ts`
- Test: `apps/packages/ui/src/data/__tests__/settings-index.test.ts`

**Step 1: Write the failing test**

Add assertions that the persona route renders `Persona Garden` framing while keeping the existing live session controls (`Connect`, memory toggle, session select) visible. Cover the online route plus the offline/unsupported empty-state branches so no hard-coded `Persona` header is missed. In settings/search tests, assert that `Persona Garden` is added as its own entry instead of renaming `Characters`.

```tsx
it("renders Persona Garden while preserving live session controls", async () => {
  render(<SidepanelPersona />)

  expect(await screen.findByText("Persona Garden")).toBeInTheDocument()
  expect(screen.getByTestId("persona-memory-toggle")).toBeInTheDocument()
  expect(screen.getByTestId("persona-resume-session-select")).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui
bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx src/data/__tests__/settings-index.test.ts
```

Expected:

- FAIL because the route/header/empty-state labels still say `Persona` instead of `Persona Garden`, and settings/search does not yet expose a separate `Persona Garden` destination

**Step 3: Write minimal implementation**

Update the shared route/header copy across all route branches without removing the current live-session controls. Add a new settings/search entry for `Persona Garden`; do not rename the existing `Characters` entry.

```tsx
<SidepanelHeaderSimple activeTitle={t("sidepanel:persona.title", "Persona Garden")} />
```

```ts
{
  id: "setting-persona-garden",
  labelKey: "settings:personaGardenNav",
  defaultLabel: "Persona Garden",
  defaultDescription: "Configure advanced personas and live persona sessions",
  route: "/persona",
  section: "Knowledge",
  keywords: ["persona", "garden", "memory", "state", "assistant"],
  controlType: "button",
}
```

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui
bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx src/data/__tests__/settings-index.test.ts
```

Expected:

- PASS with route label updates and no regressions in the current live persona flow

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx apps/packages/ui/src/components/Sidepanel/Chat/SidepanelHeaderSimple.tsx apps/packages/ui/src/data/settings-index.ts apps/packages/ui/src/data/__tests__/settings-index.test.ts
git commit -m "feat: rebrand persona route as Persona Garden"
```

### Task 2: Extract `My Chat Identity` From Persona And Make It Explicit In Chat UI

**Files:**
- Create: `apps/packages/ui/src/components/Common/MyChatIdentityMenu.tsx`
- Create: `apps/packages/ui/src/components/Common/__tests__/MyChatIdentityMenu.test.tsx`
- Modify: `apps/packages/ui/src/components/Common/CharacterSelect.tsx`
- Modify: `apps/packages/ui/src/components/Sidepanel/Chat/CharacterSelect.tsx`
- Modify: `apps/packages/ui/src/components/Sidepanel/Chat/SidepanelHeaderSimple.tsx`

**Step 1: Write the failing test**

Write a component test that verifies the quick surface exposes user identity controls separately from characters and persona navigation.

```tsx
it("keeps user identity controls separate from persona navigation", async () => {
  render(<MyChatIdentityMenu />)

  expect(screen.getByText("My Chat Identity")).toBeInTheDocument()
  expect(screen.getByText("Set your name")).toBeInTheDocument()
  expect(screen.getByText("Upload your image")).toBeInTheDocument()
  expect(screen.getByText("Prompt style templates")).toBeInTheDocument()
  expect(screen.queryByText("Scope rules")).not.toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui
bunx vitest run src/components/Common/__tests__/MyChatIdentityMenu.test.tsx
```

Expected:

- FAIL because `MyChatIdentityMenu` does not exist yet

**Step 3: Write minimal implementation**

Create a dedicated quick-surface component that owns only user display name, user avatar, and user-side prompt templates. Remove persona framing from the existing user controls in `CharacterSelect`.

```tsx
export const MyChatIdentityMenu = () => (
  <section aria-label="My Chat Identity">
    <button type="button">Set your name</button>
    <button type="button">Upload your image</button>
    <button type="button">Prompt style templates</button>
  </section>
)
```

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui
bunx vitest run src/components/Common/__tests__/MyChatIdentityMenu.test.tsx
```

Expected:

- PASS with explicit user-identity separation

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Common/MyChatIdentityMenu.tsx apps/packages/ui/src/components/Common/__tests__/MyChatIdentityMenu.test.tsx apps/packages/ui/src/components/Common/CharacterSelect.tsx apps/packages/ui/src/components/Sidepanel/Chat/CharacterSelect.tsx apps/packages/ui/src/components/Sidepanel/Chat/SidepanelHeaderSimple.tsx
git commit -m "feat: separate My Chat Identity from persona controls"
```

### Task 3: Refactor Persona Garden Into Explicit Sections While Preserving The Existing Route Contract

**Files:**
- Create: `apps/packages/ui/src/components/PersonaGarden/PersonaGardenTabs.tsx`
- Create: `apps/packages/ui/src/components/PersonaGarden/LiveSessionPanel.tsx`
- Create: `apps/packages/ui/src/components/PersonaGarden/ProfilePanel.tsx`
- Create: `apps/packages/ui/src/components/PersonaGarden/StateDocsPanel.tsx`
- Create: `apps/packages/ui/src/components/PersonaGarden/ScopesPanel.tsx`
- Create: `apps/packages/ui/src/components/PersonaGarden/PoliciesPanel.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing test**

Add route tests that require explicit sections while still preserving the current live controls and plan-approval area.

```tsx
it("shows Persona Garden sections and keeps live controls", async () => {
  render(<SidepanelPersona />)

  expect(await screen.findByRole("tab", { name: "Live Session" })).toBeInTheDocument()
  expect(screen.getByRole("tab", { name: "Profiles" })).toBeInTheDocument()
  expect(screen.getByRole("tab", { name: "State Docs" })).toBeInTheDocument()
  expect(screen.getByTestId("persona-memory-toggle")).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui
bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected:

- FAIL because the route is still a single flat layout

**Step 3: Write minimal implementation**

Decompose the large route into focused panels, but keep route-owned state and effects in `sidepanel-persona.tsx`. Websocket lifecycle, session bootstrap/resume, unsaved-state blockers, per-message memory flags, and profile-default PATCH behavior must stay in the route and be passed into presentational panels as props/callbacks. Do not move API calls or websocket effects into the panel components in this task.

```tsx
<Tabs
  items={[
    { key: "live", label: "Live Session", children: <LiveSessionPanel {...props} /> },
    { key: "profiles", label: "Profiles", children: <ProfilePanel {...props} /> },
    { key: "state", label: "State Docs", children: <StateDocsPanel {...props} /> },
    { key: "scopes", label: "Scopes", children: <ScopesPanel {...props} /> },
    { key: "policies", label: "Policies", children: <PoliciesPanel {...props} /> }
  ]}
/>
```

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui
bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected:

- PASS with the new IA and no loss of current live behavior

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/PersonaGardenTabs.tsx apps/packages/ui/src/components/PersonaGarden/LiveSessionPanel.tsx apps/packages/ui/src/components/PersonaGarden/ProfilePanel.tsx apps/packages/ui/src/components/PersonaGarden/StateDocsPanel.tsx apps/packages/ui/src/components/PersonaGarden/ScopesPanel.tsx apps/packages/ui/src/components/PersonaGarden/PoliciesPanel.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: split Persona Garden into live and configuration sections"
```

### Task 4: Add Character-To-Persona Provenance And Independent Persona Creation On The Backend

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/persona.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/persona.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Test: `tldw_Server_API/tests/Persona/test_persona_profiles_api.py`
- Test: `tldw_Server_API/tests/ChaChaNotesDB/test_persona_persistence_db.py`

**Step 1: Write the failing test**

Add backend tests proving that creating a persona from a character stores provenance snapshots but does not require live character inheritance afterward.

```python
def test_create_persona_from_character_snapshots_origin_without_live_dependency(client, character_id):
    response = client.post(
        "/api/v1/persona/profiles",
        json={"name": "Garden Helper", "character_card_id": character_id},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["character_card_id"] == character_id
    assert payload["origin_character_name"] == "Source Character"
```

```python
def test_persona_remains_valid_when_origin_character_missing(db, persona_id):
    source_character = db.get_character_card_by_name("Source Character")
    assert source_character is not None
    assert db.soft_delete_character_card(source_character["id"], expected_version=source_character["version"])
    persona = db.get_persona_profile(persona_id, user_id="1", include_deleted=False)
    assert persona is not None
    assert persona["origin_character_name"] == "Source Character"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Persona/test_persona_profiles_api.py tldw_Server_API/tests/ChaChaNotesDB/test_persona_persistence_db.py -v
```

Expected:

- FAIL because origin snapshot fields and independence semantics are not implemented yet

**Step 3: Write minimal implementation**

Add a schema migration from v28 to v29 for persona provenance snapshot fields. Keep `character_card_id` as an optional current-source link for compatibility, but do not treat it as the sole provenance field because the FK can be nulled on source deletion. Persist separate origin snapshot fields so the persona remains self-describing after source changes or deletion.

```python
class PersonaProfileResponse(BaseModel):
    id: str
    name: str
    character_card_id: int | None = None
    origin_character_id: int | None = None
    origin_character_name: str | None = None
    origin_character_snapshot_at: str | None = None
```

```python
if character_card_id is not None:
    source_character = self.get_character_card(character_card_id, user_id=user_id)
    origin_character_id = source_character.get("id")
    origin_character_name = source_character.get("name")
    origin_character_snapshot_at = datetime.utcnow().isoformat()
```

```sql
ALTER TABLE persona_profiles ADD COLUMN origin_character_id INTEGER;
ALTER TABLE persona_profiles ADD COLUMN origin_character_name TEXT;
ALTER TABLE persona_profiles ADD COLUMN origin_character_snapshot_at DATETIME;
UPDATE db_schema_version SET version = 29 WHERE schema_name = 'rag_char_chat_schema' AND version < 29;
```

Do not add automatic re-sync from character to persona in this pass. If a source character is later deleted and `character_card_id` becomes `NULL`, the `origin_*` fields must still be returned.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Persona/test_persona_profiles_api.py tldw_Server_API/tests/ChaChaNotesDB/test_persona_persistence_db.py -v
```

Expected:

- PASS with stable provenance metadata and independent persona persistence

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/persona.py tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/tests/Persona/test_persona_profiles_api.py tldw_Server_API/tests/ChaChaNotesDB/test_persona_persistence_db.py
git commit -m "feat: snapshot persona origin when creating from character"
```

### Task 5: Add `Create Persona From Character` And `Open In Persona Garden` Flows

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Characters/CharactersWorkspace.tsx`
- Modify: `apps/packages/ui/src/components/Option/Characters/Manager.tsx`
- Modify: `apps/packages/ui/src/routes/option-characters.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Create: `apps/packages/ui/src/components/Option/Characters/__tests__/CharactersWorkspace.persona-garden.test.tsx`
- Test: `tldw_Server_API/tests/Persona/test_persona_catalog.py`

**Step 1: Write the failing test**

Add frontend tests proving the Characters workspace exposes persona creation/open actions and that Persona Garden shows provenance text instead of implying live inheritance.

```tsx
it("offers Create Persona from Character from the Characters workspace", async () => {
  render(<CharactersWorkspace />)

  expect(await screen.findByText("Create Persona from Character")).toBeInTheDocument()
})
```

```tsx
it("shows origin text in Persona Garden instead of live linkage copy", async () => {
  render(<SidepanelPersona />)

  expect(await screen.findByText(/Origin: created from/i)).toBeInTheDocument()
  expect(screen.queryByText(/currently based on/i)).not.toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui
bunx vitest run src/components/Option/Characters/__tests__/CharactersWorkspace.persona-garden.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected:

- FAIL because the actions and provenance text do not exist yet

**Step 3: Write minimal implementation**

Add explicit character actions that create/open personas and update Persona Garden to display source provenance text using the new backend fields. If the open action uses `/persona?persona_id=...`, add route bootstrap logic in `sidepanel-persona.tsx` that reads the requested persona from `location.search` before falling back to catalog/default selection.

```tsx
<Button onClick={() => onCreatePersonaFromCharacter(record)}>
  Create Persona from Character
</Button>
<Button onClick={() => navigate(`/persona?persona_id=${personaId}`)}>
  Open in Persona Garden
</Button>
```

```tsx
const location = useLocation()
const requestedPersonaId = React.useMemo(
  () => new URLSearchParams(location.search).get("persona_id")?.trim() || "",
  [location.search]
)
```

```tsx
<p className="text-xs text-text-muted">
  {originCharacterName ? `Origin: created from ${originCharacterName}` : "Standalone persona"}
</p>
```

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui
bunx vitest run src/components/Option/Characters/__tests__/CharactersWorkspace.persona-garden.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx
```

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest /Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/tests/Persona/test_persona_catalog.py -v
```

Expected:

- PASS with the new action flow and correct provenance copy

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Characters/CharactersWorkspace.tsx apps/packages/ui/src/components/Option/Characters/Manager.tsx apps/packages/ui/src/routes/option-characters.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx apps/packages/ui/src/components/Option/Characters/__tests__/CharactersWorkspace.persona-garden.test.tsx tldw_Server_API/tests/Persona/test_persona_catalog.py
git commit -m "feat: add create-persona flow from Characters"
```

### Task 6: Cross-Surface Verification And Security Scan

**Files:**
- Create: `apps/tldw-frontend/e2e/workflows/persona-garden.spec.ts`
- Modify: `apps/tldw-frontend/__tests__/extension/route-registry.persona.test.ts`

**Step 1: Write the failing test**

Add an end-to-end route/parity test proving WebUI and extension both expose Persona Garden without mutating normal chat identity.

```ts
test("Persona Garden is reachable in web and extension without changing My Chat Identity", async ({ authedPage }) => {
  await authedPage.goto("/persona")
  await expect(authedPage.getByText("Persona Garden")).toBeVisible()
  await expect(authedPage.getByText("My Chat Identity")).not.toBeVisible()
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run __tests__/extension/route-registry.persona.test.ts
```

Expected:

- FAIL until route labels/e2e expectations are updated

**Step 3: Write minimal implementation**

Keep the route-registry parity test focused on route registration only, and cover `Persona Garden` branding through rendered route tests or E2E. Do not edit the approved design doc in this task unless implementation forces a semantic product change.

```ts
expect(routeRegistrySource).toMatch(/path:\s*"\/persona"/)
expect(routeRegistrySource).toMatch(/element:\s*<SidepanelPersona\s*\/>/)
```

**Step 4: Run verification commands**

Run:

```bash
cd apps/packages/ui
bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx src/components/Common/__tests__/MyChatIdentityMenu.test.tsx src/components/Option/Characters/__tests__/CharactersWorkspace.persona-garden.test.tsx
```

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend
bunx vitest run __tests__/extension/route-registry.persona.test.ts
```

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest /Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/tests/Persona/test_persona_profiles_api.py /Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/tests/Persona/test_persona_catalog.py /Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/tests/ChaChaNotesDB/test_persona_persistence_db.py -v
python -m bandit -r /Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/endpoints/persona.py /Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py -f json -o /tmp/bandit_persona_garden.json
```

Expected:

- All targeted tests PASS
- Bandit reports no new findings in touched backend scope

**Step 5: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/persona-garden.spec.ts apps/tldw-frontend/__tests__/extension/route-registry.persona.test.ts
git commit -m "test: add Persona Garden cross-surface coverage"
```

## Notes For The Implementer

- Do not change normal chat to consume persona profiles in this plan.
- Do not make persona part of `My Chat Identity`.
- Do not make persona creation a live linked dependency on a character after creation.
- Keep the current websocket/live-session route functional throughout the refactor.
- Prefer additive schema changes and compatibility-preserving endpoint behavior.
- Treat `character_card_id` as a convenience link only; `origin_*` fields are the durable provenance contract.

## Suggested Execution Order

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5
6. Task 6

## Manual QA Checklist

- Open `/persona` in WebUI and confirm the page title reads `Persona Garden`.
- Confirm live persona session connect/resume still works.
- Confirm `My Chat Identity` editing still updates user display name/avatar in normal chat only.
- Confirm Characters shows `Create Persona from Character`.
- Confirm `Open in Persona Garden` preselects the requested persona when navigating from Characters.
- Confirm a created persona shows origin/provenance text but does not imply live character inheritance.
- Confirm deleting or changing the source character does not break the persona record.
