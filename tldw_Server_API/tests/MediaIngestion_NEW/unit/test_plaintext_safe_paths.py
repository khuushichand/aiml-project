from pathlib import Path

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Plaintext import Plaintext_Files as plaintext


@pytest.mark.unit
def test_process_document_content_rejects_path_outside_base_dir(tmp_path: Path) -> None:
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    outside_path = tmp_path / "outside" / "note.txt"

    result = plaintext.process_document_content(
        doc_path=outside_path,
        perform_chunking=False,
        chunk_options=None,
        perform_analysis=False,
        summarize_recursively=False,
        api_name=None,
        api_key=None,
        custom_prompt=None,
        system_prompt=None,
        base_dir=allowed_dir,
    )

    assert result["status"] == "Error"
    assert "rejected outside allowed base directory" in (result.get("error") or "")
