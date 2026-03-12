# Llama.cpp Thinking Budget And Grammar Library Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add first-class llama.cpp grammar controls and a user-scoped grammar library, plus capability-gated thinking-budget support, across the existing chat/playground stack without introducing a new reusable preset backend.

**Architecture:** Reuse the existing `ChatModelSettings` and sidepanel/workspace snapshot pipeline for per-session persistence, add a new user-owned grammar library resource backed by the per-user ChaChaNotes database, and centralize llama.cpp request translation in a shared resolver that turns app-level fields into provider-specific `extra_body`. The resolver must guard on the resolved target provider after model normalization, not only the raw `api_provider` field. Grammar ships as a stable first-class control; thinking budget is surfaced only when shared runtime helpers find an explicit operator-configured request-key mapping and when `strict_openai_compat` does not disable advanced fields.

**Tech Stack:** FastAPI, Pydantic v2, SQLite via `CharactersRAGDB`, Zustand, React, Ant Design, Vitest, pytest, Bandit.

---

**Execution skills:** `@test-driven-development`, `@verification-before-completion`

### Task 0: Isolated Worktree Preflight (Required)

**Files:**
- Verify only: git worktree metadata and branch state

**Step 1: Create or switch to an isolated worktree**

Run:
`git worktree add .worktrees/llamacpp-grammar-thinking -b codex/llamacpp-grammar-thinking`

Expected: New isolated worktree is created on a `codex/` branch.

**Step 2: Verify branch isolation**

Run:
`cd .worktrees/llamacpp-grammar-thinking && git branch --show-current && git rev-parse --show-toplevel`

Expected:
- Branch name is `codex/llamacpp-grammar-thinking`
- Repo root is the worktree path, not the primary workspace

**Step 3: Run a narrow baseline**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/unit/test_chat_request_schemas.py tldw_Server_API/tests/Chat_NEW/unit/test_chat_schemas.py tldw_Server_API/tests/LLM_Calls/test_llamacpp_strict_filter.py`

Expected: Current baseline passes before changes begin.

### Task 1: Extend Chat Request Schema For Llama.cpp First-Class Fields

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py`
- Test: `tldw_Server_API/tests/Chat/unit/test_chat_request_schemas.py`
- Test: `tldw_Server_API/tests/Chat_NEW/unit/test_chat_schemas.py`

**Step 1: Write the failing tests**

```python
def test_chat_request_accepts_llamacpp_grammar_fields():
    req = ChatCompletionRequest(
        model="llama.cpp/local-model",
        messages=[{"role": "user", "content": "reply in JSON"}],
        grammar_mode="library",
        grammar_id="grammar_123",
        grammar_override='root ::= "ok"',
        thinking_budget_tokens=128,
    )
    assert req.grammar_mode == "library"
    assert req.grammar_id == "grammar_123"
    assert req.thinking_budget_tokens == 128


def test_chat_request_rejects_library_mode_without_grammar_id():
    with pytest.raises(ValidationError):
        ChatCompletionRequest(
            api_provider="llama.cpp",
            model="llama.cpp/local-model",
            messages=[{"role": "user", "content": "x"}],
            grammar_mode="library",
        )


def test_chat_request_rejects_inline_mode_without_grammar_inline():
    with pytest.raises(ValidationError):
        ChatCompletionRequest(
            api_provider="llama.cpp",
            model="llama.cpp/local-model",
            messages=[{"role": "user", "content": "x"}],
            grammar_mode="inline",
        )
```

