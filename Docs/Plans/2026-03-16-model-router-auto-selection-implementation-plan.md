# Model Router Auto Selection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add first-class `model="auto"` routing that resolves to a canonical provider/model pair server-side, uses an LLM router with deterministic fallback, and rolls out first to chat completions before expanding to character chat and writing flows.

**Architecture:** Build a shared routing package under `tldw_Server_API/app/core/LLM_Calls/routing/` and intercept `auto` requests before existing provider/model normalization. Keep the frontend and shared UI client aware of `auto` as an explicit sentinel, add a nested `routing` request object, and reuse the existing usage/budget infrastructure to account for router calls separately from execution calls.

**Tech Stack:** FastAPI, Pydantic, existing config parser (`config.py`), shared UI package (`apps/packages/ui/src`), Vitest, pytest, Loguru, existing AuthNZ usage tracking.

---

### Task 1: Add Routing Request/Policy Types And Config Loading

**Files:**
- Create: `tldw_Server_API/app/core/LLM_Calls/routing/__init__.py`
- Create: `tldw_Server_API/app/core/LLM_Calls/routing/models.py`
- Create: `tldw_Server_API/app/core/LLM_Calls/routing/policy.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Test: `tldw_Server_API/tests/Chat/unit/test_model_router_policy.py`
- Test: `apps/packages/ui/src/services/__tests__/tldw-api-client.chat-mutations.test.ts`

**Step 1: Write the failing tests**

```python
def test_policy_defaults_to_server_default_provider_boundary():
    policy = resolve_routing_policy(request_model="auto", explicit_provider=None)
    assert policy.boundary_mode == "server_default_provider"
    assert policy.objective == "highest_quality"
```

```ts
it("accepts nested routing overrides on chat completion requests", async () => {
  const request: ChatCompletionRequest = {
    model: "auto",
    messages: [{ role: "user", content: "hello" }],
    routing: { mode: "per_turn", cross_provider: false }
  }
  expect(request.routing?.mode).toBe("per_turn")
})
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/unit/test_model_router_policy.py -v`
Expected: FAIL because routing policy types do not exist yet.

Run: `bunx vitest run apps/packages/ui/src/services/__tests__/tldw-api-client.chat-mutations.test.ts`
Expected: FAIL because `ChatCompletionRequest` does not expose `routing`.

**Step 3: Write the minimal implementation**

Add:

- `RoutingOverride`, `RoutingPolicy`, `RoutingBoundaryMode`, and `RoutingDecision` dataclasses/Pydantic models in `models.py`
- `resolve_routing_policy(...)` in `policy.py`
- `routing: Optional[RoutingOverride]` in `ChatCompletionRequest`
- matching `routing?: { ... }` typing in `TldwApiClient.ts`

Keep `routing` optional and server-extension-only.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/unit/test_model_router_policy.py -v`
Expected: PASS

Run: `bunx vitest run apps/packages/ui/src/services/__tests__/tldw-api-client.chat-mutations.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/LLM_Calls/routing/__init__.py tldw_Server_API/app/core/LLM_Calls/routing/models.py tldw_Server_API/app/core/LLM_Calls/routing/policy.py tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py apps/packages/ui/src/services/tldw/TldwApiClient.ts tldw_Server_API/tests/Chat/unit/test_model_router_policy.py apps/packages/ui/src/services/__tests__/tldw-api-client.chat-mutations.test.ts
git commit -m "feat: add model routing policy and request types"
```

### Task 2: Build Candidate Pool Filtering And Ranking Metadata

**Files:**
- Create: `tldw_Server_API/app/core/LLM_Calls/routing/candidate_pool.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/llm_providers.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/llm_provider_overrides.py`
- Test: `tldw_Server_API/tests/Chat/unit/test_model_router_candidates.py`
- Test: `tldw_Server_API/tests/AuthNZ_Unit/test_llm_provider_overrides.py`

**Step 1: Write the failing tests**

```python
def test_candidate_pool_filters_models_outside_pinned_provider():
    candidates = build_candidate_pool(
        boundary_mode="pinned_provider",
        pinned_provider="openai",
        requested_capabilities={"tools": True},
        catalog=[
            {"provider": "openai", "model": "gpt-4.1", "tool_support": True},
            {"provider": "anthropic", "model": "claude-sonnet-4.5", "tool_support": True},
        ],
    )
    assert [(c.provider, c.model) for c in candidates] == [("openai", "gpt-4.1")]
```

