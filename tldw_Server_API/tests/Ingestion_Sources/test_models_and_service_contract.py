from __future__ import annotations

import pytest


@pytest.mark.unit
def test_create_source_normalizes_enums_and_defaults():
    from tldw_Server_API.app.core.Ingestion_Sources.service import normalize_source_payload

    payload = normalize_source_payload(
        {
            "source_type": "local_directory",
            "sink_type": "media",
            "policy": "canonical",
            "enabled": None,
        }
    )

    assert payload["source_type"] == "local_directory"
    assert payload["sink_type"] == "media"
    assert payload["policy"] == "canonical"
    assert payload["enabled"] is True
