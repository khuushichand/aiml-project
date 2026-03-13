# MinerU PDF OCR Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add MinerU as a PDF-only, document-level OCR backend behind `ocr_backend=mineru`, with capability discovery, normalized structured output, evaluator support, and documentation.

**Architecture:** Keep the public OCR API unchanged, but add a MinerU-specific document adapter that runs once per PDF and returns a bounded, versioned structured payload. Wire that adapter into the PDF pipeline as an explicit `mineru` branch, surface MinerU in OCR discovery as a `pdf_only` opt-in capability, and teach OCR evaluation to read per-page text from the normalized MinerU payload instead of requiring direct page-image OCR.

**Tech Stack:** Python, FastAPI, PyMuPDF, subprocess, pathlib, JSON, loguru, pytest

---

### Task 1: Add MinerU Capability Discovery

**Files:**
- Create: `tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_discovery.py`
- Create: `tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/mineru_adapter.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/ocr.py:25-152`

**Step 1: Write the failing test**

```python
def test_list_ocr_backends_includes_mineru_capabilities(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import ocr as ocr_mod

    monkeypatch.setattr(
        ocr_mod,
        "_describe_mineru_backend",
        lambda: {
            "available": True,
            "pdf_only": True,
            "document_level": True,
            "opt_in_only": True,
            "supports_per_page_metrics": True,
            "mode": "cli",
        },
    )

    payload = ocr_mod.list_ocr_backends()

    assert payload["mineru"]["available"] is True
    assert payload["mineru"]["pdf_only"] is True
    assert payload["mineru"]["document_level"] is True
    assert payload["mineru"]["opt_in_only"] is True
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_discovery.py -v
```

Expected: FAIL because `_describe_mineru_backend` does not exist and `/ocr/backends` does not include `mineru`.

**Step 3: Write minimal implementation**

Add a small capability helper in `mineru_adapter.py`:

```python
def describe_mineru_backend() -> dict[str, Any]:
    return {
        "available": _mineru_available(),
        "pdf_only": True,
        "document_level": True,
        "opt_in_only": True,
        "supports_per_page_metrics": True,
        "mode": "cli",
    }
```

In `ocr.py`, import it lazily and merge it into `list_ocr_backends()` as:

```python
def _describe_mineru_backend() -> dict[str, Any]:
    from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.mineru_adapter import (
        describe_mineru_backend,
    )
    return describe_mineru_backend()
```

Then:

```python
out["mineru"] = _describe_mineru_backend()
```

Do not add MinerU to the generic OCR registry in this task.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_discovery.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_discovery.py tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/mineru_adapter.py tldw_Server_API/app/api/v1/endpoints/ocr.py
git commit -m "feat: surface MinerU OCR capabilities"
```

### Task 2: Implement MinerU CLI Adapter And Normalization

**Files:**
- Modify: `tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/mineru_adapter.py`
- Create: `tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_adapter.py`

**Step 1: Write the failing tests**

```python
def test_normalize_mineru_output_returns_versioned_bounded_payload(tmp_path):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.mineru_adapter import (
        _normalize_mineru_output_dir,
    )

    out_dir = tmp_path / "mineru-out"
    out_dir.mkdir()
    (out_dir / "document.md").write_text("# Title\n\n|A|B|\n|-|-|\n|1|2|\n", encoding="utf-8")
    (out_dir / "content_list.json").write_text('[{"page_idx": 0, "text": "page one"}]', encoding="utf-8")
    (out_dir / "middle.json").write_text('{"tables": [{"page": 1, "html": "<table></table>"}]}', encoding="utf-8")

    result = _normalize_mineru_output_dir(out_dir, output_format="markdown", prompt_preset="table")

    assert result["structured"]["schema_version"] == 1
    assert result["structured"]["format"] == "markdown"
    assert result["structured"]["pages"][0]["page"] == 1
    assert result["structured"]["tables"][0]["format"] == "html"
    assert "content_list_excerpt" in result["structured"]["artifacts"]
