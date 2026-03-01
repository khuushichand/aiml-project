# PDF ETL Paragraph Reflow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add ingest-time, paragraph-safe PDF text normalization so newly ingested PDFs store flowed text without breaking structural markdown blocks.

**Architecture:** Implement a shared normalizer in the PDF ingestion library and run it once on final extracted content (after parser extraction and OCR merge, before chunking/analysis/persistence). Use structure-aware block detection so single-line wraps are reflowed only inside paragraph blocks. Fail soft on normalization errors and keep existing extraction output when fallback occurs.

**Tech Stack:** Python, FastAPI service modules, PyMuPDF/pymupdf4llm/docling parsing path, pytest.

---

### Task 1: Add Failing Unit Tests For Paragraph-Safe Normalization

**Files:**
- Create: `tldw_Server_API/tests/Media/test_pdf_text_normalization.py`
- Reference: `tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/PDF_Processing_Lib.py`

**Step 1: Write the failing tests**

```python
from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib import (
    normalize_pdf_text_for_storage,
)


def test_reflows_soft_wrapped_paragraph_lines():
    src = (
        "We are not just interested in models that perform well on a\n"
        "single physical task, but rather models that robustly generalize.\n\n"
        "Therefore, we test generalization."
    )
    out = normalize_pdf_text_for_storage(src)
    assert "perform well on a single physical task" in out
    assert "\n\nTherefore, we test generalization." in out


def test_preserves_structural_blocks():
    src = (
        "## Page 1\n\n"
        "# Heading\n"
        "- list item one\n"
        "- list item two\n\n"
        "| a | b |\n"
        "|---|---|\n"
        "| 1 | 2 |\n\n"
        "Paragraph line one\n"
        "line two\n\n"
        "---\n"
    )
    out = normalize_pdf_text_for_storage(src)
    assert "# Heading" in out
    assert "- list item one" in out
    assert "| a | b |" in out
    assert "Paragraph line one line two" in out
    assert "## Page 1" in out
    assert "\n---\n" in f"\n{out}\n"


def test_repairs_hyphenated_soft_wraps():
    src = "generaliza-\ntion improves.\n\nnon-\nLinear stays separated."
    out = normalize_pdf_text_for_storage(src)
    assert "generalization improves." in out
    assert "non- Linear" in out


def test_idempotent_normalization():
    src = "Line one\nline two\n\n# Keep heading\n"
    first = normalize_pdf_text_for_storage(src)
    second = normalize_pdf_text_for_storage(first)
    assert first == second
```

**Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media/test_pdf_text_normalization.py -v
```

Expected: FAIL with import/function-not-found errors.

**Step 3: Commit failing tests**

```bash
git add tldw_Server_API/tests/Media/test_pdf_text_normalization.py
git commit -m "test(pdf): add failing tests for paragraph-safe text normalization"
```

---

### Task 2: Implement The Normalization Helper (Minimal Green)

**Files:**
- Modify: `tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/PDF_Processing_Lib.py`
- Test: `tldw_Server_API/tests/Media/test_pdf_text_normalization.py`

**Step 1: Add minimal implementation**

```python
def normalize_pdf_text_for_storage(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text if isinstance(text, str) else ""
    # 1) Normalize newlines
    # 2) Parse into structural vs paragraph blocks
    # 3) Reflow paragraph blocks only
    # 4) Preserve one blank line between blocks
    # 5) Return normalized text
```

Add private helpers for:
- Structural line detection (headings/lists/quotes/code fences/table-ish rows/page markers/separators).
- Paragraph block reflow.
- Hyphenated wrap join rule (lowercase-start next token only).

**Step 2: Run tests**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media/test_pdf_text_normalization.py -v
```

Expected: PASS for new unit tests.

**Step 3: Commit**

```bash
git add tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/PDF_Processing_Lib.py tldw_Server_API/tests/Media/test_pdf_text_normalization.py
git commit -m "feat(pdf): add paragraph-safe text normalizer for ingest storage"
```

---

### Task 3: Integrate Normalizer Into `process_pdf` For All Parsers

**Files:**
- Modify: `tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/PDF_Processing_Lib.py`
- Reference: `tldw_Server_API/app/core/Ingestion_Media_Processing/persistence.py`

**Step 1: Add integration point**

Apply normalization to final content after parser extraction and OCR merge logic settles `result["content"]`.

Example integration pattern:

```python
final_content = result.get("content")
if isinstance(final_content, str) and final_content.strip():
    try:
        normalized = normalize_pdf_text_for_storage(final_content)
        result["content"] = normalized
        result.setdefault("analysis_details", {})["text_normalization"] = {
            "applied": True,
            "chars_before": len(final_content),
            "chars_after": len(normalized),
            "mode": "paragraph_safe",
        }
    except Exception as norm_err:
        logging.warning(f"PDF text normalization failed for {filename}: {norm_err}")
        result.setdefault("warnings", []).append(f"Text normalization failed: {norm_err}")
```

**Step 2: Run current PDF tests**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media/test_process_code_and_uploads.py -k pdf -v
```

Expected: PASS without parser-specific regressions.

**Step 3: Commit**

```bash
git add tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/PDF_Processing_Lib.py
git commit -m "feat(pdf): normalize final extracted content before chunking"
```

---

### Task 4: Add Integration Tests Across Parser Paths

**Files:**
- Modify: `tldw_Server_API/tests/Media/test_process_code_and_uploads.py`
- Optionally create: `tldw_Server_API/tests/Media/test_pdf_processing_normalization_integration.py`

**Step 1: Add parser-path tests**

Add tests that monkeypatch each parser function:
- `pymupdf4llm_parse_pdf`
- `extract_text_and_format_from_pdf`
- `docling_parse_pdf`

Each returns soft-wrapped paragraph text and asserts `process_pdf_task(..., parser=<name>)` returns flowed content in `out["content"]`.

**Step 2: Add OCR-final-content normalization test**

Monkeypatch OCR path to append wrapped lines and assert resulting final `content` is normalized.

**Step 3: Run integration tests**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media/test_process_code_and_uploads.py -k "pdf and normalization" -v
```

Expected: PASS for new coverage.

**Step 4: Commit**

```bash
git add tldw_Server_API/tests/Media/test_process_code_and_uploads.py
git commit -m "test(pdf): cover normalization across parser and OCR paths"
```

---

### Task 5: Documentation Update For Ingest Canonicalization

**Files:**
- Modify: `Docs/Code_Documentation/Ingestion_Pipeline_PDF.md`
- Modify: `Docs/Published/Code_Documentation/Ingestion_Pipeline_PDF.md`

**Step 1: Update docs**

Add a section:
- “Ingest-time text normalization (paragraph-safe)”
- Clarify canonical stored text behavior for newly ingested PDFs.
- Clarify this does not backfill existing rows.

**Step 2: Verify docs are consistent**

Run:
```bash
rg -n "Ingest-time text normalization|paragraph-safe|newly ingested" Docs/Code_Documentation/Ingestion_Pipeline_PDF.md Docs/Published/Code_Documentation/Ingestion_Pipeline_PDF.md
```

Expected: matching section present in both files.

**Step 3: Commit**

```bash
git add Docs/Code_Documentation/Ingestion_Pipeline_PDF.md Docs/Published/Code_Documentation/Ingestion_Pipeline_PDF.md
git commit -m "docs(pdf): document paragraph-safe ingest normalization behavior"
```

---

### Task 6: Final Verification And Security Gate

**Files:**
- Verify touched files only.

**Step 1: Run focused pytest**

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media/test_pdf_text_normalization.py tldw_Server_API/tests/Media/test_process_code_and_uploads.py -k pdf -v
```

Expected: PASS.

**Step 2: Run Bandit on touched scope**

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Ingestion_Media_Processing/PDF tldw_Server_API/tests/Media -f json -o /tmp/bandit_pdf_etl_paragraph_reflow.json
```

Expected: no new high-confidence/high-severity findings introduced by changed code.

**Step 3: Final commit (if needed)**

```bash
git add <any remaining touched files>
git commit -m "chore(pdf): finalize verification for paragraph-safe ingest normalization"
```

---

## Implementation Notes
1. Keep solution DRY and YAGNI: centralize normalization in one helper.
2. Preserve current API response shape; no contract changes required.
3. Use `@test-driven-development` and `@verification-before-completion` during execution.
4. If three implementation attempts fail on one defect, stop and reassess per team guideline.

