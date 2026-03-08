# Structured Output Generation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development when executing in-session. If executed in a separate session, use superpowers:executing-plans.

**Goal:** Add strict, server-validated structured output generation across chat and claims flows, with provider-aware fallback and streaming final structured events.

**Architecture:** Introduce a shared structured-generation orchestrator in `core/LLM_Calls` that performs response format negotiation, parse/schema validation, and bounded retries. Integrate it into `chat_service` for non-stream and stream finalization paths, and reuse it from claims output parsing. Keep legacy text/json paths backward compatible while adding additive structured stream events.

**Tech Stack:** FastAPI, Pydantic v2, jsonschema, pytest, existing chat streaming SSE utilities.

---

### Task 0: Isolated Worktree Preflight (Required)

**Files:**
- Verify only: git worktree metadata and branch state

**Step 1: Create/switch to isolated worktree (not `dev`)**

Run:
`git worktree add .worktrees/structured-output-generation -b codex/structured-output-generation`

Expected: New isolated worktree path created.

**Step 2: Enter the worktree and verify branch isolation**

Run:
`cd .worktrees/structured-output-generation && git branch --show-current && git rev-parse --show-toplevel`

Expected:
- Branch is `codex/structured-output-generation`
- Top-level path is worktree path, not primary workspace root.

**Step 3: Verify clean baseline for touched areas**

Run:
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/unit/test_chat_request_schemas.py tldw_Server_API/tests/Chat_NEW/unit/test_chat_schemas.py -k response_format`

Expected: Baseline passes before modifications.

### Task 1: Expand Chat Request Schema for `json_schema` Response Format

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py`
- Test: `tldw_Server_API/tests/Chat/unit/test_chat_request_schemas.py`
- Test: `tldw_Server_API/tests/Chat_NEW/unit/test_chat_schemas.py`

**Step 1: Write the failing tests**

```python
def test_response_format_accepts_json_schema_shape():
    req = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Return structured"}],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "answer_schema",
                "schema": {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]},
            },
        },
    )
    assert req.response_format.type == "json_schema"


def test_response_format_rejects_json_schema_without_schema_object():
    with pytest.raises(ValidationError):
        ChatCompletionRequest(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Return structured"}],
            response_format={"type": "json_schema", "json_schema": {"name": "bad"}},
        )
```

**Step 2: Run tests to verify they fail**

Run:  
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/unit/test_chat_request_schemas.py tldw_Server_API/tests/Chat_NEW/unit/test_chat_schemas.py -k response_format`

Expected: FAIL with validation/type mismatch for `json_schema` format.

**Step 3: Write minimal schema implementation**

```python
class ResponseFormatJsonSchemaSpec(BaseModel):
    name: str
    schema: dict[str, Any]
    strict: Optional[bool] = None


class ResponseFormat(BaseModel):
    type: Literal["text", "json_object", "json_schema"] = "text"
    json_schema: Optional[ResponseFormatJsonSchemaSpec] = None

    @model_validator(mode="after")
    def validate_json_schema_requirements(self):
        if self.type == "json_schema" and self.json_schema is None:
            raise ValueError("json_schema must be provided when type is 'json_schema'")
        if self.type != "json_schema" and self.json_schema is not None:
            raise ValueError("json_schema is only allowed when type is 'json_schema'")
        return self
```

**Step 4: Run tests to verify they pass**

Run:  
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/unit/test_chat_request_schemas.py tldw_Server_API/tests/Chat_NEW/unit/test_chat_schemas.py -k response_format`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py \
  tldw_Server_API/tests/Chat/unit/test_chat_request_schemas.py \
  tldw_Server_API/tests/Chat_NEW/unit/test_chat_schemas.py
git commit -m "feat(chat-schema): support json_schema response_format"
```

### Task 2: Add Shared Structured Generation Orchestrator

**Files:**
- Create: `tldw_Server_API/app/core/LLM_Calls/structured_generation.py`
- Test: `tldw_Server_API/tests/LLM_Calls/test_structured_generation.py`

**Step 1: Write the failing tests**

```python
def test_negotiates_json_schema_when_supported():
    result = negotiate_structured_response_mode(
        provider="openai",
        requested={"type": "json_schema", "json_schema": {"name": "a", "schema": {"type": "object"}}},
        provider_capabilities={"response_format_types": ["json_object", "json_schema"]},
    )
    assert result.mode_used == "json_schema"
    assert result.fallback_used is False


def test_falls_back_to_json_object_when_json_schema_unsupported():
    result = negotiate_structured_response_mode(
        provider="openai",
        requested={"type": "json_schema", "json_schema": {"name": "a", "schema": {"type": "object"}}},
        provider_capabilities={"response_format_types": ["json_object"]},
    )
    assert result.mode_used == "json_object"
    assert result.fallback_used is True