**Step 2: Run tests to verify they fail**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/unit/test_chat_request_schemas.py tldw_Server_API/tests/Chat_NEW/unit/test_chat_schemas.py -k llamacpp`

Expected: FAIL because the request model does not yet define the new fields or invariants.

**Step 3: Write the minimal schema implementation**

```python
class ChatCompletionRequest(BaseModel):
    ...
    thinking_budget_tokens: Optional[int] = Field(
        None,
        ge=0,
        description="[llama.cpp extension] App-level thinking budget in tokens. Only valid when the resolved target provider is llama.cpp.",
    )
    grammar_mode: Optional[Literal["none", "library", "inline"]] = Field(
        None,
        description="[llama.cpp extension] How to resolve the outbound grammar payload.",
    )
    grammar_id: Optional[str] = Field(
        None,
        min_length=1,
        max_length=128,
        description="[llama.cpp extension] Saved grammar identifier when grammar_mode='library'.",
    )
    grammar_inline: Optional[str] = Field(
        None,
        max_length=200_000,
        description="[llama.cpp extension] Inline grammar when grammar_mode='inline'.",
    )
    grammar_override: Optional[str] = Field(
        None,
        max_length=200_000,
        description="[llama.cpp extension] Optional per-request override applied on top of a saved grammar selection.",
    )

    @model_validator(mode="after")
    def validate_llamacpp_grammar_fields(self):
        if self.grammar_mode == "library" and not self.grammar_id:
            raise ValueError("grammar_id is required when grammar_mode is 'library'")
        if self.grammar_mode == "inline" and not self.grammar_inline:
            raise ValueError("grammar_inline is required when grammar_mode is 'inline'")
        return self
```

**Step 4: Run tests to verify they pass**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/unit/test_chat_request_schemas.py tldw_Server_API/tests/Chat_NEW/unit/test_chat_schemas.py -k llamacpp`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py \
  tldw_Server_API/tests/Chat/unit/test_chat_request_schemas.py \
  tldw_Server_API/tests/Chat_NEW/unit/test_chat_schemas.py
git commit -m "feat(chat-schema): add llama.cpp grammar request fields"
```

### Task 2: Add Shared Llama.cpp Request Extension Resolver

**Files:**
- Create: `tldw_Server_API/app/core/LLM_Calls/llamacpp_request_extensions.py`
- Modify: `tldw_Server_API/app/core/Chat/chat_service.py`
- Test: `tldw_Server_API/tests/LLM_Calls/test_llamacpp_request_extensions.py`
- Test: `tldw_Server_API/tests/LLM_Calls/test_llamacpp_strict_filter.py`

**Step 1: Write the failing tests**

```python
def test_resolver_merges_saved_grammar_into_extra_body():
    payload = resolve_llamacpp_request_extensions(
        request_fields={
            "grammar_mode": "library",
            "grammar_id": "grammar_1",
            "grammar_override": None,
            "thinking_budget_tokens": None,
            "extra_body": {"mirostat": 2},
        },
        provider="llama.cpp",
        grammar_record={"id": "grammar_1", "grammar_text": 'root ::= "ok"'},
        runtime_caps={"strict_openai_compat": False, "thinking_budget": {"supported": False}},
    )
    assert payload["extra_body"]["grammar"] == 'root ::= "ok"'
    assert payload["extra_body"]["mirostat"] == 2


def test_resolver_overrides_conflicting_raw_extra_body_grammar():
    payload = resolve_llamacpp_request_extensions(
        request_fields={
            "grammar_mode": "inline",
            "grammar_inline": 'root ::= "inline"',
            "extra_body": {"grammar": 'root ::= "raw"'},
        },
        provider="llama.cpp",
        grammar_record=None,
        runtime_caps={"strict_openai_compat": False, "thinking_budget": {"supported": False}},
    )
    assert payload["extra_body"]["grammar"] == 'root ::= "inline"'


def test_resolver_rejects_advanced_fields_when_strict_mode_is_effective():
    with pytest.raises(ChatBadRequestError):
        resolve_llamacpp_request_extensions(
            request_fields={"grammar_mode": "inline", "grammar_inline": 'root ::= "x"'},
            provider="llama.cpp",
            grammar_record=None,
            runtime_caps={"strict_openai_compat": True, "thinking_budget": {"supported": False}},
        )
```

**Step 2: Run tests to verify they fail**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/LLM_Calls/test_llamacpp_request_extensions.py tldw_Server_API/tests/LLM_Calls/test_llamacpp_strict_filter.py`

Expected: FAIL because the resolver module does not exist and the strict guard does not understand the new fields.

**Step 3: Write the minimal resolver and wire it into `build_call_params_from_request`**

