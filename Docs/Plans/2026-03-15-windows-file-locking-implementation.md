# Windows File Locking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `distributed_lock.py` importable and operational on Windows by adding a native file-lock fallback without changing the public lock API.

**Architecture:** Add a small internal adapter that chooses `fcntl` or `msvcrt` at runtime, then route `FileLock` acquire/release through that adapter. Keep test coverage focused on lock contention and the Windows-specific fallback branch.

**Tech Stack:** Python, pytest, stdlib `fcntl`, stdlib `msvcrt`

---

### Task 1: Add regression tests for platform-safe locking

**Files:**
- Modify: `tldw_Server_API/tests/Infrastructure/test_distributed_lock.py`

**Step 1: Write the failing test**

Add tests that:
- exercise lock contention without importing `fcntl` directly
- assert a Windows fallback helper uses `msvcrt.locking()` when `fcntl` is unavailable

**Step 2: Run test to verify it fails**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Infrastructure/test_distributed_lock.py -q
```

Expected: FAIL because the helper for the Windows fallback does not exist yet.

### Task 2: Implement the lock backend adapter

**Files:**
- Modify: `tldw_Server_API/app/core/Infrastructure/distributed_lock.py`

**Step 1: Write minimal implementation**

Add module-level helpers that:
- guard `fcntl` import
- guard `msvcrt` import
- acquire a non-blocking exclusive lock with the available backend
- release the lock with the matching backend

Route `FileLock.acquire()` and `FileLock.release()` through those helpers.

**Step 2: Run targeted tests**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Infrastructure/test_distributed_lock.py -q
```

Expected: PASS

### Task 3: Security and completion checks

**Files:**
- Modify: `tldw_Server_API/app/core/Infrastructure/distributed_lock.py`
- Modify: `tldw_Server_API/tests/Infrastructure/test_distributed_lock.py`

**Step 1: Run Bandit on the touched scope**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Infrastructure/distributed_lock.py tldw_Server_API/tests/Infrastructure/test_distributed_lock.py -f json -o /tmp/bandit_windows_file_locking.json
```

Expected: no new findings in touched code

**Step 2: Review diff and keep scope narrow**

Confirm only the lock adapter, test updates, and plan docs changed.
