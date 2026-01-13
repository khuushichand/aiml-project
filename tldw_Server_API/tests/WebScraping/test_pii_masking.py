import os

from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import extract_article_with_pipeline


def test_regex_pii_masking(monkeypatch):
    monkeypatch.setenv("REGEX_PII_MASK", "true")
    html = """
    <html>
      <body>
        Email: demo@example.com
        Phone: +1 (555) 555-1212
        Card: 4111 1111 1111 1111
      </body>
    </html>
    """

    result = extract_article_with_pipeline(
        html,
        "https://example.com",
        strategy_order=["regex"],
    )

    values_by_label = {}
    for match in result.get("regex_matches", []):
        values_by_label.setdefault(match["label"], []).append(match["value"])

    assert any("*" in value for value in values_by_label.get("email", []))
    assert any("*" in value for value in values_by_label.get("phone", []))
    assert any("*" in value for value in values_by_label.get("credit_card", []))

    monkeypatch.delenv("REGEX_PII_MASK", raising=False)