```python
def resolve_llamacpp_request_extensions(
    *,
    request_fields: Mapping[str, Any],
    provider: str,
    grammar_record: Mapping[str, Any] | None,
    runtime_caps: Mapping[str, Any],
) -> dict[str, Any]:
    if provider != "llama.cpp":
        if any(request_fields.get(key) is not None for key in (
            "thinking_budget_tokens", "grammar_mode", "grammar_id", "grammar_inline", "grammar_override"
        )):
            raise ChatBadRequestError(provider=provider, message="llama.cpp extension fields require the resolved target provider to be 'llama.cpp'")
        return {"extra_body": dict(request_fields.get("extra_body") or {})}

    if runtime_caps.get("strict_openai_compat"):
        raise ChatBadRequestError(provider=provider, message="llama.cpp advanced controls are disabled by strict_openai_compat")

    extra_body = dict(request_fields.get("extra_body") or {})
    grammar_text = ...
    if grammar_text:
        extra_body["grammar"] = grammar_text

    thinking_caps = runtime_caps.get("thinking_budget") or {}
    if request_fields.get("thinking_budget_tokens") is not None:
        if not thinking_caps.get("supported"):
            raise ChatBadRequestError(provider=provider, message="thinking_budget_tokens is not supported by this deployment")
        extra_body[thinking_caps["request_key"]] = int(request_fields["thinking_budget_tokens"])

    return {"extra_body": extra_body}
```

In `chat_service.build_call_params_from_request(...)`, call the resolver before `cleaned_args` is finalized and replace `extra_body` with the resolved value.

Important:

1. Pass `target_api_provider` into the resolver. Do not guard on `request_data.api_provider`.
2. Add a shared runtime helper in this module that resolves:
   - `strict_openai_compat`
   - `thinking_budget_request_key`
   from `LLAMA_CPP_THINKING_BUDGET_PARAM` first, then `Local-API.llama_cpp_thinking_budget_param`.
3. Use that same runtime helper from provider metadata code in Task 3 to avoid drift.

**Step 4: Run tests to verify they pass**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/LLM_Calls/test_llamacpp_request_extensions.py tldw_Server_API/tests/LLM_Calls/test_llamacpp_strict_filter.py`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/LLM_Calls/llamacpp_request_extensions.py \
  tldw_Server_API/app/core/Chat/chat_service.py \
  tldw_Server_API/tests/LLM_Calls/test_llamacpp_request_extensions.py \
  tldw_Server_API/tests/LLM_Calls/test_llamacpp_strict_filter.py
git commit -m "feat(chat): add llama.cpp request extension resolver"
```

### Task 3: Expose Stable `llama_cpp_controls` Capability Metadata

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/llm_providers.py`
- Modify: `tldw_Server_API/app/core/LLM_Calls/extra_body_compat_catalog.py`
- Test: `tldw_Server_API/tests/LLM_Adapters/unit/test_llm_providers_capabilities_merge.py`

**Step 1: Write the failing tests**

```python
def test_llm_providers_exposes_llama_cpp_controls_block(llm_client):
    response = llm_client.get("/api/v1/llm/providers")
    data = response.json()["providers"]
    llama = data["llama.cpp"]
    controls = llama["llama_cpp_controls"]
    assert controls["grammar"]["supported"] is True
    assert "thinking_budget" in controls
    assert "reserved_extra_body_keys" in controls


def test_llm_providers_disables_thinking_budget_without_verified_mapping(monkeypatch, llm_client):
    monkeypatch.delenv("LLAMA_CPP_THINKING_BUDGET_PARAM", raising=False)
    response = llm_client.get("/api/v1/llm/providers")
    controls = response.json()["providers"]["llama.cpp"]["llama_cpp_controls"]
    assert controls["thinking_budget"]["supported"] is False


def test_llm_providers_exposes_reserved_key_when_mapping_configured(monkeypatch, llm_client):
    monkeypatch.setenv("LLAMA_CPP_THINKING_BUDGET_PARAM", "reasoning_budget")
    response = llm_client.get("/api/v1/llm/providers")
    controls = response.json()["providers"]["llama.cpp"]["llama_cpp_controls"]
    assert controls["thinking_budget"]["request_key"] == "reasoning_budget"
    assert "reasoning_budget" in controls["reserved_extra_body_keys"]
