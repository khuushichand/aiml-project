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


@pytest.mark.unit
def test_normalize_source_payload_rejects_git_repository_media_sink():
    from tldw_Server_API.app.core.Ingestion_Sources.service import normalize_source_payload
    from tldw_Server_API.app.core.exceptions import IngestionSourceValidationError

    with pytest.raises(
        IngestionSourceValidationError,
        match="Git repository sources currently support the notes sink only",
    ):
        normalize_source_payload(
            {
                "source_type": "git_repository",
                "sink_type": "media",
                "policy": "canonical",
            }
        )
