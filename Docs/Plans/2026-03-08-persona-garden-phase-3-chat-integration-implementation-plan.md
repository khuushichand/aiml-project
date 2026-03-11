# Persona Garden Phase 3 Chat Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make personas first-class assistant identities in ordinary chat by adding a normalized assistant identity model, a tabbed `Characters | Personas` picker, an explicit assistant-facing persona projection, and per-conversation persona memory modes without breaking existing character chats.

**Architecture:** Extend conversation persistence so chats can store either a character or a persona as the assistant identity, then expose that normalized contract through the chat session APIs and frontend chat loaders. Define a minimal assistant-facing persona projection up front so ordinary chat does not depend on a live source-character row for greeting/avatar/prompt behavior, and explicitly hide character-only settings/diagnostic surfaces where no persona-safe mapping exists yet. On the UI side, introduce a shared assistant-selection abstraction first, then roll the tabbed picker into both common and sidepanel chat entry points, and finally add explicit persona memory writeback controls to conversation settings.

**Tech Stack:** FastAPI, Pydantic, SQLite/ChaChaNotes DB migrations, React, Zustand, TanStack Query, Ant Design, Vitest, Pytest

---

### Task 1: Add assistant identity persistence to conversations

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Modify: `tldw_Server_API/app/core/DB_Management/async_db_wrapper.py`
- Test: `tldw_Server_API/tests/ChaChaNotesDB/test_conversation_assistant_identity_db.py`

**Step 1: Write the failing test**

Create `tldw_Server_API/tests/ChaChaNotesDB/test_conversation_assistant_identity_db.py` with coverage for:

```python
def test_legacy_character_conversation_backfills_assistant_identity(db):
    conv_id = db.add_conversation({
        "id": "conv-character-1",
        "character_id": 1,
        "title": "Legacy chat",
        "root_id": "conv-character-1",
        "client_id": "test",
    })
    row = db.get_conversation_by_id(conv_id)
    assert row["assistant_kind"] == "character"
    assert row["assistant_id"] == "1"
    assert row["persona_memory_mode"] is None


def test_persona_conversation_round_trips_assistant_identity(db):
    conv_id = db.add_conversation({
        "id": "conv-persona-1",
        "assistant_kind": "persona",
        "assistant_id": "garden-helper",
        "persona_memory_mode": "read_only",
        "title": "Persona chat",
        "root_id": "conv-persona-1",
        "client_id": "test",
    })
    row = db.get_conversation_by_id(conv_id)
    assert row["character_id"] is None
    assert row["assistant_kind"] == "persona"
    assert row["assistant_id"] == "garden-helper"
    assert row["persona_memory_mode"] == "read_only"
```

Also cover `list_conversations`, `update_conversation`, and migration on an existing database row that only has `character_id`.

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/ChaChaNotesDB/test_conversation_assistant_identity_db.py -v
```

Expected: FAIL because `conversations` and DB helpers do not yet expose `assistant_kind`, `assistant_id`, or `persona_memory_mode`.

**Step 3: Write minimal implementation**

In `ChaChaNotes_DB.py`:

- add `assistant_kind TEXT CHECK(assistant_kind IN ('character','persona'))`
- add `assistant_id TEXT`
- add `persona_memory_mode TEXT CHECK(persona_memory_mode IN ('read_only','read_write'))`
- add an explicit schema migration from the current schema version to the next one:
  - at time of writing, this means a new `V31 -> V32` migration, not an ad hoc column add
  - update the target version and migration chain accordingly
- backfill existing rows:
  - `assistant_kind = 'character'` when `character_id IS NOT NULL`
  - `assistant_id = CAST(character_id AS TEXT)` when `character_id IS NOT NULL`
- update `add_conversation`, `get_conversation_by_id`, list/search helpers, and `update_conversation` so the new fields round-trip
- keep `character_id` for compatibility; only set it automatically for character-backed chats

In `async_db_wrapper.py`:

- expose any wrapper methods whose typed return values now need the new fields

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/ChaChaNotesDB/test_conversation_assistant_identity_db.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
        tldw_Server_API/app/core/DB_Management/async_db_wrapper.py \
        tldw_Server_API/tests/ChaChaNotesDB/test_conversation_assistant_identity_db.py
git commit -m "feat: persist assistant identity on conversations"
```