```

**Step 2: Run tests to verify they fail**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/LLM_Adapters/unit/test_llm_providers_capabilities_merge.py -k llama_cpp_controls`

Expected: FAIL because the endpoint does not yet return the new capability block.

**Step 3: Implement runtime capability helpers**

```python
def resolve_llama_cpp_control_caps(runtime_context: Mapping[str, Any]) -> dict[str, Any]:
    strict_mode = bool(runtime_context.get("strict_openai_compat"))
    request_key = str(runtime_context.get("thinking_budget_request_key") or "").strip()
    reserved_keys = ["grammar"]
    if request_key:
        reserved_keys.append(request_key)
    return {
        "grammar": {
            "supported": not strict_mode,
            "effective_reason": "disabled by strict_openai_compat runtime setting" if strict_mode else "supported in current deployment",
            "source": "first_class+extra_body",
        },
        "thinking_budget": {
            "supported": (not strict_mode) and bool(request_key),
            "request_key": request_key or None,
            "effective_reason": (
                "disabled by strict_openai_compat runtime setting" if strict_mode
                else "no configured thinking-budget mapping for this deployment"
                if not request_key else "supported in current deployment"
            ),
        },
        "reserved_extra_body_keys": reserved_keys,
    }
```

Update `_build_runtime_context(...)` to read:

- `LOCAL_LLM_STRICT_OPENAI_COMPAT`
- `LLAMA_CPP_THINKING_BUDGET_PARAM`
- `Local-API.llama_cpp_thinking_budget_param`

Attach `llama_cpp_controls` only for the `llama.cpp` provider object and its `models_info` entries where relevant.

**Step 4: Run tests to verify they pass**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/LLM_Adapters/unit/test_llm_providers_capabilities_merge.py -k llama_cpp_controls`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/llm_providers.py \
  tldw_Server_API/app/core/LLM_Calls/extra_body_compat_catalog.py \
  tldw_Server_API/tests/LLM_Adapters/unit/test_llm_providers_capabilities_merge.py
git commit -m "feat(providers): expose llama.cpp controls capability metadata"
```

### Task 4: Add User-Scoped Grammar Library Persistence And Service

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/chat_grammar_schemas.py`
- Create: `tldw_Server_API/app/core/Character_Chat/chat_grammar.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Test: `tldw_Server_API/tests/Character_Chat_NEW/unit/test_chat_grammar_unit.py`

**Step 1: Write the failing tests**

```python
def test_chat_grammar_service_creates_and_reads_grammar(chacha_db):
    service = ChatGrammarService(chacha_db)
    grammar_id = service.create_grammar(
        name="JSON Root",
        description="Simple test grammar",
        grammar_text='root ::= "ok"',
    )
    grammar = service.get_grammar(grammar_id)
    assert grammar["name"] == "JSON Root"
    assert grammar["validation_status"] == "unchecked"


def test_chat_grammar_service_archives_without_deleting_text(chacha_db):
    service = ChatGrammarService(chacha_db)
    grammar_id = service.create_grammar(name="Archive Me", description="", grammar_text='root ::= "x"')
    service.archive_grammar(grammar_id)
    grammar = service.get_grammar(grammar_id, include_archived=True)
    assert grammar["is_archived"] is True
    assert grammar["grammar_text"] == 'root ::= "x"'
```

**Step 2: Run tests to verify they fail**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Character_Chat_NEW/unit/test_chat_grammar_unit.py`

Expected: FAIL because the service and DB support do not exist.

**Step 3: Implement the DB table and service**

```python
CREATE TABLE IF NOT EXISTS chat_grammars (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    grammar_text TEXT NOT NULL,
    validation_status TEXT NOT NULL DEFAULT 'unchecked',
    validation_error TEXT,
    last_validated_at TIMESTAMP,
    is_archived BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT 0
);
```

```python
class ChatGrammarService:
    def __init__(self, db: CharactersRAGDB):
        self.db = db

    def create_grammar(...): ...
    def list_grammars(...): ...
    def get_grammar(...): ...
    def update_grammar(...): ...
    def archive_grammar(...): ...
    def delete_grammar(...): ...