```python
def test_candidate_pool_uses_admin_order_when_quality_rank_missing():
    chosen = choose_ranked_candidate(
        [
            {"provider": "openai", "model": "gpt-4.1-mini"},
            {"provider": "openai", "model": "gpt-4.1"},
        ],
        provider_order={"openai": ["gpt-4.1", "gpt-4.1-mini"]},
    )
    assert chosen["model"] == "gpt-4.1"
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/unit/test_model_router_candidates.py -v`
Expected: FAIL because the candidate pool module does not exist.

**Step 3: Write the minimal implementation**

Add:

- candidate record model with canonical provider/model fields
- provider-boundary filtering
- capability filtering (`tools`, `vision`, `json_mode`, `reasoning`, context)
- admin override enforcement
- ranking metadata support in `llm_providers.py`
- fallback ordered-list support when `quality_rank` is absent

Do not add cross-provider ranking heuristics beyond explicit metadata and admin order.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/unit/test_model_router_candidates.py -v`
Expected: PASS

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Unit/test_llm_provider_overrides.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/LLM_Calls/routing/candidate_pool.py tldw_Server_API/app/api/v1/endpoints/llm_providers.py tldw_Server_API/app/core/AuthNZ/llm_provider_overrides.py tldw_Server_API/tests/Chat/unit/test_model_router_candidates.py tldw_Server_API/tests/AuthNZ_Unit/test_llm_provider_overrides.py
git commit -m "feat: add model router candidate filtering"
```

### Task 3: Implement Deterministic Rules Router And Sticky Decision Store

**Files:**
- Create: `tldw_Server_API/app/core/LLM_Calls/routing/rules_router.py`
- Create: `tldw_Server_API/app/core/LLM_Calls/routing/decision_store.py`
- Test: `tldw_Server_API/tests/Chat/unit/test_model_router_rules.py`
- Test: `tldw_Server_API/tests/Chat/unit/test_model_router_sticky.py`

**Step 1: Write the failing tests**

```python
def test_rules_router_prefers_highest_quality_candidate_for_default_objective():
    decision = route_with_rules(
        objective="highest_quality",
        candidates=[
            candidate("openai", "gpt-4.1-mini", quality_rank=20),
            candidate("openai", "gpt-4.1", quality_rank=10),
        ],
    )
    assert decision.model == "gpt-4.1"
```

```python
def test_sticky_decision_is_bypassed_when_tools_become_required():
    store = InMemoryRoutingDecisionStore()
    store.save(scope="conv-1", fingerprint="chat|no-tools", provider="openai", model="gpt-4.1-mini")
    reused = maybe_reuse_sticky_decision(
        store=store,
        scope="conv-1",
        fingerprint="chat|tools-required",
    )
    assert reused is None
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/unit/test_model_router_rules.py tldw_Server_API/tests/Chat/unit/test_model_router_sticky.py -v`
Expected: FAIL because rules router and decision store do not exist.

**Step 3: Write the minimal implementation**

Add:

- `route_with_rules(...)`
- deterministic fingerprint computation
- scope-aware sticky save/load helpers
- automatic sticky bypass for hard capability changes

Start with in-memory storage and keep the persistence seam explicit for later expansion.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/unit/test_model_router_rules.py tldw_Server_API/tests/Chat/unit/test_model_router_sticky.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/LLM_Calls/routing/rules_router.py tldw_Server_API/app/core/LLM_Calls/routing/decision_store.py tldw_Server_API/tests/Chat/unit/test_model_router_rules.py tldw_Server_API/tests/Chat/unit/test_model_router_sticky.py
git commit -m "feat: add deterministic model router fallback"
```

### Task 4: Implement LLM Router Strategy And Canonical Routing Service

**Files:**
- Create: `tldw_Server_API/app/core/LLM_Calls/routing/llm_router.py`
- Create: `tldw_Server_API/app/core/LLM_Calls/routing/service.py`
- Test: `tldw_Server_API/tests/Chat/unit/test_model_router_llm_strategy.py`
- Test: `tldw_Server_API/tests/Chat/unit/test_model_router_service.py`

**Step 1: Write the failing tests**

```python
def test_llm_router_rejects_choice_outside_candidate_set():
    result = validate_llm_router_choice(
        raw_choice={"provider": "anthropic", "model": "claude-opus-4.1"},
        candidates=[candidate("openai", "gpt-4.1")],
    )
    assert result is None
