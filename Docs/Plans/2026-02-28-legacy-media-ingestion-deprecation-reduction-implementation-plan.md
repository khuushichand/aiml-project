# Legacy Media Ingestion Deprecation Reduction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce media-ingestion legacy surface in one release cycle by moving remaining compatibility behavior behind explicit adapters, adding deprecation signals, and preserving endpoint contract parity.

**Architecture:** Keep `/api/v1/media/process-*` endpoints stable while extracting compatibility behavior into dedicated helpers and a canonical execution contract module. Add test gates that lock status codes/envelopes and prove legacy shims are adapter-only before removal in release N+1.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, pytest, loguru, existing media ingestion core libs, Bandit

---

## Preconditions

- Use a dedicated worktree/branch before implementation.
- Activate the project virtualenv before running tests: `source .venv/bin/activate`.
- Follow `@test-driven-development` for each task and `@verification-before-completion` before merge.

### Task 1: Add Media Deprecation Signaling Helper

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/media/deprecation_signals.py`
- Test: `tldw_Server_API/tests/Media_Ingestion_Modification/test_media_deprecation_signals.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.api.v1.endpoints.media.deprecation_signals import build_media_legacy_signal


def test_build_media_legacy_signal_includes_standard_headers():
    signal = build_media_legacy_signal(
        successor="/api/v1/media/process-videos",
        warning_code="legacy_compat_path",
    )
    assert signal.headers["Deprecation"] == "true"
    assert "Sunset" in signal.headers
    assert signal.payload["warning"] == "deprecated_endpoint"
    assert signal.payload["code"] == "legacy_compat_path"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_media_deprecation_signals.py::test_build_media_legacy_signal_includes_standard_headers -v`
Expected: FAIL because `deprecation_signals.py` does not exist.

**Step 3: Write minimal implementation**

```python
from dataclasses import dataclass

from tldw_Server_API.app.api.v1.utils.deprecation import build_deprecation_headers


@dataclass(frozen=True)
class MediaLegacySignal:
    headers: dict[str, str]
    payload: dict[str, str]


def build_media_legacy_signal(*, successor: str, warning_code: str) -> MediaLegacySignal:
    return MediaLegacySignal(
        headers=build_deprecation_headers(successor, default_sunset_days=90),
        payload={
            "warning": "deprecated_endpoint",
            "code": warning_code,
            "successor": successor,
        },
    )
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_media_deprecation_signals.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/media/deprecation_signals.py \
  tldw_Server_API/tests/Media_Ingestion_Modification/test_media_deprecation_signals.py
git commit -m "feat(media): add media ingestion deprecation signal helper"
```

### Task 2: Lock Contract Parity for Process Endpoints

**Files:**
- Create: `tldw_Server_API/tests/Media_Ingestion_Modification/test_process_endpoints_contract_parity.py`

**Step 1: Write the failing test**

```python
import pytest


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/v1/media/process-videos",
        "/api/v1/media/process-audios",
        "/api/v1/media/process-pdfs",
        "/api/v1/media/process-documents",
        "/api/v1/media/process-ebooks",
        "/api/v1/media/process-emails",
    ],
)
def test_process_endpoint_rejects_empty_inputs_with_known_contract(client_user_only, endpoint):
    resp = client_user_only.post(endpoint, data={})
    assert resp.status_code in {400, 422}
    body = resp.json()
    assert "detail" in body or "errors" in body
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_process_endpoints_contract_parity.py -v`
Expected: FAIL on at least one endpoint due unaligned baseline assumptions that must be codified endpoint-by-endpoint.

**Step 3: Write minimal implementation**

```python
# Replace generic assertions with endpoint-specific expected status/detail
# captured from current behavior to freeze baseline.
EXPECTED_EMPTY_INPUT_CONTRACT = {
    "/api/v1/media/process-videos": (400, "No valid media sources supplied."),
    "/api/v1/media/process-audios": (400, "No valid audio sources supplied"),
    "/api/v1/media/process-pdfs": (400, "No valid media sources supplied."),
    "/api/v1/media/process-documents": (400, "No valid media sources supplied."),
    "/api/v1/media/process-ebooks": (400, "At least one 'url'"),
    "/api/v1/media/process-emails": (400, "At least one EML file must be uploaded."),
}
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_process_endpoints_contract_parity.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Media_Ingestion_Modification/test_process_endpoints_contract_parity.py
git commit -m "test(media): lock process endpoint contract parity baseline"
```

### Task 3: Extract Canonical Input Contract Helpers

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/media/input_contracts.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/process_videos.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/process_audios.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/process_documents.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/process_pdfs.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/process_ebooks.py`
- Test: `tldw_Server_API/tests/Media_Ingestion_Modification/test_input_contracts.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.api.v1.endpoints.media.input_contracts import normalize_urls_field


def test_normalize_urls_field_handles_legacy_empty_list_sentinel():
    assert normalize_urls_field([""]) is None
    assert normalize_urls_field(["https://example.com"]) == ["https://example.com"]
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_input_contracts.py::test_normalize_urls_field_handles_legacy_empty_list_sentinel -v`
Expected: FAIL because `input_contracts.py` does not exist.

