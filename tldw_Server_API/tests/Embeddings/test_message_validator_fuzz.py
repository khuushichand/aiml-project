import sys
from types import SimpleNamespace

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from tldw_Server_API.app.core.Embeddings import messages


_ASCII_TEXT = st.text(alphabet=st.characters(min_codepoint=48, max_codepoint=122), min_size=1, max_size=32)
_ASCII_KEY = st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=10)
_ASCII_VALUE = st.one_of(
    st.integers(),
    st.text(alphabet=st.characters(min_codepoint=48, max_codepoint=122), min_size=0, max_size=32),
    st.booleans(),
)


@pytest.mark.unit
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=50)
@given(
    stage=st.sampled_from(["chunking", "embedding", "storage"]),
    job_id=_ASCII_TEXT,
    user_id=st.text(alphabet=st.characters(min_codepoint=48, max_codepoint=122), min_size=1, max_size=16),
    media_id=st.integers(min_value=1, max_value=1_000_000),
    extra=st.dictionaries(keys=_ASCII_KEY, values=_ASCII_VALUE, max_size=5),
)
def test_normalize_message_accepts_extra_fields(stage, job_id, user_id, media_id, extra):
    """normalize_message should accept unknown fields (additive) and inject envelope defaults."""
    data = {"job_id": job_id, "user_id": user_id, "media_id": media_id}
    data.update(extra)
    norm = messages.normalize_message(stage, data)
    assert isinstance(norm, dict)
    assert norm.get("msg_version") == messages.CURRENT_VERSION
    assert norm.get("msg_schema") == messages.CURRENT_SCHEMA
    assert "schema_url" in norm


@pytest.mark.unit
def test_validate_schema_optional_when_jsonschema_missing(monkeypatch):
    """When jsonschema isn't installed, validate_schema should be a no-op (non-fatal)."""
    # Ensure import fails inside validate_schema
    monkeypatch.setitem(sys.modules, "jsonschema", None)
    # Remove to simulate ImportError in local function import
    sys.modules.pop("jsonschema", None)
    messages.validate_schema("embedding", {"job_id": "j", "user_id": "u", "media_id": 1})


@pytest.mark.unit
def test_validate_schema_uses_jsonschema_when_present(monkeypatch):
    calls = {"count": 0}

    def _validate(obj, schema):  # noqa: ARG001
        calls["count"] += 1
        if "job_id" not in obj:
            raise Exception("missing job_id")

    # Stub module
    stub = SimpleNamespace(validate=_validate)
    monkeypatch.setitem(sys.modules, "jsonschema", stub)
    messages.validate_schema("embedding", {"job_id": "j", "user_id": "u", "media_id": 2})
    assert calls["count"] == 1
    with pytest.raises(ValueError):
        messages.validate_schema("embedding", {"user_id": "u", "media_id": 2})