```

```python
def test_model_router_service_marks_routed_decision_as_canonical():
    decision = route_model(
        request=router_request(model="auto", surface="chat"),
        policy=default_policy(),
        candidates=[candidate("openai", "gpt-4.1")],
    )
    assert decision.canonical is True
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/unit/test_model_router_llm_strategy.py tldw_Server_API/tests/Chat/unit/test_model_router_service.py -v`
Expected: FAIL because the LLM router and service do not exist.

**Step 3: Write the minimal implementation**

Add:

- compact router prompt builder
- structured output parsing and validation
- router-model exclusion from candidates
- service orchestration: candidate pool -> sticky reuse -> LLM router -> rules router
- canonical decision output that downstream code can trust

Do not pass full message history, raw tool schemas, file contents, or image bytes to the router prompt.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/unit/test_model_router_llm_strategy.py tldw_Server_API/tests/Chat/unit/test_model_router_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/LLM_Calls/routing/llm_router.py tldw_Server_API/app/core/LLM_Calls/routing/service.py tldw_Server_API/tests/Chat/unit/test_model_router_llm_strategy.py tldw_Server_API/tests/Chat/unit/test_model_router_service.py
git commit -m "feat: add llm-backed model routing service"
```

### Task 5: Add Router Accounting And Telemetry

**Files:**
- Create: `tldw_Server_API/app/core/LLM_Calls/routing/accounting.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/chat.py`
- Test: `tldw_Server_API/tests/Chat/integration/test_chat_endpoint_auto_routing.py`
- Test: `tldw_Server_API/tests/Chat/unit/test_model_router_accounting.py`

**Step 1: Write the failing tests**

```python
def test_router_and_execution_calls_are_logged_as_separate_operations():
    rows = capture_usage_rows_for_auto_routed_request()
    assert [row["operation"] for row in rows] == ["model_router", "chat.completions"]
```

```python
def test_chat_endpoint_includes_no_routing_debug_without_opt_in():
    response = client.post("/api/v1/chat/completions", json={"model": "auto", "messages": [{"role": "user", "content": "hi"}]})
    assert "routing" not in response.json()
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/unit/test_model_router_accounting.py tldw_Server_API/tests/Chat/integration/test_chat_endpoint_auto_routing.py -v`
Expected: FAIL because router usage logging and endpoint routing are not wired.

**Step 3: Write the minimal implementation**

Add:

- router telemetry helper
- separate operation names for router vs. execution usage rows
- explicit correlation data between a routed request and its router call
- opt-in debug payload/header handling

Re-use the existing `llm_usage_log` path instead of creating a new telemetry store.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/unit/test_model_router_accounting.py tldw_Server_API/tests/Chat/integration/test_chat_endpoint_auto_routing.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/LLM_Calls/routing/accounting.py tldw_Server_API/app/api/v1/endpoints/chat.py tldw_Server_API/tests/Chat/unit/test_model_router_accounting.py tldw_Server_API/tests/Chat/integration/test_chat_endpoint_auto_routing.py
git commit -m "feat: log model router usage separately"
```

### Task 6: Integrate Auto Routing Into Chat Completions

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/chat.py`
- Modify: `tldw_Server_API/app/core/Chat/chat_service.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py`
- Test: `tldw_Server_API/tests/Chat/integration/test_chat_endpoint_auto_routing.py`
- Test: `tldw_Server_API/tests/Chat/unit/test_chat_default_provider.py`

**Step 1: Write the failing tests**

```python
def test_chat_endpoint_routes_auto_before_provider_normalization(client):
    response = client.post(
        "/api/v1/chat/completions",
        json={"model": "auto", "messages": [{"role": "user", "content": "summarize this"}]},
    )
    assert response.status_code == 200
    assert response.json()["model"] != "auto"
```

```python
def test_canonical_routing_decision_skips_follow_up_provider_inference():
    decision = make_canonical_decision(provider="openrouter", model="anthropic/claude-4.5-sonnet")
    provider, model = apply_execution_resolution(decision)
    assert (provider, model) == ("openrouter", "anthropic/claude-4.5-sonnet")
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/integration/test_chat_endpoint_auto_routing.py tldw_Server_API/tests/Chat/unit/test_chat_default_provider.py -v`
Expected: FAIL because the chat endpoint does not route `auto` yet.

**Step 3: Write the minimal implementation**

Add an early `model == "auto"` interception point in `chat.py` before the current provider/model normalization path. Feed the resulting canonical decision into downstream execution without renormalizing it in `chat_service.py`.

