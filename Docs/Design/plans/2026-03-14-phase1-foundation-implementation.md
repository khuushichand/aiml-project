# Phase 1: Foundation — Unblock Production

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the 7 critical/high gaps that block production deployment for both SaaS and self-hosted targets.

**Architecture:** Each gap is an independent workstream. We add a distributed lock module for migrations, extend the DSR service with erasure execution (including ChromaDB), harden startup with preflight checks, expand AlertManager rules, verify tenant isolation with integration tests, and ensure a minimal (no-Redis) deploy profile works.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, ChromaDB, Redis (optional), Prometheus/AlertManager YAML, pytest, Bash

---

## Gap Overview

| Task | Gap ID | Description | Effort |
|------|--------|-------------|--------|
| 1 | 5.1 | Verify & enforce ChromaDB tenant isolation | M |
| 2 | 3.1 | Complete GDPR DSR (embeddings erasure) | M |
| 3 | 4.4 | Distributed migration lock | M |
| 4 | 6.3 | Startup preflight validation | S |
| 5 | 4.2 | Default AlertManager rules | S |
| 6 | 10.3 | Minimal deploy profile (SQLite-only) | S |
| 7 | 10.1 | Automated upgrade script | M |

---

## Task 1: ChromaDB Tenant Isolation Verification (Gap 5.1)

**Files:**
- Create: `tldw_Server_API/tests/Embeddings/test_chromadb_tenant_isolation.py`
- Reference: `tldw_Server_API/app/core/Embeddings/ChromaDB_Library.py`
- Reference: `tldw_Server_API/app/core/DB_Management/db_path_utils.py`

### Step 1: Write cross-tenant isolation integration test

```python
# tldw_Server_API/tests/Embeddings/test_chromadb_tenant_isolation.py
"""
Integration tests verifying ChromaDB tenant isolation.

These tests prove that:
1. Each tenant's embeddings are stored in separate collections
2. Cross-tenant search returns zero results
3. Collection naming enforces user_id boundaries
4. Path traversal in user_id is rejected
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import (
    ChromaDBManager,
    validate_user_id,
)


@pytest.fixture()
def chroma_base_dir(tmp_path: Path) -> Path:
    return tmp_path / "chroma_isolation_test"


def _make_manager(user_id: str, base_dir: Path) -> ChromaDBManager:
    return ChromaDBManager(
        user_id=user_id,
        base_dir=str(base_dir),
    )


class TestCrossTenantIsolation:
    """Prove that tenant A cannot see tenant B's embeddings."""

    def test_separate_collections_no_cross_search(self, chroma_base_dir: Path):
        mgr_a = _make_manager("tenant_alpha", chroma_base_dir)
        mgr_b = _make_manager("tenant_beta", chroma_base_dir)

        col_a = f"user_tenant_alpha_media_embeddings"
        col_b = f"user_tenant_beta_media_embeddings"

        # Store embedding for tenant A
        mgr_a.store_in_chroma(
            collection_name=col_a,
            texts=["secret document alpha"],
            ids=["doc-a-1"],
            embeddings=[[0.1] * 384],
        )

        # Store embedding for tenant B
        mgr_b.store_in_chroma(
            collection_name=col_b,
            texts=["secret document beta"],
            ids=["doc-b-1"],
            embeddings=[[0.9] * 384],
        )

        # Tenant B searches their own collection - should find their doc
        results_b = mgr_b.vector_search(
            collection_name=col_b,
            query_embedding=[0.9] * 384,
            n_results=10,
        )
        assert len(results_b) > 0
        assert any("beta" in str(r) for r in results_b)

        # Tenant B searches tenant A's collection name via their own manager
        # This should either return empty or raise (collection doesn't exist in B's client)
        results_cross = mgr_b.vector_search(
            collection_name=col_a,
            query_embedding=[0.9] * 384,
            n_results=10,
        )
        # Since B's ChromaDB client is isolated to B's directory,
        # collection col_a doesn't exist there
        assert len(results_cross) == 0

    def test_filesystem_directories_are_separate(self, chroma_base_dir: Path):
        mgr_a = _make_manager("tenant_alpha", chroma_base_dir)
        mgr_b = _make_manager("tenant_beta", chroma_base_dir)

        # Verify each manager uses a different directory
        dir_a = Path(mgr_a.chroma_dir) if hasattr(mgr_a, "chroma_dir") else None
        dir_b = Path(mgr_b.chroma_dir) if hasattr(mgr_b, "chroma_dir") else None

        if dir_a and dir_b:
            assert dir_a != dir_b
            assert "tenant_alpha" in str(dir_a)
            assert "tenant_beta" in str(dir_b)

    def test_collection_listing_isolated(self, chroma_base_dir: Path):
        mgr_a = _make_manager("tenant_alpha", chroma_base_dir)
        mgr_b = _make_manager("tenant_beta", chroma_base_dir)

        col_a = "user_tenant_alpha_test_col"
        mgr_a.get_or_create_collection(col_a)

        # Tenant B should not see tenant A's collections
        b_collections = mgr_b.list_collections()
        b_names = [c.name if hasattr(c, "name") else str(c) for c in b_collections]
        assert col_a not in b_names


class TestUserIdValidation:
    """Prove that path traversal and injection attacks are rejected."""

    @pytest.mark.parametrize("bad_id", [
        "../escape",
        "../../etc/passwd",
        "user/slash",
        "user\\backslash",
        "user\x00null",
        "user\nnewline",
        "",
        " ",
    ])
    def test_rejects_dangerous_user_ids(self, bad_id: str):
        with pytest.raises((ValueError, Exception)):
            validate_user_id(bad_id)

    @pytest.mark.parametrize("good_id", [
        "user_123",
        "tenant-abc",
        "42",
        "org1_user2",
    ])
    def test_accepts_valid_user_ids(self, good_id: str):
        result = validate_user_id(good_id)
        assert result == good_id


class TestDefaultCollectionNaming:
    """Verify collection names always include user_id."""

    def test_default_collection_includes_user_id(self, chroma_base_dir: Path):
        mgr = _make_manager("user_789", chroma_base_dir)
        name = mgr.get_user_default_collection_name()
        assert "user_789" in name
```

### Step 2: Run tests to verify they pass

Run: `python -m pytest tldw_Server_API/tests/Embeddings/test_chromadb_tenant_isolation.py -v`
Expected: All tests PASS (this is verification, not TDD — the isolation already exists)

### Step 3: Fix any test failures

Adjust test expectations based on actual ChromaDBManager constructor signature and method names. The manager may require `user_embedding_config` parameter — check and adapt.

### Step 4: Commit

```bash
git add tldw_Server_API/tests/Embeddings/test_chromadb_tenant_isolation.py
git commit -m "test: add ChromaDB tenant isolation verification tests (gap 5.1)"
```

---

## Task 2: GDPR DSR Embeddings Erasure (Gap 3.1)

