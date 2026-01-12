import pytest

from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import (
    DEFAULT_EXTRACTION_STRATEGY_ORDER,
    extract_article_with_pipeline,
)
from tldw_Server_API.app.core.Web_Scraping.scraper_router import ScraperRouter


def test_pipeline_trace_default_order():
    def fake_extractor(html: str, url: str):  # noqa: ANN001
        return {
            "url": url,
            "title": "Test",
            "author": "N/A",
            "date": "N/A",
            "content": "Hello",
            "extraction_successful": True,
        }

    result = extract_article_with_pipeline(
        "<html><body><p>hello</p></body></html>",
        "https://example.com",
        fallback_extractor=fake_extractor,
    )

    assert result["extraction_successful"] is True
    assert result["extraction_strategy"] == "trafilatura"
    assert [entry["strategy"] for entry in result["extraction_trace"]] == DEFAULT_EXTRACTION_STRATEGY_ORDER


def test_pipeline_strategy_order_override_from_router():
    rules = ScraperRouter.validate_rules(
        {
            "domains": {
                "example.com": {
                    "strategy_order": ["schema", "trafilatura"],
                }
            }
        }
    )
    router = ScraperRouter(rules)
    plan = router.resolve("https://example.com/page")

    assert plan.strategy_order == ["schema", "trafilatura"]

    def fake_extractor(html: str, url: str):  # noqa: ANN001
        return {
            "url": url,
            "title": "Test",
            "author": "N/A",
            "date": "N/A",
            "content": "Hello",
            "extraction_successful": True,
        }

    result = extract_article_with_pipeline(
        "<html><body><p>hello</p></body></html>",
        "https://example.com/page",
        strategy_order=plan.strategy_order,
        fallback_extractor=fake_extractor,
    )
    assert [entry["strategy"] for entry in result["extraction_trace"]] == ["schema", "trafilatura"]


def test_pipeline_handler_stage_short_circuits():
    def handler(html: str, url: str):  # noqa: ANN001
        return {
            "url": url,
            "title": "Handled",
            "author": "N/A",
            "date": "N/A",
            "content": "Handled",
            "extraction_successful": True,
        }

    result = extract_article_with_pipeline(
        "<html><body><p>hello</p></body></html>",
        "https://example.com/handled",
        strategy_order=["schema", "trafilatura"],
        handler=handler,
    )
    assert result["extraction_successful"] is True
    assert result["extraction_strategy"] == "schema"
    assert [entry["strategy"] for entry in result["extraction_trace"]] == ["schema"]
