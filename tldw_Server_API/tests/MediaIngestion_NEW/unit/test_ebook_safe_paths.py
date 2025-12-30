from pathlib import Path

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Books import Book_Processing_Lib as books


@pytest.mark.unit
def test_process_epub_rejects_path_outside_base_dir(tmp_path: Path) -> None:
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    outside_path = tmp_path / "outside" / "book.epub"

    result = books.process_epub(
        file_path=str(outside_path),
        perform_chunking=False,
        perform_analysis=False,
        base_dir=allowed_dir,
    )

    assert result["status"] == "Error"
    assert "rejected outside allowed base directory" in (result.get("error") or "")