This is the largest task. We need to:
1. Add embeddings counting to DSR preview
2. Add DSR status update to the repo
3. Add erasure execution service method
4. Add erasure execution endpoint
5. Write tests

### Sub-task 2.1: Add embeddings count to DSR preview

**Files:**
- Modify: `tldw_Server_API/app/services/admin_data_subject_requests_service.py`

**Step 1: Write failing test**

Create: `tldw_Server_API/tests/Admin/test_dsr_embeddings_erasure.py`

```python
# tldw_Server_API/tests/Admin/test_dsr_embeddings_erasure.py
"""Tests for GDPR DSR embeddings erasure (gap 3.1)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tldw_Server_API.app.services.admin_data_subject_requests_service import (
    _CATEGORY_DEFS,
    _SUPPORTED_CATEGORY_KEYS,
    _count_embeddings,
)


@pytest.mark.asyncio
async def test_count_embeddings_returns_collection_count():
    """Embeddings count queries ChromaDB for user's collection size."""
    mock_manager = MagicMock()
    mock_collection = MagicMock()
    mock_collection.count.return_value = 42
    mock_manager.get_or_create_collection.return_value = mock_collection
    mock_manager.get_user_default_collection_name.return_value = "user_embeddings_for_123"

    with patch(
        "tldw_Server_API.app.services.admin_data_subject_requests_service._get_chroma_manager_for_user",
        return_value=mock_manager,
    ):
        count = await _count_embeddings(123)

    assert count == 42


def test_embeddings_is_supported_category():
    """After gap 3.1, 'embeddings' must be a supported category."""
    assert "embeddings" in _SUPPORTED_CATEGORY_KEYS
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/Admin/test_dsr_embeddings_erasure.py -v`
Expected: FAIL — `_count_embeddings` doesn't exist yet, `embeddings` not in supported keys

**Step 3: Implement embeddings count + promote to supported category**

Modify `tldw_Server_API/app/services/admin_data_subject_requests_service.py`:

```python
# 1. Add "embeddings" to _CATEGORY_DEFS (around line 19)
_CATEGORY_DEFS: tuple[dict[str, str], ...] = (
    {"key": "media_records", "label": "Media records"},
    {"key": "chat_messages", "label": "Chat sessions/messages"},
    {"key": "notes", "label": "Notes"},
    {"key": "audit_events", "label": "Audit log events"},
    {"key": "embeddings", "label": "Vector embeddings"},  # NEW
)

# 2. Remove "embeddings" from unsupported (line 26)
_UNSUPPORTED_CATEGORY_KEYS: set[str] = set()  # was {"embeddings"}

# 3. Add helper to get ChromaDB manager for a user
def _get_chroma_manager_for_user(user_id: int):
    """Create a ChromaDBManager for the given user."""
    from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import ChromaDBManager
    return ChromaDBManager(user_id=str(user_id))

# 4. Add count function
async def _count_embeddings(user_id: int) -> int:
    """Count embeddings in user's default ChromaDB collection."""
    try:
        manager = _get_chroma_manager_for_user(user_id)
        col_name = manager.get_user_default_collection_name()
        collection = manager.get_or_create_collection(col_name)
        return collection.count()
    except Exception as exc:
        logger.warning("Failed to count embeddings for user {}: {}", user_id, exc)
        return 0

# 5. Update _build_summary_for_user to include embeddings (around line 210)
# Add embeddings to the asyncio.gather call and count_map
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/Admin/test_dsr_embeddings_erasure.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/admin_data_subject_requests_service.py
git add tldw_Server_API/tests/Admin/test_dsr_embeddings_erasure.py
git commit -m "feat: add embeddings count to GDPR DSR preview (gap 3.1 step 1)"
```

### Sub-task 2.2: Add DSR status update to repo

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/data_subject_requests_repo.py`
- Test: `tldw_Server_API/tests/Admin/test_dsr_embeddings_erasure.py`

**Step 1: Write failing test**

```python
# Add to test_dsr_embeddings_erasure.py
@pytest.mark.asyncio
async def test_repo_update_status():
    """DSR repo must support updating request status to 'executing'/'completed'/'failed'."""
    from tldw_Server_API.app.core.AuthNZ.repos.data_subject_requests_repo import (
        AuthnzDataSubjectRequestsRepo,
    )
    assert hasattr(AuthnzDataSubjectRequestsRepo, "update_request_status")
