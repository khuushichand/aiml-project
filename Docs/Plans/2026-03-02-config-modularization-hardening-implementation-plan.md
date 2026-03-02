# Config Modularization and Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split `core/config.py` into focused modules with stable typed accessors so configuration changes stop causing cross-domain regressions.

**Architecture:** Introduce a config package with domain loaders (`auth`, `rag`, `audio`, `providers`) and a compatibility facade that keeps existing callsites functional during migration. Lock behavior with config precedence tests before moving code.

**Tech Stack:** Python dataclasses/Pydantic models, pytest, existing env/config parser logic.

---

### Task 1: Lock Current Config Precedence

**Files:**
- Create: `tldw_Server_API/tests/Config/test_config_precedence_contract.py`
- Reference: `tldw_Server_API/app/core/config.py`

**Step 1: Write the failing tests**

```python
def test_env_overrides_config_file_for_auth_mode(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    cfg = load_settings_for_test()
    assert cfg.auth_mode == "multi_user"


def test_missing_tts_defaults_never_emit_fixme_literal(cfg):
    assert "FIXME" not in str(cfg)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Config/test_config_precedence_contract.py -v`
Expected: FAIL until test harness and assertions are wired.

**Step 3: Write minimal implementation**

```python
# Add helper to construct config deterministically in tests.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Config/test_config_precedence_contract.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Config/test_config_precedence_contract.py
git commit -m "test(config): add precedence and default safety contracts"
```

### Task 2: Create Modular Config Package

**Files:**
- Create: `tldw_Server_API/app/core/config_sections/__init__.py`
- Create: `tldw_Server_API/app/core/config_sections/auth.py`
- Create: `tldw_Server_API/app/core/config_sections/rag.py`
- Create: `tldw_Server_API/app/core/config_sections/audio.py`
- Create: `tldw_Server_API/app/core/config_sections/providers.py`
- Modify: `tldw_Server_API/app/core/config.py`
- Test: `tldw_Server_API/tests/Config/test_config_precedence_contract.py`

**Step 1: Write the failing test**

```python
def test_section_loaders_return_typed_models():
    sections = load_all_sections_for_test()
    assert hasattr(sections, "auth")
    assert hasattr(sections, "rag")
    assert hasattr(sections, "audio")
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Config/test_config_precedence_contract.py::test_section_loaders_return_typed_models -v`
Expected: FAIL because modular package is missing.

**Step 3: Write minimal implementation**

```python
# auth.py / rag.py / audio.py
@dataclass
class AuthConfig:
    mode: str
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Config/test_config_precedence_contract.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/config_sections/__init__.py tldw_Server_API/app/core/config_sections/auth.py tldw_Server_API/app/core/config_sections/rag.py tldw_Server_API/app/core/config_sections/audio.py tldw_Server_API/app/core/config_sections/providers.py tldw_Server_API/app/core/config.py tldw_Server_API/tests/Config/test_config_precedence_contract.py
git commit -m "refactor(config): introduce modular config section loaders"
```

### Task 3: Add Backward-Compatible Facade and Migrate Call Sites

**Files:**
- Modify: `tldw_Server_API/app/core/config.py`
- Modify: `tldw_Server_API/app/main.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/config.py`
- Test: `tldw_Server_API/tests/Config/test_effective_config_api.py`
- Test: `tldw_Server_API/tests/Config/test_config_adapter.py`

**Step 1: Write the failing test**

```python
def test_legacy_config_accessors_still_resolve_values():
    assert legacy_get("AUTH_MODE") in {"single_user", "multi_user"}
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Config/test_config_adapter.py -v`
Expected: FAIL for legacy accessors after modular split.

**Step 3: Write minimal implementation**

```python
# config.py

def legacy_get(key: str):
    return NEW_CONFIG_FACADE.get(key)
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Config/test_config_adapter.py tldw_Server_API/tests/Config/test_effective_config_api.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/config.py tldw_Server_API/app/main.py tldw_Server_API/app/api/v1/endpoints/config.py tldw_Server_API/tests/Config/test_config_adapter.py
git commit -m "refactor(config): add compatibility facade over modular settings"
```

### Task 4: Remove High-Risk Placeholder Defaults and Document Migration

**Files:**
- Modify: `tldw_Server_API/app/core/config.py`
- Modify: `Docs/Operations/Env_Vars.md`
- Create: `Docs/Plans/2026-03-02-config-modularization-migration-notes.md`
- Test: `tldw_Server_API/tests/Config/test_local_api_and_custom_openai2_config_keys.py`

**Step 1: Write the failing test**

```python
def test_tts_defaults_are_valid_values_not_placeholders():
    cfg = load_settings_for_test()
    assert cfg.tts.default_voice
    assert cfg.tts.default_model
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Config/test_config_precedence_contract.py::test_missing_tts_defaults_never_emit_fixme_literal -v`
Expected: FAIL if placeholders still leak.

**Step 3: Write minimal implementation**

```python
# Replace placeholder fallback='FIXME' with safe provider-specific defaults.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Config/test_config_precedence_contract.py tldw_Server_API/tests/Config/test_local_api_and_custom_openai2_config_keys.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/config.py Docs/Operations/Env_Vars.md Docs/Plans/2026-03-02-config-modularization-migration-notes.md tldw_Server_API/tests/Config/test_config_precedence_contract.py
git commit -m "fix(config): remove placeholder defaults and document migration"
```