```

Mirror the optimistic-locking and per-user ownership style used by `ChatDictionaryService`.

**Step 4: Run tests to verify they pass**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Character_Chat_NEW/unit/test_chat_grammar_unit.py`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/chat_grammar_schemas.py \
  tldw_Server_API/app/core/Character_Chat/chat_grammar.py \
  tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
  tldw_Server_API/tests/Character_Chat_NEW/unit/test_chat_grammar_unit.py
git commit -m "feat(chat): add user-scoped grammar library service"
```

### Task 5: Add Grammar Library API Endpoints And Router Wiring

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/chat_grammars.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/chat.py`
- Test: `tldw_Server_API/tests/Chat/unit/test_chat_grammar_endpoints.py`

**Step 1: Write the failing endpoint tests**

```python
@pytest.mark.asyncio
async def test_create_and_list_chat_grammars(chacha_db):
    created = await chat_grammar_endpoints.create_chat_grammar(
        ChatGrammarCreate(name="Root", description="desc", grammar_text='root ::= "ok"'),
        db=chacha_db,
    )
    assert created.name == "Root"

    listing = await chat_grammar_endpoints.list_chat_grammars(db=chacha_db)
    assert listing.total == 1
    assert listing.items[0].id == created.id


@pytest.mark.asyncio
async def test_get_archived_grammar_requires_include_archived(chacha_db):
    ...
```

**Step 2: Run tests to verify they fail**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/unit/test_chat_grammar_endpoints.py`

Expected: FAIL because the router and schemas are missing.

**Step 3: Implement router and include it from `chat.py`**

```python
router = APIRouter(prefix="/grammars", tags=["chat-grammars"])

@router.post("", response_model=ChatGrammarResponse, status_code=201)
async def create_chat_grammar(...): ...

@router.get("", response_model=ChatGrammarListResponse)
async def list_chat_grammars(...): ...

@router.get("/{grammar_id}", response_model=ChatGrammarResponse)
async def get_chat_grammar(...): ...

@router.patch("/{grammar_id}", response_model=ChatGrammarResponse)
async def update_chat_grammar(...): ...

@router.delete("/{grammar_id}", status_code=204)
async def delete_chat_grammar(...): ...
```

In `tldw_Server_API/app/api/v1/endpoints/chat.py`:

```python
from . import chat_dictionaries, chat_documents, chat_grammars
router.include_router(chat_grammars.router)
```

**Step 4: Run tests to verify they pass**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/unit/test_chat_grammar_endpoints.py`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/chat_grammars.py \
  tldw_Server_API/app/api/v1/endpoints/chat.py \
  tldw_Server_API/tests/Chat/unit/test_chat_grammar_endpoints.py
git commit -m "feat(chat-api): add grammar library endpoints"
```

### Task 6: Add Chat-Completions Integration Coverage For Grammar Resolution And Guards

**Files:**
- Create: `tldw_Server_API/tests/Chat_NEW/integration/test_chat_llamacpp_extensions_api.py`
- Modify: `tldw_Server_API/app/core/Chat/chat_service.py`
- Modify: `tldw_Server_API/app/core/LLM_Calls/llamacpp_request_extensions.py`

**Step 1: Write the failing integration tests**

```python
def test_chat_completions_resolves_saved_grammar_into_llamacpp_payload(client, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Chat.chat_service.perform_chat_api_call",
        lambda **kwargs: captured.update(kwargs) or {"choices": [{"message": {"content": "ok"}}]},
    )
    response = client.post(
        "/api/v1/chat/completions",
        json={
            "model": "llama.cpp/local-model",
            "messages": [{"role": "user", "content": "x"}],
            "grammar_mode": "inline",
            "grammar_inline": 'root ::= "ok"',
        },
    )
    assert response.status_code == 200
    assert captured["api_endpoint"] == "llama.cpp"
    assert captured["extra_body"]["grammar"] == 'root ::= "ok"'