Keep explicit-model behavior unchanged.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/integration/test_chat_endpoint_auto_routing.py tldw_Server_API/tests/Chat/unit/test_chat_default_provider.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/chat.py tldw_Server_API/app/core/Chat/chat_service.py tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py tldw_Server_API/tests/Chat/integration/test_chat_endpoint_auto_routing.py tldw_Server_API/tests/Chat/unit/test_chat_default_provider.py
git commit -m "feat: route auto model selections in chat completions"
```

### Task 7: Make The Shared UI Treat `auto` As A Valid Model Sentinel

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Models/index.tsx`
- Modify: `apps/packages/ui/src/utils/chat-model-availability.ts`
- Modify: `apps/packages/ui/src/utils/resolve-api-provider.ts`
- Modify: `apps/packages/ui/src/services/tldw/TldwChat.ts`
- Modify: `apps/packages/ui/src/models/ChatTldw.ts`
- Test: `apps/packages/ui/src/utils/__tests__/chat-model-availability.test.ts`
- Test: `apps/packages/ui/src/utils/__tests__/resolve-api-provider.test.ts`
- Test: `apps/packages/ui/src/hooks/__tests__/useMessageOption.selected-model-sync.test.tsx`

**Step 1: Write the failing tests**

```ts
it("treats auto as a valid selected model during availability checks", () => {
  expect(normalizeChatModelId("auto")).toBe("auto")
  expect(findUnavailableChatModel(["auto"], ["gpt-4.1"])).toBeNull()
})
```

```ts
it("does not force a concrete provider inference for auto selections", async () => {
  await expect(resolveApiProviderForModel({ modelId: "auto" })).resolves.toBeUndefined()
})
```

```ts
it("keeps selectedModel synced without clearing auto selections", async () => {
  // render/use hook, set selectedModel=auto, and verify sync logic preserves it
})
```

**Step 2: Run tests to verify they fail**

Run: `bunx vitest run apps/packages/ui/src/utils/__tests__/chat-model-availability.test.ts apps/packages/ui/src/utils/__tests__/resolve-api-provider.test.ts apps/packages/ui/src/hooks/__tests__/useMessageOption.selected-model-sync.test.tsx`
Expected: FAIL because `auto` is currently treated like a non-catalog model or missing selection.

**Step 3: Write the minimal implementation**

Add:

- explicit `auto` option in model settings UI
- `auto` special-casing in availability and validation helpers
- no forced provider inference when `modelId === "auto"`
- nested `routing` object pass-through in shared request builders

Keep concrete model behavior unchanged.

**Step 4: Run tests to verify they pass**

Run: `bunx vitest run apps/packages/ui/src/utils/__tests__/chat-model-availability.test.ts apps/packages/ui/src/utils/__tests__/resolve-api-provider.test.ts apps/packages/ui/src/hooks/__tests__/useMessageOption.selected-model-sync.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Models/index.tsx apps/packages/ui/src/utils/chat-model-availability.ts apps/packages/ui/src/utils/resolve-api-provider.ts apps/packages/ui/src/services/tldw/TldwChat.ts apps/packages/ui/src/models/ChatTldw.ts apps/packages/ui/src/utils/__tests__/chat-model-availability.test.ts apps/packages/ui/src/utils/__tests__/resolve-api-provider.test.ts apps/packages/ui/src/hooks/__tests__/useMessageOption.selected-model-sync.test.tsx
git commit -m "feat: support auto model sentinel in shared ui"
```

### Task 8: Integrate Character Chat And Writing Playground With Canonical Routing

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/chat_session_schemas.py`
- Modify: `apps/packages/ui/src/components/Option/WritingPlayground/index.tsx`
- Modify: `apps/packages/ui/src/utils/resolve-api-provider.ts`
- Test: `tldw_Server_API/tests/Character_Chat_NEW/unit/test_chat_completion_precheck.py`
- Test: `tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_chat_auto_routing.py`
- Test: `apps/packages/ui/src/components/Option/WritingPlayground/__tests__/WritingPlayground.phase1-baseline.test.tsx`

**Step 1: Write the failing tests**

```python
def test_character_chat_routes_auto_before_shared_resolution():
    response = post_character_completion(model="auto")
    assert response.status_code == 200
