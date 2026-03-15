# Failing Test Clusters Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the current 11 failing tests and 2 secondary errors by restoring endpoint compatibility, guarding non-critical embedding failures, and stabilizing deterministic test assumptions.

**Architecture:** Apply minimal, localized fixes at API boundaries and normalization helpers instead of broad refactors. Keep behavior backward-compatible for existing tests, treat embedding sync as best-effort, and preserve strict model validation where appropriate after credential gating.

**Tech Stack:** FastAPI, pytest, Hypothesis, SQLite/PostgreSQL DB layer, ChromaDB wrapper.

---

### Task 1: Fix Character Exemplar Route Parameter Typing

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py`
- Test: `tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_exemplars_api.py`

**Step 1: Reproduce current routing failure**

Run:
```bash
source .venv/bin/activate && python -m pytest -vv \
  tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_exemplars_api.py::TestCharacterExemplarEndpoints::test_character_exemplar_crud_and_search \
  tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_exemplars_api.py::TestCharacterExemplarEndpoints::test_character_exemplar_crud_triggers_embedding_sync_hooks
```
Expected: FAIL with `404` on `/{exemplar_id}` routes and/or follow-on errors.

**Step 2: Update route path converters to string IDs**

Change route decorators:
```python
@router.get("/{character_id:int}/exemplars/{exemplar_id}", ...)
@router.put("/{character_id:int}/exemplars/{exemplar_id}", ...)
@router.delete("/{character_id:int}/exemplars/{exemplar_id}", ...)
```

**Step 3: Re-run targeted exemplar CRUD tests**

Run:
```bash
source .venv/bin/activate && python -m pytest -vv \
  tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_exemplars_api.py::TestCharacterExemplarEndpoints::test_character_exemplar_crud_and_search \
  tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_exemplars_api.py::TestCharacterExemplarEndpoints::test_character_exemplar_crud_triggers_embedding_sync_hooks
```
Expected: PASS for routing behavior (remaining failures, if any, move to Task 2).

**Step 4: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py
git commit -m "fix(characters): accept string exemplar ids in CRUD routes"
```

### Task 2: Guard Persona Exemplar Embedding Panics as Best-Effort Failures

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py`
- Modify: `tldw_Server_API/app/core/Character_Chat/modules/persona_exemplar_embeddings.py`
- Test: `tldw_Server_API/tests/Character_Chat_NEW/unit/test_persona_exemplar_embeddings.py`
- Test: `tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_exemplars_api.py`
- Test: `tldw_Server_API/tests/Chat_NEW/integration/test_chat_persona_exemplars_integration.py`

**Step 1: Add panic-safe helper for BaseException in embedding paths**

Add helper and use it in embedding best-effort wrappers:
```python
def _should_reraise_base_exception(exc: BaseException) -> bool:
    return isinstance(exc, (KeyboardInterrupt, SystemExit))

...
except BaseException as exc:
    if _should_reraise_base_exception(exc):
        raise
    logger.warning(...)
```

**Step 2: Apply same guard in exemplar embedding module**

Update `_create_chroma_manager`, `upsert_character_exemplar_embeddings`, and `delete_character_exemplar_embeddings`:
```python
except BaseException as exc:
    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
        raise
    logger.warning(...)
    return 0  # or None for manager creation
```

**Step 3: Add a unit regression test for BaseException handling**

Add a test that simulates a `BaseException` from manager initialization and asserts no crash:
```python
def test_upsert_character_exemplar_embeddings_handles_base_exception_from_manager(...):
    class _Panic(BaseException): ...
    ...
    assert upsert_character_exemplar_embeddings(...) == 0
```

**Step 4: Verify integration paths that previously raised BaseExceptionGroup**

Run:
```bash
source .venv/bin/activate && python -m pytest -vv \
  tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_exemplars_api.py::TestCharacterExemplarEndpoints::test_character_exemplar_crud_and_search \
  tldw_Server_API/tests/Chat_NEW/integration/test_chat_persona_exemplars_integration.py::test_chat_completion_injects_persona_exemplar_guidance_and_debug_meta \
  tldw_Server_API/tests/Character_Chat_NEW/unit/test_persona_exemplar_embeddings.py
```
Expected: no `BaseExceptionGroup`; targeted tests pass.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py \
  tldw_Server_API/app/core/Character_Chat/modules/persona_exemplar_embeddings.py \
  tldw_Server_API/tests/Character_Chat_NEW/unit/test_persona_exemplar_embeddings.py
git commit -m "fix(persona-exemplars): treat chroma panics as non-fatal best-effort failures"
```

