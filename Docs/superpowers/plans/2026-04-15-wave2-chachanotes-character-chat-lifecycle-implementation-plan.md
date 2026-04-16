# Wave 2 ChaChaNotes And Character Chat Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-baseline the Wave 2 character and ChaChaNotes lifecycle surface against the current tree, fix the still-live order-dependent bootstrap `503` failures, and close the remaining misleading world-book response contract that is still live in source.

**Architecture:** Treat the March 2026 characters-backend review as historical evidence rather than a list of assumed still-live defects. Start by recording what is already closed in the current tree and what still reproduces on `dev`. Then add a deterministic regression around ChaChaNotes shutdown/init state reuse in `ChaCha_Notes_DB_Deps.py`, fix the lifecycle reset semantics so mixed-suite request-path bootstrap survives teardown churn, and finish with one small response-contract cleanup in the world-book endpoint family where source still returns misleading ids.

**Tech Stack:** Python, FastAPI, asyncio, httpx, SQLite, pytest, loguru, Bandit

---

## File Map

### Wave 2 Rebaseline Artifact

- Create: `Docs/superpowers/reviews/characters-backend/2026-04-15-rebaseline.md`
  - Record which Stage 5 findings are already closed in the current tree and which ones remain live after the focused Wave 2 reruns.
- Modify: `Docs/superpowers/reviews/characters-backend/README.md`
  - Link the current-tree rebaseline so later work does not blindly re-open already-closed lifecycle/versioning findings.

### ChaChaNotes Lifecycle Reset And Mixed-Suite Bootstrap

- Modify: `tldw_Server_API/app/api/v1/API_Deps/ChaCha_Notes_DB_Deps.py`
  - Make shutdown/reset semantics clear stale init latches, init errors, and any other request-path poison state that can survive between test slices or repeated app lifecycles.
- Modify: `tldw_Server_API/app/main.py`
  - Only if startup warmup/reset still relies on lifespan paths that the request-path dependency must tolerate missing.
- Modify: `tldw_Server_API/tests/Chat/test_chacha_notes_db_deps_sqlite_policy.py`
  - Add focused dependency-layer regressions around shutdown/reset and next-bootstrap recovery.
- Modify: `tldw_Server_API/tests/Streaming/test_character_chat_sse_unified_flag.py`
  - Keep the currently reproduced mixed-suite SSE file as the endpoint-level guard for the request-path bootstrap contract.
- Modify: `tldw_Server_API/tests/Character_Chat/test_world_book_and_limits.py`
  - Keep the world-book lifecycle surface in scope for mixed-suite verification.
- Modify: `tldw_Server_API/tests/Character_Chat/test_world_book_negatives.py`
  - Preserve negative-path coverage in the Stage 4 mixed-suite rerun.
- Modify: `tldw_Server_API/tests/Character_Chat/test_world_book_manager_legacy.py`
  - Preserve legacy world-book behavior in the Stage 4 mixed-suite rerun.
- Modify: `tldw_Server_API/tests/Character_Chat/test_world_book_negatives_and_new_endpoint.py`
  - Keep the currently reproduced world-book mixed-suite `503` file as a second endpoint-level guard.
- Modify: `tldw_Server_API/tests/RAG/test_dual_backend_characters_retriever.py`
  - Preserve the Stage 4 retriever boundary in the exact rerun that currently reproduces the world-book `503`s.

### World-Book Response Contract Cleanup

- Modify: `tldw_Server_API/app/api/v1/schemas/character_schemas.py`
  - Introduce an explicit delete/detach response shape that can represent character, world-book, and entry resource ids without overloading `character_id`.
- Modify: `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py`
  - Return explicit ids for world-book delete, world-book detach, and world-book entry delete paths while preserving the existing character delete contract.
- Modify: `tldw_Server_API/tests/Characters/test_characters_endpoint.py`
  - Add response assertions for world-book delete/detach payload semantics.

## Notes