def test_validate_structured_payload_raises_on_schema_mismatch():
    with pytest.raises(StructuredGenerationSchemaError):
        validate_structured_payload(
            payload={"answer": 123},
            schema={"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]},
        )
```

**Step 2: Run tests to verify they fail**

Run:  
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/LLM_Calls/test_structured_generation.py`

Expected: FAIL (module/functions missing).

**Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class StructuredModeDecision:
    mode_used: str
    fallback_used: bool


def negotiate_structured_response_mode(...)-> StructuredModeDecision:
    ...


def parse_and_validate_structured_output(...)-> dict[str, Any] | list[Any]:
    parsed = parse_structured_output(raw_text, options=StructuredOutputOptions(parse_mode=parse_mode, strip_think_tags=True))
    Draft202012Validator(schema).validate(parsed)
    return parsed
```

Include:
- capability checks
- retry helper (bounded attempts)
- typed errors for capability/parse/schema failures.

**Step 4: Run tests to verify they pass**

Run:  
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/LLM_Calls/test_structured_generation.py`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/LLM_Calls/structured_generation.py \
  tldw_Server_API/tests/LLM_Calls/test_structured_generation.py
git commit -m "feat(llm): add shared structured generation orchestrator"
```

### Task 3: Integrate Structured Validation into Non-Streaming Chat Path

**Files:**
- Modify: `tldw_Server_API/app/core/Chat/chat_service.py`
- Test: `tldw_Server_API/tests/Chat/integration/test_chat_endpoint.py`

**Step 1: Write the failing tests**

```python
def test_non_stream_structured_success_returns_metadata(...):
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "return structured"}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "answer_schema", "schema": {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}},
        },
    }
    ...
    assert response.status_code == 200
    assert response.json()["tldw_structured"]["validated"] is True


def test_non_stream_structured_failure_returns_400(...):
    ...
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "structured_output_schema_error"
```

**Step 2: Run tests to verify they fail**

Run:  
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/integration/test_chat_endpoint.py -k structured`

Expected: FAIL.

**Step 3: Write minimal implementation**

```python
structured_req = cleaned_args.get("response_format")
if _is_structured_request(structured_req):
    structured_result = await run_structured_generation_non_stream(...)
    _attach_structured_metadata(encoded_payload, structured_result)
else:
    # existing flow
```

On terminal structured validation failure:
- Raise `HTTPException(400, detail={...structured error payload...})`.

Important behavior rule:
- Run schema validation on the final outbound assistant content (post any moderation redaction/transformation) so the API guarantee reflects what clients actually receive.

**Step 4: Run tests to verify they pass**

Run:  
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/integration/test_chat_endpoint.py -k structured`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Chat/chat_service.py \
  tldw_Server_API/tests/Chat/integration/test_chat_endpoint.py
git commit -m "feat(chat): enforce structured validation in non-stream path"
```

### Task 4: Add Streaming Final Structured Events (`structured_result` / `structured_error`)

**Files:**
- Modify: `tldw_Server_API/app/core/Chat/chat_service.py`
- Modify: `tldw_Server_API/app/core/Chat/streaming_utils.py`
- Test: `tldw_Server_API/tests/Chat/unit/test_streaming_structured_events.py`

**Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_stream_emits_structured_result_before_done():
    events = [chunk async for chunk in stream_chunks]
    assert any("event: structured_result" in chunk for chunk in events)
    done_indices = [i for i, chunk in enumerate(events) if "data: [DONE]" in chunk]
    assert done_indices, "missing DONE marker"
    done_idx = done_indices[-1]
    structured_idx = next(i for i, chunk in enumerate(events) if "event: structured_result" in chunk)
    assert structured_idx < done_idx


@pytest.mark.asyncio
async def test_stream_emits_structured_error_and_done_on_validation_failure():
    events = [chunk async for chunk in stream_chunks]
    assert any("event: structured_error" in chunk for chunk in events)
    assert any("data: [DONE]" in chunk for chunk in events)
```

**Step 2: Run tests to verify they fail**

Run:  
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/unit/test_streaming_structured_events.py`

Expected: FAIL.

**Step 3: Write minimal implementation**

In `save_callback` or stream finalization path:

```python
if structured_requested:
    try:
        # Validate on final outbound accumulated text (post-transform/moderation)
        validated = parse_and_validate_structured_output(...)
        events.append({"event": "structured_result", "data": {"validated_payload": validated, "mode_used": mode_used, "fallback_used": fallback_used}})
    except StructuredGenerationError as exc:
        events.append({"event": "structured_error", "data": {"code": exc.code, "message": str(exc), "attempts": exc.attempts}})
```

Ensure order:
1. optional structured event
2. `stream_end`
3. `[DONE]`

**Step 4: Run tests to verify they pass**

