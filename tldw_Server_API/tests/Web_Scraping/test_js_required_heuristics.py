from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import _js_required


def test_js_required_detection_simple_phrase():
    html = "<html><body>Please enable JavaScript to continue</body></html>"
    assert _js_required(html, {}) is True
