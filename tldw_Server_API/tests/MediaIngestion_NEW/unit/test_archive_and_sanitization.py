import os
import tarfile
import tempfile
import zipfile
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Upload_Sink import (
    FileValidator,
)


@pytest.mark.unit
def test_validate_tar_archive_simple(tmp_path: Path):
    # Create a simple tar archive with one small file
    inner_dir = tmp_path / "inner"
    inner_dir.mkdir()
    (inner_dir / "a.txt").write_text("hello", encoding="utf-8")

    tar_path = tmp_path / "sample.tar"
    with tarfile.open(tar_path, "w") as tar:
        tar.add(inner_dir / "a.txt", arcname="a.txt")

    # Avoid MIME enforcement to make test robust across environments
    validator = FileValidator(custom_media_configs={
        "archive": {"allowed_mimetypes": None}
    })

    res = validator.validate_archive_contents(tar_path)
    assert res.is_valid, f"Expected valid tar archive, got issues: {res.issues}"


@pytest.mark.unit
def test_validate_tar_archive_limits(tmp_path: Path):
    # Create a tar archive with two files and set limit=1
    (tmp_path / "f1.txt").write_text("x", encoding="utf-8")
    (tmp_path / "f2.txt").write_text("y", encoding="utf-8")
    tar_path = tmp_path / "many.tar"
    with tarfile.open(tar_path, "w") as tar:
        tar.add(tmp_path / "f1.txt", arcname="f1.txt")
        tar.add(tmp_path / "f2.txt", arcname="f2.txt")

    validator = FileValidator(custom_media_configs={
        "archive": {
            "allowed_mimetypes": None,
            "max_internal_files": 1,
        }
    })

    res = validator.validate_archive_contents(tar_path)
    assert not res.is_valid
    joined = " ".join(res.issues).lower()
    assert "too many files" in joined or "exceeded max internal file limit" in joined


@pytest.mark.unit
def test_nested_archive_scanning_detects_inner_payload(tmp_path: Path):
    inner_zip = tmp_path / "inner.zip"
    with zipfile.ZipFile(inner_zip, "w") as zf:
        zf.writestr("payload.exe", b"MZ")

    outer_zip = tmp_path / "outer.zip"
    with zipfile.ZipFile(outer_zip, "w") as zf:
        zf.write(inner_zip, arcname="inner.zip")

    validator = FileValidator(custom_media_configs={
        "archive": {
            "allowed_mimetypes": None,
            "max_internal_files": 10,
            "max_depth": 2,
        }
    })

    res = validator.validate_archive_contents(outer_zip)
    assert not res.is_valid
    message = " ".join(res.issues).lower()
    assert "nested archive" in message or ".exe" in message


@pytest.mark.unit
def test_html_sanitization_removes_script():
    validator = FileValidator()
    html = "<html><head><script>alert('x')</script></head><body><p>OK</p></body></html>"
    cleaned = validator.sanitize_html_content(html, config={"strip": True})
    assert "script" not in cleaned.lower()
    assert "ok" in cleaned.lower()


@pytest.mark.unit
def test_xml_sanitization_strips_comments_and_pi():
    try:
        import defusedxml  # noqa: F401
    except Exception:
        pytest.skip("defusedxml not installed")

    validator = FileValidator()
    xml = """<?xml version='1.0'?>
    <?processing instruction?>
    <!-- a comment -->
    <root><child>ok</child></root>
    """
    cleaned = validator.sanitize_xml_content(xml, config={"strip_comments": True, "strip_processing_instructions": True})
    low = cleaned.lower()
    assert "processing" not in low and "comment" not in low
    assert "child" in low and "ok" in low
