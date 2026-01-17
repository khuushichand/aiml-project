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


def test_router_carries_regex_and_cluster_settings():
    rules = ScraperRouter.validate_rules(
        {
            "domains": {
                "example.com": {
                    "regex_settings": {"mask_pii": False},
                    "cluster_settings": {"cluster_linkage": "average", "min_word_count": 3},
                }
            }
        }
    )
    router = ScraperRouter(rules)
    plan = router.resolve("https://example.com/path")

    assert plan.regex_settings == {"mask_pii": False}
    assert plan.cluster_settings["cluster_linkage"] == "average"
    assert plan.cluster_settings["min_word_count"] == 3


def test_router_allows_regex_cluster_alias_keys():
    rules = ScraperRouter.validate_rules(
        {
            "domains": {
                "example.com": {
                    "regex": {"mask_pii": True},
                    "cluster": {"cluster_linkage": "complete"},
                }
            }
        }
    )
    router = ScraperRouter(rules)
    plan = router.resolve("https://example.com/path")

    assert plan.regex_settings == {"mask_pii": True}
    assert plan.cluster_settings == {"cluster_linkage": "complete"}