### Task 2: Expose normalized assistant identity through chat session and conversation APIs

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/chat_session_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/chat_conversation_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/chat.py`
- Test: `tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py`
- Test: `tldw_Server_API/tests/Chat/unit/test_chat_conversations_api.py`

**Step 1: Write the failing test**

Add tests that assert:

```python
def test_create_chat_accepts_persona_assistant_identity(client, auth_headers):
    payload = {
        "assistant_kind": "persona",
        "assistant_id": "garden-helper",
        "persona_memory_mode": "read_only",
        "title": "Persona-backed chat",
    }
    response = client.post("/api/v1/chats/", json=payload, headers=auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["assistant_kind"] == "persona"
    assert body["assistant_id"] == "garden-helper"
    assert body["character_id"] is None


def test_create_chat_keeps_character_id_fallback(client, auth_headers):
    response = client.post("/api/v1/chats/", json={"character_id": 1}, headers=auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["assistant_kind"] == "character"
    assert body["assistant_id"] == "1"
    assert body["character_id"] == 1
```

Also cover conversation list/get/patch responses returning `assistant_kind`, `assistant_id`, and `persona_memory_mode`.

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py \
  tldw_Server_API/tests/Chat/unit/test_chat_conversations_api.py -v
```

Expected: FAIL because the schemas and endpoint converters are still character-only.

**Step 3: Write minimal implementation**

In `chat_session_schemas.py`:

- update `ChatSessionCreate` to accept:
  - `assistant_kind: Literal["character", "persona"] | None`
  - `assistant_id: str | None`
  - `persona_memory_mode: Literal["read_only", "read_write"] | None`
- keep `character_id` as a compatibility input
- add validators that:
  - synthesize `assistant_kind="character"` + `assistant_id=str(character_id)` when only `character_id` is supplied
  - require `assistant_id` when `assistant_kind` is provided
  - reject `persona_memory_mode` for character chats

In `chat_session_schemas.py` and `chat_conversation_schemas.py` responses:

- add `assistant_kind`, `assistant_id`, and `persona_memory_mode`

In `character_chat_sessions.py`:

- resolve assistant identity once in `POST /api/v1/chats/`
- validate persona existence when `assistant_kind="persona"`
- keep `character_id` set only for character-backed chats
- update `_convert_db_conversation_to_response(...)`

In `chat.py`:

- update conversation list/get/patch/tree metadata builders to emit the normalized assistant fields

Important compatibility rule:

- responses should keep `character_id` for legacy character chats and compatibility callers
- persona-backed chats should not synthesize a fake `character_id` just to satisfy old clients

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py \
  tldw_Server_API/tests/Chat/unit/test_chat_conversations_api.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/chat_session_schemas.py \
        tldw_Server_API/app/api/v1/schemas/chat_conversation_schemas.py \
        tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py \
        tldw_Server_API/app/api/v1/endpoints/chat.py \
        tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py \
        tldw_Server_API/tests/Chat/unit/test_chat_conversations_api.py
git commit -m "feat: add assistant identity to chat APIs"
```


### Task 3: Implement persona-backed ordinary chat runtime and memory-mode gating

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/chat.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Test: `tldw_Server_API/tests/Persona/test_persona_memory_integration.py`
- Test: `tldw_Server_API/tests/Chat/integration/test_persona_backed_chat_conversations.py`

**Step 1: Write the failing test**

Create `tldw_Server_API/tests/Chat/integration/test_persona_backed_chat_conversations.py` with coverage for:

```python
def test_persona_backed_chat_uses_persona_identity_when_loading_prompt(...):
    # create conversation with assistant_kind="persona"
    # send a normal chat turn
    # assert prompt assembly uses the persona profile, not character_id fallback


def test_persona_memory_mode_read_only_does_not_write_memory(...):
    # assistant_kind="persona", persona_memory_mode="read_only"
    # send a turn and assert no durable persona memory entry is written


def test_persona_memory_mode_read_write_allows_memory_write(...):
    # assistant_kind="persona", persona_memory_mode="read_write"
    # send a turn and assert durable persona memory write occurs


def test_persona_backed_chat_uses_projection_fallbacks_without_source_character_dependency(...):
    # persona-backed chat has no persona greeting/avatar fields
    # assert ordinary chat still works with generic assistant fallback behavior
```

Also add schema tests ensuring the deprecated `persona_id` alias remains separate from the new ordinary-chat assistant identity contract.

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Persona/test_persona_memory_integration.py \
  tldw_Server_API/tests/Chat/integration/test_persona_backed_chat_conversations.py -v
```

Expected: FAIL because ordinary chat does not yet resolve persona-backed conversations or gate memory writes by `persona_memory_mode`.

**Step 3: Write minimal implementation**

In `character_chat_sessions.py` and `chat.py`:

- add a shared helper that resolves the active assistant projection from conversation metadata:

```python
if conversation["assistant_kind"] == "persona":
    projection = resolve_persona_chat_projection(...)
else:
    projection = resolve_character_chat_projection(...)
```

- the persona projection must define at least:
  - `kind`
  - `id`
  - `display_name`
  - prompt/state inputs required for the assistant system layer
  - optional `avatar_url`
  - optional `greeting`
  - optional `extensions`
- persona-backed ordinary chat must not require a live source-character lookup in order to function
- persona projection fallback rules for initial rollout:
  - no greeting injection when persona greeting is absent
  - generic assistant avatar when persona avatar is absent
  - no character-extension behavior when persona extensions are absent

- use persona projection data for persona-backed prompt assembly
- keep character-backed prompt assembly unchanged

For memory gating:

- honor `persona_memory_mode == "read_only"` by skipping durable persona memory writes
- allow writeback only when `persona_memory_mode == "read_write"`

For the initial rollout compatibility matrix:

- keep persona-backed ordinary chat single-assistant only
- do not silently reuse source-character behavior for:
  - directed-character routing
  - participant/group-chat behavior
  - `speaker_character_id` metadata
  - mood detection/persistence that depends on character identity
  - world-book/lorebook character diagnostics
- where a behavior has no persona-safe mapping yet, disable it explicitly for persona-backed chats instead of falling back to the source character

In `chat_request_schemas.py`:

- leave the deprecated `persona_id` alias behavior intact
- do not reinterpret it as the new assistant identity API

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Persona/test_persona_memory_integration.py \
  tldw_Server_API/tests/Chat/integration/test_persona_backed_chat_conversations.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py \
        tldw_Server_API/app/api/v1/endpoints/chat.py \
        tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py \
        tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
        tldw_Server_API/tests/Persona/test_persona_memory_integration.py \
        tldw_Server_API/tests/Chat/integration/test_persona_backed_chat_conversations.py
git commit -m "feat: support persona-backed ordinary chat runtime"
```


### Task 4: Introduce a shared frontend assistant-selection abstraction

**Files:**
- Create: `apps/packages/ui/src/types/assistant-selection.ts`
- Create: `apps/packages/ui/src/utils/selected-assistant-storage.ts`
- Create: `apps/packages/ui/src/hooks/useSelectedAssistant.ts`
- Modify: `apps/packages/ui/src/hooks/useSelectedCharacter.ts`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Test: `apps/packages/ui/src/hooks/__tests__/useSelectedAssistant.test.tsx`
- Test: `apps/packages/ui/src/components/Common/__tests__/CharacterSelect.identity-smoke.test.tsx`

**Step 1: Write the failing test**

Create `apps/packages/ui/src/hooks/__tests__/useSelectedAssistant.test.tsx` to cover:

```tsx
it("migrates a stored selectedCharacter record into a character assistant selection", async () => {
  // seed legacy selectedCharacter storage
  // mount useSelectedAssistant
  // expect { kind: "character", id: "7", ... }
})

it("broadcasts persona assistant selections to subscribers", async () => {
  // set { kind: "persona", id: "garden-helper" }
  // expect subscriber update
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/hooks/__tests__/useSelectedAssistant.test.tsx \
  src/components/Common/__tests__/CharacterSelect.identity-smoke.test.tsx
```

Expected: FAIL because the hook and types do not exist yet.

**Step 3: Write minimal implementation**

Create `assistant-selection.ts` with a minimal normalized type:

```ts
export type AssistantKind = "character" | "persona"

export type AssistantSelection = {
  kind: AssistantKind
  id: string
  name: string
  avatar_url?: string | null
  greeting?: string | null
}
```

Add `useSelectedAssistant.ts`:

- store assistant selections in a new storage key
- migrate legacy `selectedCharacter` storage into `{ kind: "character", ... }`
- keep broadcast semantics

Update `useSelectedCharacter.ts`:

- keep it as a compatibility wrapper that reads/writes only `character` assistant selections until all callers migrate

Update `TldwApiClient.ts`:

- extend `ServerChatSummary` and `normalizeChatSummary(...)` to include:
  - `assistant_kind`
  - `assistant_id`
  - `persona_memory_mode`
- add persona fetch helpers, for example:
  - `listPersonaProfiles(...)`
  - `getPersonaProfile(...)`

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/hooks/__tests__/useSelectedAssistant.test.tsx \
  src/components/Common/__tests__/CharacterSelect.identity-smoke.test.tsx
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/types/assistant-selection.ts \
        apps/packages/ui/src/utils/selected-assistant-storage.ts \
        apps/packages/ui/src/hooks/useSelectedAssistant.ts \
        apps/packages/ui/src/hooks/useSelectedCharacter.ts \
        apps/packages/ui/src/services/tldw/TldwApiClient.ts \
        apps/packages/ui/src/hooks/__tests__/useSelectedAssistant.test.tsx \
        apps/packages/ui/src/components/Common/__tests__/CharacterSelect.identity-smoke.test.tsx
git commit -m "feat: add shared assistant selection state"
```


### Task 5: Roll out the tabbed `Characters | Personas` picker and restore logic

**Files:**
- Create: `apps/packages/ui/src/components/Common/AssistantSelect.tsx`
- Modify: `apps/packages/ui/src/components/Common/CharacterSelect.tsx`
- Modify: `apps/packages/ui/src/components/Sidepanel/Chat/CharacterSelect.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-chat.tsx`
- Modify: `apps/packages/ui/src/hooks/chat/useChatActions.ts`
- Modify: `apps/packages/ui/src/hooks/chat/useSelectServerChat.ts`
- Modify: `apps/packages/ui/src/hooks/chat/useServerChatLoader.ts`
- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/ComposerToolbar.tsx`
- Modify: `apps/packages/ui/src/store/option/types.ts`
- Modify: `apps/packages/ui/src/store/option/slices/server-chat-slice.ts`
- Modify: `apps/packages/ui/src/components/Common/Settings/ActorPopout.tsx`
- Modify: `apps/packages/ui/src/components/Common/Settings/CurrentChatModelSettings.tsx`
- Test: `apps/packages/ui/src/components/Common/__tests__/AssistantSelect.tabs.test.tsx`
- Test: `apps/packages/ui/src/hooks/chat/__tests__/useChatActions.persona.integration.test.tsx`
- Test: `apps/packages/ui/src/hooks/__tests__/useServerChatLoader.test.ts`

**Step 1: Write the failing test**

Add tests that assert:

```tsx
it("shows separate Characters and Personas tabs", async () => {
  render(<AssistantSelect />)
  expect(screen.getByRole("tab", { name: "Characters" })).toBeInTheDocument()
  expect(screen.getByRole("tab", { name: "Personas" })).toBeInTheDocument()
})

it("creates a persona-backed chat with assistant_kind=persona", async () => {
  // select persona tab + persona item
  // send first message
  // expect createChat payload to include assistant_kind/persona id
})

it("restores a reopened persona chat as a persona selection", async () => {
  // loader receives server chat summary with assistant_kind=persona
  // expect selected assistant kind to be persona
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Common/__tests__/AssistantSelect.tabs.test.tsx \
  src/hooks/chat/__tests__/useChatActions.persona.integration.test.tsx \
  src/hooks/__tests__/useServerChatLoader.test.ts
```

Expected: FAIL because the picker, chat creation payloads, and restore paths are still character-only.

**Step 3: Write minimal implementation**

Create `AssistantSelect.tsx`:

- shared tabbed picker with `Characters` and `Personas`
- reuse as much of the existing character picker behavior as possible
- fetch persona list via the new client helpers

Update chat creation and restore paths:

- `useChatActions.ts`
  - create chats with normalized assistant identity
  - stop assuming `character_id` is always the active assistant
- `useSelectServerChat.ts` and `useServerChatLoader.ts`
  - restore selected assistant from `assistant_kind` + `assistant_id`
  - only fetch character details for character-backed chats
  - fetch persona details for persona-backed chats
- `store/option/types.ts` and `store/option/slices/server-chat-slice.ts`
  - add `serverChatAssistantKind`, `serverChatAssistantId`, and `serverChatPersonaMemoryMode`
- `ActorPopout.tsx` and `CurrentChatModelSettings.tsx`
  - stop assuming `selectedCharacter` always exists for ordinary chat
  - for persona-backed chats, either use assistant-aware data or hide character-fallback controls that do not yet have persona-safe mappings

For backward compatibility:

- keep `CharacterSelect.tsx` as a wrapper or compatibility export during the rollout if other call sites still import it

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Common/__tests__/AssistantSelect.tabs.test.tsx \
  src/hooks/chat/__tests__/useChatActions.persona.integration.test.tsx \
  src/hooks/__tests__/useServerChatLoader.test.ts
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Common/AssistantSelect.tsx \
        apps/packages/ui/src/components/Common/CharacterSelect.tsx \
        apps/packages/ui/src/components/Sidepanel/Chat/CharacterSelect.tsx \
        apps/packages/ui/src/routes/sidepanel-chat.tsx \
        apps/packages/ui/src/hooks/chat/useChatActions.ts \
        apps/packages/ui/src/hooks/chat/useSelectServerChat.ts \
        apps/packages/ui/src/hooks/chat/useServerChatLoader.ts \
        apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx \
        apps/packages/ui/src/components/Option/Playground/ComposerToolbar.tsx \
        apps/packages/ui/src/store/option/types.ts \
        apps/packages/ui/src/store/option/slices/server-chat-slice.ts \
        apps/packages/ui/src/components/Common/Settings/ActorPopout.tsx \
        apps/packages/ui/src/components/Common/Settings/CurrentChatModelSettings.tsx \
        apps/packages/ui/src/components/Common/__tests__/AssistantSelect.tabs.test.tsx \
        apps/packages/ui/src/hooks/chat/__tests__/useChatActions.persona.integration.test.tsx \
        apps/packages/ui/src/hooks/__tests__/useServerChatLoader.test.ts
git commit -m "feat: add persona-backed assistant picker for chat"
```


### Task 6: Add explicit persona memory mode controls and run full verification

**Files:**
- Modify: `apps/packages/ui/src/components/Common/Settings/tabs/ConversationTab.tsx`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Modify: `apps/packages/ui/src/hooks/chat/useChatActions.ts`
- Modify: `apps/packages/ui/src/store/option/types.ts`
- Modify: `apps/packages/ui/src/store/option/slices/server-chat-slice.ts`
- Modify: `apps/packages/ui/src/components/Common/Settings/PromptAssemblyPreview.tsx`
- Modify: `apps/packages/ui/src/components/Common/Settings/LorebookDebugPanel.tsx`
- Modify: `apps/packages/ui/src/components/Common/Settings/ActorPopout.tsx`
- Modify: `apps/packages/ui/src/components/Common/Settings/CurrentChatModelSettings.tsx`
- Test: `apps/packages/ui/src/components/Common/Settings/tabs/__tests__/ConversationTab.persona-memory-mode.test.tsx`
- Test: `apps/packages/ui/src/components/Common/Settings/__tests__/PersonaChatGuards.test.tsx`
- Test: `apps/packages/ui/src/hooks/chat/__tests__/useChatActions.persona.integration.test.tsx`

**Step 1: Write the failing test**

Create `apps/packages/ui/src/components/Common/Settings/tabs/__tests__/ConversationTab.persona-memory-mode.test.tsx` with coverage for:

```tsx
it("shows persona memory mode controls only for persona-backed chats", async () => {
  // render ConversationTab with assistant_kind=persona
  // expect read-only / read-write control
})

it("requires explicit user action to switch to read_write", async () => {
  // start in read_only
  // toggle to read_write
  // expect updateChat payload to include persona_memory_mode="read_write"
})
```

Also extend the chat action integration test so new persona chats default to `read_only`.

Add `apps/packages/ui/src/components/Common/Settings/__tests__/PersonaChatGuards.test.tsx` with coverage for:

```tsx
it("hides character-only preview and diagnostics affordances for persona-backed chats", async () => {
  // render settings surfaces with serverChatAssistantKind="persona"
  // assert character-only panels or actions are absent / disabled
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Common/Settings/tabs/__tests__/ConversationTab.persona-memory-mode.test.tsx \
  src/components/Common/Settings/__tests__/PersonaChatGuards.test.tsx \
  src/hooks/chat/__tests__/useChatActions.persona.integration.test.tsx
```

Expected: FAIL because no explicit persona memory mode control exists yet.

**Step 3: Write minimal implementation**

In `ConversationTab.tsx`:

- render persona memory mode controls only when `serverChatAssistantKind === "persona"`
- default to `read_only`
- persist changes through `tldwClient.updateChat(...)`

In the frontend chat state:

- thread `persona_memory_mode` through chat creation, restore, and update paths
- avoid exposing the control for character-backed chats

In the character-only settings/diagnostic surfaces:

- `PromptAssemblyPreview.tsx`
  - do not call character-only prompt preview endpoints for persona-backed chats unless a persona-aware preview contract exists
- `LorebookDebugPanel.tsx`
  - do not assume `chat.character_id` exists for persona-backed chats
- `ActorPopout.tsx` and `CurrentChatModelSettings.tsx`
  - hide or disable character-fallback controls for persona-backed chats until they gain assistant-aware behavior

**Step 4: Run tests and verification**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Common/__tests__/AssistantSelect.tabs.test.tsx \
  src/components/Common/__tests__/CharacterSelect.identity-smoke.test.tsx \
  src/components/Common/Settings/tabs/__tests__/ConversationTab.persona-memory-mode.test.tsx \
  src/components/Common/Settings/__tests__/PersonaChatGuards.test.tsx \
  src/hooks/__tests__/useSelectedAssistant.test.tsx \
  src/hooks/__tests__/useServerChatLoader.test.ts \
  src/hooks/chat/__tests__/useChatActions.persona.integration.test.tsx
```

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/ChaChaNotesDB/test_conversation_assistant_identity_db.py \
  tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py \
  tldw_Server_API/tests/Chat/unit/test_chat_conversations_api.py \
  tldw_Server_API/tests/Persona/test_persona_memory_integration.py \
  tldw_Server_API/tests/Chat/integration/test_persona_backed_chat_conversations.py -v
```

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py \
  tldw_Server_API/app/api/v1/endpoints/chat.py \
  tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py \
  tldw_Server_API/app/api/v1/schemas/chat_session_schemas.py \
  tldw_Server_API/app/api/v1/schemas/chat_conversation_schemas.py \
  tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
  -f json -o /tmp/bandit_persona_garden_phase3.json
```

Expected:

- frontend tests PASS
- backend tests PASS
- Bandit reports no new findings in touched code

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Common/Settings/tabs/ConversationTab.tsx \
        apps/packages/ui/src/services/tldw/TldwApiClient.ts \
        apps/packages/ui/src/hooks/chat/useChatActions.ts \
        apps/packages/ui/src/store/option/types.ts \
        apps/packages/ui/src/store/option/slices/server-chat-slice.ts \
        apps/packages/ui/src/components/Common/Settings/PromptAssemblyPreview.tsx \
        apps/packages/ui/src/components/Common/Settings/LorebookDebugPanel.tsx \
        apps/packages/ui/src/components/Common/Settings/ActorPopout.tsx \
        apps/packages/ui/src/components/Common/Settings/CurrentChatModelSettings.tsx \
        apps/packages/ui/src/components/Common/Settings/tabs/__tests__/ConversationTab.persona-memory-mode.test.tsx \
        apps/packages/ui/src/components/Common/Settings/__tests__/PersonaChatGuards.test.tsx \
        apps/packages/ui/src/hooks/chat/__tests__/useChatActions.persona.integration.test.tsx
git commit -m "feat: add persona memory mode controls to chat"
```


### Notes for the implementer

- Do not repurpose the deprecated `persona_id` alias as the new assistant identity API.
- Keep `useSelectedCharacter` working as a compatibility layer until every caller is migrated.
- Preserve legacy character chats exactly when reopened.
- Do not expand default-character preference or server defaults to personas in this phase unless the task explicitly requires it.
- Prefer creating a shared assistant-selection abstraction before editing both picker UIs.
- Keep Persona Garden live-session behavior separate from ordinary persona-backed chat.
- Before implementing the UI rollout, grep remaining `selectedCharacter` and `character_id` assumptions in `apps/packages/ui/src/components/Common/Settings` and `apps/packages/ui/src/hooks/chat` so persona-backed chats do not inherit character-only panels by accident.
