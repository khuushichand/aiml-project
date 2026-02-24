from __future__ import annotations

import pytest

from tldw_Server_API.app.api.v1.endpoints import messages as messages_endpoint


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("http://localhost:8080/v1/messages", "http://localhost:8080"),
        ("http://localhost:8080/v1/messages/count_tokens", "http://localhost:8080"),
        ("http://localhost:8080/messages", "http://localhost:8080"),
        ("http://localhost:8080/messages/count_tokens", "http://localhost:8080"),
    ],
)
def test_llamacpp_normalize_base_url_strips_messages_suffixes(raw: str, expected: str) -> None:
    assert messages_endpoint._normalize_llamacpp_base_url(raw) == expected


@pytest.mark.unit
def test_llamacpp_resolved_base_url_does_not_duplicate_messages_path() -> None:
    base = messages_endpoint._resolve_messages_base_url(
        "llama.cpp",
        {"llama_api": {"api_ip": "http://localhost:8080/v1/messages"}},
    )

    messages_url = messages_endpoint._join_messages_endpoint(base, "/messages")
    count_tokens_url = messages_endpoint._join_messages_endpoint(base, "/messages/count_tokens")

    assert messages_url == "http://localhost:8080/v1/messages"
    assert count_tokens_url == "http://localhost:8080/v1/messages/count_tokens"
