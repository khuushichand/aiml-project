from __future__ import annotations

import pytest


@pytest.mark.unit
def test_normalize_source_payload_accepts_git_repository():
    from tldw_Server_API.app.core.Ingestion_Sources.service import normalize_source_payload

    payload = normalize_source_payload(
        {
            "source_type": "git_repository",
            "sink_type": "notes",
            "policy": "import_only",
        }
    )

    assert payload["source_type"] == "git_repository"
