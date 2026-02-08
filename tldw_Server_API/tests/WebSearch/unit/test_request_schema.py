import pytest
from pydantic import ValidationError

pytestmark = pytest.mark.unit


def test_websearch_request_accepts_max_archived_threads_per_board():
    from tldw_Server_API.app.api.v1.schemas.websearch_schemas import WebSearchRequest

    payload = WebSearchRequest(
        query="rust memory safety",
        engine="4chan",
        max_archived_threads_per_board=200,
    )

    assert payload.max_archived_threads_per_board == 200


def test_websearch_request_rejects_max_archived_threads_per_board_out_of_range():
    from tldw_Server_API.app.api.v1.schemas.websearch_schemas import WebSearchRequest

    with pytest.raises(ValidationError):
        WebSearchRequest(
            query="rust memory safety",
            engine="4chan",
            max_archived_threads_per_board=0,
        )

    with pytest.raises(ValidationError):
        WebSearchRequest(
            query="rust memory safety",
            engine="4chan",
            max_archived_threads_per_board=501,
        )