```

```python
def test_build_mineru_command_returns_argv_tokens(monkeypatch, tmp_path):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.mineru_adapter import (
        _build_mineru_command,
    )

    monkeypatch.setenv("MINERU_CMD", "mineru")
    cmd = _build_mineru_command(pdf_path=tmp_path / "sample.pdf", output_dir=tmp_path / "out")

    assert isinstance(cmd, list)
    assert all(isinstance(part, str) for part in cmd)
    assert "sample.pdf" in " ".join(cmd)
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_adapter.py -v
```

Expected: FAIL because adapter helpers are incomplete or missing.

**Step 3: Write minimal implementation**

Implement:

```python
def _build_mineru_command(*, pdf_path: Path, output_dir: Path) -> list[str]:
    base = shlex.split(os.getenv("MINERU_CMD", "mineru"))
    return [*base, "-p", str(pdf_path), "-o", str(output_dir)]
```

```python
def _normalize_mineru_output_dir(output_dir: Path, *, output_format: str | None, prompt_preset: str | None) -> dict[str, Any]:
    markdown_text = _read_first_existing(output_dir, ["document.md", "output.md", "result.md"])
    content_list = _read_json_if_exists(output_dir / "content_list.json")
    middle = _read_json_if_exists(output_dir / "middle.json")
    pages = _pages_from_content_list(content_list)
    tables = _tables_from_middle(middle)
    structured = {
        "schema_version": 1,
        "text": markdown_text,
        "format": "markdown",
        "pages": pages,
        "tables": tables,
        "artifacts": {
            "content_list_excerpt": content_list[:10] if isinstance(content_list, list) else [],
            "middle_json_excerpt": _bounded_middle_excerpt(middle),
        },
        "meta": {
            "backend": "mineru",
            "mode": "cli",
            "supports_per_page_metrics": bool(pages),
            "prompt_preset": prompt_preset,
            "requested_output_format": output_format,
        },
    }
    return {"text": _coerce_text_output(markdown_text, output_format), "structured": structured}
```

Also add:

- timeout-aware subprocess execution
- temp output cleanup
- no shell invocation
- bounded raw artifact behavior behind `MINERU_DEBUG_SAVE_RAW`

**Step 4: Run tests to verify they pass**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_adapter.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/mineru_adapter.py tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_adapter.py
git commit -m "feat: add MinerU CLI adapter and normalization"
```

### Task 3: Wire MinerU Into The PDF Pipeline

**Files:**
- Modify: `tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/PDF_Processing_Lib.py:658-754`
- Modify: `tldw_Server_API/tests/Media_Ingestion_Modification/test_ocr_structured_output.py`
- Create: `tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_pdf_pipeline.py`

**Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_process_pdf_uses_mineru_document_adapter_for_always(monkeypatch):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF import PDF_Processing_Lib as pdf_lib

    monkeypatch.setattr(pdf_lib, "pymupdf4llm_parse_pdf", lambda path: "parser text")
    monkeypatch.setattr(
        pdf_lib,
        "_run_mineru_document_ocr",
        lambda **kwargs: {
            "text": "# MinerU Markdown",
            "structured": {
                "schema_version": 1,
                "format": "markdown",
                "text": "# MinerU Markdown",
                "pages": [{"page": 1, "text": "MinerU page"}],
                "tables": [],
                "artifacts": {},
                "meta": {"backend": "mineru", "supports_per_page_metrics": True},
            },
            "details": {"backend": "mineru", "mode": "always"},
            "warnings": [],
        },
    )

    res = await pdf_lib.process_pdf_task(
        file_bytes=_build_minimal_pdf_bytes(),
        filename="mineru.pdf",
        parser="pymupdf4llm",
        perform_chunking=False,
        perform_analysis=False,
        enable_ocr=True,
        ocr_backend="mineru",
        ocr_mode="always",
    )

    assert res["content"] == "# MinerU Markdown"
    assert res["analysis_details"]["ocr"]["backend"] == "mineru"
    assert res["analysis_details"]["ocr"]["structured"]["schema_version"] == 1
