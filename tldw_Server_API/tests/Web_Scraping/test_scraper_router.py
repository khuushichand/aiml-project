from tldw_Server_API.app.core.Web_Scraping.scraper_router import ScraperRouter


def test_router_precedence_exact_over_wildcard_and_patterns():
    rules = {
        "domains": {
            "example.com": {
                "backend": "curl",
                "handler": "tldw_Server_API.app.core.Web_Scraping.handlers:handle_generic_html",
                "ua_profile": "chrome_120_win",
                "impersonate": "chrome120",
            },
            "*.example.com": {
                "backend": "httpx",
                "handler": "tldw_Server_API.app.core.Web_Scraping.handlers:handle_generic_html",
                "ua_profile": "firefox_120_win",
                "url_patterns": [".*\\?output=1$"]
            },
        }
    }
    router = ScraperRouter(rules, ua_mode="fixed")

    # Exact domain wins
    plan1 = router.resolve("https://example.com/article?id=1")
    assert plan1.domain == "example.com"
    assert plan1.backend == "curl"
    assert plan1.ua_profile == "chrome_120_win"

    # Wildcard applies for subdomain when no exact rule exists
    plan2 = router.resolve("https://sub.example.com/post?output=1")
    assert plan2.domain == "sub.example.com"
    assert plan2.backend == "httpx"
    assert plan2.ua_profile == "firefox_120_win"

    # Wildcard pattern present but not matching -> falls back to default plan
    plan3 = router.resolve("https://sub.example.com/post?id=2")
    assert plan3.backend == "auto"  # default


def test_handler_allowlist_blocks_unknown():
    rules = {
        "domains": {
            "evil.example": {
                "backend": "curl",
                "handler": "os.system:rm -rf /",  # should be denied
            }
        }
    }
    router = ScraperRouter(rules)
    plan = router.resolve("https://evil.example/")
    # Should fall back to safe handler
    assert plan.handler.startswith("tldw_Server_API.app.core.Web_Scraping.handlers:")


def test_router_proxies_parsed():
    rules = {
        "domains": {
            "proxied.example": {
                "backend": "curl",
                "proxies": {"http": "http://localhost:8080", "https": "http://localhost:8080"},
            }
        }
    }
    router = ScraperRouter(ScraperRouter.validate_rules(rules))
    plan = router.resolve("https://proxied.example/path")
    assert plan.proxies.get("http").startswith("http://")
