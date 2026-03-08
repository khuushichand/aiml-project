from __future__ import annotations

import io
import zipfile

import pytest


@pytest.mark.asyncio
@pytest.mark.unit
async def test_archive_refresh_keeps_previous_snapshot_when_candidate_fails(tmp_path):
    from tldw_Server_API.app.core.Ingestion_Sources.archive_snapshot import apply_archive_candidate

    current_snapshot = {"id": 3, "status": "active"}

    with pytest.raises(ValueError, match="Invalid ZIP archive"):
        await apply_archive_candidate(
            source_id=11,
            archive_bytes=b"not-a-zip",
            filename="broken.zip",
            current_snapshot=current_snapshot,
        )

    assert current_snapshot == {"id": 3, "status": "active"}


@pytest.mark.unit
def test_archive_media_snapshot_supports_pdf_and_epub_with_collected_failures(monkeypatch):
    import tldw_Server_API.app.core.Ingestion_Sources.archive_snapshot as archive_snapshot

    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("export/report.pdf", b"%PDF-1.4 fake\n")
        archive.writestr("export/book.epub", b"fake-epub")
        archive.writestr("export/bad.pdf", b"%PDF-1.4 broken\n")
    archive_bytes = archive_buffer.getvalue()

    def _fake_process_pdf(file_input, *, filename, **kwargs):
        del file_input, kwargs
        if filename == "bad.pdf":
            return {
                "status": "Error",
                "error": "pdf parse failed",
                "warnings": ["pdf parse failed"],
            }
        return {
            "status": "Success",
            "content": f"content for {filename}",
            "metadata": {"title": filename, "author": "PDF Author", "raw": {"pages": 1}},
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

    monkeypatch.setattr(archive_snapshot, "process_pdf", _fake_process_pdf)
    monkeypatch.setattr(archive_snapshot, "process_epub", _fake_process_epub)

    items, failures = archive_snapshot.build_archive_snapshot_from_bytes_with_failures(
        archive_bytes=archive_bytes,
        filename="documents.zip",
        sink_type="media",
    )

    assert set(items) == {"book.epub", "report.pdf"}
    assert set(failures) == {"bad.pdf"}
    assert items["report.pdf"]["source_format"] == "pdf"
    assert items["book.epub"]["source_format"] == "epub"
    assert failures["bad.pdf"]["error"] == "pdf parse failed"
