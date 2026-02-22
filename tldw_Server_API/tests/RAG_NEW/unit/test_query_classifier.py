import pytest

from tldw_Server_API.app.core.RAG.rag_service.query_classifier import (
    _parse_classification_response,
)


pytestmark = pytest.mark.unit


def test_parse_classification_response_parses_fenced_json_with_think_tags():
    raw = (
        "<think>reasoning</think>\n"
        "```json\n"
        "{"
        '"skip_search": false,'
        '"search_local_db": true,'
        '"search_web": true,'
        '"search_academic": false,'
        '"search_discussions": false,'
        '"standalone_query": "what is rag",'
        '"detected_intent": "definitional",'
        '"confidence": 0.9,'
        '"reasoning": "needs retrieval"'
        "}\n"
        "```"
    )

    parsed = _parse_classification_response(raw)
    assert parsed["search_web"] is True
    assert parsed["standalone_query"] == "what is rag"


def test_parse_classification_response_accepts_list_wrapped_object():
    raw = '[{"skip_search": true, "search_local_db": false, "search_web": false}]'
    parsed = _parse_classification_response(raw)
    assert parsed["skip_search"] is True
    assert parsed["search_local_db"] is False
