# Runtime FIXME Hotspot Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate high-risk runtime `TODO/FIXME` hotspots in auth, CORS, config defaults, and sync/search data integrity flows.

**Architecture:** Prioritize only production-path markers (exclude archived/static assets), convert each hotspot into a failing safety test, then implement the minimal fix and remove the marker. Track remaining markers in a debt register.

**Tech Stack:** FastAPI middleware/config, pytest, AuthNZ tests, sync/search endpoint tests.

---

### Task 1: Create Hotspot Register and Failing Safety Tests

**Files:**
- Create: `Docs/Plans/2026-03-02-runtime-fixme-hotspot-register.md`
- Create: `tldw_Server_API/tests/Security/test_runtime_fixme_hotspots.py`
- Reference: `tldw_Server_API/app/main.py`
- Reference: `tldw_Server_API/app/core/config.py`
- Reference: `tldw_Server_API/app/api/v1/endpoints/sync.py`

**Step 1: Write the failing tests**

```python
def test_cors_policy_not_wildcard_in_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    app = build_app_for_test()
    assert "*" not in get_cors_allow_origins(app)


def test_sync_endpoint_enforces_fts_update_path(client):
    resp = client.post("/api/v1/sync/...", json={...})
    assert resp.status_code in {200, 202}
    assert "fts" not in resp.text.lower() or "disabled" not in resp.text.lower()
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Security/test_runtime_fixme_hotspots.py -v`
Expected: FAIL on unresolved runtime FIXME behaviors.

**Step 3: Write minimal implementation**

```python
# Wire deterministic app/test builders and endpoint fixtures.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Security/test_runtime_fixme_hotspots.py -v`
Expected: PASS for test scaffolding and baseline contracts.

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-02-runtime-fixme-hotspot-register.md tldw_Server_API/tests/Security/test_runtime_fixme_hotspots.py
git commit -m "test(security): add runtime hotspot contract tests"
```

### Task 2: Fix CORS and Startup Security Defaults

**Files:**
- Modify: `tldw_Server_API/app/main.py`
- Modify: `tldw_Server_API/app/core/config.py`
- Test: `tldw_Server_API/tests/Security/test_runtime_fixme_hotspots.py`
- Test: `tldw_Server_API/tests/Health/test_security_health_thresholds.py`

**Step 1: Write the failing test**

```python
def test_production_cors_requires_explicit_origin_list(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    with pytest.raises(ValueError):
        build_app_with_origins(["*"])
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Security/test_runtime_fixme_hotspots.py::test_production_cors_requires_explicit_origin_list -v`
Expected: FAIL while wildcard remains accepted.

**Step 3: Write minimal implementation**

```python
# Reject wildcard origins in production mode; require explicit allowlist.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Security/test_runtime_fixme_hotspots.py tldw_Server_API/tests/Health/test_security_health_thresholds.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/main.py tldw_Server_API/app/core/config.py tldw_Server_API/tests/Security/test_runtime_fixme_hotspots.py
git commit -m "fix(security): enforce production cors safety defaults"
```

### Task 3: Fix Config Placeholder/Default Hotspots in Runtime Paths

**Files:**
- Modify: `tldw_Server_API/app/core/config.py`
- Test: `tldw_Server_API/tests/Config/test_config_precedence_contract.py`
- Test: `tldw_Server_API/tests/TTS/test_kokoro_health_and_errors.py`

**Step 1: Write the failing test**

```python
def test_runtime_config_never_returns_placeholder_literals():
    cfg = load_runtime_config_for_test()
    serialized = str(cfg)
    assert "FIXME" not in serialized
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Config/test_config_precedence_contract.py::test_runtime_config_never_returns_placeholder_literals -v`
Expected: FAIL if placeholder fallback values exist.

**Step 3: Write minimal implementation**

```python
# Replace placeholder fallback values with validated safe defaults or explicit errors.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Config/test_config_precedence_contract.py tldw_Server_API/tests/TTS/test_kokoro_health_and_errors.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/config.py tldw_Server_API/tests/Config/test_config_precedence_contract.py
git commit -m "fix(config): remove runtime placeholder defaults in hot paths"
```

### Task 4: Fix Sync/Search Data Integrity FIXME Paths

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/sync.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Test: `tldw_Server_API/tests/Sync/test_sync_content_ingest.py`
- Test: `tldw_Server_API/tests/Media/test_media_search.py`

**Step 1: Write the failing test**

```python
def test_sync_write_updates_fts_index(client):
    create_media_via_sync(client, title="needle")
    search = client.get("/api/v1/media/search", params={"query": "needle"}).json()
    assert search["results"]
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Sync/test_sync_content_ingest.py::test_sync_write_updates_fts_index -v`
Expected: FAIL while FTS update remains disabled.

**Step 3: Write minimal implementation**

```python
# Re-enable and harden FTS update call path with rollback-safe behavior.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Sync/test_sync_content_ingest.py tldw_Server_API/tests/Media/test_media_search.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/sync.py tldw_Server_API/app/core/DB_Management/Media_DB_v2.py tldw_Server_API/tests/Sync/test_sync_content_ingest.py
git commit -m "fix(sync): restore fts update integrity path"
```