def test_chat_completions_rejects_llamacpp_fields_for_openai(client):
    response = client.post(
        "/api/v1/chat/completions",
        json={
            "api_provider": "openai",
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "x"}],
            "grammar_mode": "inline",
            "grammar_inline": 'root ::= "ok"',
        },
    )
    assert response.status_code == 400
```

**Step 2: Run tests to verify they fail**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat_NEW/integration/test_chat_llamacpp_extensions_api.py`

Expected: FAIL because the endpoint path does not yet resolve grammars or enforce the provider guard end to end.

**Step 3: Finish integration wiring**

Ensure `build_call_params_from_request(...)`:

1. loads the grammar record when `grammar_mode == "library"`
2. calls the shared resolver
3. passes the resolved `target_api_provider` into the resolver
4. returns translated `extra_body`
5. raises stable `HTTPException`/`ChatBadRequestError` for invalid provider or missing grammar references

**Step 4: Run tests to verify they pass**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat_NEW/integration/test_chat_llamacpp_extensions_api.py`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Chat_NEW/integration/test_chat_llamacpp_extensions_api.py \
  tldw_Server_API/app/core/Chat/chat_service.py \
  tldw_Server_API/app/core/LLM_Calls/llamacpp_request_extensions.py
git commit -m "test(chat): cover llama.cpp grammar request integration"
```

### Task 7: Extend Frontend Shared State And Session Persistence

**Files:**
- Modify: `apps/packages/ui/src/store/model.tsx`
- Modify: `apps/packages/ui/src/store/sidepanel-chat-tabs.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-chat.tsx`
- Modify: `apps/packages/ui/src/services/model-settings.ts`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage9.persistence.test.tsx`
- Create: `apps/packages/ui/src/store/__tests__/model.llamacpp-controls.test.ts`

**Step 1: Write the failing frontend tests**

```ts
it("stores llama.cpp grammar settings in ChatModelSettings", () => {
  const store = useStoreChatModelSettings.getState()
  store.updateSettings({
    llamaGrammarMode: "library",
    llamaGrammarId: "grammar_1",
    llamaGrammarOverride: 'root ::= "override"',
    llamaThinkingBudgetTokens: 64
  })
  const next = useStoreChatModelSettings.getState()
  expect(next.llamaGrammarMode).toBe("library")
  expect(next.llamaThinkingBudgetTokens).toBe(64)
})

it("persists llama.cpp settings in sidepanel snapshots", () => {
  ...
})
```

**Step 2: Run tests to verify they fail**

Run:
`bunx vitest run apps/packages/ui/src/store/__tests__/model.llamacpp-controls.test.ts apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage9.persistence.test.tsx`

Expected: FAIL because the store and snapshot types do not yet include the new fields.

**Step 3: Add the new state keys everywhere the snapshot model is duplicated**

```ts
type ChatModelSettings = {
  ...
  llamaThinkingBudgetTokens?: number
  llamaGrammarMode?: "none" | "library" | "inline"
  llamaGrammarId?: string
  llamaGrammarInline?: string
  llamaGrammarOverride?: string
}
```

Update:

- the Zustand store state and setters
- `ChatModelSettingsSnapshot`
- `MODEL_SETTINGS_KEYS`
- sidepanel snapshot pick/apply helpers
- persisted settings helpers in `model-settings.ts`

Do not treat this as a single persistence path. The task is only complete when the new keys round-trip through all duplicated state definitions.

**Step 4: Run tests to verify they pass**

Run:
`bunx vitest run apps/packages/ui/src/store/__tests__/model.llamacpp-controls.test.ts apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage9.persistence.test.tsx`

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/store/model.tsx \
  apps/packages/ui/src/store/sidepanel-chat-tabs.tsx \
  apps/packages/ui/src/routes/sidepanel-chat.tsx \
  apps/packages/ui/src/services/model-settings.ts \
  apps/packages/ui/src/store/__tests__/model.llamacpp-controls.test.ts \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage9.persistence.test.tsx
git commit -m "feat(ui-state): persist llama.cpp grammar settings"
```

