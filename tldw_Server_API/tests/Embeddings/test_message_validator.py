import json
import pytest

from tldw_Server_API.app.core.Embeddings.messages import normalize_message
from pydantic import ValidationError


@pytest.mark.unit
def test_normalize_message_adds_version_and_schema():
    raw = {
        "job_id": "j1",
        "user_id": "u",
        "media_id": 1,
        "priority": 50,
        "user_tier": "free",
        "content": "hello",
        "content_type": "text",
        "chunking_config": {"chunk_size": 1000, "overlap": 200, "separator": "\n"},
        "source_metadata": {},
    }
    out = normalize_message("chunking", raw)
    assert isinstance(out, dict)
    assert out.get("msg_version") == 1
    # new field name is msg_schema (accepts alias 'schema')
    assert out.get("msg_schema") == "tldw.embeddings.v1"


@pytest.mark.unit
def test_normalize_message_rejects_bad_stage():
    with pytest.raises(ValueError):
        normalize_message("invalid_stage", {"job_id": "x"})


@pytest.mark.unit
def test_normalize_message_invalid_chunking_config():
    # chunk_size below minimum should raise
    raw = {
        "job_id": "j2",
        "user_id": "u",
        "media_id": 1,
        "priority": 50,
        "user_tier": "free",
        "content": "hello",
        "content_type": "text",
        "chunking_config": {"chunk_size": 10, "overlap": 0, "separator": "\n"},
        "source_metadata": {},
    }
    with pytest.raises(ValidationError):
        normalize_message("chunking", raw)


@pytest.mark.unit
def test_normalize_message_schema_alias_handling():
    raw = {
        "schema": "custom.schema.v1",
        "job_id": "j3",
        "user_id": "u",
        "media_id": 1,
        "priority": 50,
        "user_tier": "free",
        "content": "hello",
        "content_type": "text",
        "chunking_config": {"chunk_size": 1000, "overlap": 200, "separator": "\n"},
        "source_metadata": {},
    }
    out = normalize_message("chunking", raw)
    assert out.get("msg_schema") == "custom.schema.v1"
