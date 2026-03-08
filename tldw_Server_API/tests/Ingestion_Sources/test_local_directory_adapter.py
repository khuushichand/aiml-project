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
