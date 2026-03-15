# Chat Completions Continuation Controls Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add optional continuation controls to `POST /api/v1/chat/completions` so clients can branch/append from a specific message anchor and optionally prefill assistant output, without changing default behavior.

**Architecture:** Keep the existing endpoint and request shape, add one optional extension object (`tldw_continuation`), resolve continuation in `chat_service.build_context_and_messages`, and thread continuation metadata/parent linkage through existing stream + non-stream save/response paths. Reuse existing conversation tree storage via `parent_message_id` and avoid provider-adapter changes.

**Tech Stack:** FastAPI, Pydantic v2, Chat core service (`chat_service.py`), SSE handler (`streaming_utils.py`), ChaChaNotes DB (`CharactersRAGDB`), pytest.

## Execution Status (2026-03-06)

- Task 1: Complete
- Task 2: Complete
- Task 3: Complete
- Task 4: Complete
- Task 5: Complete
- Task 6: Complete

Notes:
- Combined touched-scope pytest initially failed due duplicate module basename conflict between unit/integration continuation tests.
- Resolved by renaming integration test file to `test_chat_continuation_controls_integration.py`.

---

Execution skills to apply while implementing: `@test-driven-development`, `@verification-before-completion`.

### Task 1: Add Request Schema for Continuation Controls

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py:665-860`
- Test: `tldw_Server_API/tests/Chat/unit/test_chat_request_schemas.py`
- Test: `tldw_Server_API/tests/Chat_NEW/unit/test_chat_schemas.py`

**Step 1: Write the failing tests**

```python
def test_chat_completion_request_accepts_tldw_continuation_branch():
    req = ChatCompletionRequest(
        model="gpt-4o-mini",
        conversation_id="conv-1",
        messages=[{"role": "user", "content": "continue"}],
        tldw_continuation={
            "from_message_id": "msg-1",
            "mode": "branch",
            "assistant_prefill": "Draft: ",
        },
    )
    assert req.tldw_continuation is not None
    assert req.tldw_continuation.mode == "branch"


def test_chat_completion_request_requires_conversation_for_continuation():
    with pytest.raises(ValidationError):
        ChatCompletionRequest(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "continue"}],
            tldw_continuation={"from_message_id": "msg-1", "mode": "append"},
        )
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/unit/test_chat_request_schemas.py -k continuation`
Expected: FAIL with unknown field / missing validation for `tldw_continuation`.

**Step 3: Write minimal implementation**

```python
class TLDWContinuationSpec(BaseModel):
    from_message_id: str = Field(..., min_length=1, max_length=128)
    mode: Literal["branch", "append"]
    assistant_prefill: Optional[str] = Field(None, max_length=MAX_MESSAGE_CONTENT_LENGTH)


class ChatCompletionRequest(BaseModel):
    ...
    tldw_continuation: Optional[TLDWContinuationSpec] = Field(
        None,
        description="[Extension] Optional continuation controls for anchored branch/append generation.",
    )

    @model_validator(mode="after")
    def validate_tldw_continuation(self):
        if self.tldw_continuation and not self.conversation_id:
            raise ValueError("conversation_id is required when tldw_continuation is provided")
        return self
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/unit/test_chat_request_schemas.py -k continuation`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py \
        tldw_Server_API/tests/Chat/unit/test_chat_request_schemas.py \
        tldw_Server_API/tests/Chat_NEW/unit/test_chat_schemas.py
git commit -m "feat(chat): add tldw_continuation request schema"
```

### Task 2: Add Parent Message Support to Message Persistence Helper

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/chat.py:1431-1670`
- Create: `tldw_Server_API/tests/Chat_NEW/unit/test_parent_message_persistence.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_save_message_turn_persists_parent_message_id(populated_chacha_db):
    conv_id = populated_chacha_db.add_conversation({"character_id": 1, "title": "parent-link"})
    parent_id = populated_chacha_db.add_message({"conversation_id": conv_id, "sender": "user", "content": "A"})

    msg_id = await _save_message_turn_to_db(
        populated_chacha_db,
        conv_id,
        {"role": "assistant", "content": "B", "parent_message_id": parent_id},
        use_transaction=True,
    )

    saved = populated_chacha_db.get_message_by_id(msg_id)
    assert saved["parent_message_id"] == parent_id
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat_NEW/unit/test_parent_message_persistence.py`
Expected: FAIL because `parent_message_id` is not included in DB payload.

**Step 3: Write minimal implementation**

```python
parent_message_id = message_obj.get("parent_message_id")
...
db_payload = {
    "conversation_id": conversation_id,
    "sender": sender,
    "content": "\n".join(text_parts) if text_parts else "",
    "image_data": primary_image_data,
    "image_mime_type": primary_image_mime,
    "client_id": db.client_id,
}
if isinstance(parent_message_id, str) and parent_message_id.strip():
    db_payload["parent_message_id"] = parent_message_id.strip()
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat_NEW/unit/test_parent_message_persistence.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/chat.py \
        tldw_Server_API/tests/Chat_NEW/unit/test_parent_message_persistence.py