```

```python
@pytest.mark.asyncio
async def test_process_pdf_mineru_fallback_preserves_parser_text_on_failure(monkeypatch):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF import PDF_Processing_Lib as pdf_lib

    monkeypatch.setattr(pdf_lib, "pymupdf4llm_parse_pdf", lambda path: "parser text")
    monkeypatch.setattr(pdf_lib, "_run_mineru_document_ocr", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    res = await pdf_lib.process_pdf_task(
        file_bytes=_build_minimal_pdf_bytes(),
        filename="mineru.pdf",
        parser="pymupdf4llm",
        perform_chunking=False,
        perform_analysis=False,
        enable_ocr=True,
        ocr_backend="mineru",
        ocr_mode="fallback",
        ocr_min_page_text_chars=9999,
    )

    assert res["content"] == "parser text"
    assert any("MinerU" in warning or "OCR error" in warning for warning in res["warnings"])
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_pdf_pipeline.py tldw_Server_API/tests/Media_Ingestion_Modification/test_ocr_structured_output.py -v
```

Expected: FAIL because `process_pdf_task` still routes all OCR through `_get_ocr_backend(...)` and `_ocr_pdf_pages(...)`.

**Step 3: Write minimal implementation**

In `PDF_Processing_Lib.py`, add an explicit branch before `_get_ocr_backend(...)`:

```python
if should_ocr and (ocr_backend or "").strip().lower() == "mineru":
    mineru_result = _run_mineru_document_ocr(
        pdf_path=Path(path_for_processing),
        output_format=ocr_output_format,
        prompt_preset=ocr_prompt_preset,
        requested_lang=ocr_lang,
        requested_dpi=ocr_dpi,
    )
    result.setdefault("analysis_details", {})
    result["analysis_details"]["ocr"] = mineru_result["details"]
    result["analysis_details"]["ocr"]["structured"] = mineru_result["structured"]
    result["warnings"].extend(mineru_result.get("warnings") or [])
    if mineru_result["text"].strip():
        result["content"] = mineru_result["text"]
        result["parser_used"] = f"{result['parser_used']}+mineru"
```

Also:

- record warnings when `ocr_lang` and `ocr_dpi` are ignored
- do not append parser text plus MinerU text by default
- keep current non-MinerU OCR flow unchanged

**Step 4: Run tests to verify they pass**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_pdf_pipeline.py tldw_Server_API/tests/Media_Ingestion_Modification/test_ocr_structured_output.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/PDF_Processing_Lib.py tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_pdf_pipeline.py tldw_Server_API/tests/Media_Ingestion_Modification/test_ocr_structured_output.py
git commit -m "feat: route PDF OCR through MinerU adapter"
```

### Task 4: Teach OCR Evaluation To Read MinerU Structured Pages

**Files:**
- Create: `tldw_Server_API/tests/Evaluations/test_mineru_ocr_evaluator.py`
- Modify: `tldw_Server_API/app/core/Evaluations/ocr_evaluator.py:141-310`

**Step 1: Write the failing tests**

```python
def test_ocr_evaluator_uses_mineru_structured_pages_for_per_page_metrics(monkeypatch):
    from tldw_Server_API.app.core.Evaluations.ocr_evaluator import OCREvaluator

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib.process_pdf",
        lambda **kwargs: {
            "content": "page one\npage two",
            "analysis_details": {
                "ocr": {
                    "backend": "mineru",
                    "total_pages": 2,
                    "ocr_pages": 2,
                    "structured": {
                        "schema_version": 1,
                        "pages": [
                            {"page": 1, "text": "page one"},
                            {"page": 2, "text": "page two"},
                        ],
                        "meta": {"supports_per_page_metrics": True},
                    },
                }
            },
        },
    )

    evaluator = OCREvaluator()
    result = evaluator.evaluate_ocr(
        items=[{
            "id": "mineru-doc",
            "pdf_bytes": b"%PDF-1.4",
            "ground_truth_text": "page one page two",
            "ground_truth_pages": ["page one", "page two"],
        }],
        ocr_options={"ocr_backend": "mineru"},
    )

    assert result["results"][0]["per_page_metrics"][0]["page"] == 1
    assert result["results"][0]["page_coverage"] == 1.0
```

```python
def test_ocr_evaluator_warns_when_mineru_has_no_page_slices(monkeypatch):
    ...
    assert result["results"][0]["page_coverage"] is None or result["results"][0]["ocr_details"]["supports_per_page_metrics"] is False
```

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Evaluations/test_mineru_ocr_evaluator.py -v
```

Expected: FAIL because the evaluator only knows how to derive per-page text from direct OCR backend calls.

**Step 3: Write minimal implementation**

In `ocr_evaluator.py`, add an explicit MinerU branch before direct backend use:

```python
if (ocr_options or {}).get("ocr_backend") == "mineru":
    out = process_pdf(...)
    hyp_text = (out or {}).get("content") or ""
    ocr_details = (out or {}).get("analysis_details", {}).get("ocr") or {}
    structured = ocr_details.get("structured") or {}
    pages = structured.get("pages") if isinstance(structured, dict) else None
    if isinstance(pages, list):
        page_texts = [str(page.get("text") or "") for page in pages if isinstance(page, dict)]
    else:
        ocr_details["supports_per_page_metrics"] = False
        ocr_details.setdefault("warnings", []).append("MinerU output did not include page slices")
    ocr_info.update(ocr_details)
```

Keep the existing direct page-image OCR path for other backends unchanged.

**Step 4: Run tests to verify they pass**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Evaluations/test_mineru_ocr_evaluator.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Evaluations/test_mineru_ocr_evaluator.py tldw_Server_API/app/core/Evaluations/ocr_evaluator.py
git commit -m "feat: support MinerU structured OCR evaluation"
```

### Task 5: Add Config Contract, Docs, And Final Verification

**Files:**
- Create: `tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_config_contract.py`
- Modify: `tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/mineru_adapter.py`
- Modify: `Docs/OCR/OCR_Providers.md`
- Modify: `Docs/API-related/OCR_API_Documentation.md`
- Modify: `Docs/Operations/Env_Vars.md`

**Step 1: Write the failing test**

```python
def test_describe_mineru_backend_reports_configured_mode(monkeypatch):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.mineru_adapter import (
        describe_mineru_backend,
    )

    monkeypatch.setenv("MINERU_CMD", "mineru")
    monkeypatch.setenv("MINERU_TIMEOUT_SEC", "45")
    monkeypatch.setenv("MINERU_MAX_CONCURRENCY", "2")

    info = describe_mineru_backend()

    assert info["mode"] == "cli"
    assert info["pdf_only"] is True
    assert info["opt_in_only"] is True
    assert info["timeout_sec"] == 45
    assert info["max_concurrency"] == 2
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_config_contract.py -v
```

Expected: FAIL because config metadata is incomplete.

**Step 3: Write minimal implementation**

Extend `describe_mineru_backend()` to report:

```python
{
    "available": ...,
    "pdf_only": True,
    "document_level": True,
    "opt_in_only": True,
    "supports_per_page_metrics": True,
    "mode": "cli",
    "timeout_sec": _get_timeout(),
    "max_concurrency": _get_max_concurrency(),
}
```

Update docs to cover:

- `ocr_backend=mineru`
- PDF-only/document-level behavior
- exclusion from `auto`
- `ocr_lang` and `ocr_dpi` being advisory/ignored
- new env vars:
  - `MINERU_CMD`
  - `MINERU_TIMEOUT_SEC`
  - `MINERU_MAX_CONCURRENCY`
  - `MINERU_TMP_ROOT`
  - `MINERU_DEBUG_SAVE_RAW`

**Step 4: Run tests and security verification**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_discovery.py tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_adapter.py tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_pdf_pipeline.py tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_config_contract.py tldw_Server_API/tests/Evaluations/test_mineru_ocr_evaluator.py tldw_Server_API/tests/Media_Ingestion_Modification/test_ocr_structured_output.py -v
```

Expected: PASS

Run:

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/mineru_adapter.py tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/PDF_Processing_Lib.py tldw_Server_API/app/api/v1/endpoints/ocr.py tldw_Server_API/app/core/Evaluations/ocr_evaluator.py -f json -o /tmp/bandit_mineru_pdf_ocr.json
```

Expected: exit code `0` and `/tmp/bandit_mineru_pdf_ocr.json` written with no new high-confidence issues in touched code.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Media_Ingestion_Modification/test_mineru_config_contract.py tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/mineru_adapter.py Docs/OCR/OCR_Providers.md Docs/API-related/OCR_API_Documentation.md Docs/Operations/Env_Vars.md
git commit -m "docs: document MinerU PDF OCR integration"
```