- Focused current-tree evidence gathered on `2026-04-15`:
  - `tldw_Server_API/tests/Characters/test_character_functionality_db.py` already encodes active-row restore as `409` and empty updates as a deliberate no-op. Do not reopen those paths unless the API contract changes.
  - The historical Stage 5 mixed suite still reproduces on the current tree with the same shape: `100 passed, 5 skipped, 6 failed, 1 error in 87.52s`.
  - The six real failures are all in `tldw_Server_API/tests/Streaming/test_character_chat_sse_unified_flag.py` and all fail at `GET /api/v1/characters/` with `503 Service Unavailable`.
  - The isolated SSE rerun still passes on the same tree: `6 passed, 5 warnings in 7.76s`.
  - The historical Stage 4 mixed world-book suite also still reproduces on the current tree: `103 passed, 4 skipped, 4 failed, 7 warnings in 747.34s`.
  - The four real Stage 4 failures are all in `tldw_Server_API/tests/Character_Chat/test_world_book_negatives_and_new_endpoint.py` and return the same order-dependent `503` bootstrap shape.
  - Source-only current-tree drift that still appears live:
    - `characters_endpoint.py` world-book delete/detach paths still reuse `DeletionResponse.character_id` for non-character resources.
- Keep Wave 2 bounded:
  - Do not reopen avatar history/revert, malformed import fallback, exemplar pagination cleanup, or quota-policy redesign unless the lifecycle regression investigation proves one of them is directly coupled to the reproduced `503` path.

### Task 1: Re-Baseline Wave 2 Against The Current Tree

**Files:**
- Create: `Docs/superpowers/reviews/characters-backend/2026-04-15-rebaseline.md`
- Modify: `Docs/superpowers/reviews/characters-backend/README.md`
- Test:
  - `tldw_Server_API/tests/Characters/test_character_functionality_db.py`
  - `tldw_Server_API/tests/Characters/test_characters_endpoint.py`
  - `tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py`
  - `tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_chat_auto_routing.py`
  - `tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_chat_stream_and_persist.py`
  - `tldw_Server_API/tests/Character_Chat/unit/test_chat_session_character_scope_api.py`
  - `tldw_Server_API/tests/ChaChaNotesDB/test_conversation_character_scope_filters.py`
  - `tldw_Server_API/tests/Character_Chat_NEW/unit/test_character_chat_default_provider.py`
  - `tldw_Server_API/tests/Character_Chat_NEW/unit/test_character_chat_manager.py`
  - `tldw_Server_API/tests/Character_Chat_NEW/unit/test_character_memory.py`
  - `tldw_Server_API/tests/unit/test_character_rate_limiter.py`
  - `tldw_Server_API/tests/Streaming/test_character_chat_sse_unified_flag.py`
  - `tldw_Server_API/tests/Character_Chat/test_world_book_and_limits.py`
  - `tldw_Server_API/tests/Character_Chat/test_world_book_negatives.py`
  - `tldw_Server_API/tests/Character_Chat/test_world_book_manager_legacy.py`
  - `tldw_Server_API/tests/Character_Chat/test_world_book_negatives_and_new_endpoint.py`
  - `tldw_Server_API/tests/RAG/test_dual_backend_characters_retriever.py`
  - `tldw_Server_API/tests/e2e/test_chats_and_characters.py`
  - `tldw_Server_API/tests/server_e2e_tests/test_character_chats_workflow.py`

- [ ] **Step 1: Run the focused Wave 2 mixed-suite rebaseline commands**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Characters/test_character_functionality_db.py -k "empty_update_payload_remains_a_noop or restore_character_card_raises_conflict_when_row_is_already_active" tldw_Server_API/tests/Characters/test_characters_endpoint.py -k "restore_character_active_row_returns_409" tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_chat_auto_routing.py tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_chat_stream_and_persist.py tldw_Server_API/tests/Character_Chat/unit/test_chat_session_character_scope_api.py tldw_Server_API/tests/ChaChaNotesDB/test_conversation_character_scope_filters.py tldw_Server_API/tests/Character_Chat_NEW/unit/test_character_chat_default_provider.py tldw_Server_API/tests/Character_Chat_NEW/unit/test_character_chat_manager.py tldw_Server_API/tests/Character_Chat_NEW/unit/test_character_memory.py tldw_Server_API/tests/unit/test_character_rate_limiter.py tldw_Server_API/tests/Streaming/test_character_chat_sse_unified_flag.py tldw_Server_API/tests/e2e/test_chats_and_characters.py tldw_Server_API/tests/server_e2e_tests/test_character_chats_workflow.py -v`
Expected: the only product failures should be the six SSE `503` cases; the server-e2e port-bind error remains a sandbox artifact.

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Character_Chat/test_world_book_and_limits.py tldw_Server_API/tests/Character_Chat/test_world_book_negatives.py tldw_Server_API/tests/Character_Chat/test_world_book_manager_legacy.py tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py tldw_Server_API/tests/Characters/test_characters_endpoint.py tldw_Server_API/tests/Characters/test_characters_world_book_permissions_unit.py tldw_Server_API/tests/Character_Chat/test_world_book_negatives_and_new_endpoint.py tldw_Server_API/tests/RAG/test_dual_backend_characters_retriever.py -v`
Expected: the only product failures should be the four world-book `503` cases in `test_world_book_negatives_and_new_endpoint.py`.