git commit -m "feat(chat): support parent_message_id in message save helper"
```

### Task 3: Implement Continuation Resolver in Context Builder

**Files:**
- Modify: `tldw_Server_API/app/core/Chat/chat_service.py:1829-2325`
- Create: `tldw_Server_API/tests/Chat_NEW/unit/test_chat_continuation_controls.py`

**Step 1: Write failing resolver tests**

```python
@pytest.mark.asyncio
async def test_continuation_branch_uses_anchor_chain(populated_chacha_db):
    # seed root -> child -> tip in one conversation
    # request with tldw_continuation.from_message_id=child, mode=branch
    # assert llm payload includes history up to child, not tip branch siblings

@pytest.mark.asyncio
async def test_continuation_append_requires_tip(populated_chacha_db):
    # from_message_id is not latest message
    # assert HTTPException.status_code == 409
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat_NEW/unit/test_chat_continuation_controls.py`
Expected: FAIL with missing continuation behavior.

**Step 3: Write minimal implementation**

```python
async def _resolve_tldw_continuation(...):
    # validate anchor exists and belongs to conversation
    # enforce append-tip rule via get_latest_message_for_conversation
    # walk parent_message_id chain to build anchored chronological history
    # return metadata + assistant_parent_message_id + optional prefill


async def build_context_and_messages(..., runtime_state: dict[str, Any] | None = None):
    continuation_spec = getattr(request_data, "tldw_continuation", None)
    if continuation_spec:
        history_records, continuation_meta = await _resolve_tldw_continuation(...)
        historical_msgs = [_convert_db_record_to_llm_message(...) for rec in history_records]
        assistant_parent_message_id = continuation_meta["parent_message_id"]
        if runtime_state is not None:
            runtime_state["tldw_continuation"] = continuation_meta
            runtime_state["assistant_parent_message_id"] = assistant_parent_message_id
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat_NEW/unit/test_chat_continuation_controls.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Chat/chat_service.py \
        tldw_Server_API/tests/Chat_NEW/unit/test_chat_continuation_controls.py
git commit -m "feat(chat): resolve anchored continuation in context builder"
```

### Task 4: Thread Continuation Metadata and Parent Link Through Stream + Non-Stream Paths

**Files:**
- Modify: `tldw_Server_API/app/core/Chat/chat_service.py:2302-3376`
- Modify: `tldw_Server_API/app/core/Chat/chat_service.py:3376-4050`
- Modify: `tldw_Server_API/app/core/Chat/streaming_utils.py:316-373`
- Modify: `tldw_Server_API/app/core/Chat/streaming_utils.py:571-1065`
- Test: `tldw_Server_API/tests/Chat/unit/test_chat_service_fallback.py`
- Test: `tldw_Server_API/tests/Chat/unit/test_chat_service_streaming_tool_autoexec.py`
- Test: `tldw_Server_API/tests/Chat/unit/test_streaming_utils.py`

**Step 1: Write failing tests for metadata + parent linkage**

```python
# non-stream
assert response["tldw_continuation"]["applied"] is True
assert saved_payload["parent_message_id"] == "anchor-msg"

# stream_end / tool_results payloads
assert payload["tldw_continuation"]["mode"] == "branch"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/unit/test_chat_service_fallback.py -k continuation`
Expected: FAIL because continuation metadata/parent linkage is absent.

**Step 3: Write minimal implementation**

```python
# chat_service signatures
async def execute_non_stream_call(..., assistant_parent_message_id: str | None = None, continuation_metadata: dict[str, Any] | None = None):
...
if assistant_parent_message_id:
    message_payload["parent_message_id"] = assistant_parent_message_id
...
if continuation_metadata:
    encoded_payload["tldw_continuation"] = continuation_metadata


async def execute_streaming_call(..., assistant_parent_message_id: str | None = None, continuation_metadata: dict[str, Any] | None = None):
...
if assistant_parent_message_id:
    message_payload["parent_message_id"] = assistant_parent_message_id
...
generator = create_streaming_response_with_timeout(..., continuation_metadata=continuation_metadata)