**Step 3: Write minimal implementation**

```python
from tldw_Server_API.app.api.v1.endpoints import media as media_mod


def normalize_urls_field(urls: list[str] | None) -> list[str] | None:
    if urls and urls == [""]:
        return None
    return urls


def validate_media_inputs(media_type: str, urls, files) -> None:
    media_mod._validate_inputs(media_type, urls, files)
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_input_contracts.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/media/input_contracts.py \
  tldw_Server_API/app/api/v1/endpoints/media/process_videos.py \
  tldw_Server_API/app/api/v1/endpoints/media/process_audios.py \
  tldw_Server_API/app/api/v1/endpoints/media/process_documents.py \
  tldw_Server_API/app/api/v1/endpoints/media/process_pdfs.py \
  tldw_Server_API/app/api/v1/endpoints/media/process_ebooks.py \
  tldw_Server_API/tests/Media_Ingestion_Modification/test_input_contracts.py
git commit -m "refactor(media): centralize process endpoint input contracts"
```

### Task 4: Add Explicit Compatibility Patch-Points Module

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/media/compat_patchpoints.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/process_documents.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/process_pdfs.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/process_ebooks.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/process_web_scraping.py`
- Test: `tldw_Server_API/tests/Media_Ingestion_Modification/test_media_compat_patchpoints.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.api.v1.endpoints.media.compat_patchpoints import get_download_url_async


def test_get_download_url_async_resolves_callable():
    fn = get_download_url_async()
    assert callable(fn)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_media_compat_patchpoints.py::test_get_download_url_async_resolves_callable -v`
Expected: FAIL because `compat_patchpoints.py` does not exist.

**Step 3: Write minimal implementation**

```python
from tldw_Server_API.app.api.v1.endpoints import media as media_mod
from tldw_Server_API.app.services.web_scraping_service import process_web_scraping_task


def get_download_url_async():
    return media_mod._download_url_async


def get_save_uploaded_files():
    return media_mod._save_uploaded_files


def get_process_web_scraping_task():
    return getattr(media_mod, "process_web_scraping_task", process_web_scraping_task)
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_media_compat_patchpoints.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/media/compat_patchpoints.py \
  tldw_Server_API/app/api/v1/endpoints/media/process_documents.py \
  tldw_Server_API/app/api/v1/endpoints/media/process_pdfs.py \
  tldw_Server_API/app/api/v1/endpoints/media/process_ebooks.py \
  tldw_Server_API/app/api/v1/endpoints/media/process_web_scraping.py \
  tldw_Server_API/tests/Media_Ingestion_Modification/test_media_compat_patchpoints.py
git commit -m "refactor(media): isolate compatibility patchpoints for process endpoints"
```

### Task 5: Emit Deprecation Signals When Legacy Compatibility Paths Are Used

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/process_videos.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/process_audios.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/process_documents.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/process_pdfs.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/process_ebooks.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/process_emails.py`
- Test: `tldw_Server_API/tests/Media_Ingestion_Modification/test_media_process_deprecation_headers.py`

**Step 1: Write the failing test**

```python
def test_process_videos_sets_deprecation_headers_for_legacy_urls_sentinel(client_user_only):
    resp = client_user_only.post("/api/v1/media/process-videos", data={"urls": ""})
    assert resp.headers.get("Deprecation") == "true"
    assert "Sunset" in resp.headers
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_media_process_deprecation_headers.py::test_process_videos_sets_deprecation_headers_for_legacy_urls_sentinel -v`
Expected: FAIL because endpoint does not add deprecation headers yet.

**Step 3: Write minimal implementation**

