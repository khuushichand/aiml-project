import pytest


pytestmark = pytest.mark.unit


def test_resolve_provider_config_merges_defaults_and_drops_unknown_keys():
    from tldw_Server_API.app.core.Research.providers.config import resolve_provider_config

    resolved = resolve_provider_config(
        {
            "local": {"top_k": 4, "sources": ["media_db", "notes", "bad_source"], "ignored": True},
            "web": {"engine": "duckduckgo", "result_count": 3, "bad": "x"},
            "academic": {"providers": ["arxiv", "pubmed", "bad"], "max_results": 2},
            "synthesis": {"provider": "openai", "model": "gpt-4.1-mini", "temperature": 0.2, "bad": "x"},
            "extra": {"value": "ignored"},
        }
    )

    assert resolved["local"]["top_k"] == 4
    assert resolved["local"]["sources"] == ["media_db", "notes"]
    assert "ignored" not in resolved["local"]
    assert resolved["web"]["engine"] == "duckduckgo"
    assert resolved["web"]["result_count"] == 3
    assert "bad" not in resolved["web"]
    assert resolved["academic"]["providers"] == ["arxiv", "pubmed"]
    assert resolved["academic"]["max_results"] == 2
    assert resolved["synthesis"]["provider"] == "openai"
    assert resolved["synthesis"]["model"] == "gpt-4.1-mini"
    assert resolved["synthesis"]["temperature"] == 0.2
    assert "extra" not in resolved


def test_resolve_provider_config_clamps_out_of_range_values():
    from tldw_Server_API.app.core.Research.providers.config import resolve_provider_config

    resolved = resolve_provider_config(
        {
            "local": {"top_k": 999},
            "web": {"result_count": -5},
            "academic": {"max_results": 999},
            "synthesis": {"temperature": 9},
        }
    )

    assert resolved["local"]["top_k"] == 20
    assert resolved["web"]["result_count"] == 1
    assert resolved["academic"]["max_results"] == 20
    assert resolved["synthesis"]["temperature"] == 1.0


def test_resolve_provider_config_supplies_defaults_when_overrides_missing():
    from tldw_Server_API.app.core.Research.providers.config import resolve_provider_config

    resolved = resolve_provider_config(None)

    assert resolved["local"]["top_k"] == 5
    assert resolved["local"]["sources"] == ["media_db"]
    assert resolved["web"]["engine"] == "duckduckgo"
    assert resolved["web"]["result_count"] == 5
    assert resolved["academic"]["providers"] == ["arxiv", "pubmed", "crossref"]
    assert resolved["academic"]["max_results"] == 5
    assert resolved["synthesis"]["temperature"] == 0.2