# streaming_utils
class StreamingResponseHandler:
    self.continuation_metadata: Optional[dict[str, Any]] = None

    def _attach_stream_metadata(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...
        if self.continuation_metadata:
            payload.setdefault("tldw_continuation", self.continuation_metadata)
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/unit/test_chat_service_fallback.py tldw_Server_API/tests/Chat/unit/test_chat_service_streaming_tool_autoexec.py tldw_Server_API/tests/Chat/unit/test_streaming_utils.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Chat/chat_service.py \
        tldw_Server_API/app/core/Chat/streaming_utils.py \
        tldw_Server_API/tests/Chat/unit/test_chat_service_fallback.py \
        tldw_Server_API/tests/Chat/unit/test_chat_service_streaming_tool_autoexec.py \
        tldw_Server_API/tests/Chat/unit/test_streaming_utils.py
git commit -m "feat(chat): propagate continuation metadata across stream and non-stream responses"
```

### Task 5: Wire Endpoint Runtime State + Integration Coverage

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/chat.py:2623-3317`
- Create: `tldw_Server_API/tests/Chat_NEW/integration/test_chat_continuation_controls_integration.py`

**Step 1: Write failing integration tests**

```python
def test_branch_continuation_returns_metadata_and_parent_link(...):
    # call /api/v1/chat/completions with tldw_continuation.mode=branch
    # assert 200 + response['tldw_continuation']['applied']
    # assert saved assistant message parent_message_id == anchor


def test_append_continuation_non_tip_returns_409(...):
    # anchor older than latest
    # assert response.status_code == 409
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat_NEW/integration/test_chat_continuation_controls_integration.py`
Expected: FAIL because endpoint does not pass continuation runtime metadata into execute paths.

**Step 3: Write minimal implementation**

```python
continuation_runtime: dict[str, Any] = {}
(
    ...
) = await build_context_and_messages(..., runtime_state=continuation_runtime)

continuation_meta = continuation_runtime.get("tldw_continuation")
assistant_parent_message_id = continuation_runtime.get("assistant_parent_message_id")

stream_response = await execute_streaming_call(
    ...,
    assistant_parent_message_id=assistant_parent_message_id,
    continuation_metadata=continuation_meta,
)

encoded_payload = await execute_non_stream_call(
    ...,
    assistant_parent_message_id=assistant_parent_message_id,
    continuation_metadata=continuation_meta,
)
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat_NEW/integration/test_chat_continuation_controls_integration.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/chat.py \
        tldw_Server_API/tests/Chat_NEW/integration/test_chat_continuation_controls_integration.py
git commit -m "feat(chat): wire continuation runtime state into chat completions endpoint"
```

### Task 6: Documentation + Security + Verification Sweep

**Files:**
- Modify: `Docs/API-related/Chat_API_Documentation.md`

**Step 1: Write failing doc-check test (if doc lint exists) or checklist assertion**

```text
Checklist:
- Request docs include tldw_continuation fields and semantics.
- Response docs include tldw_continuation metadata for stream/non-stream.
- Error table includes 409 append-non-tip and 404 invalid anchor.
```

**Step 2: Run verification commands before doc update**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat_NEW/unit/test_chat_continuation_controls.py tldw_Server_API/tests/Chat_NEW/integration/test_chat_continuation_controls_integration.py`
Expected: PASS from previous tasks.

**Step 3: Update docs with concrete examples**

```markdown
"tldw_continuation": {
  "from_message_id": "msg-456",
  "mode": "branch",
  "assistant_prefill": "Draft response prefix..."
}
```

Add behavior note:
- Regenerate = full assistant turn regeneration from anchor.
- Continue = branch/append anchored continuation.

**Step 4: Run full touched-scope checks + Bandit**

Run:
- `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/unit/test_chat_request_schemas.py tldw_Server_API/tests/Chat_NEW/unit/test_chat_schemas.py tldw_Server_API/tests/Chat_NEW/unit/test_chat_continuation_controls.py tldw_Server_API/tests/Chat_NEW/unit/test_parent_message_persistence.py tldw_Server_API/tests/Chat/unit/test_chat_service_fallback.py tldw_Server_API/tests/Chat/unit/test_chat_service_streaming_tool_autoexec.py tldw_Server_API/tests/Chat/unit/test_streaming_utils.py tldw_Server_API/tests/Chat_NEW/integration/test_chat_continuation_controls_integration.py`
- `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py tldw_Server_API/app/core/Chat/chat_service.py tldw_Server_API/app/core/Chat/streaming_utils.py tldw_Server_API/app/api/v1/endpoints/chat.py -f json -o /tmp/bandit_chat_continuation_controls.json`

Expected: pytest PASS; Bandit reports no new high-confidence/high-severity findings in touched code.

**Step 5: Commit**

```bash
git add Docs/API-related/Chat_API_Documentation.md
git commit -m "docs(chat): document continuation controls for chat completions"
```

## Final Verification Gate

Run before merge:

```bash
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat_NEW/unit/test_chat_continuation_controls.py tldw_Server_API/tests/Chat_NEW/integration/test_chat_continuation_controls_integration.py
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py tldw_Server_API/app/core/Chat/chat_service.py tldw_Server_API/app/core/Chat/streaming_utils.py tldw_Server_API/app/api/v1/endpoints/chat.py -f json -o /tmp/bandit_chat_continuation_controls.json
```

Expected:
- `pytest`: all selected tests PASS.
- `bandit`: no new unresolved high-severity issues in touched files.
