from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_local_directory_adapter_rejects_path_outside_allowed_roots(tmp_path, monkeypatch):
    from tldw_Server_API.app.core.Ingestion_Sources.local_directory import validate_local_directory_source

    allowed_root = tmp_path / "allowed"
    outside_root = tmp_path / "outside"
    allowed_root.mkdir()
    outside_root.mkdir()

    monkeypatch.setenv("INGESTION_SOURCE_ALLOWED_ROOTS", str(allowed_root))

    with pytest.raises(ValueError, match="allowed roots"):
        validate_local_directory_source({"path": str(outside_root)})


@pytest.mark.unit
def test_local_directory_adapter_accepts_existing_directory_within_allowed_roots(tmp_path, monkeypatch):
    from tldw_Server_API.app.core.Ingestion_Sources.local_directory import validate_local_directory_source

    allowed_root = tmp_path / "allowed"
    source_dir = allowed_root / "docs"
    source_dir.mkdir(parents=True)

    monkeypatch.setenv("INGESTION_SOURCE_ALLOWED_ROOTS", str(allowed_root))

    validated_path = validate_local_directory_source({"path": str(source_dir)})

    assert validated_path == Path(source_dir).resolve(strict=False)


@pytest.mark.unit
def test_local_directory_media_snapshot_supports_pdf_and_epub(tmp_path, monkeypatch):
    import tldw_Server_API.app.core.Ingestion_Sources.local_directory as local_directory

    allowed_root = tmp_path / "allowed"
    source_dir = allowed_root / "docs"
    source_dir.mkdir(parents=True)
    (source_dir / "report.pdf").write_bytes(b"%PDF-1.4 fake\n")
    (source_dir / "book.epub").write_bytes(b"fake-epub")

    monkeypatch.setenv("INGESTION_SOURCE_ALLOWED_ROOTS", str(allowed_root))

    def _fake_process_pdf(file_input, *, filename, **kwargs):
        del file_input, kwargs
        return {
            "status": "Success",
            "content": "pdf body",
            "metadata": {"title": "Quarterly Report", "author": "PDF Author", "raw": {"pages": 1}},
            "parser_used": "pymupdf4llm",
            "input_ref": filename,
        }

    def _fake_process_epub(file_path, **kwargs):
        del file_path, kwargs
        return {
            "status": "Success",
            "content": "epub body",
            "metadata": {"title": "Book Title", "author": "EPUB Author", "raw": {"chapters": 2}},
            "parser_used": "filtered",
        }

    monkeypatch.setattr(local_directory, "process_pdf", _fake_process_pdf)
    monkeypatch.setattr(local_directory, "process_epub", _fake_process_epub)

    items, failures = local_directory.build_local_directory_snapshot_with_failures(
        {"path": str(source_dir)},
        sink_type="media",
    )

    assert failures == {}
    assert set(items) == {"book.epub", "report.pdf"}
    assert items["report.pdf"]["source_format"] == "pdf"
    assert items["report.pdf"]["raw_metadata"]["title"] == "Quarterly Report"
    assert items["book.epub"]["source_format"] == "epub"
    assert items["book.epub"]["raw_metadata"]["title"] == "Book Title"
