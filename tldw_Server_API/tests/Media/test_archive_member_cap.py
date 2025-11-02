import os
import zipfile

import pytest


pytestmark = pytest.mark.unit


def test_validate_archive_per_member_cap(tmp_path):
    # Create a zip with a single member larger than the per-member cap
    zpath = tmp_path / "big_member.zip"
    big_bytes = b"a" * (2 * 1024 * 1024)  # 2MB
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("big.txt", big_bytes)

    # Configure validator to cap per-member uncompressed size at 1MB
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Upload_Sink import FileValidator

    v = FileValidator(
        custom_media_configs={
            "archive": {
                "scan_contents": True,
                "max_internal_files": 10,
                "max_internal_uncompressed_size_mb": 50,
                "max_member_uncompressed_size_mb": 1,  # 1MB per file
            }
        }
    )

    res = v.validate_archive_contents(zpath)
    assert not res, f"Expected failure due to per-member cap; issues: {res.issues}"
    # Ensure the issue indicates member size exceeded
    assert any("per-file size cap" in i.lower() for i in res.issues), res.issues