- [ ] **Step 2: Run the isolated SSE rerun**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Streaming/test_character_chat_sse_unified_flag.py -v`
Expected: PASS, confirming the `503` behavior is still order-dependent rather than a stable endpoint regression.

- [ ] **Step 3: Write the Wave 2 rebaseline artifact**

```markdown
## Rebaseline Summary

- Closed in current tree:
  - restore on an already-active character now conflicts instead of returning success
  - restore endpoint returns `409` for active rows
  - empty update payload remains an intentional no-op and is now explicitly tested as such

- Still live:
  - mixed-suite character-chat SSE bootstrap can fail with `503` while isolated reruns pass
  - mixed-suite world-book paths can fail with the same order-dependent `503` bootstrap behavior
  - world-book delete/detach response ids are still misleading in source

- Next action:
  - add a deterministic lifecycle regression around ChaChaNotes shutdown/init reuse
  - fix the request-path bootstrap leak
  - re-verify both the SSE and world-book mixed suites
  - clean up the remaining misleading world-book response contract
```

- [ ] **Step 4: Update the characters-backend README to link the rebaseline**

```markdown
- `2026-04-15-rebaseline.md`
  - Current-tree Wave 2 rebaseline; identifies which March character/ChaChaNotes findings are already closed and which still reproduce on `dev`.
```

- [ ] **Step 5: Commit**

```bash
git add Docs/superpowers/reviews/characters-backend/2026-04-15-rebaseline.md Docs/superpowers/reviews/characters-backend/README.md
git commit -m "docs: rebaseline wave2 character lifecycle findings"
```

### Task 2: Fix ChaChaNotes Mixed-Suite Bootstrap Poisoning

**Files:**
- Modify: `tldw_Server_API/app/api/v1/API_Deps/ChaCha_Notes_DB_Deps.py`
- Modify: `tldw_Server_API/app/main.py`
- Modify: `tldw_Server_API/tests/Chat/test_chacha_notes_db_deps_sqlite_policy.py`
- Modify: `tldw_Server_API/tests/Streaming/test_character_chat_sse_unified_flag.py`

- [ ] **Step 1: Add a deterministic dependency-layer regression for stale lifecycle state**

```python
@pytest.mark.unit
@pytest.mark.asyncio
async def test_shutdown_clears_stale_init_state_before_next_bootstrap(monkeypatch):
    import threading
    from pathlib import Path
    import tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps as deps

    deps._chacha_db_instances.clear()
    deps._chacha_db_init_events.clear()
    deps._chacha_db_init_errors.clear()

    cache_key = "/tmp/chacha-wave2-user"
    deps._chacha_db_init_events[cache_key] = threading.Event()
    deps._chacha_db_init_errors[cache_key] = RuntimeError("stale init failure")

    monkeypatch.setattr(deps.DatabasePaths, "get_user_base_directory", lambda _uid: Path(cache_key))
    monkeypatch.setattr(deps, "_create_and_prepare_db", lambda _uid, _cid: object())

    await deps.shutdown_chacha_resources(wait_timeout=0.0)
    deps.reset_chacha_shutdown_state()

    db = await deps._get_or_init_db_instance(1, "1")
    assert db is not None
    assert cache_key not in deps._chacha_db_init_events
    assert cache_key not in deps._chacha_db_init_errors
```

- [ ] **Step 2: Keep the existing mixed-suite SSE file as the endpoint-level regression guard**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/test_chacha_notes_db_deps_sqlite_policy.py -k "stale_init_state or shutdown" -v`
Expected: FAIL before the fix in the new deterministic lifecycle test. If it unexpectedly passes, tighten the reproducer until it encodes the mixed-suite failure before changing production code.

