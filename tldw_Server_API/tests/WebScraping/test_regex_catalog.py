from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import extract_article_with_pipeline


def test_regex_catalog_extracts_expected_labels():
    html = """
    <html>
      <body>
        Contact: test.user@example.com or +1 (555) 555-1212.
        Visit https://example.com/docs for more info.
        IPv4: 192.168.0.1 IPv6: 2001:db8::1
        UUID: 550e8400-e29b-41d4-a716-446655440000
        Price: $1,234.50 and 25% off.
        Date: 2025-01-15 13:45
        Postal: 90210 and SW1A 1AA
        Color: #ff00ff
        Handle: @example_user
        MAC: aa:bb:cc:dd:ee:ff
        IBAN: GB82WEST12345698765432
        Card: 4111 1111 1111 1111
      </body>
    </html>
    """

    result = extract_article_with_pipeline(
        html,
        "https://example.com",
        strategy_order=["regex"],
    )

    labels = {match["label"] for match in result.get("regex_matches", [])}
    expected = {
        "email",
        "phone",
        "url",
        "ipv4",
        "ipv6",
        "uuid",
        "currency",
        "percentage",
        "datetime",
        "postal_us",
        "postal_uk",
        "hex_color",
        "social_handle",
        "mac",
        "iban",
        "credit_card",
    }
    assert expected.issubset(labels)


def test_regex_catalog_filters_invalid_credit_cards_and_spans(monkeypatch):
    monkeypatch.setenv("REGEX_PII_MASK", "false")
    html = """
    <html>
      <body>
        Valid card: 4111 1111 1111 1111
        Invalid card: 4111 1111 1111 1112
        Email: test.user@example.com
      </body>
    </html>
    """

    result = extract_article_with_pipeline(
        html,
        "https://example.com",
        strategy_order=["regex"],
    )

    credit_cards = [
        match for match in result.get("regex_matches", [])
        if match.get("label") == "credit_card"
    ]
    assert len(credit_cards) == 1
    assert credit_cards[0].get("value", "").endswith("1111")

    email_matches = [
        match for match in result.get("regex_matches", [])
        if match.get("label") == "email"
    ]
    assert email_matches
    span = email_matches[0].get("span")
    assert isinstance(span, list)
    assert len(span) == 2
    assert all(isinstance(item, int) for item in span)
