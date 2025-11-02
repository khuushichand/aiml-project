import io
import os
import zipfile
import pytest

from tldw_Server_API.app.services import document_processing_service as dps


def _make_bad_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add a traversal entry
        zf.writestr("../evil.txt", "owned")
    return buf.getvalue()


def test_safe_zip_extraction_blocks_traversal(tmp_path):
    bad = tmp_path / "bad.zip"
    bad.write_bytes(_make_bad_zip_bytes())
    with pytest.raises(Exception):
        # Function should raise due to unsafe path
        dps._extract_zip_and_combine(str(bad))
