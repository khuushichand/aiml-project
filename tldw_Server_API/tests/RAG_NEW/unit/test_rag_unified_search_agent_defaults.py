import pytest

import tldw_Server_API.app.api.v1.endpoints.rag_unified as rag_ep
from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedRAGRequest


pytestmark = pytest.mark.unit


_EMPTY_DB_PATHS = {
    "media_db_path": None,
    "notes_db_path": None,
    "character_db_path": None,
    "kanban_db_path": None,
}


def _config_value_factory(mapping: dict[str, str]):
    def _fake_get_config_value(section: str, key: str, default=None, reload: bool = False):  # noqa: ANN001, ARG001
        if section != "Search-Agent":
            return default
        return mapping.get(key, default)

    return _fake_get_config_value


def test_search_agent_defaults_apply_when_request_fields_omitted(monkeypatch):
    for env_key in (
        "SEARCH_QUERY_CLASSIFICATION",
        "SEARCH_DEFAULT_MODE",
        "SEARCH_QUERY_REFORMULATION",
        "SEARCH_RESEARCH_LOOP",
        "SEARCH_DISCUSSIONS_ENABLED",
        "SEARCH_DISCUSSION_PLATFORMS",
        "SEARCH_PROGRESS_STREAMING",
        "SEARCH_URL_SCRAPING",
        "SEARCH_CLASSIFIER_PROVIDER",
        "SEARCH_CLASSIFIER_MODEL",
        "SEARCH_MAX_ITERATIONS_SPEED",
        "SEARCH_MAX_ITERATIONS_BALANCED",
        "SEARCH_MAX_ITERATIONS_QUALITY",
    ):
        monkeypatch.delenv(env_key, raising=False)

    monkeypatch.setattr(
        rag_ep,
        "get_config_value",
        _config_value_factory(
            {
                "search_query_classification": "true",
                "search_default_mode": "quality",
                "search_query_reformulation": "false",
                "search_research_loop": "true",
                "search_discussions_enabled": "true",
                "search_discussion_platforms": "reddit,stackoverflow",
                "search_progress_streaming": "true",
                "search_url_scraping": "false",
                "search_classifier_provider": "openai",
                "search_classifier_model": "gpt-4o-mini",
                "search_max_iterations_speed": "3",
                "search_max_iterations_balanced": "7",
                "search_max_iterations_quality": "15",
            }
        ),
    )

    request = UnifiedRAGRequest(query="default behavior check")
    kwargs = rag_ep._build_unified_pipeline_kwargs(
        request=request,
        db_paths=_EMPTY_DB_PATHS,
        media_db=None,  # type: ignore[arg-type]
        chacha_db=None,  # type: ignore[arg-type]
        current_user=None,
    )

    assert kwargs["enable_query_classification"] is True
    assert kwargs["search_depth_mode"] == "quality"
    assert kwargs["enable_query_reformulation"] is False
    assert kwargs["enable_research_loop"] is True
    assert kwargs["enable_discussion_search"] is True
    assert kwargs["discussion_platforms"] == ["reddit", "stackoverflow"]
    assert kwargs["enable_research_progress"] is True
    assert kwargs["search_url_scraping"] is False
    assert kwargs["classifier_provider"] == "openai"
    assert kwargs["classifier_model"] == "gpt-4o-mini"
    assert kwargs["research_max_iterations_speed"] == 3
    assert kwargs["research_max_iterations_balanced"] == 7
    assert kwargs["research_max_iterations_quality"] == 15


def test_search_agent_defaults_do_not_override_explicit_request_values(monkeypatch):
    monkeypatch.setattr(
        rag_ep,
        "get_config_value",
        _config_value_factory(
            {
                "search_query_classification": "true",
                "search_default_mode": "quality",
                "search_query_reformulation": "true",
                "search_research_loop": "true",
                "search_discussions_enabled": "true",
                "search_discussion_platforms": "reddit,stackoverflow",
                "search_url_scraping": "true",
                "search_classifier_provider": "openai",
                "search_classifier_model": "gpt-4.1",
                "search_max_iterations_speed": "9",
                "search_max_iterations_balanced": "9",
                "search_max_iterations_quality": "9",
            }
        ),
    )

    request = UnifiedRAGRequest(
        query="explicit should win",
        enable_query_classification=False,
        search_depth_mode="speed",
        enable_query_reformulation=False,
        enable_research_loop=False,
        enable_discussion_search=False,
        discussion_platforms=["quora"],
        search_url_scraping=False,
        classifier_provider="anthropic",
        classifier_model="claude-3-5-sonnet",
        research_max_iterations_speed=1,
        research_max_iterations_balanced=2,
        research_max_iterations_quality=3,
    )
    kwargs = rag_ep._build_unified_pipeline_kwargs(
        request=request,
        db_paths=_EMPTY_DB_PATHS,
        media_db=None,  # type: ignore[arg-type]
        chacha_db=None,  # type: ignore[arg-type]
        current_user=None,
    )

    assert kwargs["enable_query_classification"] is False
    assert kwargs["search_depth_mode"] == "speed"
    assert kwargs["enable_query_reformulation"] is False
    assert kwargs["enable_research_loop"] is False
    assert kwargs["enable_discussion_search"] is False
    assert kwargs["discussion_platforms"] == ["quora"]
    assert kwargs["search_url_scraping"] is False
    assert kwargs["classifier_provider"] == "anthropic"
    assert kwargs["classifier_model"] == "claude-3-5-sonnet"
    assert kwargs["research_max_iterations_speed"] == 1
    assert kwargs["research_max_iterations_balanced"] == 2
    assert kwargs["research_max_iterations_quality"] == 3


def test_search_agent_env_overrides_config_defaults(monkeypatch):
    monkeypatch.setattr(
        rag_ep,
        "get_config_value",
        _config_value_factory(
            {
                "search_query_classification": "false",
                "search_default_mode": "speed",
                "search_discussion_platforms": "reddit",
            }
        ),
    )

    monkeypatch.setenv("SEARCH_QUERY_CLASSIFICATION", "true")
    monkeypatch.setenv("SEARCH_DEFAULT_MODE", "balanced")
    monkeypatch.setenv("SEARCH_DISCUSSION_PLATFORMS", "stackoverflow,hackernews")

    request = UnifiedRAGRequest(query="env should override config")
    kwargs = rag_ep._build_unified_pipeline_kwargs(
        request=request,
        db_paths=_EMPTY_DB_PATHS,
        media_db=None,  # type: ignore[arg-type]
        chacha_db=None,  # type: ignore[arg-type]
        current_user=None,
    )

    assert kwargs["enable_query_classification"] is True
    assert kwargs["search_depth_mode"] == "balanced"
    assert kwargs["discussion_platforms"] == ["stackoverflow", "hackernews"]
