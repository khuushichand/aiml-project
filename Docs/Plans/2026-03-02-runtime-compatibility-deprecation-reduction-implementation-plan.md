# Runtime Compatibility and Deprecation Reduction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce hidden behavior branches by retiring runtime compatibility shims and enforcing explicit deprecation windows.

**Architecture:** Create a deprecation registry that tracks compatibility paths and sunset dates, then migrate highest-risk runtime shims (web scraping fallback, chat/LLM legacy wrappers, auth compatibility helpers) behind controlled flags with removal tests.

**Tech Stack:** Python services, FastAPI endpoints, pytest, existing logging/deprecation utilities.

---

### Task 1: Build Compatibility Inventory and Contract Tests

**Files:**
- Create: `Docs/Plans/2026-03-02-runtime-compatibility-inventory.md`
- Create: `tldw_Server_API/tests/Services/test_compatibility_registry_contract.py`
- Reference: `tldw_Server_API/app/services/web_scraping_service.py`
- Reference: `tldw_Server_API/app/core/LLM_Calls/chat_calls.py`
- Reference: `tldw_Server_API/app/services/auth_service.py`

**Step 1: Write the failing test**

```python
def test_all_runtime_compat_paths_registered():
    registry = load_compat_registry()
    assert "web_scraping_legacy_fallback" in registry
    assert "llm_chat_legacy_session" in registry
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Services/test_compatibility_registry_contract.py -v`
Expected: FAIL until registry exists.

**Step 3: Write minimal implementation**

```python
COMPAT_PATHS = {
    "web_scraping_legacy_fallback": {"sunset": "2026-06-30"},
}
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Services/test_compatibility_registry_contract.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-02-runtime-compatibility-inventory.md tldw_Server_API/tests/Services/test_compatibility_registry_contract.py
git commit -m "test(compat): add runtime compatibility registry contracts"
```

### Task 2: Add Central Deprecation Registry and Telemetry

**Files:**
- Create: `tldw_Server_API/app/core/deprecations/runtime_registry.py`
- Create: `tldw_Server_API/app/core/deprecations/__init__.py`
- Modify: `tldw_Server_API/app/services/web_scraping_service.py`
- Modify: `tldw_Server_API/app/core/LLM_Calls/deprecation.py`
- Test: `tldw_Server_API/tests/Web_Scraping/test_enhanced_web_scraping.py`
- Test: `tldw_Server_API/tests/Chat/test_provider_config_shim_removed.py`

**Step 1: Write the failing test**

```python
def test_deprecation_registry_emits_once_per_request_cycle(caplog):
    log_runtime_deprecation("web_scraping_legacy_fallback")
    log_runtime_deprecation("web_scraping_legacy_fallback")
    assert sum("web_scraping_legacy_fallback" in r.message for r in caplog.records) == 1
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Services/test_compatibility_registry_contract.py::test_deprecation_registry_emits_once_per_request_cycle -v`
Expected: FAIL with missing runtime registry.

**Step 3: Write minimal implementation**

```python
# runtime_registry.py

def log_runtime_deprecation(key: str) -> None:
    ...
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Services/test_compatibility_registry_contract.py tldw_Server_API/tests/Chat/test_provider_config_shim_removed.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/deprecations/runtime_registry.py tldw_Server_API/app/core/deprecations/__init__.py tldw_Server_API/app/services/web_scraping_service.py tldw_Server_API/app/core/LLM_Calls/deprecation.py tldw_Server_API/tests/Services/test_compatibility_registry_contract.py
git commit -m "refactor(compat): centralize runtime deprecation registry"
```

### Task 3: Remove First Wave of Runtime Compatibility Paths

**Files:**
- Modify: `tldw_Server_API/app/services/web_scraping_service.py`
- Modify: `tldw_Server_API/app/services/auth_service.py`
- Modify: `tldw_Server_API/app/core/LLM_Calls/chat_calls.py`
- Modify: `tldw_Server_API/app/core/LLM_Calls/local_chat_calls.py`
- Test: `tldw_Server_API/tests/Web_Scraping/test_web_scraping_service_integration.py`
- Test: `tldw_Server_API/tests/LLM_Calls/test_adapter_registry_wrapper_migration.py`
- Test: `tldw_Server_API/tests/AuthNZ/unit/test_startup_integrity.py`

**Step 1: Write the failing test**

```python
def test_compat_path_disabled_returns_explicit_error_shape(client):
    response = client.post("/api/v1/research/websearch", json={"method": "legacy_only"})
    assert response.status_code in {400, 422}
    assert "deprecated" in response.text.lower()
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Web_Scraping/test_web_scraping_service_integration.py -v`
Expected: FAIL while legacy path silently executes.

**Step 3: Write minimal implementation**

```python
# Replace silent fallback with explicit deprecation error path gated by runtime flag.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Web_Scraping/test_web_scraping_service_integration.py tldw_Server_API/tests/LLM_Calls/test_adapter_registry_wrapper_migration.py tldw_Server_API/tests/AuthNZ/unit/test_startup_integrity.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/web_scraping_service.py tldw_Server_API/app/services/auth_service.py tldw_Server_API/app/core/LLM_Calls/chat_calls.py tldw_Server_API/app/core/LLM_Calls/local_chat_calls.py tldw_Server_API/tests/Web_Scraping/test_web_scraping_service_integration.py
git commit -m "refactor(compat): remove first-wave runtime legacy fallbacks"
```

### Task 4: Enforce No New Runtime Compatibility Debt

**Files:**
- Create: `tldw_Server_API/tests/lint/test_no_new_runtime_compat_markers.py`
- Modify: `.github/workflows/pre-commit.yml`

**Step 1: Write the failing test**

```python
def test_no_new_runtime_compatibility_markers():
    assert scan_for_new_compat_markers() == []
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/lint/test_no_new_runtime_compat_markers.py -v`
Expected: FAIL until baseline and scanner exist.

**Step 3: Write minimal implementation**

```python
# Add marker scanner with baseline allowlist committed to repo.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/lint/test_no_new_runtime_compat_markers.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/lint/test_no_new_runtime_compat_markers.py .github/workflows/pre-commit.yml
git commit -m "test(compat): block new runtime compatibility debt"
```