### Task 8: Add Grammar Library Client And Llama.cpp Controls UI

**Files:**
- Create: `apps/packages/ui/src/services/tldw/TldwLlamaGrammars.ts`
- Create: `apps/packages/ui/src/components/Common/Settings/LlamaGrammarLibraryModal.tsx`
- Create: `apps/packages/ui/src/components/Common/Settings/LlamaCppAdvancedControls.tsx`
- Modify: `apps/packages/ui/src/components/Sidepanel/Chat/ModelParamsPanel.tsx`
- Modify: `apps/packages/ui/src/components/Sidepanel/Chat/form.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Modify: `apps/packages/ui/src/services/tldw/TldwChat.ts`
- Modify: `apps/packages/ui/src/components/Common/Settings/CurrentChatModelSettings.tsx`
- Create: `apps/packages/ui/src/components/Sidepanel/Chat/__tests__/ModelParamsPanel.llamacpp-controls.test.tsx`
- Create: `apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.llamacpp-controls.integration.test.tsx`

**Step 1: Write the failing UI/request tests**

```tsx
it("shows llama.cpp advanced controls when the selected model resolves to llama.cpp", () => {
  mockChatModelSettings({ apiProvider: "" })
  mockSelectedModel("llama.cpp/local-model")
  render(<ModelParamsPanel />)
  expect(screen.getByText(/Grammar source/i)).toBeInTheDocument()
})

it("builds chat request with first-class llama.cpp fields and parsed extra_body", async () => {
  mockChatModelSettings({
    apiProvider: "llama.cpp",
    llamaGrammarMode: "inline",
    llamaGrammarInline: 'root ::= "ok"',
    llamaThinkingBudgetTokens: 64,
    extraBody: '{"mirostat":2}'
  })
  ...
  expect(sentBody.grammar_mode).toBe("inline")
  expect(sentBody.grammar_inline).toContain('root ::= "ok"')
  expect(sentBody.extra_body).toEqual({ mirostat: 2 })
})
```

**Step 2: Run tests to verify they fail**

Run:
`bunx vitest run apps/packages/ui/src/components/Sidepanel/Chat/__tests__/ModelParamsPanel.llamacpp-controls.test.tsx apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.llamacpp-controls.integration.test.tsx`

Expected: FAIL because the controls, client, and request fields do not exist.

**Step 3: Implement the UI and request plumbing**

Add a small client:

```ts
export class TldwLlamaGrammars {
  list() { ... }
  create(input) { ... }
  update(id, input) { ... }
  remove(id) { ... }
}
```

Add a shared controls component:

```tsx
export function LlamaCppAdvancedControls({ resolvedProvider }: { resolvedProvider: string | null }) {
  const grammarMode = useStoreChatModelSettings((s) => s.llamaGrammarMode)
  ...
  if (resolvedProvider !== "llama.cpp") return null
  return (
    <>
      <InputNumber ... />
      <Segmented options={[...]} ... />
      <Select ... />
      <TextArea ... />
    </>
  )
}
```

In the sidepanel path, plumb `selectedModel` or `resolvedProvider` from `form.tsx` into `ModelParamsPanel`/`LlamaCppAdvancedControls`. Do not key this UI off the raw `apiProvider` field alone.

In `PlaygroundForm.tsx` and `TldwChat.ts`, include:

```ts
thinking_budget_tokens: currentChatModelSettings.llamaThinkingBudgetTokens,
grammar_mode: currentChatModelSettings.llamaGrammarMode,
grammar_id: currentChatModelSettings.llamaGrammarId,
grammar_inline: currentChatModelSettings.llamaGrammarInline,
grammar_override: currentChatModelSettings.llamaGrammarOverride,
```

**Step 4: Run tests to verify they pass**

Run:
`bunx vitest run apps/packages/ui/src/components/Sidepanel/Chat/__tests__/ModelParamsPanel.llamacpp-controls.test.tsx apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.llamacpp-controls.integration.test.tsx`

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/TldwLlamaGrammars.ts \
  apps/packages/ui/src/components/Common/Settings/LlamaGrammarLibraryModal.tsx \
  apps/packages/ui/src/components/Common/Settings/LlamaCppAdvancedControls.tsx \
  apps/packages/ui/src/components/Sidepanel/Chat/ModelParamsPanel.tsx \
  apps/packages/ui/src/components/Sidepanel/Chat/form.tsx \
  apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx \
  apps/packages/ui/src/services/tldw/TldwChat.ts \
  apps/packages/ui/src/components/Common/Settings/CurrentChatModelSettings.tsx \
  apps/packages/ui/src/components/Sidepanel/Chat/__tests__/ModelParamsPanel.llamacpp-controls.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.llamacpp-controls.integration.test.tsx
git commit -m "feat(ui): add llama.cpp grammar and thinking controls"
```

