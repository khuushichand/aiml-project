from tldw_Server_API.app.core.Watchlists.fetchers import extract_schema_fields


def test_schema_dsl_extraction_with_transforms_and_nested_fields():
    html = """
    <html>
      <body>
        <article>
          <h1> Example Title </h1>
          <div class="meta">
            <time>2025-01-15</time>
            <span class="views">1,234</span>
            <span class="price">$19.99</span>
          </div>
          <p class="content">First paragraph.</p>
          <p class="content">Second paragraph.</p>
          <a class="more" href="/read-more">Read more</a>
          <div class="tags">
            <span class="tag">News</span>
            <span class="tag">Tech</span>
          </div>
          <div class="author">
            <span class="name">Ada Lovelace</span>
            <span class="handle">@ada</span>
          </div>
          <ul class="related">
            <li><a href="/r1">Related One</a></li>
            <li><a href="/r2">Related Two</a></li>
          </ul>
        </article>
      </body>
    </html>
    """
    rules = {
        "name": "article",
        "baseSelector": "//article",
        "baseFields": [
            {"name": "title", "type": "text", "selector": ".//h1", "transforms": ["strip"]},
            {"name": "content", "type": "text", "selector": ".//p[@class='content']", "join_with": "\n"},
            {
                "name": "published",
                "type": "text",
                "selector": ".//time",
                "transforms": [{"name": "date_normalize", "format": "%Y-%m-%d"}],
            },
            {"name": "views", "type": "text", "selector": ".//span[@class='views']", "transforms": [{"name": "number_normalize"}]},
        ],
        "fields": [
            {
                "name": "link",
                "type": "attribute",
                "selector": ".//a[@class='more']",
                "attribute": "href",
                "transforms": [{"name": "urljoin"}],
            },
            {
                "name": "tags",
                "type": "list",
                "selector": ".//span[@class='tag']",
                "itemType": "text",
                "transforms": ["lowercase"],
            },
            {
                "name": "author",
                "type": "nested",
                "selector": ".//div[@class='author']",
                "fields": [
                    {"name": "name", "type": "text", "selector": ".//span[@class='name']"},
                    {"name": "handle", "type": "text", "selector": ".//span[@class='handle']"},
                ],
            },
            {
                "name": "related",
                "type": "nested_list",
                "selector": ".//ul[@class='related']/li",
                "fields": [
                    {"name": "title", "type": "text", "selector": ".//a"},
                    {
                        "name": "url",
                        "type": "attribute",
                        "selector": ".//a",
                        "attribute": "href",
                        "transforms": [{"name": "urljoin"}],
                    },
                ],
            },
            {
                "name": "price",
                "type": "regex",
                "selector": ".//span[@class='price']",
                "pattern": r"\$(\d+\.\d+)",
                "group": 1,
            },
            {
                "name": "slug",
                "type": "computed",
                "from": "title",
                "transforms": ["lowercase", {"name": "regex_replace", "pattern": r"\s+", "repl": "-"}],
            },
        ],
    }

    result = extract_schema_fields(html, "https://example.com/post", rules)
    schema_fields = result.get("schema_fields", {})

    assert result["extraction_successful"] is True
    assert result.get("schema_name") == "article"
    assert schema_fields["title"] == "Example Title"
    assert result["title"] == "Example Title"
    assert "First paragraph." in result.get("content", "")
    assert "Second paragraph." in result.get("content", "")
    assert schema_fields["link"] == "https://example.com/read-more"
    assert schema_fields["tags"] == ["news", "tech"]
    assert schema_fields["author"]["name"] == "Ada Lovelace"
    assert schema_fields["related"][0]["url"] == "https://example.com/r1"
    assert schema_fields["price"] == "19.99"
    assert schema_fields["slug"] == "example-title"
    assert schema_fields["views"] == "1234"
    assert schema_fields["published"].startswith("2025-01-15")
