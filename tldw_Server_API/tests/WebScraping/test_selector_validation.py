from tldw_Server_API.app.core.Watchlists.fetchers import (
    reload_selector_guardrails_from_env,
    validate_selector_rules,
)


def test_validate_selector_rules_flags_invalid_xpath():
    rules = {
        "content_xpath": "//*[",
        "title_xpath": "//h1",
    }
    report = validate_selector_rules(rules)

    assert report["errors"]
    assert any(err["key"] == "content_xpath" for err in report["errors"])


def test_validate_selector_rules_flags_invalid_css():
    rules = {
        "content_selector": "css:div[",
    }
    report = validate_selector_rules(rules)

    assert report["errors"]
    assert any(err["key"] == "content_selector" for err in report["errors"])


def test_validate_selector_rules_warns_on_non_unique_selector():
    html = """
    <html>
      <body>
        <h1>Title One</h1>
        <h1>Title Two</h1>
      </body>
    </html>
    """
    rules = {"title_xpath": "//h1"}
    report = validate_selector_rules(rules, html_text=html)

    assert report["warnings"]
    assert any(warning["warning"] == "non_unique_selector" for warning in report["warnings"])


def test_validate_selector_rules_warns_on_fragile_css_selector():
    html = """
    <html>
      <body>
        <div class="css-abc123def456">Hello</div>
      </body>
    </html>
    """
    rules = {"title_selector": "css:.css-abc123def456"}
    report = validate_selector_rules(rules, html_text=html)

    assert report["warnings"]
    assert any(warning["warning"] == "fragile_selector" for warning in report["warnings"])


def test_validate_selector_rules_flags_overly_complex_xpath():
    # Deliberately long selector to enforce complexity limits for user-supplied XPath.
    rules = {"content_xpath": "//div" + "/span" * 200}
    report = validate_selector_rules(rules)

    assert report["errors"]
    assert any(
        err["key"] == "content_xpath" and "selector_too_complex" in str(err.get("error", ""))
        for err in report["errors"]
    )


def test_validate_selector_rules_honors_env_guardrail_override(monkeypatch):
    monkeypatch.setenv("WATCHLIST_SELECTOR_MAX_EXPR_LEN", "32")
    reload_selector_guardrails_from_env()
    try:
        rules = {"content_xpath": "//article//section//header//h2/text()"}
        report = validate_selector_rules(rules)
        assert report["errors"]
        assert any("length>32" in str(err.get("error", "")) for err in report["errors"])
    finally:
        monkeypatch.delenv("WATCHLIST_SELECTOR_MAX_EXPR_LEN", raising=False)
        reload_selector_guardrails_from_env()