```

```ts
it("writing playground keeps auto selection and submits model='auto'", async () => {
  render(<WritingPlayground />)
  // select auto, trigger generation, assert request body includes model=auto
})
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Character_Chat_NEW/unit/test_chat_completion_precheck.py tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_chat_auto_routing.py -v`
Expected: FAIL because character chat has no auto-routing interception.

Run: `bunx vitest run apps/packages/ui/src/components/Option/WritingPlayground/__tests__/WritingPlayground.phase1-baseline.test.tsx`
Expected: FAIL because writing playground does not preserve `auto` end-to-end.

**Step 3: Write the minimal implementation**

Add:

- early `auto` routing interception in `character_chat_sessions.py`
- `routing` override support in `CharacterChatCompletionV2Request`
- canonical routing pass-through for character chat execution
- writing playground generation support for `model="auto"`
- writing playground token-inspection guard so tokenizer-dependent tools still require a concrete model

Do not implement RAG/media integration in this task.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Character_Chat_NEW/unit/test_chat_completion_precheck.py tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_chat_auto_routing.py -v`
Expected: PASS

Run: `bunx vitest run apps/packages/ui/src/components/Option/WritingPlayground/__tests__/WritingPlayground.phase1-baseline.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py tldw_Server_API/app/api/v1/schemas/chat_session_schemas.py tldw_Server_API/tests/Character_Chat_NEW/unit/test_chat_completion_precheck.py tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_chat_auto_routing.py apps/packages/ui/src/components/Option/WritingPlayground/index.tsx apps/packages/ui/src/utils/resolve-api-provider.ts apps/packages/ui/src/components/Option/WritingPlayground/__tests__/WritingPlayground.phase1-baseline.test.tsx
git commit -m "feat: route auto model selections in character chat and writing"
```

### Task 9: Verification, Security Check, And Final Docs Pass

**Files:**
- Modify: `Docs/Plans/2026-03-16-model-router-auto-selection-design.md`
- Modify: `Docs/Plans/2026-03-16-model-router-auto-selection-implementation-plan.md`

**Step 1: Run the targeted backend tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Chat/unit/test_model_router_policy.py \
  tldw_Server_API/tests/Chat/unit/test_model_router_candidates.py \
  tldw_Server_API/tests/Chat/unit/test_model_router_rules.py \
  tldw_Server_API/tests/Chat/unit/test_model_router_sticky.py \
  tldw_Server_API/tests/Chat/unit/test_model_router_llm_strategy.py \
  tldw_Server_API/tests/Chat/unit/test_model_router_service.py \
  tldw_Server_API/tests/Chat/unit/test_model_router_accounting.py \
  tldw_Server_API/tests/Chat/integration/test_chat_endpoint_auto_routing.py \
  tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_chat_auto_routing.py \
  tldw_Server_API/tests/Character_Chat_NEW/unit/test_chat_completion_precheck.py \
  tldw_Server_API/tests/AuthNZ_Unit/test_llm_provider_overrides.py -v
```

Expected: PASS

**Step 2: Run the targeted frontend tests**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/services/__tests__/tldw-api-client.chat-mutations.test.ts \
  apps/packages/ui/src/utils/__tests__/chat-model-availability.test.ts \
  apps/packages/ui/src/utils/__tests__/resolve-api-provider.test.ts \
  apps/packages/ui/src/hooks/__tests__/useMessageOption.selected-model-sync.test.tsx \
  apps/packages/ui/src/components/Option/WritingPlayground/__tests__/WritingPlayground.phase1-baseline.test.tsx
```

Expected: PASS

**Step 3: Run Bandit on touched backend paths**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/core/LLM_Calls/routing \
  tldw_Server_API/app/api/v1/endpoints/chat.py \
  tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py \
  tldw_Server_API/app/core/Chat/chat_service.py \
  -f json -o /tmp/bandit_model_router_auto.json
```

Expected: no new findings in changed code; existing low-severity findings may remain in unchanged sections of `character_chat_sessions.py`

**Step 4: Update docs if verification exposed drift**

Update the design and plan docs only if test names, file paths, or rollout sequencing changed during implementation.

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-16-model-router-auto-selection-design.md Docs/Plans/2026-03-16-model-router-auto-selection-implementation-plan.md
git commit -m "docs: finalize model router auto selection plan"
```

Plan complete and saved to `Docs/Plans/2026-03-16-model-router-auto-selection-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch a fresh subagent per task, review between tasks, and implement here.

**2. Parallel Session (separate)** - Open a new session with `superpowers:executing-plans` and execute the plan task-by-task in a separate flow.

Which approach?
