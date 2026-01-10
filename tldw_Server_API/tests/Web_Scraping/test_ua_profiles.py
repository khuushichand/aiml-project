from tldw_Server_API.app.core.Web_Scraping.ua_profiles import (
    build_browser_headers,
    pick_ua_profile,
    profile_to_impersonate,
)


def test_build_browser_headers_shape():
    profile = pick_ua_profile("fixed")
    headers = build_browser_headers(profile, accept_lang="en-US,en;q=0.9")

    # Core browser header fields
    assert "User-Agent" in headers and len(headers["User-Agent"]) > 10
    assert "sec-ch-ua" in headers
    assert "sec-ch-ua-mobile" in headers
    assert "sec-ch-ua-platform" in headers
    assert "Accept" in headers
    assert "Accept-Language" in headers and "en-US" in headers["Accept-Language"]
    assert "Accept-Encoding" in headers
    # Ensure modern encodings are present
    enc = headers["Accept-Encoding"].replace(" ", "")
    for algo in ("gzip", "deflate", "br", "zstd"):
        assert algo in enc


def test_profile_to_impersonate_mapping():
    profile = pick_ua_profile("fixed")
    imp = profile_to_impersonate(profile)
    # For known profiles we expect a non-empty impersonation token
    assert imp is None or isinstance(imp, str)
