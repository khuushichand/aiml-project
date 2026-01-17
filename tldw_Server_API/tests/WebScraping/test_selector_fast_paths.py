from tldw_Server_API.app.core.Watchlists.fetchers import extract_schema_fields


def test_context_sensitive_xpath_scopes_to_base_selector():
    html = """
    <html>
      <body>
        <section id="one"><p>First section</p></section>
        <section id="two"><p>Second section</p></section>
      </body>
    </html>
    """
    rules = {
        "name": "article",
        "baseSelector": "//section[@id='one']",
        "fields": [
            {"name": "content", "selector": "//p"},
        ],
    }

    result = extract_schema_fields(html, "https://example.com", rules)

    assert result["extraction_successful"] is True
    assert result["schema_fields"]["content"] == "First section"


def test_css_table_nth_child_fast_path():
    html = """
    <html>
      <body>
        <table>
          <tr><td>R1C1</td><td>R1C2</td></tr>
          <tr><td>R2C1</td><td>R2C2</td></tr>
        </table>
      </body>
    </html>
    """
    rules = {
        "name": "table",
        "fields": [
            {"name": "cell", "selector": "css:table tr:nth-child(2) td:nth-child(1)"},
        ],
    }

    result = extract_schema_fields(html, "https://example.com", rules)

    assert result["extraction_successful"] is True
    assert result["schema_fields"]["cell"] == "R2C1"
