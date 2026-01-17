from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import _js_required


def test_js_required_detection_simple_phrase():
    html = "<html><body>Please enable JavaScript to continue</body></html>"
    assert _js_required(html, {}, "https://example.com") is True


def test_js_required_domain_hint_with_thin_content():
    html = "<html><head></head><body><div id='__next'></div></body></html>"
    assert _js_required(html, {}, "https://medium.com/@demo/test") is True


def test_js_required_app_shell_marker():
    html = (
        "<html><body><div id='__next'></div>"
        "<script src='app.js'></script><script>var x=1;</script></body></html>"
    )
    assert _js_required(html, {}, "https://example.org") is True


def test_js_required_allows_rich_content():
    html = "<html><body>" + ("word " * 400) + "</body></html>"
    assert _js_required(html, {}, "https://example.org") is False


def test_js_required_domain_hint_low_content():
    html = "<html><head><script>var x=1;</script></head><body><div id='__next'></div></body></html>"
    assert _js_required(html, {}, url="https://twitter.com/example") is True


def test_js_required_domain_hint_contentful():
    html = "<html><body>" + ("hello world " * 200) + "</body></html>"
    assert _js_required(html, {}, url="https://twitter.com/example") is False