### Task 3: Restore Character Tag Serialization Compatibility

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Test: `tldw_Server_API/tests/Character_Chat_NEW/property/test_character_properties.py`
- Test: `tldw_Server_API/tests/Characters/test_character_functionality_db.py`

**Step 1: Reproduce tag behavior regressions**

Run:
```bash
source .venv/bin/activate && python -m pytest -vv \
  tldw_Server_API/tests/Character_Chat_NEW/property/test_character_properties.py::TestCharacterCardProperties::test_create_then_get_preserves_data \
  tldw_Server_API/tests/Characters/test_character_functionality_db.py::TestCharacterCardAddition::test_add_character_with_set_json_fields \
  tldw_Server_API/tests/Characters/test_character_functionality_db.py::TestCharacterCardAddition::test_add_character_with_invalid_string_for_json_field_becomes_none
```
Expected: FAIL with whitespace/set/invalid-string mismatches.

**Step 2: Update `_normalize_character_tags_for_operation`**

Implement compatibility behavior:
```python
if isinstance(tags_value, (list, set, tuple)):
    raw_tags = list(tags_value)
elif isinstance(tags_value, str):
    if tags_value.strip() == "":
        return []
    try:
        parsed = json.loads(tags_value)
        raw_tags = parsed if isinstance(parsed, list) else [tags_value]
    except ...:
        raw_tags = [tags_value]
```
And preserve significant whitespace in tag items (do not blanket `.strip()` values before storage).

**Step 3: Re-run targeted tag tests**

Run:
```bash
source .venv/bin/activate && python -m pytest -vv \
  tldw_Server_API/tests/Character_Chat_NEW/property/test_character_properties.py::TestCharacterCardProperties::test_create_then_get_preserves_data \
  tldw_Server_API/tests/Characters/test_character_functionality_db.py::TestCharacterCardAddition::test_add_character_with_set_json_fields \
  tldw_Server_API/tests/Characters/test_character_functionality_db.py::TestCharacterCardAddition::test_add_character_with_invalid_string_for_json_field_becomes_none
```
Expected: PASS.

**Step 4: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py
git commit -m "fix(characters-db): restore legacy tag normalization semantics"
```

### Task 4: Restore Legacy Unknown-Sender Formatting for Empty Sender Tokens

**Files:**
- Modify: `tldw_Server_API/app/core/Character_Chat/modules/character_chat.py`
- Test: `tldw_Server_API/tests/Characters/test_character_chat_lib.py`

**Step 1: Patch unknown sender formatting branch**

Use conditional prefixing:
```python
sender_label = str(sender or "")
if sender_label.strip():
    formatted_content = f"[{sender_label}] {processed_content}"
else:
    formatted_content = processed_content
```

**Step 2: Verify property regression test**

Run:
```bash
source .venv/bin/activate && python -m pytest -vv \
  tldw_Server_API/tests/Characters/test_character_chat_lib.py::test_property_process_db_messages_to_ui_history_only_char
```
Expected: PASS.

**Step 3: Commit**

```bash
git add tldw_Server_API/app/core/Character_Chat/modules/character_chat.py
git commit -m "fix(character-chat): avoid bracket prefix for blank unknown senders"
```

### Task 5: Ensure Missing Provider Credentials Error Precedes Strict Model Availability Error

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/chat.py`
- Test: `tldw_Server_API/tests/Chat/integration/test_chat_endpoint.py`

**Step 1: Move strict model check after BYOK missing-key gate**

Relocate this block:
```python
if strict_model_selection and explicit_model_requested:
    availability_error = _validate_explicit_model_availability(provider, model)
    if availability_error:
        raise HTTPException(status_code=400, detail=availability_error)
```
to run only after:
```python
if provider_requires_api_key(...) and not provider_api_key:
    raise HTTPException(status_code=503, detail={...})
```

**Step 2: Re-run missing-key regression test**

Run:
```bash
source .venv/bin/activate && python -m pytest -vv \
  tldw_Server_API/tests/Chat/integration/test_chat_endpoint.py::test_missing_api_key_for_required_provider
```
Expected: PASS with `503 missing_provider_credentials`.

**Step 3: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/chat.py
git commit -m "fix(chat): prioritize missing-credentials error before model availability validation"
```

### Task 6: Make `complete-v2` Integration Test Deterministic for Offline Simulation

**Files:**
- Modify: `tldw_Server_API/tests/Character_Chat/test_world_book_negatives_and_new_endpoint.py`

**Step 1: Update the request payload to explicitly use local offline path**

Adjust test payload:
```python
payload = {
    "append_user_message": "Hello there",
    "save_to_db": True,
    "provider": "local-llm",
    "model": "local-test",
}
```

**Step 2: Re-run target test**

Run:
```bash
source .venv/bin/activate && python -m pytest -vv \
  tldw_Server_API/tests/Character_Chat/test_world_book_negatives_and_new_endpoint.py::test_complete_v2_operational_and_persists