- [ ] **Step 3: Implement minimal lifecycle reset semantics in the dependency layer**

```python
def _clear_chacha_init_state(unblock_waiters: bool = False) -> None:
    with _chacha_db_lock:
        pending_events = list(_chacha_db_init_events.values())
        _chacha_db_init_events.clear()
        _chacha_db_init_errors.clear()
    if unblock_waiters:
        for event in pending_events:
            event.set()


def close_all_chacha_db_instances():
    ...
    _clear_chacha_init_state(unblock_waiters=True)


async def shutdown_chacha_resources(wait_timeout: float = 5.0) -> None:
    _set_chacha_shutting_down(True)
    ...
    close_all_chacha_db_instances()
```

Implementation note:
- If the failing regression instead points at a different minimal state leak, keep the fix scoped to the exact runtime state proven by the test. Do not refactor the whole dependency layer.
- Only touch `app/main.py` if request-path correctness still depends on startup-only resets that may not run under `ASGITransport`.

- [ ] **Step 4: Re-run the lifecycle verification, then the exact Stage 5 and Stage 4 mixed suites**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/test_chacha_notes_db_deps_sqlite_policy.py tldw_Server_API/tests/Streaming/test_character_chat_sse_unified_flag.py -v`
Expected: PASS

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_chat_auto_routing.py tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_chat_stream_and_persist.py tldw_Server_API/tests/Character_Chat/unit/test_chat_session_character_scope_api.py tldw_Server_API/tests/ChaChaNotesDB/test_conversation_character_scope_filters.py tldw_Server_API/tests/Character_Chat_NEW/unit/test_character_chat_default_provider.py tldw_Server_API/tests/Character_Chat_NEW/unit/test_character_chat_manager.py tldw_Server_API/tests/Character_Chat_NEW/unit/test_character_memory.py tldw_Server_API/tests/unit/test_character_rate_limiter.py tldw_Server_API/tests/Streaming/test_character_chat_sse_unified_flag.py tldw_Server_API/tests/e2e/test_chats_and_characters.py tldw_Server_API/tests/server_e2e_tests/test_character_chats_workflow.py -v`
Expected: the six SSE `503` failures are gone; sandbox-only server binding remains the only expected non-product issue.

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Character_Chat/test_world_book_and_limits.py tldw_Server_API/tests/Character_Chat/test_world_book_negatives.py tldw_Server_API/tests/Character_Chat/test_world_book_manager_legacy.py tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py tldw_Server_API/tests/Characters/test_characters_endpoint.py tldw_Server_API/tests/Characters/test_characters_world_book_permissions_unit.py tldw_Server_API/tests/Character_Chat/test_world_book_negatives_and_new_endpoint.py tldw_Server_API/tests/RAG/test_dual_backend_characters_retriever.py -v`
Expected: the four world-book `503` failures are gone; Postgres skips remain acceptable in environments without a reachable local server.

- [ ] **Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/API_Deps/ChaCha_Notes_DB_Deps.py tldw_Server_API/app/main.py tldw_Server_API/tests/Chat/test_chacha_notes_db_deps_sqlite_policy.py tldw_Server_API/tests/Streaming/test_character_chat_sse_unified_flag.py
git commit -m "fix: reset chachanotes lifecycle state between bootstrap runs"
```

### Task 3: Fix World-Book Delete And Detach Response Semantics

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/character_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py`
- Modify: `tldw_Server_API/tests/Characters/test_characters_endpoint.py`

- [ ] **Step 1: Add endpoint regressions for explicit resource ids**

```python
def test_world_book_detach_response_reports_character_and_world_book_ids(
    self, client: TestClient
):
    ...
    detach_response = client.delete(
        f"{CHARACTERS_ENDPOINT_PREFIX}/{character_id}/world-books/{world_book_id}"
    )
    assert detach_response.status_code == 200
    payload = detach_response.json()
    assert int(payload["character_id"]) == character_id
    assert int(payload["world_book_id"]) == world_book_id
