from tldw_Server_API.app.core.Web_Scraping.scraper_router import ScraperRouter


def test_validate_rules_normalizes_and_drops_invalid():
    raw = {
        "domains": {
            "invalid": {"backend": "curl", "unknown": True},  # no dot or wildcard
            "example.com": {
                "backend": "bogus",
                "handler": "tldw_Server_API.app.core.Web_Scraping.handlers:handle_generic_html",
                "url_patterns": [".*\\?ok=1$", "["],  # second is invalid regex
                "extra_headers": {"Referer": "https://google.com"},
                "cookies": [{"k": "v"}],  # wrong shape
                "unknown_key": 123,
            },
            "*.sub.example.com": {
                "backend": "curl",
                "url_patterns": [".*"],
            },
        }
    }

    cleaned = ScraperRouter.validate_rules(raw)
    assert "invalid" not in cleaned.get("domains", {})

    ex = cleaned["domains"]["example.com"]
    # backend normalized to 'auto'
    assert ex["backend"] == "auto"
    # unknown keys dropped; invalid regex removed
    assert ex.get("unknown_key") is None
    assert ex["url_patterns"] == [".*\\?ok=1$"]
    # cookies normalized to map
    assert ex["cookies"] == {}

    sub = cleaned["domains"]["*.sub.example.com"]
    assert sub["backend"] == "curl"
    assert sub["url_patterns"] == [".*"]
