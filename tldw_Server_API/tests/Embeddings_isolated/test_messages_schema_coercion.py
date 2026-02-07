from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Embeddings.messages import validate_schema


@pytest.mark.unit
def test_validate_schema_accepts_numeric_string_media_id():
    payload = {"job_id": "job-1", "user_id": "user-1", "media_id": "123"}
    validate_schema("embedding", payload)


@pytest.mark.unit
def test_validate_schema_rejects_non_numeric_media_id():
    payload = {"job_id": "job-1", "user_id": "user-1", "media_id": "abc"}
    with pytest.raises(ValueError):
        validate_schema("embedding", payload)
