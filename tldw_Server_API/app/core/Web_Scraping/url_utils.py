from urllib.parse import urlparse, urlunparse, urljoin, parse_qsl, urlencode
from typing import Iterable, Set


_TRACKING_PARAMS: Set[str] = {
    # Common analytics params
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "igshid", "mc_cid", "mc_eid",
    # Misc
    "ref", "ref_src",
}


def _strip_tracking_params(query_items: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """Remove common tracking parameters and return a sorted, stable list."""
    filtered = [(k, v) for (k, v) in query_items if k not in _TRACKING_PARAMS and not k.startswith("utm_")]
    # Sort for stability to avoid duplicates caused by param ordering
    filtered.sort(key=lambda kv: (kv[0], kv[1]))
    return filtered


def _normalize_path(path: str) -> str:
    """Normalize path by collapsing duplicate slashes and stripping trailing slash (except root)."""
    if not path:
        return "/"
    # Collapse duplicate slashes
    while "//" in path:
        path = path.replace("//", "/")
    # Ensure leading slash
    if not path.startswith('/'):
        path = '/' + path
    # Strip trailing slash (except root)
    if len(path) > 1 and path.endswith('/'):
        path = path[:-1]
    return path


def normalize_for_crawl(url: str, source: str) -> str:
    """Return a canonicalized HTTP(S) URL for crawling and dedupe.

    - Resolve relative URLs against `source`.
    - Lowercase scheme/host; strip fragments.
    - Remove default ports (80, 443) and collapse duplicate slashes.
    - Remove trivial tracking params (utm_*, gclid, fbclid, etc.).
    - Normalize trailing slash (no trailing slash for non-root).
    """
    if not url:
        return ""

    # Resolve relativity
    abs_url = urljoin(source or "", url)

    p = urlparse(abs_url)

    # Only support http/https targets for crawl
    scheme = (p.scheme or "").lower()
    if scheme not in {"http", "https"}:
        return abs_url  # return as-is; caller may further decide

    netloc = p.netloc.lower()
    # Strip default ports
    if (scheme == "http" and netloc.endswith(":80")):
        netloc = netloc[:-3]
    elif (scheme == "https" and netloc.endswith(":443")):
        netloc = netloc[:-4]

    # Clean query params
    q_items = parse_qsl(p.query, keep_blank_values=True)
    q_items = _strip_tracking_params(q_items)
    query = urlencode(q_items, doseq=True)

    # Normalize path and strip fragments
    path = _normalize_path(p.path)
    fragment = ""  # always strip

    normalized = urlunparse((scheme, netloc, path, "", query, fragment))
    return normalized
