# _NEW Track Consolidation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Consolidate duplicated `_NEW` and legacy tracks into one canonical path per domain to reduce maintenance overhead and conflicting behavior.

**Architecture:** Build a migration matrix for `Chat`, `RAG`, `TTS`, `MediaIngestion`, `Notes`, `Embeddings`, and `Character_Chat`. Use parity tests to prove behavior equivalence, then progressively switch imports/tests to canonical modules and remove duplicates.

**Tech Stack:** Existing module/test suites, pytest integration/property tests, import wrappers and deprecation logging.

---

### Task 1: Build Consolidation Matrix and Parity Test Harness

**Files:**
- Create: `Docs/Plans/2026-03-02-new-track-consolidation-matrix.md`
- Create: `tldw_Server_API/tests/sanity_tests/test_new_track_parity_matrix.py`
- Reference: `tldw_Server_API/tests/Chat_NEW`
- Reference: `tldw_Server_API/tests/Character_Chat_NEW`
- Reference: `tldw_Server_API/tests/RAG_NEW`
- Reference: `tldw_Server_API/tests/TTS_NEW`

**Step 1: Write the failing test**

```python
def test_all_new_tracks_mapped_to_canonical_target():
    matrix = load_consolidation_matrix()
    assert matrix["Chat_NEW"]["target"] == "Chat"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sanity_tests/test_new_track_parity_matrix.py -v`
Expected: FAIL until matrix file exists.

**Step 3: Write minimal implementation**

```python
CONSOLIDATION_MATRIX = {
    "Chat_NEW": {"target": "Chat"},
}
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sanity_tests/test_new_track_parity_matrix.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-02-new-track-consolidation-matrix.md tldw_Server_API/tests/sanity_tests/test_new_track_parity_matrix.py
git commit -m "test(consolidation): add _NEW-to-canonical parity matrix"
```

### Task 2: Consolidate Chat and Character Chat Tracks

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/chat.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py`
- Modify: `tldw_Server_API/tests/Chat_NEW/*` (migrate to `tldw_Server_API/tests/Chat/*`)
- Modify: `tldw_Server_API/tests/Character_Chat_NEW/*` (migrate to `tldw_Server_API/tests/Character_Chat/*`)
- Test: `tldw_Server_API/tests/Chat/integration/test_chat_completions_integration.py`
- Test: `tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py`

**Step 1: Write the failing test**

```python
def test_chat_new_and_chat_return_equivalent_response_shape(client):
    old = call_chat_legacy(client)
    new = call_chat_new(client)
    assert normalize(old) == normalize(new)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sanity_tests/test_new_track_parity_matrix.py::test_chat_new_and_chat_return_equivalent_response_shape -v`
Expected: FAIL while dual implementations diverge.

**Step 3: Write minimal implementation**

```python
# Route both paths through one canonical chat service facade.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/integration/test_chat_completions_integration.py tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/chat.py tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py tldw_Server_API/tests/Chat tldw_Server_API/tests/Character_Chat tldw_Server_API/tests/sanity_tests/test_new_track_parity_matrix.py
git commit -m "refactor(consolidation): unify chat and character chat canonical paths"
```

### Task 3: Consolidate RAG, TTS, and Embeddings Tracks

**Files:**
- Modify: `tldw_Server_API/app/core/RAG/*`
- Modify: `tldw_Server_API/app/core/TTS/*`
- Modify: `tldw_Server_API/app/core/Embeddings/*`
- Modify: `tldw_Server_API/tests/RAG_NEW/*` -> `tldw_Server_API/tests/RAG/*`
- Modify: `tldw_Server_API/tests/TTS_NEW/*` -> `tldw_Server_API/tests/TTS/*`
- Modify: `tldw_Server_API/tests/Embeddings_NEW/*` -> `tldw_Server_API/tests/Embeddings/*`

**Step 1: Write the failing test**

```python
def test_rag_new_and_rag_health_contracts_identical(client):
    assert get_rag_new_health(client) == get_rag_health(client)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/sanity_tests/test_new_track_parity_matrix.py::test_rag_new_and_rag_health_contracts_identical -v`
Expected: FAIL while implementations diverge.

**Step 3: Write minimal implementation**

```python
# Move canonical imports to non-_NEW modules and add redirect wrappers where needed.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG tldw_Server_API/tests/TTS tldw_Server_API/tests/Embeddings -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/RAG tldw_Server_API/app/core/TTS tldw_Server_API/app/core/Embeddings tldw_Server_API/tests/RAG tldw_Server_API/tests/TTS tldw_Server_API/tests/Embeddings tldw_Server_API/tests/sanity_tests/test_new_track_parity_matrix.py
git commit -m "refactor(consolidation): unify rag/tts/embeddings canonical implementations"
```

### Task 4: Remove Redundant _NEW Trees and Add Drift Guard

**Files:**
- Delete: `tldw_Server_API/tests/Chat_NEW/*` (after migration)
- Delete: `tldw_Server_API/tests/RAG_NEW/*` (after migration)
- Delete: `tldw_Server_API/tests/TTS_NEW/*` (after migration)
- Delete: `tldw_Server_API/tests/Embeddings_NEW/*` (after migration)
- Delete: `tldw_Server_API/tests/Notes_NEW/*` (after migration)
- Delete: `tldw_Server_API/tests/Prompt_Management_NEW/*` (after migration)
- Delete: `tldw_Server_API/tests/MediaIngestion_NEW/*` (after migration)
- Delete: `tldw_Server_API/tests/Character_Chat_NEW/*` (after migration)
- Create: `tldw_Server_API/tests/lint/test_no_new_track_dirs.py`

**Step 1: Write the failing test**

```python
def test_no_new_track_directories_present():
    assert discover_new_track_dirs() == []
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/lint/test_no_new_track_dirs.py -v`
Expected: FAIL until cleanup is complete.

**Step 3: Write minimal implementation**

```python
# Implement directory scanner for *_NEW under tests/app packages.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/lint/test_no_new_track_dirs.py tldw_Server_API/tests/sanity_tests/test_new_track_parity_matrix.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/lint/test_no_new_track_dirs.py tldw_Server_API/tests/sanity_tests/test_new_track_parity_matrix.py tldw_Server_API/tests
git commit -m "chore(consolidation): remove migrated _NEW tracks and add drift guard"
```