Run:  
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/unit/test_streaming_structured_events.py`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Chat/chat_service.py \
  tldw_Server_API/app/core/Chat/streaming_utils.py \
  tldw_Server_API/tests/Chat/unit/test_streaming_structured_events.py
git commit -m "feat(chat-stream): emit terminal structured result/error events"
```

### Task 5: Replace Claims Local Negotiation/Validation with Shared Orchestrator

**Files:**
- Modify: `tldw_Server_API/app/core/Claims_Extraction/output_parser.py`
- Test: `tldw_Server_API/tests/Claims/test_claims_output_parser.py`
- Test: `tldw_Server_API/tests/Claims/test_claims_response_format_contracts.py`

**Step 1: Write the failing tests**

```python
def test_claims_uses_shared_orchestrator_for_response_format_resolution(monkeypatch):
    ...
    assert observed["called_shared_negotiation"] is True


def test_claims_parse_path_uses_shared_schema_validation(monkeypatch):
    ...
    assert observed["called_shared_parse_validate"] is True
```

**Step 2: Run tests to verify they fail**

Run:  
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Claims/test_claims_output_parser.py tldw_Server_API/tests/Claims/test_claims_response_format_contracts.py`

Expected: FAIL.

**Step 3: Write minimal implementation**

Refactor claims parser helpers to delegate to shared orchestrator utilities while preserving existing public function names:

```python
def resolve_claims_response_format(...):
    return resolve_structured_response_format(...)


def parse_claims_llm_output(...):
    return parse_structured_output(...)
```

Map shared exceptions back into claims-specific exception classes to preserve contracts.

**Step 4: Run tests to verify they pass**

Run:  
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Claims/test_claims_output_parser.py tldw_Server_API/tests/Claims/test_claims_response_format_contracts.py`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Claims_Extraction/output_parser.py \
  tldw_Server_API/tests/Claims/test_claims_output_parser.py \
  tldw_Server_API/tests/Claims/test_claims_response_format_contracts.py
git commit -m "refactor(claims): route structured parsing through shared orchestrator"
```

### Task 6: Verification, Security Scan, and Documentation Sync

**Files:**
- Modify: `Docs/Development/LLM_Adapters_Authoring_Guide.md` (if response format guidance needs update)
- Modify: `Docs/Plans/2026-03-06-structured-output-generation-design.md` (status links only if needed)

**Step 1: Run targeted test suite**

Run:  
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/LLM_Calls/test_structured_generation.py tldw_Server_API/tests/Chat/unit/test_streaming_structured_events.py tldw_Server_API/tests/Claims/test_claims_output_parser.py tldw_Server_API/tests/Claims/test_claims_response_format_contracts.py && python -m pytest -q tldw_Server_API/tests/Chat/integration/test_chat_endpoint.py -k structured`

Expected: PASS.

**Step 2: Run Bandit on touched backend paths**

Run:  
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/LLM_Calls/structured_generation.py tldw_Server_API/app/core/Chat/chat_service.py tldw_Server_API/app/core/Chat/streaming_utils.py tldw_Server_API/app/core/Claims_Extraction/output_parser.py tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py -f json -o /tmp/bandit_structured_output_generation.json`

Expected: No new high-confidence findings in changed code.

**Step 3: Update docs with final behavior contract**

```markdown
- `response_format.type` supports `text`, `json_object`, `json_schema`.
- When `json_schema` unsupported by provider, server may downgrade to `json_object` but still validates against requested schema.
- Streaming structured mode emits `structured_result` or `structured_error` before stream termination.
```

**Step 4: Re-run docs + targeted tests**

Run:  
`source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/integration/test_chat_endpoint.py -k structured`

Expected: PASS.

**Step 5: Final commit**

```bash
git add Docs/Development/LLM_Adapters_Authoring_Guide.md \
  tldw_Server_API/app/core/LLM_Calls/structured_generation.py \
  tldw_Server_API/app/core/Chat/chat_service.py \
  tldw_Server_API/app/core/Chat/streaming_utils.py \
  tldw_Server_API/app/core/Claims_Extraction/output_parser.py \
  tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py \
  tldw_Server_API/tests/LLM_Calls/test_structured_generation.py \
  tldw_Server_API/tests/Chat/integration/test_chat_endpoint.py \
  tldw_Server_API/tests/Chat/unit/test_streaming_structured_events.py \
  tldw_Server_API/tests/Claims/test_claims_output_parser.py \
  tldw_Server_API/tests/Claims/test_claims_response_format_contracts.py
git commit -m "feat(chat+claims): add strict structured output generation with streaming terminal events"
```

## Notes for Execution

- Use @test-driven-development for each task before implementation changes.
- Use @verification-before-completion before claiming success.
- Keep commits small and task-scoped as listed above.
- Do not modify unrelated UI files currently dirty in working tree.