```
Expected: PASS consistently without network/provider key dependency.

**Step 3: Commit**

```bash
git add tldw_Server_API/tests/Character_Chat/test_world_book_negatives_and_new_endpoint.py
git commit -m "test(character-chat): pin complete-v2 test to local offline provider path"
```

### Task 7: Reject Path-Traversal Filenames Early in Chatbooks Upload Validation

**Files:**
- Modify: `tldw_Server_API/app/core/Chatbooks/chatbook_validators.py`
- Test: `tldw_Server_API/tests/Chatbooks/test_chatbooks_path_traversal.py`

**Step 1: Update filename validator to reject traversal input instead of silently collapsing**

Implement early rejection:
```python
normalized_input = filename.replace("\\", "/")
base_filename = os.path.basename(normalized_input).strip()
if normalized_input != base_filename:
    return False, "Invalid filename", ""
```

**Step 2: Re-run traversal tests**

Run:
```bash
source .venv/bin/activate && python -m pytest -vv \
  tldw_Server_API/tests/Chatbooks/test_chatbooks_path_traversal.py::test_import_rejects_path_traversal_filename \
  tldw_Server_API/tests/Chatbooks/test_chatbooks_path_traversal.py::test_preview_rejects_path_traversal_filename
```
Expected: PASS with `400` and filename-related detail.

**Step 3: Commit**

```bash
git add tldw_Server_API/app/core/Chatbooks/chatbook_validators.py
git commit -m "fix(chatbooks): reject path-traversal filenames before zip validation"
```

### Task 8: Final Verification Sweep and Security Check

**Files:**
- Verify only (no new edits unless failures appear)

**Step 1: Run the full originally failing subset**

Run:
```bash
source .venv/bin/activate && python -m pytest -vv \
  tldw_Server_API/tests/Character_Chat/test_world_book_negatives_and_new_endpoint.py::test_complete_v2_operational_and_persists \
  tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_exemplars_api.py::TestCharacterExemplarEndpoints::test_character_exemplar_crud_and_search \
  tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_exemplars_api.py::TestCharacterExemplarEndpoints::test_character_exemplar_crud_triggers_embedding_sync_hooks \
  tldw_Server_API/tests/Character_Chat_NEW/property/test_character_properties.py::TestCharacterCardProperties::test_create_then_get_preserves_data \
  tldw_Server_API/tests/Characters/test_character_chat_lib.py::test_property_process_db_messages_to_ui_history_only_char \
  tldw_Server_API/tests/Characters/test_character_functionality_db.py::TestCharacterCardAddition::test_add_character_with_set_json_fields \
  tldw_Server_API/tests/Characters/test_character_functionality_db.py::TestCharacterCardAddition::test_add_character_with_invalid_string_for_json_field_becomes_none \
  tldw_Server_API/tests/Chat/integration/test_chat_endpoint.py::test_missing_api_key_for_required_provider \
  tldw_Server_API/tests/Chat_NEW/integration/test_chat_persona_exemplars_integration.py::test_chat_completion_injects_persona_exemplar_guidance_and_debug_meta \
  tldw_Server_API/tests/Chatbooks/test_chatbooks_path_traversal.py::test_import_rejects_path_traversal_filename \
  tldw_Server_API/tests/Chatbooks/test_chatbooks_path_traversal.py::test_preview_rejects_path_traversal_filename
```
Expected: all PASS; no `TaskGroup` or portal teardown errors.

**Step 2: Run Bandit on touched paths**

Run:
```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py \
  tldw_Server_API/app/core/Character_Chat/modules/persona_exemplar_embeddings.py \
  tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
  tldw_Server_API/app/core/Character_Chat/modules/character_chat.py \
  tldw_Server_API/app/api/v1/endpoints/chat.py \
  tldw_Server_API/app/core/Chatbooks/chatbook_validators.py \
  tldw_Server_API/tests/Character_Chat/test_world_book_negatives_and_new_endpoint.py \
  -f json -o /tmp/bandit_failing_test_clusters.json
```
Expected: no new high-severity findings in touched logic.

**Step 3: Optional confidence run across affected suites**

Run:
```bash
source .venv/bin/activate && python -m pytest -vv \
  tldw_Server_API/tests/Character_Chat_NEW \
  tldw_Server_API/tests/Characters \
  tldw_Server_API/tests/Chat \
  tldw_Server_API/tests/Chat_NEW \
  tldw_Server_API/tests/Chatbooks
```
Expected: no regressions in neighboring tests.