### Task 9: Add Conflict Warnings, API Docs, And Final Verification

**Files:**
- Modify: `apps/packages/ui/src/components/Common/Settings/LlamaCppAdvancedControls.tsx`
- Modify: `Docs/API-related/Chat_API_Documentation.md`
- Modify: `Docs/API-related/Providers_API_Documentation.md`
- Modify: `Docs/API-related/llamacpp_integration_modes.md`

**Step 1: Write the final failing tests**

```tsx
it("warns when raw extraBody contains reserved llama.cpp keys", () => {
  mockChatModelSettings({
    apiProvider: "llama.cpp",
    extraBody: '{"grammar":"root ::= \\"raw\\""}',
    llamaGrammarMode: "inline",
    llamaGrammarInline: 'root ::= "ui"',
  })
  render(<LlamaCppAdvancedControls resolvedProvider="llama.cpp" />)
  expect(screen.getByText(/first-class llama.cpp controls override raw extra body/i)).toBeInTheDocument()
})
```

**Step 2: Run the targeted test suites**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/unit/test_chat_grammar_endpoints.py tldw_Server_API/tests/Character_Chat_NEW/unit/test_chat_grammar_unit.py tldw_Server_API/tests/Chat_NEW/integration/test_chat_llamacpp_extensions_api.py tldw_Server_API/tests/LLM_Adapters/unit/test_llm_providers_capabilities_merge.py tldw_Server_API/tests/LLM_Calls/test_llamacpp_request_extensions.py`

Expected: PASS.

Run:
`bunx vitest run apps/packages/ui/src/store/__tests__/model.llamacpp-controls.test.ts apps/packages/ui/src/components/Sidepanel/Chat/__tests__/ModelParamsPanel.llamacpp-controls.test.tsx apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.llamacpp-controls.integration.test.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage9.persistence.test.tsx`

Expected: PASS.

**Step 3: Run Bandit on touched backend scope**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/chat.py tldw_Server_API/app/api/v1/endpoints/chat_grammars.py tldw_Server_API/app/api/v1/endpoints/llm_providers.py tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py tldw_Server_API/app/api/v1/schemas/chat_grammar_schemas.py tldw_Server_API/app/core/Chat/chat_service.py tldw_Server_API/app/core/Character_Chat/chat_grammar.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/app/core/LLM_Calls/llamacpp_request_extensions.py -f json -o /tmp/bandit_llamacpp_grammar.json`

Expected: `No issues identified` or only pre-existing findings outside the touched behavior.

**Step 4: Update docs**

Document:

1. new chat request fields and llama.cpp-only guard
2. new grammar library endpoints
3. `llama_cpp_controls` capability metadata
4. `strict_openai_compat` disabling advanced controls
5. operator config for thinking-budget mapping: `LLAMA_CPP_THINKING_BUDGET_PARAM` and `Local-API.llama_cpp_thinking_budget_param`
6. explicit v1 boundary: `/chat/completions` only, `/messages` not yet supported

**Step 5: Commit**

```bash
git add Docs/API-related/Chat_API_Documentation.md \
  Docs/API-related/Providers_API_Documentation.md \
  Docs/API-related/llamacpp_integration_modes.md \
  apps/packages/ui/src/components/Common/Settings/LlamaCppAdvancedControls.tsx
git commit -m "docs: document llama.cpp grammar and thinking controls"
```
