# Active Org Fallback `id` Key Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix `get_active_org_id()` so the OSS org fallback works when org rows use `id` instead of `org_id`.

**Architecture:** Add a regression test for the `id`-only row shape, verify it fails, implement the minimal fallback fix, then rerun the targeted unit test and Bandit on the touched scope.

**Tech Stack:** Python, pytest, FastAPI dependency helpers.

---

### Task 1: Add the failing regression test

**Files:**
- Modify: `tldw_Server_API/tests/AuthNZ_Unit/test_org_deps.py`

**Step 1: Write the failing test**

Add a test that stubs `get_user_orgs()` to return `[{\"id\": 321}]` and asserts `get_active_org_id()` returns `321`.

**Step 2: Run it to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/AuthNZ_Unit/test_org_deps.py -q
```

Expected: the new test fails because the current code only reads `org_id`.

### Task 2: Implement the minimal fallback fix

**Files:**
- Modify: `tldw_Server_API/app/api/v1/API_Deps/org_deps.py`

**Step 1: Update the fallback lookup**

Use:

```python
active_org_id = user_orgs[0].get("org_id") or user_orgs[0].get("id")
if active_org_id is not None:
    return int(active_org_id)
```

**Step 2: Run the test again**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/AuthNZ_Unit/test_org_deps.py -q
```

Expected: all tests pass.

### Task 3: Verify touched scope and commit

**Files:**
- Verify: `tldw_Server_API/app/api/v1/API_Deps/org_deps.py`
- Verify: `tldw_Server_API/tests/AuthNZ_Unit/test_org_deps.py`

**Step 1: Run Bandit on the touched scope**

Run:

```bash
source .venv/bin/activate
python -m bandit -r tldw_Server_API/app/api/v1/API_Deps/org_deps.py tldw_Server_API/tests/AuthNZ_Unit/test_org_deps.py
```

**Step 2: Commit**

```bash
git add Docs/Plans/2026-03-21-active-org-fallback-id-key-design.md Docs/Plans/2026-03-21-active-org-fallback-id-key-implementation-plan.md tldw_Server_API/app/api/v1/API_Deps/org_deps.py tldw_Server_API/tests/AuthNZ_Unit/test_org_deps.py
git commit -m "fix: support id-key org fallback"
```