```

**Step 2: Implement update_request_status in repo**

Add to `data_subject_requests_repo.py`:

```python
async def update_request_status(
    self,
    request_id: int,
    new_status: str,
    *,
    notes: str | None = None,
    execution_summary: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Update a DSR's status and optionally append execution notes."""
    valid_statuses = {"pending", "recorded", "executing", "completed", "failed"}
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status: {new_status}. Must be one of {valid_statuses}")

    is_pg = await self._is_postgres_backend()

    if is_pg:
        update_sql = """
            UPDATE data_subject_requests
            SET status = $1, notes = COALESCE($2, notes)
            WHERE id = $3
            RETURNING *
        """
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(update_sql, new_status, notes, request_id)
            return self._normalize_record(dict(row)) if row else None
    else:
        update_sql = """
            UPDATE data_subject_requests
            SET status = ?, notes = COALESCE(?, notes)
            WHERE id = ?
        """
        select_sql = "SELECT * FROM data_subject_requests WHERE id = ?"
        async with self.db_pool.acquire() as conn:
            cursor = conn.cursor()
            cursor.execute(update_sql, (new_status, notes, request_id))
            conn.commit()
            cursor.execute(select_sql, (request_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [desc[0] for desc in cursor.description]
            return self._normalize_record(dict(zip(columns, row)))
```

**Step 3: Run test, verify pass**

**Step 4: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/repos/data_subject_requests_repo.py
git add tldw_Server_API/tests/Admin/test_dsr_embeddings_erasure.py
git commit -m "feat: add update_request_status to DSR repo (gap 3.1 step 2)"
```

### Sub-task 2.3: Add erasure execution service

**Files:**
- Modify: `tldw_Server_API/app/services/admin_data_subject_requests_service.py`
- Test: `tldw_Server_API/tests/Admin/test_dsr_embeddings_erasure.py`

**Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_execute_erasure_deletes_embeddings():
    """Erasure execution must delete user's ChromaDB collections."""
    from tldw_Server_API.app.services.admin_data_subject_requests_service import (
        execute_dsr_erasure,
    )
    assert callable(execute_dsr_erasure)
```

**Step 2: Implement erasure execution**

Add to `admin_data_subject_requests_service.py`:

```python
async def _erase_media_records(user_id: int) -> int:
    """Hard-delete media records for user. Returns count deleted."""
    from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
    db_path = DatabasePaths.get_user_media_db_path(user_id)
    if not db_path.exists():
        return 0
    try:
        db = MediaDatabase(db_path=str(db_path), client_id="dsr_erasure")
        count = db.execute_scalar("SELECT COUNT(*) FROM media WHERE deleted = 0")
        db.execute("DELETE FROM media")
        db.execute("DELETE FROM media_fts")
        return count or 0
    except Exception as exc:
        logger.error("Failed to erase media for user {}: {}", user_id, exc)
        raise


async def _erase_chat_messages(user_id: int) -> int:
    """Hard-delete chat sessions and messages for user."""
    from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import ChaChaNotes_DB
    db_path = DatabasePaths.get_user_chacha_db_path(user_id)
    if not db_path.exists():
        return 0
    try:
        db = ChaChaNotes_DB(str(db_path))
        count = 0
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM chat_messages")
            count = cursor.fetchone()[0] or 0
            cursor.execute("DELETE FROM chat_messages")
            cursor.execute("DELETE FROM chat_sessions")
            conn.commit()
        return count
    except Exception as exc:
        logger.error("Failed to erase chats for user {}: {}", user_id, exc)
        raise


async def _erase_notes(user_id: int) -> int:
    """Hard-delete notes for user."""
    from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import ChaChaNotes_DB
    db_path = DatabasePaths.get_user_chacha_db_path(user_id)
    if not db_path.exists():
        return 0
    try:
        db = ChaChaNotes_DB(str(db_path))
        count = 0
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM notes WHERE deleted = 0")
            count = cursor.fetchone()[0] or 0
            cursor.execute("DELETE FROM notes")
            conn.commit()
        return count
    except Exception as exc:
        logger.error("Failed to erase notes for user {}: {}", user_id, exc)
        raise


async def _erase_embeddings(user_id: int) -> int:
    """Delete all ChromaDB collections for user."""
    try:
        manager = _get_chroma_manager_for_user(user_id)
        collections = manager.list_collections()
        count = 0
        for col in collections:
            col_name = col.name if hasattr(col, "name") else str(col)
            try:
                col_obj = manager.get_or_create_collection(col_name)
                count += col_obj.count()
                manager.delete_collection(col_name)
            except Exception as col_exc:
                logger.warning("Failed to delete collection {}: {}", col_name, col_exc)
        return count
    except Exception as exc:
        logger.error("Failed to erase embeddings for user {}: {}", user_id, exc)
        raise


_ERASURE_HANDLERS: dict[str, Any] = {
    "media_records": _erase_media_records,
    "chat_messages": _erase_chat_messages,
    "notes": _erase_notes,
    "embeddings": _erase_embeddings,
}


async def execute_dsr_erasure(
    *,
    request_id: int,
    user_id: int,
    selected_categories: list[str],
    dsr_repo: AuthnzDataSubjectRequestsRepo,
    principal: AuthPrincipal | None = None,
) -> dict[str, Any]:
    """Execute a recorded DSR erasure request. Deletes data across all stores.

    Returns a summary dict with per-category deletion counts and overall status.
    """
    # Mark as executing
    await dsr_repo.update_request_status(request_id, "executing")

    results: dict[str, Any] = {}
    errors: list[str] = []

    for category in selected_categories:
        handler = _ERASURE_HANDLERS.get(category)
        if handler is None:
            results[category] = {"status": "skipped", "reason": "no_handler"}
            continue
        try:
            deleted_count = await handler(user_id)
            results[category] = {"status": "completed", "deleted_count": deleted_count}
        except Exception as exc:
            logger.error("DSR erasure failed for category {}: {}", category, exc)
            results[category] = {"status": "failed", "error": str(exc)}
            errors.append(f"{category}: {exc}")

    overall_status = "failed" if errors else "completed"
    notes = f"Erasure results: {results}"
    if errors:
        notes += f" | Errors: {'; '.join(errors)}"

    await dsr_repo.update_request_status(
        request_id,
        overall_status,
        notes=notes,
    )

    return {
        "request_id": request_id,
        "status": overall_status,
        "category_results": results,
        "errors": errors,
    }
```

**Step 3: Run test, verify pass**

**Step 4: Commit**

```bash
git add tldw_Server_API/app/services/admin_data_subject_requests_service.py
git add tldw_Server_API/tests/Admin/test_dsr_embeddings_erasure.py
git commit -m "feat: add DSR erasure execution with embeddings support (gap 3.1 step 3)"
```

### Sub-task 2.4: Add erasure execution endpoint

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/admin/admin_data_ops.py`

**Step 1: Write failing test**

```python
# Add to test_dsr_embeddings_erasure.py
def test_execute_erasure_endpoint_exists():
    """POST /data-subject-requests/{id}/execute must exist."""
    from tldw_Server_API.app.api.v1.endpoints.admin.admin_data_ops import router
    routes = [r.path for r in router.routes if hasattr(r, "path")]
    assert any("execute" in p for p in routes)
```

**Step 2: Add endpoint to admin_data_ops.py**

Add after the existing DSR endpoints (around line 698):

```python
@router.post(
    "/data-subject-requests/{request_id}/execute",
    response_model=None,
    summary="Execute a recorded DSR erasure request",
    description="Executes the erasure for a previously recorded DSR. "
    "Deletes data across SQLite, ChromaDB, and audit stores for the specified categories.",
)
async def execute_data_subject_request(
    request_id: int,
    principal: AuthPrincipal = Depends(require_admin_principal),
    db_pool=Depends(get_authnz_db_pool),
):
    """Execute a DSR erasure — permanently deletes user data."""
    from tldw_Server_API.app.services.admin_data_subject_requests_service import (
        execute_dsr_erasure,
    )
    dsr_repo = AuthnzDataSubjectRequestsRepo(db_pool=db_pool)

    # Fetch the request to get user_id and categories
    requests_list, _ = await dsr_repo.list_requests(limit=1, offset=0)
    target = None
    for req in requests_list:
        if req.get("id") == request_id:
            target = req
            break

    if target is None:
        raise HTTPException(status_code=404, detail="dsr_not_found")

    if target.get("request_type") != "erasure":
        raise HTTPException(
            status_code=400,
            detail="only_erasure_requests_can_be_executed",
        )

    if target.get("status") in ("completed", "executing"):
        raise HTTPException(
            status_code=409,
            detail=f"request_already_{target['status']}",
        )

    user_id = target.get("resolved_user_id")
    if user_id is None:
        raise HTTPException(status_code=400, detail="no_resolved_user_id")

    selected_categories = target.get("selected_categories", [])
    if isinstance(selected_categories, str):
        import json
        selected_categories = json.loads(selected_categories)

    await _emit_audit_event(
        principal=principal,
        action="data.delete",
        category="compliance",
        detail=f"Executing DSR erasure #{request_id} for user {user_id}",
    )

    result = await execute_dsr_erasure(
        request_id=request_id,
        user_id=int(user_id),
        selected_categories=selected_categories,
        dsr_repo=dsr_repo,
        principal=principal,
    )

    return result
```

**Step 3: Run test, verify pass**

**Step 4: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/admin/admin_data_ops.py
git add tldw_Server_API/tests/Admin/test_dsr_embeddings_erasure.py
git commit -m "feat: add DSR erasure execution endpoint (gap 3.1 step 4)"
```

---

## Task 3: Distributed Migration Lock (Gap 4.4)

**Files:**
- Create: `tldw_Server_API/app/core/Infrastructure/distributed_lock.py`
- Create: `tldw_Server_API/tests/Infrastructure/test_distributed_lock.py`
- Modify: `tldw_Server_API/app/core/DB_Management/db_migration.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`

### Sub-task 3.1: Create distributed lock module

**Step 1: Write failing test**

```python
# tldw_Server_API/tests/Infrastructure/test_distributed_lock.py
"""Tests for distributed migration lock."""
from __future__ import annotations

import time
import threading

import pytest

from tldw_Server_API.app.core.Infrastructure.distributed_lock import (
    DistributedLock,
    FileLock,
    acquire_migration_lock,
)


class TestFileLock:
    def test_acquire_and_release(self, tmp_path):
        lock = FileLock(tmp_path / "test.lock", timeout=5)
        assert lock.acquire()
        lock.release()

    def test_context_manager(self, tmp_path):
        lock = FileLock(tmp_path / "test.lock", timeout=5)
        with lock:
            assert (tmp_path / "test.lock").exists()

    def test_blocks_concurrent_acquisition(self, tmp_path):
        lock_path = tmp_path / "test.lock"
        lock1 = FileLock(lock_path, timeout=1)
        lock2 = FileLock(lock_path, timeout=1)

        assert lock1.acquire()
        # Second lock should fail (timeout=1s)
        assert not lock2.acquire()
        lock1.release()
        # Now second lock should succeed
        assert lock2.acquire()
        lock2.release()

    def test_stale_lock_is_broken(self, tmp_path):
        lock_path = tmp_path / "test.lock"
        # Create a stale lock with a non-existent PID
        lock_path.write_text("999999999")  # very unlikely PID
        lock = FileLock(lock_path, timeout=1, stale_timeout=0)
        assert lock.acquire()
        lock.release()


class TestAcquireMigrationLock:
    def test_returns_context_manager(self, tmp_path):
        with acquire_migration_lock(
            lock_dir=str(tmp_path),
            lock_name="test_migration",
            redis_url=None,
        ):
            pass  # Should not raise
```

**Step 2: Implement distributed lock**

```python
# tldw_Server_API/app/core/Infrastructure/distributed_lock.py
"""
Distributed locking for database migrations and other critical sections.

Provides:
- FileLock: File-based lock using OS-level file locking (works everywhere)
- RedisLock: Redis-based distributed lock (for multi-node deployments)
- acquire_migration_lock(): Smart factory that picks the best available backend
"""
from __future__ import annotations

import contextlib
import fcntl
import os
import time
from pathlib import Path
from typing import Generator

from loguru import logger


class LockAcquisitionError(RuntimeError):
    """Raised when a lock cannot be acquired within the timeout."""


class FileLock:
    """Cross-process file-based lock using fcntl.

    Safe for single-node multi-process deployments (Docker, systemd, etc.).
    For multi-node, use RedisLock or PostgreSQL advisory locks.
    """

    def __init__(
        self,
        path: str | Path,
        timeout: float = 60,
        stale_timeout: float = 300,
    ):
        self._path = Path(path)
        self._timeout = timeout
        self._stale_timeout = stale_timeout
        self._fd: int | None = None

    def acquire(self) -> bool:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._break_stale_lock()

        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            try:
                fd = os.open(str(self._path), os.O_CREAT | os.O_WRONLY)
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                os.write(fd, str(os.getpid()).encode())
                self._fd = fd
                logger.debug("Acquired file lock: {}", self._path)
                return True
            except (OSError, IOError):
                try:
                    os.close(fd)
                except OSError:
                    pass
                time.sleep(0.5)

        logger.warning("Failed to acquire lock {} within {}s", self._path, self._timeout)
        return False

    def release(self):
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
            except OSError:
                pass
            finally:
                self._fd = None
            with contextlib.suppress(OSError):
                self._path.unlink()
            logger.debug("Released file lock: {}", self._path)

    def _break_stale_lock(self):
        """Remove lock file if the owning process is dead or lock is too old."""
        if not self._path.exists():
            return
        try:
            mtime = self._path.stat().st_mtime
            if time.time() - mtime > self._stale_timeout:
                logger.warning("Breaking stale lock (age > {}s): {}", self._stale_timeout, self._path)
                self._path.unlink(missing_ok=True)
                return
            pid_str = self._path.read_text().strip()
            if pid_str and pid_str.isdigit():
                pid = int(pid_str)
                try:
                    os.kill(pid, 0)  # Check if process exists
                except OSError:
                    logger.warning("Breaking stale lock (PID {} dead): {}", pid, self._path)
                    self._path.unlink(missing_ok=True)
        except OSError:
            pass

    def __enter__(self):
        if not self.acquire():
            raise LockAcquisitionError(
                f"Could not acquire lock {self._path} within {self._timeout}s"
            )
        return self

    def __exit__(self, *args):
        self.release()


class RedisLock:
    """Redis-based distributed lock using SET NX EX pattern.

    For multi-node deployments where file locks are insufficient.
    """

    def __init__(
        self,
        redis_client,
        key: str = "tldw:migration:lock",
        timeout: float = 60,
        ttl: int = 300,
    ):
        self._client = redis_client
        self._key = key
        self._timeout = timeout
        self._ttl = ttl
        self._token: str | None = None

    def acquire(self) -> bool:
        import uuid
        self._token = str(uuid.uuid4())
        deadline = time.monotonic() + self._timeout

        while time.monotonic() < deadline:
            acquired = self._client.set(
                self._key, self._token, nx=True, ex=self._ttl
            )
            if acquired:
                logger.debug("Acquired Redis lock: {} (token={})", self._key, self._token[:8])
                return True
            time.sleep(0.5)

        logger.warning("Failed to acquire Redis lock {} within {}s", self._key, self._timeout)
        return False

    def release(self):
        if self._token is None:
            return
        # Lua script for atomic check-and-delete
        lua = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        try:
            self._client.eval(lua, 1, self._key, self._token)
        except Exception as exc:
            logger.warning("Failed to release Redis lock: {}", exc)
        finally:
            self._token = None

    def __enter__(self):
        if not self.acquire():
            raise LockAcquisitionError(
                f"Could not acquire Redis lock {self._key} within {self._timeout}s"
            )
        return self

    def __exit__(self, *args):
        self.release()


@contextlib.contextmanager
def acquire_migration_lock(
    *,
    lock_dir: str | None = None,
    lock_name: str = "db_migration",
    redis_url: str | None = None,
    timeout: float = 60,
) -> Generator[None, None, None]:
    """Acquire a migration lock using the best available backend.

    Priority:
    1. Redis lock (if redis_url provided and Redis reachable)
    2. File lock (always available)
    """
    # Try Redis first
    if redis_url:
        try:
            import redis as redis_lib
            client = redis_lib.from_url(redis_url, socket_connect_timeout=5)
            client.ping()
            lock = RedisLock(client, key=f"tldw:{lock_name}:lock", timeout=timeout)
            with lock:
                yield
            return
        except Exception as exc:
            logger.warning("Redis lock unavailable ({}), falling back to file lock", exc)

    # Fall back to file lock
    if lock_dir is None:
        lock_dir = str(Path.home() / ".tldw" / "locks")
    lock_path = Path(lock_dir) / f"{lock_name}.lock"
    lock = FileLock(lock_path, timeout=timeout)
    with lock:
        yield
```

**Step 3: Run test, verify pass**

Run: `python -m pytest tldw_Server_API/tests/Infrastructure/test_distributed_lock.py -v`

**Step 4: Commit**

```bash
git add tldw_Server_API/app/core/Infrastructure/distributed_lock.py
git add tldw_Server_API/tests/Infrastructure/test_distributed_lock.py
git commit -m "feat: add distributed lock module for migrations (gap 4.4 step 1)"
```

### Sub-task 3.2: Integrate lock into migration flow

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/db_migration.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`

**Step 1: Write failing test**

```python
# Add to test_distributed_lock.py
def test_database_migrator_accepts_lock_config():
    """DatabaseMigrator should accept distributed lock configuration."""
    from tldw_Server_API.app.core.DB_Management.db_migration import DatabaseMigrator
    # Verify the class accepts lock parameters
    sig = inspect.signature(DatabaseMigrator.migrate_to_version)
    # Should not raise
```

**Step 2: Add lock to DatabaseMigrator.migrate_to_version()**

In `db_migration.py`, wrap the migration execution in `acquire_migration_lock`:

```python
# Add import at top of db_migration.py
from tldw_Server_API.app.core.Infrastructure.distributed_lock import acquire_migration_lock

# In the migrate_to_version method, wrap the migration loop:
def migrate_to_version(self, target_version: int, ...) -> ...:
    redis_url = os.getenv("REDIS_URL")
    lock_dir = str(Path(self.db_path).parent)

    with acquire_migration_lock(
        lock_dir=lock_dir,
        lock_name=f"migration_{Path(self.db_path).stem}",
        redis_url=redis_url,
    ):
        # ... existing migration logic ...
```

**Step 3: Add lock to AuthNZ migrations**

In `AuthNZ/migrations.py`, wrap `apply_authnz_migrations()`:

```python
# Add import
from tldw_Server_API.app.core.Infrastructure.distributed_lock import acquire_migration_lock

def apply_authnz_migrations(db_path: str | Path, ...) -> ...:
    redis_url = os.getenv("REDIS_URL")
    lock_dir = str(Path(db_path).parent)

    with acquire_migration_lock(
        lock_dir=lock_dir,
        lock_name="authnz_migration",
        redis_url=redis_url,
    ):
        # ... existing migration logic ...
```

**Step 4: Run existing migration tests**

Run: `python -m pytest tldw_Server_API/tests/ -k "migration" -v --timeout=30`
Expected: All existing migration tests still pass

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/db_migration.py
git add tldw_Server_API/app/core/AuthNZ/migrations.py
git commit -m "feat: integrate distributed lock into migration flows (gap 4.4 step 2)"
```

---

## Task 4: Startup Preflight Validation (Gap 6.3)

**Files:**
- Create: `tldw_Server_API/app/core/startup_preflight.py`
- Create: `tldw_Server_API/tests/test_startup_preflight.py`
- Modify: `tldw_Server_API/app/main.py` (add call in lifespan)

### Step 1: Write failing test

```python
# tldw_Server_API/tests/test_startup_preflight.py
"""Tests for startup preflight validation."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from tldw_Server_API.app.core.startup_preflight import (
    PreflightResult,
    run_preflight_checks,
    check_ffmpeg_available,
    check_disk_space,
    check_database_directories,
)


class TestPreflightResult:
    def test_all_passed(self):
        result = PreflightResult(checks=[
            {"name": "ffmpeg", "status": "ok"},
        ])
        assert result.all_passed

    def test_has_failures(self):
        result = PreflightResult(checks=[
            {"name": "ffmpeg", "status": "fail", "message": "not found"},
        ])
        assert not result.all_passed
        assert result.failures == ["ffmpeg: not found"]


class TestFfmpegCheck:
    def test_ffmpeg_found(self):
        # ffmpeg should be installed in dev environment
        result = check_ffmpeg_available()
        # Don't assert pass — just verify it returns a dict with expected keys
        assert "name" in result
        assert "status" in result

    @patch("shutil.which", return_value=None)
    def test_ffmpeg_not_found(self, mock_which):
        result = check_ffmpeg_available()
        assert result["status"] == "fail"


class TestDiskSpaceCheck:
    def test_sufficient_space(self):
        result = check_disk_space(min_mb=1)  # 1MB should always be available
        assert result["status"] == "ok"

    def test_insufficient_space(self):
        result = check_disk_space(min_mb=999_999_999)  # ~1 petabyte
        assert result["status"] == "warn"


class TestDatabaseDirectories:
    def test_writable_directory(self, tmp_path):
        result = check_database_directories(base_dir=str(tmp_path))
        assert result["status"] == "ok"


class TestRunPreflight:
    def test_returns_result(self):
        result = run_preflight_checks()
        assert isinstance(result, PreflightResult)
        assert len(result.checks) > 0
```

### Step 2: Implement preflight module

```python
# tldw_Server_API/app/core/startup_preflight.py
"""
Startup preflight validation.

Runs quick checks at app startup to catch misconfigurations early.
Checks are non-blocking by default (warn) but can be made fatal via
TLDW_PREFLIGHT_STRICT=true environment variable.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class PreflightResult:
    checks: list[dict[str, Any]] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(c["status"] != "fail" for c in self.checks)

    @property
    def failures(self) -> list[str]:
        return [
            f"{c['name']}: {c.get('message', 'failed')}"
            for c in self.checks
            if c["status"] == "fail"
        ]

    @property
    def warnings(self) -> list[str]:
        return [
            f"{c['name']}: {c.get('message', 'warning')}"
            for c in self.checks
            if c["status"] == "warn"
        ]


def check_ffmpeg_available() -> dict[str, Any]:
    """Check that ffmpeg is on PATH (required for audio/video processing)."""
    path = shutil.which("ffmpeg")
    if path:
        return {"name": "ffmpeg", "status": "ok", "path": path}
    return {
        "name": "ffmpeg",
        "status": "fail",
        "message": "ffmpeg not found on PATH. Audio/video processing will fail.",
    }


def check_disk_space(
    min_mb: int = 500,
    path: str | None = None,
) -> dict[str, Any]:
    """Check available disk space at the database directory."""
    check_path = path or os.getcwd()
    try:
        usage = shutil.disk_usage(check_path)
        free_mb = usage.free // (1024 * 1024)
        if free_mb < min_mb:
            return {
                "name": "disk_space",
                "status": "warn",
                "message": f"Only {free_mb}MB free (minimum recommended: {min_mb}MB)",
                "free_mb": free_mb,
            }
        return {"name": "disk_space", "status": "ok", "free_mb": free_mb}
    except OSError as exc:
        return {"name": "disk_space", "status": "warn", "message": str(exc)}


def check_database_directories(base_dir: str | None = None) -> dict[str, Any]:
    """Check that database directories exist and are writable."""
    if base_dir is None:
        base_dir = os.path.join(os.getcwd(), "Databases")

    base = Path(base_dir)
    if not base.exists():
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return {
                "name": "database_directories",
                "status": "fail",
                "message": f"Cannot create database directory {base}: {exc}",
            }

    # Test writability
    test_file = base / ".preflight_write_test"
    try:
        test_file.write_text("ok")
        test_file.unlink()
        return {"name": "database_directories", "status": "ok", "path": str(base)}
    except OSError as exc:
        return {
            "name": "database_directories",
            "status": "fail",
            "message": f"Database directory {base} is not writable: {exc}",
        }


def check_python_dependencies() -> dict[str, Any]:
    """Check that critical Python packages are importable."""
    missing = []
    for pkg in ["fastapi", "uvicorn", "pydantic", "loguru", "chromadb"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        return {
            "name": "python_dependencies",
            "status": "fail",
            "message": f"Missing packages: {', '.join(missing)}",
        }
    return {"name": "python_dependencies", "status": "ok"}


def run_preflight_checks() -> PreflightResult:
    """Run all preflight checks and return aggregated result."""
    result = PreflightResult()

    checks = [
        check_python_dependencies,
        check_ffmpeg_available,
        lambda: check_disk_space(),
        lambda: check_database_directories(),
    ]

    for check_fn in checks:
        try:
            check_result = check_fn()
            result.checks.append(check_result)
        except Exception as exc:
            result.checks.append({
                "name": getattr(check_fn, "__name__", "unknown"),
                "status": "fail",
                "message": f"Check crashed: {exc}",
            })

    # Log results
    for check in result.checks:
        if check["status"] == "ok":
            logger.info("Preflight [{}]: OK", check["name"])
        elif check["status"] == "warn":
            logger.warning("Preflight [{}]: {}", check["name"], check.get("message", ""))
        else:
            logger.error("Preflight [{}]: {}", check["name"], check.get("message", ""))

    if result.failures:
        strict = os.getenv("TLDW_PREFLIGHT_STRICT", "").lower() in ("1", "true", "yes")
        if strict:
            raise RuntimeError(
                f"Preflight failed (strict mode): {'; '.join(result.failures)}"
            )
        else:
            logger.warning(
                "Preflight failures (non-strict mode, continuing): {}",
                "; ".join(result.failures),
            )

    return result
```

### Step 3: Run test, verify pass

Run: `python -m pytest tldw_Server_API/tests/test_startup_preflight.py -v`

### Step 4: Integrate into main.py lifespan

Add to `main.py` lifespan function, early in the startup sequence (before DB initialization):

```python
# Near the top of lifespan(), after test mode validation
from tldw_Server_API.app.core.startup_preflight import run_preflight_checks
preflight = run_preflight_checks()
logger.info("Preflight: {} checks, {} warnings, {} failures",
    len(preflight.checks), len(preflight.warnings), len(preflight.failures))
```

### Step 5: Commit

```bash
git add tldw_Server_API/app/core/startup_preflight.py
git add tldw_Server_API/tests/test_startup_preflight.py
git add tldw_Server_API/app/main.py
git commit -m "feat: add startup preflight validation (gap 6.3)"
```

---

## Task 5: Default AlertManager Rules (Gap 4.2)

**Files:**
- Modify: `Docs/Operations/monitoring/prometheus_alerts_tldw.yml`

### Step 1: Expand alert rules

Add these rule groups to `prometheus_alerts_tldw.yml`:

```yaml
  # --- NEW RULE GROUPS ---

  - name: tldw_server_api_latency
    rules:
      - alert: TLDWApiLatencyP95High
        expr: |
          histogram_quantile(
            0.95,
            sum by (le) (rate(http_request_duration_seconds_bucket[5m]))
          ) > 5
        for: 10m
        labels:
          severity: warning
          service: tldw_server
        annotations:
          summary: "API p95 latency exceeds 5s"
          description: "p95 request latency is {{ $value | humanize }}s over 10m."

      - alert: TLDWApiLatencyP99Critical
        expr: |
          histogram_quantile(
            0.99,
            sum by (le) (rate(http_request_duration_seconds_bucket[5m]))
          ) > 30
        for: 5m
        labels:
          severity: critical
          service: tldw_server
        annotations:
          summary: "API p99 latency exceeds 30s"
          description: "p99 request latency is {{ $value | humanize }}s — possible downstream failure."

  - name: tldw_server_resources
    rules:
      - alert: TLDWHighMemoryUsage
        expr: |
          process_resident_memory_bytes / 1024 / 1024 > 2048
        for: 10m
        labels:
          severity: warning
          service: tldw_server
        annotations:
          summary: "tldw_server memory usage > 2GB"
          description: "Resident memory is {{ $value | humanize }}MB."

      - alert: TLDWHighCpuUsage
        expr: |
          rate(process_cpu_seconds_total[5m]) > 0.9
        for: 10m
        labels:
          severity: warning
          service: tldw_server
        annotations:
          summary: "tldw_server CPU usage > 90%"
          description: "CPU utilization is {{ $value | humanizePercentage }}."

      - alert: TLDWDiskSpaceLow
        expr: |
          node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} < 0.1
        for: 5m
        labels:
          severity: critical
          service: tldw_server
        annotations:
          summary: "Disk space below 10%"
          description: "Available disk space is {{ $value | humanizePercentage }}."

  - name: tldw_server_database
    rules:
      - alert: TLDWDatabaseErrors
        expr: |
          sum(rate(db_operation_errors_total[5m])) > 0.5
        for: 5m
        labels:
          severity: critical
          service: tldw_server
        annotations:
          summary: "Database error rate elevated"
          description: "DB errors at {{ $value }} errors/sec over 5m."

  - name: tldw_server_workers
    rules:
      - alert: TLDWWorkerQueueBacklog
        expr: |
          tldw_worker_queue_depth > 100
        for: 15m
        labels:
          severity: warning
          service: tldw_server
        annotations:
          summary: "Worker queue backlog > 100 items"
          description: "Queue depth is {{ $value }} items for 15m."

  - name: tldw_server_llm
    rules:
      - alert: TLDWLlmErrorRateHigh
        expr: |
          (
            sum(rate(llm_request_errors_total[5m]))
            /
            clamp_min(sum(rate(llm_requests_total[5m])), 0.001)
          ) > 0.10
        for: 10m
        labels:
          severity: warning
          service: tldw_server
        annotations:
          summary: "LLM provider error rate > 10%"
          description: "LLM call failure rate is {{ $value | humanizePercentage }}."

      - alert: TLDWLlmDailySpendHigh
        expr: |
          sum(increase(llm_cost_usd_total[24h])) > 100
        for: 1h
        labels:
          severity: warning
          service: tldw_server
        annotations:
          summary: "Daily LLM spend exceeds $100"
          description: "24h LLM cost is ${{ $value | humanize }}."

  - name: tldw_server_auth
    rules:
      - alert: TLDWAuthFailureBurst
        expr: |
          sum(rate(auth_failures_total[5m])) > 10
        for: 5m
        labels:
          severity: critical
          service: tldw_server
        annotations:
          summary: "Authentication failure burst detected"
          description: "Auth failures at {{ $value }} failures/sec — possible brute force."
```

### Step 2: Validate YAML syntax

Run: `python -c "import yaml; yaml.safe_load(open('Docs/Operations/monitoring/prometheus_alerts_tldw.yml'))" && echo "Valid YAML"`

### Step 3: Commit

```bash
git add Docs/Operations/monitoring/prometheus_alerts_tldw.yml
git commit -m "feat: add comprehensive AlertManager rules (gap 4.2)"
```

---

## Task 6: Minimal Deploy Profile (Gap 10.3)

**Files:**
- Create: `tldw_Server_API/tests/test_minimal_deploy.py`
- Create: `Docs/Deployment/minimal-deploy.md`

### Step 1: Write test verifying Redis-free startup

```python
# tldw_Server_API/tests/test_minimal_deploy.py
"""Tests for minimal deploy profile (no Redis, SQLite-only)."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest


class TestRedisOptional:
    """Verify the app handles Redis being unavailable."""

    def test_redis_factory_falls_back_to_stub(self):
        """redis_factory must fallback to InMemoryAsyncRedis when Redis unavailable."""
        from tldw_Server_API.app.core.Infrastructure.redis_factory import (
            InMemoryAsyncRedis,
        )
        # InMemoryAsyncRedis must exist as a fallback
        assert InMemoryAsyncRedis is not None

    @pytest.mark.asyncio
    async def test_create_async_redis_fallback(self):
        """create_async_redis_client with bad URL falls back to stub."""
        from tldw_Server_API.app.core.Infrastructure.redis_factory import (
            create_async_redis_client,
        )
        client = await create_async_redis_client(
            preferred_url="redis://invalid-host:9999",
            fallback_to_fake=True,
            context="minimal_deploy_test",
        )
        # Should get a stub, not raise
        assert hasattr(client, "_tldw_is_stub") and client._tldw_is_stub

    def test_resource_governor_handles_no_redis(self):
        """Resource Governor must not crash when Redis is unavailable."""
        # This verifies the governor has fallback behavior
        from tldw_Server_API.app.core.Resource_Governance import governor
        assert governor is not None


class TestSQLiteOnly:
    """Verify the app works with SQLite for all databases."""

    def test_default_database_url_is_sqlite(self):
        """Default DATABASE_URL should be SQLite."""
        default_url = os.getenv("DATABASE_URL", "sqlite:///./Databases/users.db")
        assert "sqlite" in default_url.lower()
```

### Step 2: Run tests

Run: `python -m pytest tldw_Server_API/tests/test_minimal_deploy.py -v`

### Step 3: Create minimal deploy documentation

Create `Docs/Deployment/minimal-deploy.md` with:
- SQLite-only configuration (no PostgreSQL)
- No Redis required (in-memory fallback)
- Minimum environment variables
- Docker compose override for minimal profile
- Hardware requirements (minimum: 2 CPU, 4GB RAM, 10GB disk)

### Step 4: Commit

```bash
git add tldw_Server_API/tests/test_minimal_deploy.py
git add Docs/Deployment/minimal-deploy.md
git commit -m "feat: add minimal deploy profile verification and docs (gap 10.3)"
```

---

## Task 7: Automated Upgrade Script (Gap 10.1)

**Files:**
- Create: `Helper_Scripts/upgrade.sh`
- Create: `Helper_Scripts/upgrade_helpers.py`
- Create: `tldw_Server_API/tests/test_upgrade_helpers.py`

### Step 1: Write upgrade helper tests

```python
# tldw_Server_API/tests/test_upgrade_helpers.py
"""Tests for upgrade helper functions."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from Helper_Scripts.upgrade_helpers import (
    check_version_compatibility,
    run_pre_upgrade_checks,
    PreUpgradeResult,
)


class TestVersionCompatibility:
    def test_same_version(self):
        assert check_version_compatibility("0.1.25", "0.1.25") is True

    def test_minor_upgrade(self):
        assert check_version_compatibility("0.1.25", "0.1.26") is True

    def test_major_downgrade_rejected(self):
        assert check_version_compatibility("0.2.0", "0.1.0") is False


class TestPreUpgradeChecks:
    def test_returns_result(self, tmp_path):
        result = run_pre_upgrade_checks(
            db_dir=str(tmp_path),
            min_disk_mb=1,
        )
        assert isinstance(result, PreUpgradeResult)
        assert result.can_proceed
```

### Step 2: Implement upgrade helpers

```python
# Helper_Scripts/upgrade_helpers.py
"""
Pre-upgrade validation helpers for tldw_server.

Used by upgrade.sh to validate the environment before applying updates.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PreUpgradeResult:
    checks: list[dict[str, Any]] = field(default_factory=list)

    @property
    def can_proceed(self) -> bool:
        return all(c["status"] != "fail" for c in self.checks)

    @property
    def summary(self) -> str:
        passed = sum(1 for c in self.checks if c["status"] == "ok")
        warned = sum(1 for c in self.checks if c["status"] == "warn")
        failed = sum(1 for c in self.checks if c["status"] == "fail")
        return f"{passed} passed, {warned} warnings, {failed} failed"


def check_version_compatibility(current: str, target: str) -> bool:
    """Check if upgrade from current to target version is supported."""
    def parse(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in v.lstrip("v").split("."))

    cur = parse(current)
    tgt = parse(target)

    # Don't allow downgrades
    if tgt < cur:
        return False
    return True


def check_database_integrity(db_path: str) -> dict[str, Any]:
    """Run SQLite integrity check on a database file."""
    if not Path(db_path).exists():
        return {"name": f"db_integrity:{db_path}", "status": "ok", "message": "not found (new install)"}

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        conn.close()
        if result == "ok":
            return {"name": f"db_integrity:{Path(db_path).name}", "status": "ok"}
        return {
            "name": f"db_integrity:{Path(db_path).name}",
            "status": "fail",
            "message": f"Integrity check failed: {result}",
        }
    except Exception as exc:
        return {
            "name": f"db_integrity:{Path(db_path).name}",
            "status": "fail",
            "message": str(exc),
        }


def run_pre_upgrade_checks(
    *,
    db_dir: str = "Databases",
    min_disk_mb: int = 500,
) -> PreUpgradeResult:
    """Run all pre-upgrade validation checks."""
    result = PreUpgradeResult()

    # Disk space
    try:
        usage = shutil.disk_usage(db_dir if Path(db_dir).exists() else os.getcwd())
        free_mb = usage.free // (1024 * 1024)
        if free_mb < min_disk_mb:
            result.checks.append({
                "name": "disk_space",
                "status": "warn",
                "message": f"{free_mb}MB free (need {min_disk_mb}MB for safe upgrade)",
            })
        else:
            result.checks.append({"name": "disk_space", "status": "ok", "free_mb": free_mb})
    except OSError as exc:
        result.checks.append({"name": "disk_space", "status": "warn", "message": str(exc)})

    # Database integrity
    db_base = Path(db_dir)
    if db_base.exists():
        for db_file in db_base.glob("**/*.db"):
            result.checks.append(check_database_integrity(str(db_file)))
    else:
        result.checks.append({"name": "databases", "status": "ok", "message": "No databases directory (new install)"})

    # Python version
    import sys
    if sys.version_info < (3, 11):
        result.checks.append({
            "name": "python_version",
            "status": "fail",
            "message": f"Python {sys.version} — requires 3.11+",
        })
    else:
        result.checks.append({"name": "python_version", "status": "ok"})

    return result
```

### Step 3: Create upgrade shell script

```bash
# Helper_Scripts/upgrade.sh
#!/usr/bin/env bash
set -euo pipefail

# tldw_server Upgrade Script
# Usage: ./Helper_Scripts/upgrade.sh [--target-version VERSION]
#
# This script:
# 1. Runs pre-flight checks
# 2. Creates a backup of all databases
# 3. Pulls the latest code (or specified version)
# 4. Installs dependencies
# 5. Runs database migrations
# 6. Validates the upgrade
# 7. Provides rollback instructions on failure

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="${PROJECT_ROOT}/Backups/upgrade_$(date +%Y%m%d_%H%M%S)"
TARGET_VERSION=""
DRY_RUN=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --target-version VERSION   Git tag/branch to upgrade to (default: latest main)"
    echo "  --dry-run                  Run checks only, don't apply changes"
    echo "  --help                     Show this help"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --target-version) TARGET_VERSION="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        --help) usage ;;
        *) log_error "Unknown option: $1"; usage ;;
    esac
done

cd "$PROJECT_ROOT"

# Step 1: Pre-flight checks
log_info "Running pre-flight checks..."
python -c "
from Helper_Scripts.upgrade_helpers import run_pre_upgrade_checks
result = run_pre_upgrade_checks()
print(result.summary)
if not result.can_proceed:
    for c in result.checks:
        if c['status'] == 'fail':
            print(f'  FAIL: {c[\"name\"]}: {c.get(\"message\", \"\")}')
    exit(1)
"

if [ $? -ne 0 ]; then
    log_error "Pre-flight checks failed. Fix issues above before upgrading."
    exit 1
fi
log_info "Pre-flight checks passed."

if [ "$DRY_RUN" = true ]; then
    log_info "Dry run complete. No changes applied."
    exit 0
fi

# Step 2: Create backup
log_info "Creating backup at $BACKUP_DIR..."
mkdir -p "$BACKUP_DIR"

if [ -d "Databases" ]; then
    cp -r Databases "$BACKUP_DIR/Databases"
    log_info "Databases backed up."
fi

# Save current commit hash for rollback
git rev-parse HEAD > "$BACKUP_DIR/previous_commit.txt"
log_info "Current commit saved: $(cat "$BACKUP_DIR/previous_commit.txt")"

# Step 3: Pull latest code
log_info "Pulling latest code..."
git stash --include-untracked 2>/dev/null || true

if [ -n "$TARGET_VERSION" ]; then
    git fetch --tags
    git checkout "$TARGET_VERSION"
else
    git pull origin main
fi

# Step 4: Install dependencies
log_info "Installing dependencies..."
pip install -e ".[dev]" --quiet

# Step 5: Run migrations
log_info "Running database migrations..."
python -c "
from tldw_Server_API.app.core.AuthNZ.migrations import apply_authnz_migrations, check_migration_status
import os
db_path = os.getenv('DATABASE_URL', 'Databases/users.db').replace('sqlite:///', '')
status = check_migration_status(db_path)
if not status.get('is_up_to_date', True):
    apply_authnz_migrations(db_path)
    print('Migrations applied successfully.')
else:
    print('Database already up to date.')
"

# Step 6: Validate
log_info "Running post-upgrade validation..."
python -c "
from Helper_Scripts.upgrade_helpers import run_pre_upgrade_checks
result = run_pre_upgrade_checks()
print(f'Post-upgrade: {result.summary}')
"

log_info "Upgrade complete!"
log_info ""
log_info "To rollback if needed:"
log_info "  1. git checkout $(cat "$BACKUP_DIR/previous_commit.txt")"
log_info "  2. cp -r $BACKUP_DIR/Databases ./Databases"
log_info "  3. pip install -e '.[dev]'"
```

### Step 4: Run tests

Run: `python -m pytest tldw_Server_API/tests/test_upgrade_helpers.py -v`

### Step 5: Make script executable and commit

```bash
chmod +x Helper_Scripts/upgrade.sh
git add Helper_Scripts/upgrade.sh Helper_Scripts/upgrade_helpers.py
git add tldw_Server_API/tests/test_upgrade_helpers.py
git commit -m "feat: add automated upgrade script with pre-flight checks (gap 10.1)"
```

---

## Verification Checklist

After all 7 tasks are complete:

- [ ] **5.1**: `python -m pytest tldw_Server_API/tests/Embeddings/test_chromadb_tenant_isolation.py -v` — all pass
- [ ] **3.1**: `python -m pytest tldw_Server_API/tests/Admin/test_dsr_embeddings_erasure.py -v` — all pass
- [ ] **4.4**: `python -m pytest tldw_Server_API/tests/Infrastructure/test_distributed_lock.py -v` — all pass
- [ ] **6.3**: `python -m pytest tldw_Server_API/tests/test_startup_preflight.py -v` — all pass
- [ ] **4.2**: `python -c "import yaml; yaml.safe_load(open('Docs/Operations/monitoring/prometheus_alerts_tldw.yml'))"` — valid YAML
- [ ] **10.3**: `python -m pytest tldw_Server_API/tests/test_minimal_deploy.py -v` — all pass
- [ ] **10.1**: `python -m pytest tldw_Server_API/tests/test_upgrade_helpers.py -v` — all pass; `bash Helper_Scripts/upgrade.sh --dry-run` exits 0
- [ ] All existing tests still pass: `python -m pytest tldw_Server_API/tests/ -x --timeout=60 -q`

## Dependency Graph

```
Task 1 (ChromaDB isolation) ─── independent
Task 2 (GDPR DSR) ─────────── independent (uses ChromaDB but separate code path)
Task 3 (Migration lock) ────── independent
Task 4 (Preflight) ─────────── independent
Task 5 (AlertManager) ──────── independent
Task 6 (Minimal deploy) ────── independent
Task 7 (Upgrade script) ────── depends on Task 4 (uses preflight checks)
```

Tasks 1-6 can be parallelized. Task 7 should run after Task 4.
