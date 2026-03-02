# DB Megafile Repository Split Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce data-layer fragility by splitting large DB modules into focused repository components with explicit transaction boundaries.

**Architecture:** Introduce repositories for media metadata, chunk records, and notes operations while keeping existing API-level calls stable through adapter wrappers. Migrate incrementally with parity tests to avoid schema/regression fallout.

**Tech Stack:** SQLite/PostgreSQL adapters, aiosqlite/SQLAlchemy wrappers already in repo, pytest integration tests.

---

### Task 1: Add DB Behavior Contracts Before Extraction

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_media_db_repository_contract.py`
- Create: `tldw_Server_API/tests/DB_Management/test_chachanotes_db_repository_contract.py`
- Reference: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Reference: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`

**Step 1: Write the failing tests**

```python
def test_media_insert_then_fetch_roundtrip(tmp_db):
    media_id = insert_media(tmp_db, title="x")
    row = fetch_media(tmp_db, media_id)
    assert row["title"] == "x"


def test_notes_insert_preserves_user_scope(tmp_notes_db):
    note_id = insert_note(tmp_notes_db, user_id="u1", text="hello")
    assert get_note(tmp_notes_db, note_id)["user_id"] == "u1"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/DB_Management/test_media_db_repository_contract.py -v`
Expected: FAIL until helpers are wired.

**Step 3: Write minimal implementation**

```python
# Build fixture wrappers using existing DB methods.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/DB_Management/test_media_db_repository_contract.py tldw_Server_API/tests/DB_Management/test_chachanotes_db_repository_contract.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_media_db_repository_contract.py tldw_Server_API/tests/DB_Management/test_chachanotes_db_repository_contract.py
git commit -m "test(db): add media/notes repository behavior contracts"
```

### Task 2: Extract Media Repositories

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/repositories/media_repository.py`
- Create: `tldw_Server_API/app/core/DB_Management/repositories/media_chunks_repository.py`
- Create: `tldw_Server_API/app/core/DB_Management/repositories/__init__.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Test: `tldw_Server_API/tests/DB_Management/test_media_db_repository_contract.py`

**Step 1: Write the failing test**

```python
def test_media_repository_create_and_get(tmp_db):
    repo = MediaRepository(tmp_db)
    media_id = repo.create_media(title="abc")
    assert repo.get_media(media_id)["title"] == "abc"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/DB_Management/test_media_db_repository_contract.py::test_media_repository_create_and_get -v`
Expected: FAIL with missing repository class.

**Step 3: Write minimal implementation**

```python
class MediaRepository:
    def __init__(self, db):
        self.db = db
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/DB_Management/test_media_db_repository_contract.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/repositories/media_repository.py tldw_Server_API/app/core/DB_Management/repositories/media_chunks_repository.py tldw_Server_API/app/core/DB_Management/repositories/__init__.py tldw_Server_API/app/core/DB_Management/Media_DB_v2.py tldw_Server_API/tests/DB_Management/test_media_db_repository_contract.py
git commit -m "refactor(db): extract media repositories from Media_DB_v2"
```

### Task 3: Extract Notes Repositories

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/repositories/notes_repository.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Test: `tldw_Server_API/tests/DB_Management/test_chachanotes_db_repository_contract.py`

**Step 1: Write the failing test**

```python
def test_notes_repository_filters_by_user(tmp_notes_db):
    repo = NotesRepository(tmp_notes_db)
    repo.create(user_id="u1", text="a")
    repo.create(user_id="u2", text="b")
    assert len(repo.list_for_user("u1")) == 1
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/DB_Management/test_chachanotes_db_repository_contract.py::test_notes_repository_filters_by_user -v`
Expected: FAIL with missing repository class.

**Step 3: Write minimal implementation**

```python
class NotesRepository:
    def __init__(self, db):
        self.db = db
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/DB_Management/test_chachanotes_db_repository_contract.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/repositories/notes_repository.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/tests/DB_Management/test_chachanotes_db_repository_contract.py
git commit -m "refactor(db): extract notes repository from ChaChaNotes_DB"
```

### Task 4: Add Transaction Boundary Tests and Integration Coverage

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_repository_transaction_boundaries.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py`
- Modify: `tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py`

**Step 1: Write the failing test**

```python
def test_failed_write_rolls_back_atomic_unit(tmp_db):
    with pytest.raises(RuntimeError):
        run_multi_step_write_with_forced_error(tmp_db)
    assert invariant_counts_unchanged(tmp_db)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/DB_Management/test_repository_transaction_boundaries.py -v`
Expected: FAIL because atomic helper is not explicit.

**Step 3: Write minimal implementation**

```python
# Add explicit transaction context manager for repository operations.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/DB_Management/test_repository_transaction_boundaries.py tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/DB_Management/test_repository_transaction_boundaries.py tldw_Server_API/tests/DB_Management/test_media_db_connection_cleanup.py tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py tldw_Server_API/app/core/DB_Management
# Commit all touched DB repo files in this step
git commit -m "test(db): enforce transaction boundaries for extracted repositories"
```
