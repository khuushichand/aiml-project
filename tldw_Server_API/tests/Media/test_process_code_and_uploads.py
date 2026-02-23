import os
import io
import json
import pytest
from fastapi import UploadFile


pytestmark = pytest.mark.unit


def test_process_code_js_lines(client_with_single_user):


    client, _ = client_with_single_user
    code = b"console.log('hi');\nconsole.log('bye');\n"
    files = [("files", ("script.js", code, "application/javascript"))]
    data = {
        "perform_chunking": "true",
        "chunk_method": "lines",
        "chunk_size": "1",
        "chunk_overlap": "0",
    }
    r = client.post("/api/v1/media/process-code", files=files, data=data)
    assert r.status_code in (200, 207), r.text
    payload = r.json()
    assert payload.get("results"), payload
    res0 = payload["results"][0]
    assert res0["status"] in ("Success", "Warning"), res0
    assert isinstance(res0.get("chunks"), list)
    # For lines method with size=1 and 2 lines, expect at least 2 chunks
    assert len(res0["chunks"]) >= 2


def test_process_code_js_codechunk(client_with_single_user):


    client, _ = client_with_single_user
    code = b"function add(a,b){return a+b;}\nexport default add;\n"
    files = [("files", ("lib.js", code, "application/javascript"))]
    data = {
        "perform_chunking": "true",
        "chunk_method": "code",
        "chunk_size": "4000",
        "chunk_overlap": "100",
    }
    r = client.post("/api/v1/media/process-code", files=files, data=data)
    # Even if chunker falls back, endpoint should succeed
    assert r.status_code in (200, 207), r.text
    payload = r.json()
    assert payload.get("results"), payload
    assert payload["results"][0]["status"] in ("Success", "Warning")


@pytest.mark.asyncio
async def test_save_uploaded_files_extension_candidates_tar_gz(tmp_path, monkeypatch):
    # Call internal helper to validate multi-suffix support (.tar.gz)
    from tldw_Server_API.app.api.v1.endpoints import media as media_mod
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Upload_Sink import FileValidator

    content = b"fake tar gz content"
    up = UploadFile(filename="archive.tar.gz", file=io.BytesIO(content))

    saved, errors = await media_mod._save_uploaded_files(
        files=[up],
        temp_dir=tmp_path,
        validator=FileValidator(),
        allowed_extensions=[".tar.gz"],
        skip_archive_scanning=True,
    )
    assert not errors, errors
    assert len(saved) == 1
    assert saved[0]["original_filename"] == "archive.tar.gz"
    assert str(saved[0]["path"]).endswith("archive.tar.gz")
    assert "archive.tar.tar.gz" not in str(saved[0]["path"])


def test_process_docs_streaming_respects_validator_limits(client_with_single_user, monkeypatch, tmp_path):


    # Monkeypatch the file_validator_instance to enforce a tiny max size for documents
    from tldw_Server_API.app.api.v1.endpoints import media as media_mod
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Upload_Sink import FileValidator

    tiny_validator = FileValidator(custom_media_configs={
        "document": {"max_size_mb": 0.0001},  # ~100 bytes
    })
    monkeypatch.setattr(media_mod, "file_validator_instance", tiny_validator)

    client, _ = client_with_single_user
    big = b"x" * 200  # > 100 bytes
    files = [("files", ("note.txt", big, "text/plain"))]
    data = {
        "perform_analysis": "false",
    }
    r = client.post("/api/v1/media/process-documents", files=files, data=data)
    # Expect partial failure with an oversize error or hard 413
    if r.status_code == 413:
        return
    assert r.status_code in (200, 207), r.text
    payload = r.json()
    assert payload.get("errors_count", 0) >= 1


def test_process_code_logs_upload_errors_when_test_mode_is_single_letter_y(
    client_with_single_user,
    monkeypatch,
):
    from tldw_Server_API.app.api.v1.endpoints.media import process_code as process_code_mod

    client, _ = client_with_single_user
    monkeypatch.setenv("TEST_MODE", "y")
    logged: list[str] = []
    monkeypatch.setattr(
        process_code_mod.logger,
        "warning",
        lambda message, *args, **kwargs: logged.append(str(message)),
        raising=True,
    )

    files = [("files", ("bad.exe", b"MZ\x90\x00", "application/octet-stream"))]
    response = client.post("/api/v1/media/process-code", files=files, data={})

    assert response.status_code in (200, 207), response.text
    assert any("TEST_MODE: process-code upload_errors=" in msg for msg in logged)


@pytest.mark.asyncio
async def test_pdf_analysis_without_explicit_api_key(monkeypatch):
    # Unit level: exercise process_pdf_task so that analysis runs with api_name only
    import tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib as pdf_mod

    # Stub parser and metadata to avoid heavy dependencies and errors
    monkeypatch.setattr(pdf_mod, "pymupdf4llm_parse_pdf", lambda path: "Some extracted content")
    monkeypatch.setattr(pdf_mod, "extract_metadata_from_pdf", lambda path: {})
    # Stub analyze to a quick response
    monkeypatch.setattr(pdf_mod, "analyze", lambda **kwargs: "OK")

    out = await pdf_mod.process_pdf_task(
        file_bytes=b"%PDF-fake",
        filename="paper.pdf",
        parser="pymupdf4llm",
        perform_chunking=False,
        perform_analysis=True,
        api_name="openai",
        api_key=None,
    )
    assert out.get("status") in ("Success", "Warning"), out
    # Analysis should run using api_name only
    assert out.get("analysis") == "OK"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("parser_name", "patch_attr"),
    [
        ("pymupdf4llm", "pymupdf4llm_parse_pdf"),
        ("pymupdf", "extract_text_and_format_from_pdf"),
        ("docling", "docling_parse_pdf"),
    ],
)
async def test_pdf_text_normalization_applies_to_all_parser_paths(
    monkeypatch,
    parser_name,
    patch_attr,
):
    import importlib.util
    import tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib as pdf_mod

    wrapped_text = (
        "We are not just interested in models that perform well on a\n"
        "single physical task."
    )
    monkeypatch.setattr(pdf_mod, patch_attr, lambda path: wrapped_text)
    if parser_name == "docling":
        monkeypatch.setattr(importlib.util, "find_spec", lambda _name: object())

    out = await pdf_mod.process_pdf_task(
        file_bytes=b"%PDF-fake",
        filename=f"{parser_name}.pdf",
        parser=parser_name,
        perform_chunking=False,
        perform_analysis=False,
    )
    assert out.get("status") in ("Success", "Warning"), out
    assert "perform well on a single physical task." in (out.get("content") or "")


@pytest.mark.asyncio
async def test_pdf_text_normalization_applies_after_ocr_merge(monkeypatch):
    import tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib as pdf_mod

    monkeypatch.setattr(pdf_mod, "pymupdf4llm_parse_pdf", lambda path: "Parser output")
    monkeypatch.setattr(
        pdf_mod,
        "_ocr_pdf_pages",
        lambda **kwargs: ("OCR line one\nline two", 1, [1], None),
    )

    class _FakeOcrBackend:
        name = "fake-ocr"

    monkeypatch.setattr(pdf_mod, "_get_ocr_backend", lambda _name=None: _FakeOcrBackend())

    out = await pdf_mod.process_pdf_task(
        file_bytes=b"%PDF-fake",
        filename="ocr-path.pdf",
        parser="pymupdf4llm",
        perform_chunking=False,
        perform_analysis=False,
        enable_ocr=True,
        ocr_mode="always",
    )
    assert out.get("status") in ("Success", "Warning"), out
    assert out.get("content") == "OCR line one line two"
