"""
Minimal fetchers for Watchlists: RSS/Atom and Site pages.

Design notes:
- RSS fetch: reuse the existing workflows adapter logic to avoid duplicating
  URL policy checks and XML parsing. Falls back to a small fake result when
  TEST_MODE is set to avoid network in tests.
- Site fetch: use the existing article extraction library (blocking variant)
  which relies on requests + trafilatura for robustness without Playwright.

Returned item structure (normalized):
- RSS items: { 'title': str, 'url': str, 'summary': Optional[str], 'published': Optional[str] }
- Site items: { 'title': str, 'url': str, 'content': str, 'author': Optional[str] }
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import os

from loguru import logger
from typing import Iterable
from typing import Tuple
import httpx
import xml.etree.ElementTree as ET

from tldw_Server_API.app.core.Security.egress import is_url_allowed_for_tenant, is_url_allowed


async def fetch_rss_items(urls: List[str], *, limit: int = 10, tenant_id: str = "default") -> List[Dict[str, Any]]:
    """Fetch RSS/Atom feed items for the given URLs.

    Uses the workflows adapter implementation for consistency with URL
    allowlisting and parsing heuristics. In TEST_MODE, returns a single fake
    item to keep tests offline.
    """
    urls = [u for u in (urls or []) if isinstance(u, str) and u.strip()]
    if not urls:
        return []

    # Offline mode for unit tests
    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
        return [{"title": "Test Item", "url": "https://example.com/x", "summary": "Test", "published": None}][:limit]

    try:
        from tldw_Server_API.app.core.Workflows.adapters import run_rss_fetch_adapter  # reuse existing parser
        cfg = {"urls": urls, "limit": limit, "include_content": True}
        ctx = {"tenant_id": tenant_id}
        res = await run_rss_fetch_adapter(cfg, ctx)
        items = []
        for r in (res.get("results") or []):
            items.append({
                "title": r.get("title") or "",
                "url": r.get("link") or r.get("url") or "",
                "summary": r.get("summary"),
                "published": r.get("published"),
                "guid": r.get("guid"),
            })
        return items[:limit]
    except Exception as e:
        logger.warning(f"fetch_rss_items failed: {e}")
        return []


def fetch_site_article(url: str) -> Optional[Dict[str, Any]]:
    """Fetch and extract a single site article.

    Uses the blocking path from Article_Extractor, which works without a
    Playwright runtime. Returns None on failure.
    """
    try:
        from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import (
            scrape_article_blocking,
            ContentMetadataHandler,  # type: ignore
        )
    except Exception as e:
        logger.error(f"Article extractor import failed: {e}")
        return None

    try:
        data = scrape_article_blocking(url)
        if not data:
            return None
        # Normalize
        title = data.get("title") or "Untitled"
        author = data.get("author") or None
        content = data.get("content") or ""
        try:
            content = ContentMetadataHandler.strip_metadata(content)  # type: ignore[attr-defined]
        except Exception:
            pass
        return {"title": title, "url": url, "content": content, "author": author}
    except Exception as e:
        logger.warning(f"fetch_site_article failed for {url}: {e}")
        return None


async def fetch_site_top_links(base_url: str, *, top_n: int = 10, method: str = "frontpage") -> List[str]:
    """Discover top-N content links from a site.

    - method="frontpage": fetch homepage and extract likely-article links
    - method="sitemap": try EnhancedWebScraper.scrape_sitemap to pull URLs only

    Returns a list of URLs (same-origin) deduplicated, up to top_n.
    TEST_MODE: returns [base_url] repeated to satisfy callers without network.
    """
    if top_n <= 0:
        return []

    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
        # Provide stable deterministic links
        return [base_url] * min(top_n, 3)

    # Try using EnhancedWebScraper when available
    try:
        from urllib.parse import urlparse, urljoin
        from bs4 import BeautifulSoup
        import aiohttp
        from tldw_Server_API.app.core.Web_Scraping.enhanced_web_scraping import EnhancedWebScraper
        from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import is_content_page

        parsed = urlparse(base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        # Auto-detect sitemap via robots.txt or common path when method='auto'
        async def _detect_sitemap(u: str) -> Optional[str]:
            try:
                import re
                timeout = aiohttp.ClientTimeout(total=6)
                robots_url = urljoin(origin, "/robots.txt")
                async with aiohttp.ClientSession(timeout=timeout) as s:
                    async with s.get(robots_url) as resp:
                        if resp.status // 100 == 2:
                            txt = await resp.text()
                            # Look for Sitemap lines
                            for line in txt.splitlines():
                                if line.lower().startswith("sitemap:"):
                                    sitemap_url = line.split(":", 1)[1].strip()
                                    return sitemap_url
                # Try common location
                common = urljoin(origin, "/sitemap.xml")
                async with aiohttp.ClientSession(timeout=timeout) as s:
                    async with s.get(common) as resp:
                        if resp.status // 100 == 2:
                            return common
            except Exception:
                return None
            return None

        effective_method = method or "auto"
        sitemap_url_for_auto: Optional[str] = None
        if effective_method == "auto":
            sitemap_url_for_auto = await _detect_sitemap(base_url)
            if sitemap_url_for_auto:
                effective_method = "sitemap"
            else:
                effective_method = "frontpage"

        # Sitemap method
        if effective_method == "sitemap" or base_url.endswith(".xml") or "sitemap" in base_url:
            scraper = EnhancedWebScraper()
            # We only need URLs; call scrape_sitemap then pluck the url fields
            sitemap_to_use = sitemap_url_for_auto or base_url
            results = await scraper.scrape_sitemap(sitemap_to_use, filter_func=is_content_page, max_urls=top_n)
            urls = []
            for r in results:
                u = r.get("url") or r.get("source_url")
                if not u:
                    continue
                if urlparse(u).netloc == parsed.netloc:
                    urls.append(u)
            # Dedup while preserving order
            seen = set()
            uniq = []
            for u in urls:
                if u not in seen:
                    seen.add(u)
                    uniq.append(u)
            return uniq[:top_n]

        # Frontpage method: fetch HTML and pull article-like links
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(base_url) as resp:
                if resp.status // 100 != 2:
                    return [base_url]
                html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")
        links: List[str] = []
        for a in soup.find_all("a"):
            href = a.get("href")
            if not href:
                continue
            href = urljoin(origin, href)
            # Same origin and looks like content
            try:
                if urlparse(href).netloc != parsed.netloc:
                    continue
                if not is_content_page(href):
                    continue
            except Exception:
                continue
            links.append(href)
        # Dedup preserve order
        seen = set()
        uniq = []
        for u in links:
            if u not in seen:
                seen.add(u)
                uniq.append(u)
        return uniq[:top_n] if uniq else [base_url]
    except Exception as e:
        logger.debug(f"fetch_site_top_links fallback: {e}")
        return [base_url]


async def fetch_rss_feed(
    url: str,
    *,
    etag: Optional[str] = None,
    last_modified: Optional[str] = None,
    timeout: float = 8.0,
    tenant_id: str = "default",
) -> Dict[str, Any]:
    """Fetch a single RSS/Atom feed with conditional headers.

    Returns dict:
      - status: int HTTP code (200/304/429/other)
      - items: list[dict] when 200
      - etag: str|None (from response headers)
      - last_modified: str|None (from response headers)
      - retry_after: int seconds (only when 429 and header present)
    """
    try:
        if not (url.startswith("http://") or url.startswith("https://")):
            return {"status": 400, "items": []}
        allowed = False
        try:
            allowed = is_url_allowed_for_tenant(url, tenant_id)
        except Exception:
            allowed = is_url_allowed(url)
        if not allowed:
            return {"status": 403, "items": []}

        headers = {
            "Accept": "application/atom+xml, application/rss+xml, application/xml;q=0.9, */*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "User-Agent": "tldw-watchlist/0.1 (+https://github.com/your-org/tldw_server2)"
        }
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)

        status = int(resp.status_code)
        # Retry-After handling
        if status == 429:
            ra = resp.headers.get("Retry-After")
            retry_after_secs = None
            if ra:
                ra = ra.strip()
                # Seconds or HTTP-date
                try:
                    retry_after_secs = int(ra)
                except Exception:
                    from email.utils import parsedate_to_datetime
                    try:
                        dt = parsedate_to_datetime(ra)
                        import datetime as _dt
                        retry_after_secs = max(0, int((dt - _dt.datetime.utcnow().replace(tzinfo=dt.tzinfo)).total_seconds()))
                    except Exception:
                        retry_after_secs = None
            return {"status": 429, "items": [], "retry_after": retry_after_secs}

        if status == 304:
            return {
                "status": 304,
                "items": [],
                "etag": resp.headers.get("ETag"),
                "last_modified": resp.headers.get("Last-Modified"),
            }

        if status // 100 != 2:
            return {"status": status, "items": []}

        text = resp.text
        try:
            root = ET.fromstring(text)
        except Exception:
            return {
                "status": status,
                "items": [],
                "etag": resp.headers.get("ETag"),
                "last_modified": resp.headers.get("Last-Modified"),
            }

        def _find_text(node, names):
            for n in names:
                x = node.find(n)
                if x is not None and (x.text or "").strip():
                    return x.text.strip()
            return None

        items_nodes = root.findall('.//item')
        if not items_nodes:
            items_nodes = root.findall('.//{http://www.w3.org/2005/Atom}entry')
        items: List[Dict[str, Any]] = []
        for it in items_nodes:
            title = _find_text(it, ["title", "{http://www.w3.org/2005/Atom}title"]) or ""
            link = None
            lnode = it.find("link")
            if lnode is not None and (lnk := lnode.get("href")):
                link = lnk
            else:
                link = _find_text(it, ["link", "{http://www.w3.org/2005/Atom}link"]) or ""
            summary = _find_text(it, ["description", "{http://www.w3.org/2005/Atom}summary", "{http://www.w3.org/2005/Atom}content"]) or ""
            published = _find_text(it, ["pubDate", "{http://www.w3.org/2005/Atom}updated", "{http://www.w3.org/2005/Atom}published"]) or None
            guid = _find_text(it, ["guid", "{http://www.w3.org/2005/Atom}id"]) or None
            rec = {"title": title, "url": link or "", "summary": summary, "published": published}
            if guid:
                rec["guid"] = guid
            items.append(rec)
        return {
            "status": 200,
            "items": items,
            "etag": resp.headers.get("ETag"),
            "last_modified": resp.headers.get("Last-Modified"),
        }
    except Exception as e:
        logger.debug(f"fetch_rss_feed error: {e}")
        return {"status": 500, "items": []}
