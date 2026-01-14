from tldw_Server_API.app.core.Web_Scraping.scraper_router import ScraperRouter


def test_router_carries_llm_settings():
    rules = ScraperRouter.validate_rules(
        {
            "domains": {
                "example.com": {
                    "llm_settings": {
                        "provider": "openai",
                        "delay_ms": 25,
                        "max_concurrency": 2,
                    }
                }
            }
        }
    )
    router = ScraperRouter(rules)
    plan = router.resolve("https://example.com/path")

    assert plan.llm_settings["provider"] == "openai"
    assert plan.llm_settings["delay_ms"] == 25
    assert plan.llm_settings["max_concurrency"] == 2


def test_router_allows_llm_alias_key():
    rules = ScraperRouter.validate_rules(
        {
            "domains": {
                "example.com": {
                    "llm": {
                        "provider": "openai",
                        "delay_ms": 10,
                    }
                }
            }
        }
    )
    router = ScraperRouter(rules)
    plan = router.resolve("https://example.com/path")

    assert plan.llm_settings["provider"] == "openai"
    assert plan.llm_settings["delay_ms"] == 10