```

Add matching assertions for:
- world-book delete returning `world_book_id`
- world-book entry delete returning `entry_id`

- [ ] **Step 2: Run the world-book response tests to verify failure**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Characters/test_characters_endpoint.py -k "character_world_book_attachment_lifecycle_integration or world_book_detach_response_reports_character_and_world_book_ids or world_book_delete_response_reports_world_book_id or world_book_entry_delete_response_reports_entry_id or restore_character_active_row_returns_409" -v`
Expected: FAIL on the new delete/detach/entry-delete response assertions because the endpoint still reuses `character_id` for non-character resources.

- [ ] **Step 3: Introduce explicit response fields without regressing character delete**

```python
class DeletionResponse(BaseModel):
    message: str
    character_id: int | None = None
    world_book_id: int | None = None
    entry_id: int | None = None
```

```python
return DeletionResponse(
    message=f"World book {world_book_id} detached from character {character_id}",
    character_id=character_id,
    world_book_id=world_book_id,
)
```

```python
return DeletionResponse(
    message=f"World book entry (ID: {entry_id}) deleted",
    entry_id=entry_id,
)
```

Implementation note:
- Keep `character_id` populated for actual character deletes so the existing contract remains intact.
- Prefer additive response changes over breaking field renames.

- [ ] **Step 4: Re-run the world-book endpoint slice**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Characters/test_characters_endpoint.py -k "character_world_book_attachment_lifecycle_integration or world_book_detach_response_reports_character_and_world_book_ids or world_book_delete_response_reports_world_book_id or world_book_entry_delete_response_reports_entry_id or restore_character_active_row_returns_409" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/character_schemas.py tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py tldw_Server_API/tests/Characters/test_characters_endpoint.py
git commit -m "fix: clarify world book deletion response ids"
```

### Task 4: Final Verification And Security Gate

**Files:**
- Verify only

- [ ] **Step 1: Run the focused Wave 2 verification set**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/test_chacha_notes_db_deps_sqlite_policy.py tldw_Server_API/tests/Streaming/test_character_chat_sse_unified_flag.py tldw_Server_API/tests/Characters/test_characters_endpoint.py -v`
Expected: PASS

- [ ] **Step 2: Re-run the exact Stage 5 and Stage 4 mixed suites**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_chat_auto_routing.py tldw_Server_API/tests/Character_Chat_NEW/integration/test_character_chat_stream_and_persist.py tldw_Server_API/tests/Character_Chat/unit/test_chat_session_character_scope_api.py tldw_Server_API/tests/ChaChaNotesDB/test_conversation_character_scope_filters.py tldw_Server_API/tests/Character_Chat_NEW/unit/test_character_chat_default_provider.py tldw_Server_API/tests/Character_Chat_NEW/unit/test_character_chat_manager.py tldw_Server_API/tests/Character_Chat_NEW/unit/test_character_memory.py tldw_Server_API/tests/unit/test_character_rate_limiter.py tldw_Server_API/tests/Streaming/test_character_chat_sse_unified_flag.py tldw_Server_API/tests/e2e/test_chats_and_characters.py tldw_Server_API/tests/server_e2e_tests/test_character_chats_workflow.py -v`
Expected: SSE failures gone; sandbox-only server binding remains the only expected non-product issue if it still reproduces.

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Character_Chat/test_world_book_and_limits.py tldw_Server_API/tests/Character_Chat/test_world_book_negatives.py tldw_Server_API/tests/Character_Chat/test_world_book_manager_legacy.py tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py tldw_Server_API/tests/Characters/test_characters_endpoint.py tldw_Server_API/tests/Characters/test_characters_world_book_permissions_unit.py tldw_Server_API/tests/Character_Chat/test_world_book_negatives_and_new_endpoint.py tldw_Server_API/tests/RAG/test_dual_backend_characters_retriever.py -v`
Expected: the Stage 4 world-book `503` failures are gone; Postgres skips remain acceptable in environments without a reachable local server.

- [ ] **Step 3: Run Bandit on the touched backend and API scope**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/API_Deps/ChaCha_Notes_DB_Deps.py tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py tldw_Server_API/app/api/v1/schemas/character_schemas.py -f json -o /tmp/bandit_wave2_character_lifecycle.json`
Expected: no new high-severity findings in the touched scope.

- [ ] **Step 4: Update the plan checkboxes/status notes as work completes**

Expected: each completed task reflects the actual implementation state and verification evidence.

- [ ] **Step 5: Commit the final verification-only follow-up if needed**

```bash
# No-op if verification required no additional edits.
```
