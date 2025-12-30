from pathlib import Path

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF import PDF_Processing_Lib as pdf_lib


@pytest.mark.unit
def test_process_pdf_rejects_path_outside_base_dir(tmp_path: Path) -> None:
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    outside_path = tmp_path / "outside" / "paper.pdf"

    result = pdf_lib.process_pdf(
        file_input=str(outside_path),
        filename="paper.pdf",
        perform_chunking=False,
        perform_analysis=False,
        base_dir=allowed_dir,
    )

    assert result["status"] == "Error"
    assert "rejected outside allowed base directory" in (result.get("error") or "")
