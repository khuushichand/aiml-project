from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import extract_article_with_pipeline


def test_schema_extraction_uses_watchlist_selectors():
    html = """
    <html>
      <body>
        <article>
          <h1>Example Title</h1>
          <p>First paragraph.</p>
          <p>Second paragraph.</p>
        </article>
      </body>
    </html>
    """
    rules = {
        "title_xpath": "//article//h1",
        "content_xpath": "//article//p",
        "content_join_with": "\n",
    }

    result = extract_article_with_pipeline(
        html,
        "https://example.com/post",
        strategy_order=["schema", "trafilatura"],
        schema_rules=rules,
    )

    assert result["extraction_successful"] is True
    assert result["extraction_strategy"] == "schema"
    assert "First paragraph." in result.get("content", "")
    assert "Second paragraph." in result.get("content", "")
    assert result.get("title") == "Example Title"