```python
# process_videos.py (pattern for each endpoint)
legacy_compat_used = bool(form_data.urls and form_data.urls == [""])
...
response = JSONResponse(status_code=final_status_code, content=batch_result)
if legacy_compat_used:
    signal = build_media_legacy_signal(
        successor="/api/v1/media/process-videos",
        warning_code="legacy_urls_empty_sentinel",
    )
    response.headers.update(signal.headers)
return response
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_media_process_deprecation_headers.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/media/process_videos.py \
  tldw_Server_API/app/api/v1/endpoints/media/process_audios.py \
  tldw_Server_API/app/api/v1/endpoints/media/process_documents.py \
  tldw_Server_API/app/api/v1/endpoints/media/process_pdfs.py \
  tldw_Server_API/app/api/v1/endpoints/media/process_ebooks.py \
  tldw_Server_API/app/api/v1/endpoints/media/process_emails.py \
  tldw_Server_API/tests/Media_Ingestion_Modification/test_media_process_deprecation_headers.py
git commit -m "feat(media): emit deprecation headers for legacy compatibility paths"
```

### Task 6: Convert Legacy Media Shim to Explicit Adapter-Only Contract

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/__init__.py`
- Test: `tldw_Server_API/tests/Media_Ingestion_Modification/test_media_shim_contract.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.api.v1.endpoints import media


def test_legacy_media_shim_exposes_adapter_only_markers():
    assert hasattr(media, "_legacy_media")
    assert getattr(media, "LEGACY_MEDIA_SHIM_MODE", "") == "adapter_only"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_media_shim_contract.py::test_legacy_media_shim_exposes_adapter_only_markers -v`
Expected: FAIL because marker is not defined.

**Step 3: Write minimal implementation**

```python
# media/__init__.py
LEGACY_MEDIA_SHIM_MODE = "adapter_only"
_legacy_media = None
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_media_shim_contract.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/media/__init__.py \
  tldw_Server_API/tests/Media_Ingestion_Modification/test_media_shim_contract.py
git commit -m "chore(media): mark legacy media shim as adapter-only"
```

### Task 7: Update Documentation and Changelog for the One-Release Window

**Files:**
- Modify: `Docs/Published/Code_Documentation/Ingestion_Media_Processing.md`
- Modify: `Docs/Published/API-related/Email_Processing_API.md`
- Modify: `Docs/Published/User_Guides/Server/Web_Scraping_Ingestion_Guide.md`
- Modify: `CHANGELOG.md`

**Step 1: Write the failing doc check test**

```python
from pathlib import Path


def test_media_deprecation_window_documented():
    doc = Path("Docs/Published/Code_Documentation/Ingestion_Media_Processing.md").read_text(encoding="utf-8")
    assert "one-release compatibility window" in doc
    assert "Deprecation" in doc
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_media_docs_contract.py::test_media_deprecation_window_documented -v`
Expected: FAIL because the exact compatibility-window language is not present.

**Step 3: Write minimal implementation**

```markdown
## Deprecation Window (Media Processing)
- Release N: compatibility shims retained; deprecation headers may be emitted when legacy compatibility input forms are used.
- Release N+1: compatibility shims removed after parity tests and telemetry gates pass.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_media_docs_contract.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add Docs/Published/Code_Documentation/Ingestion_Media_Processing.md \
  Docs/Published/API-related/Email_Processing_API.md \
  Docs/Published/User_Guides/Server/Web_Scraping_Ingestion_Guide.md \
  CHANGELOG.md \
  tldw_Server_API/tests/Media_Ingestion_Modification/test_media_docs_contract.py
git commit -m "docs(media): document one-release deprecation window and migration signals"
```

### Task 8: Verification, Security, and Cleanup Gate

**Files:**
- Modify as needed from prior tasks only.

**Step 1: Run targeted media test suites**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_media_processing.py tldw_Server_API/tests/Media_Ingestion_Modification/test_process_endpoints_contract_parity.py tldw_Server_API/tests/Media_Ingestion_Modification/test_media_process_deprecation_headers.py -v`
Expected: PASS

**Step 2: Run related web scraping/email integration tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Web_Scraping/test_process_web_scraping_strategy_validation.py tldw_Server_API/tests/Media_Ingestion_Modification/test_process_emails_endpoint.py -v`
Expected: PASS

**Step 3: Run Bandit on touched scope**

Run: `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/media tldw_Server_API/app/api/v1/utils/deprecation.py -f json -o /tmp/bandit_media_deprecation_reduction.json`
Expected: Bandit completes; no new high-severity findings in changed code.

**Step 4: Run focused lint/static checks (if configured)**

Run: `source .venv/bin/activate && python -m pytest -m "unit" tldw_Server_API/tests/Media_Ingestion_Modification -q`
Expected: PASS

**Step 5: Commit verification artifacts and final code**

```bash
git add -A
git commit -m "chore(media): finalize legacy deprecation reduction wave 1 with parity gates"
```

